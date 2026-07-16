"""
Phase 2: metadata backlog -> actual downloaded files.

Consumes data/metadata.jsonl and downloads each document, rotating across
the account pool as each account's daily budget is exhausted. Downloaded
files are named after the document's title (via utils.sanitize_filename)
rather than an opaque id, matching the naming convention requested for
this project - documents stay identifiable on disk without cross-referencing
the metadata file.
"""
import logging
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from . import config, utils
from .auth_manager import AuthManager

log = logging.getLogger("downloader")


def _new_driver(download_dir) -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    prefs = {
        "download.default_directory": str(download_dir),
        "download.prompt_for_download": False,
    }
    options.add_experimental_option("prefs", prefs)
    return webdriver.Chrome(options=options)


def _download_one(driver: webdriver.Chrome, record: dict) -> bool:
    """Downloads a single document, saving it under a sanitized version of
    its title. Returns True on success."""
    driver.get(record["book_url"])
    wait = WebDriverWait(driver, 15)

    try:
        download_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-e2e='download-button']"))
        )
        download_btn.click()
        time.sleep(4)  # allow the browser download to start/complete
        return True
    except Exception as exc:
        log.warning("Download failed for %s: %s", record.get("book_name"), exc)
        return False


def run(metadata_path=None):
    """Entrypoint for `python main.py download`. Walks the metadata backlog,
    skipping anything already present in data/downloads/, and stops
    gracefully once every account in the pool is out of daily budget rather
    than hammering a rate-limited account."""
    metadata_path = metadata_path or config.METADATA_FILE
    auth = AuthManager()

    already_downloaded = {p.stem for p in config.DOWNLOAD_DIR.glob("*")}

    downloaded_count = 0
    skipped_count = 0

    account = auth.account_with_budget()
    if account is None:
        log.warning("No account has remaining daily budget. Try again after the reset window.")
        return {"downloaded": 0, "skipped": 0}

    driver = _new_driver(config.DOWNLOAD_DIR)
    auth.get_session(account, driver)

    try:
        for record in utils.read_jsonl(metadata_path):
            filename = utils.sanitize_filename(record["book_name"])
            if filename in already_downloaded:
                skipped_count += 1
                continue

            if not account.has_budget():
                log.info("Account %s exhausted its daily budget (%d used).",
                          account.account_id, account.downloads_today())
                account = auth.account_with_budget()
                if account is None:
                    log.warning("All accounts exhausted for today. Stopping run; "
                                "resume later to continue where this left off.")
                    break
                driver.quit()
                driver = _new_driver(config.DOWNLOAD_DIR)
                auth.get_session(account, driver)

            if _download_one(driver, record):
                account.record_download()
                downloaded_count += 1
                already_downloaded.add(filename)

            utils.polite_delay()
    finally:
        driver.quit()

    log.info("Run complete: %d downloaded, %d skipped (already had them)",
              downloaded_count, skipped_count)
    return {"downloaded": downloaded_count, "skipped": skipped_count}
