"""
Central configuration for the Scribd bulk scraper.

All secrets are loaded from environment variables (see .env.example) -
nothing sensitive is hardcoded here or anywhere else in the project.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
COOKIES_DIR = ROOT_DIR / "cookies"
LOGS_DIR = ROOT_DIR / "logs"

for _dir in (DATA_DIR, COOKIES_DIR, LOGS_DIR):
    _dir.mkdir(exist_ok=True)

METADATA_FILE = DATA_DIR / "metadata.jsonl"
SEEN_URLS_FILE = DATA_DIR / "seen_urls.json"
DOWNLOAD_DIR = DATA_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Empirically observed cap before Scribd starts silently failing downloads.
# Not officially documented - treat as a conservative estimate, not a guarantee.
DAILY_LIMIT_PER_ACCOUNT = int(os.getenv("SCRIBD_DAILY_LIMIT_PER_ACCOUNT", "200"))

# Minimum delay (seconds) between requests from the same session, to avoid
# looking like a burst of automated traffic.
MIN_REQUEST_DELAY = 3.0
MAX_REQUEST_DELAY = 7.0

# Number of parallel worker processes for the metadata-scraping phase.
SCRAPE_WORKERS = 4

SCRIBD_BASE_URL = "https://www.scribd.com"
SCRIBD_SEARCH_URL = SCRIBD_BASE_URL + "/search?query={query}&page={page}"


def load_account_pool():
    """
    Parses SCRIBD_ACCOUNT_POOL from the environment into a list of
    (email, password) tuples. Expected format:
        email1:pass1,email2:pass2,...
    """
    raw = os.getenv("SCRIBD_ACCOUNT_POOL", "")
    accounts = []
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        email, password = pair.split(":", 1)
        accounts.append((email.strip(), password.strip()))
    if not accounts:
        raise RuntimeError(
            "No accounts configured. Set SCRIBD_ACCOUNT_POOL in your .env file "
            "(see .env.example)."
        )
    return accounts
