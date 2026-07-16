"""
Phase 1: keyword search -> document metadata.

Walks Scribd's search results for each keyword, extracts metadata for every
new (not-yet-seen) document, and appends it to data/metadata.jsonl
immediately - so a crash mid-run never loses already-scraped progress.
"""
import logging
from multiprocessing import Manager, Pool
from typing import List

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from . import config, utils
from .models import DocumentMetadata

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(config.LOGS_DIR / "scraper.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("scraper")


def _new_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)


def _extract_metadata(driver: webdriver.Chrome, url: str) -> DocumentMetadata:
    """Best-effort field extraction. Scribd's markup isn't fully consistent
    across document types, so every field lookup is individually guarded -
    a missing field becomes null rather than aborting the whole record."""
    driver.get(url)

    def _text(selector: str):
        try:
            return driver.find_element(By.CSS_SELECTOR, selector).text.strip()
        except NoSuchElementException:
            return None

    book_name = _text("h1[data-e2e='doc-title']") or driver.title
    uploaded_by = _text("[data-e2e='uploaded-by'] a")
    page_numbers = _text("[data-e2e='page-count']")
    likes = _text("[data-e2e='rating-summary']")   # e.g. "83% (6)"
    views = _text("[data-e2e='view-count']")
    description = _text("[data-e2e='doc-description']")

    return DocumentMetadata(
        book_name=book_name,
        uploaded_by=uploaded_by,
        page_numbers=page_numbers,
        likes=likes,
        views=views,
        description=description,
        book_url=url,
    )


def _collect_search_result_urls(driver: webdriver.Chrome, keyword: str, max_pages: int) -> List[str]:
    urls = []
    for page in range(1, max_pages + 1):
        search_url = config.SCRIBD_SEARCH_URL.format(query=keyword, page=page)
        driver.get(search_url)
        try:
            cards = driver.find_elements(By.CSS_SELECTOR, "a[data-e2e='search-result-title']")
        except TimeoutException:
            break
        if not cards:
            log.info("Keyword '%s': no more results after page %d", keyword, page - 1)
            break
        for card in cards:
            href = card.get_attribute("href")
            if href:
                urls.append(href)
        utils.polite_delay()
    log.info("Keyword '%s': found %d result URLs", keyword, len(urls))
    return urls


def _worker(args):
    url, seen_urls, lock = args
    with lock:
        if url in seen_urls:
            return None
        seen_urls[url] = True

    driver = _new_driver()
    try:
        metadata = _extract_metadata(driver, url)
        utils.append_jsonl(config.METADATA_FILE, metadata.to_dict())
        log.info("Scraped: %s", metadata.book_name)
        return metadata.to_dict()
    except Exception as exc:
        log.warning("Failed to scrape %s: %s", url, exc)
        return None
    finally:
        driver.quit()
        utils.polite_delay()


def run(keywords: List[str], max_pages_per_keyword: int = 20, workers: int = config.SCRAPE_WORKERS):
    """Entrypoint for `python main.py scrape`."""
    driver = _new_driver()
    all_urls: List[str] = []
    try:
        for keyword in keywords:
            all_urls.extend(_collect_search_result_urls(driver, keyword, max_pages_per_keyword))
    finally:
        driver.quit()

    log.info("Total URLs across all keywords (pre-dedup): %d", len(all_urls))

    with Manager() as manager:
        seen_urls = manager.dict()
        for existing in utils.load_seen_urls(config.SEEN_URLS_FILE):
            seen_urls[existing] = True
        lock = manager.Lock()

        with Pool(processes=workers) as pool:
            results = pool.map(_worker, [(u, seen_urls, lock) for u in all_urls])

        utils.save_seen_urls(config.SEEN_URLS_FILE, set(seen_urls.keys()))

    scraped = [r for r in results if r]
    log.info("Newly scraped this run: %d documents", len(scraped))
    return scraped
