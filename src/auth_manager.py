"""
Handles the multi-account rotation problem.

Scribd enforces a per-account daily download cap. Instead of one account
hitting that wall and stalling the whole pipeline, AuthManager tracks a pool
of accounts, how many downloads each has used today, and hands out whichever
account still has budget left - persisting cookies per-account so repeat
runs don't need to re-authenticate every time.
"""
import json
import pickle
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from . import config


class Account:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.account_id = email.split("@")[0]
        self.cookie_path = config.COOKIES_DIR / f"{self.account_id}.pkl"
        self.usage_path = config.COOKIES_DIR / f"{self.account_id}.usage.json"

    def _load_usage(self) -> dict:
        if self.usage_path.exists():
            with open(self.usage_path, "r") as f:
                return json.load(f)
        return {"date": "", "count": 0}

    def _save_usage(self, usage: dict) -> None:
        with open(self.usage_path, "w") as f:
            json.dump(usage, f)

    def downloads_today(self) -> int:
        usage = self._load_usage()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if usage.get("date") != today:
            return 0
        return usage.get("count", 0)

    def record_download(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        usage = self._load_usage()
        if usage.get("date") != today:
            usage = {"date": today, "count": 0}
        usage["count"] += 1
        self._save_usage(usage)

    def has_budget(self) -> bool:
        return self.downloads_today() < config.DAILY_LIMIT_PER_ACCOUNT

    def remaining_budget(self) -> int:
        return max(0, config.DAILY_LIMIT_PER_ACCOUNT - self.downloads_today())


class AuthManager:
    """Owns the account pool and hands out authenticated Selenium sessions,
    reusing persisted cookies where possible instead of logging in fresh
    every time a session is needed."""

    def __init__(self):
        self.accounts = [Account(email, pw) for email, pw in config.load_account_pool()]

    def account_with_budget(self) -> Optional[Account]:
        for account in self.accounts:
            if account.has_budget():
                return account
        return None

    def status(self) -> list:
        return [
            {
                "account_id": a.account_id,
                "used_today": a.downloads_today(),
                "remaining": a.remaining_budget(),
            }
            for a in self.accounts
        ]

    def get_session(self, account: Account, driver: webdriver.Chrome) -> webdriver.Chrome:
        """Loads persisted cookies for this account if present, otherwise
        performs an interactive login and persists the resulting cookies
        for future runs."""
        driver.get(config.SCRIBD_BASE_URL)

        if account.cookie_path.exists():
            with open(account.cookie_path, "rb") as f:
                cookies = pickle.load(f)
            for cookie in cookies:
                cookie.pop("sameSite", None)
                try:
                    driver.add_cookie(cookie)
                except Exception:
                    continue
            driver.get(config.SCRIBD_BASE_URL)
            if self._is_logged_in(driver):
                return driver

        self._login(driver, account)
        with open(account.cookie_path, "wb") as f:
            pickle.dump(driver.get_cookies(), f)
        return driver

    @staticmethod
    def _is_logged_in(driver: webdriver.Chrome) -> bool:
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-e2e='user-menu']"))
            )
            return True
        except Exception:
            return False

    @staticmethod
    def _login(driver: webdriver.Chrome, account: Account) -> None:
        driver.get(config.SCRIBD_BASE_URL + "/login")
        wait = WebDriverWait(driver, 15)

        email_field = wait.until(EC.presence_of_element_located((By.NAME, "email")))
        email_field.send_keys(account.email)

        password_field = driver.find_element(By.NAME, "password")
        password_field.send_keys(account.password)

        submit = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit.click()

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-e2e='user-menu']")))
        time.sleep(1)
