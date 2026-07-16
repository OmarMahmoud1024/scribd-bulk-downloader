"""
Tests the actual account-rotation and daily-budget-tracking logic - the
core problem this whole project exists to solve (Scribd's ~200/day/account
cap). None of this needs a browser; it's pure state tracking backed by
small JSON files on disk.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import config
from src.auth_manager import Account, AuthManager


def _make_account(tmp_path, email="test1@example.com"):
    config.COOKIES_DIR = tmp_path
    return Account(email, "password123")


def test_fresh_account_has_full_budget(tmp_path):
    account = _make_account(tmp_path)
    assert account.downloads_today() == 0
    assert account.has_budget() is True
    assert account.remaining_budget() == config.DAILY_LIMIT_PER_ACCOUNT


def test_recording_downloads_decrements_remaining_budget(tmp_path):
    account = _make_account(tmp_path)
    for _ in range(5):
        account.record_download()

    assert account.downloads_today() == 5
    assert account.remaining_budget() == config.DAILY_LIMIT_PER_ACCOUNT - 5
    assert account.has_budget() is True


def test_account_loses_budget_once_daily_limit_reached(tmp_path):
    config.DAILY_LIMIT_PER_ACCOUNT = 3
    account = _make_account(tmp_path)

    for _ in range(3):
        account.record_download()

    assert account.has_budget() is False
    assert account.remaining_budget() == 0


def test_usage_from_a_previous_day_does_not_carry_over(tmp_path):
    """Simulates yesterday's usage file being present - today's budget
    should be fresh, not inherited from a stale date."""
    import json
    config.COOKIES_DIR = tmp_path
    account = Account("test2@example.com", "pw")
    account.usage_path.write_text(json.dumps({"date": "2000-01-01", "count": 999}))

    assert account.downloads_today() == 0
    assert account.has_budget() is True


def test_auth_manager_rotates_to_next_account_when_first_is_exhausted(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "SCRIBD_ACCOUNT_POOL",
        "acct1@example.com:pw1,acct2@example.com:pw2,acct3@example.com:pw3",
    )
    config.COOKIES_DIR = tmp_path
    config.DAILY_LIMIT_PER_ACCOUNT = 2

    auth = AuthManager()
    assert len(auth.accounts) == 3

    first = auth.account_with_budget()
    assert first.account_id == "acct1"

    # Exhaust account 1's budget.
    first.record_download()
    first.record_download()

    second = auth.account_with_budget()
    assert second.account_id == "acct2", "Should rotate to the next account once the first is exhausted"


def test_auth_manager_returns_none_when_entire_pool_is_exhausted(tmp_path, monkeypatch):
    monkeypatch.setenv("SCRIBD_ACCOUNT_POOL", "solo@example.com:pw")
    config.COOKIES_DIR = tmp_path
    config.DAILY_LIMIT_PER_ACCOUNT = 1

    auth = AuthManager()
    account = auth.account_with_budget()
    account.record_download()

    assert auth.account_with_budget() is None


def test_load_account_pool_parses_env_correctly(monkeypatch):
    from src.config import load_account_pool
    monkeypatch.setenv("SCRIBD_ACCOUNT_POOL", "a@x.com:p1, b@x.com:p2 ,c@x.com:p3")

    accounts = load_account_pool()

    assert accounts == [("a@x.com", "p1"), ("b@x.com", "p2"), ("c@x.com", "p3")]


def test_load_account_pool_raises_clear_error_when_unset(monkeypatch):
    monkeypatch.delenv("SCRIBD_ACCOUNT_POOL", raising=False)
    from src.config import load_account_pool
    import pytest
    with pytest.raises(RuntimeError, match="No accounts configured"):
        load_account_pool()
