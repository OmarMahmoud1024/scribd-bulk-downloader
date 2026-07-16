# Scribd Bulk Metadata Scraper & Downloader

A resilient, multi-account scraping pipeline built to search Scribd by keyword, extract structured
document metadata, and bulk-download documents at scale while working around aggressive per-account
rate limiting.

This project was originally built during a freelance/internship engagement for a research team that
needed to archive tens of thousands of publicly listed documents matching specific keywords. It's
reconstructed here (original repo was lost) to demonstrate the architecture and techniques used.

## The problem

Scribd doesn't expose a public API for bulk document search/download, and enforces:

- A per-account daily download cap (observed empirically at ~200 documents/24h before requests started
  silently failing).
- Session-based access that requires a logged-in cookie, not just a static request.
- No stable pagination guarantees — identical searches can return slightly different result ordering
  between runs.

A single-account, single-request scraper hits the rate limit almost immediately and can't realistically
process a multi-thousand-document backlog in any reasonable timeframe.

## The approach

**1. Multi-account rotation.** Credentials for N accounts are loaded from environment variables (see
`.env.example`) rather than hardcoded. `AuthManager` cycles through accounts, tracking how many
downloads each has performed in the current 24h window, and automatically switches to the next
available account once one is exhausted.

**2. Cookie persistence.** Each account's session cookies are pickled to disk after first login
(`cookies/<account_id>.pkl`) so subsequent runs reuse the session instead of re-authenticating —
this both avoids repeated login friction and reduces the chance of triggering login-abuse detection.

**3. Search → metadata → download, decoupled.** The pipeline runs in two independent phases:
   - `scraper.py` walks keyword search results, collecting document URLs and metadata
     (title, uploader, page count, like/view stats, description) as it goes.
   - `downloader.py` consumes the metadata backlog and performs the actual file downloads,
     respecting per-account budgets.

   Decoupling these means metadata collection (cheap, less rate-limited) can run far ahead of the
   actual downloads (expensive, rate-limited), and either phase can be resumed independently.

**4. Incremental, crash-safe output.** Results are appended to a JSON Lines file as they're found,
not buffered and written once at the end — if the process is killed mid-run (network blip, rate limit,
manual stop), nothing already scraped is lost.

**5. Deduplication.** A persisted set of already-seen document URLs is checked before each new
search result is queued, since keyword searches frequently return overlapping results across
different search terms.

**6. Parallelism.** `multiprocessing.Pool` fans out metadata scraping across worker processes, each
with its own browser session, while a shared `Manager` dict/set coordinates the dedup state and
per-account download counters across processes.

## Project structure

```
scribd-bulk-downloader/
├── src/
│   ├── config.py          # Keyword list, paths, rate-limit constants
│   ├── models.py          # DocumentMetadata dataclass
│   ├── auth_manager.py    # Multi-account login, cookie persistence, rotation
│   ├── scraper.py         # Keyword search + metadata extraction
│   ├── downloader.py      # Rate-limit-aware bulk download orchestration
│   └── utils.py           # JSONL append/read helpers, filename sanitizing
├── main.py                # CLI entrypoint (scrape / download / status)
├── requirements.txt
├── .env.example
└── data/                  # Output: metadata.jsonl, downloaded files (gitignored)
```

## Usage

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in account credentials
python main.py scrape --keywords keywords.txt        # phase 1: collect metadata
python main.py download --input data/metadata.jsonl  # phase 2: download files
python main.py status                                 # per-account budget remaining today
```

## Metadata schema

Each line in `data/metadata.jsonl`:

```json
{
  "book_name": "string",
  "uploaded_by": "string",
  "page_numbers": "string",
  "likes": "83% (6)",
  "views": "11K",
  "description": "string or null",
  "book_url": "string"
}
```

`uploaded_by` intentionally isn't called `author` — Scribd's byline is whoever uploaded the document,
which is frequently not the actual author, so the field name reflects what's really being captured.
Any field Scribd doesn't expose for a given document is written as `null` rather than omitted, so
downstream consumers always see a consistent schema.

## Known limitations

- Scribd's per-account limit isn't officially documented; the ~200/day figure in `config.py` is an
  empirical estimate from observed failures and may drift over time.
- This is a portfolio reconstruction — the account rotation logic and rate-limit handling reflect the
  real approach used, but this repo isn't configured against live credentials.

## Testing

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -v
```

17 tests, all passing. Real Scribd login/download can't be exercised without a paid account (this
repo intentionally ships no real credentials), so the tests target what's actually testable and
matters most:

- **`test_auth_manager.py`** — the core problem this project solves. Verifies budget tracking per
  account, that a stale usage file from a previous day doesn't carry over, that `AuthManager` rotates
  to the next account once one is exhausted, and returns `None` once the whole pool is out of budget.
- **`test_scraper_extraction.py`** — metadata field extraction against fixture HTML, via a small fake
  Selenium driver (`tests/fake_driver.py`) so `scraper.py`'s real extraction code runs unmodified
  against a page with every field present and one with several missing, confirming missing fields
  degrade to `null` instead of crashing the run.
- **`test_models_and_utils.py`** — JSONL append/read round-tripping, filename sanitizing, and
  seen-URL persistence for dedup.

## Skills demonstrated

Session/cookie management · multi-account rate-limit evasion · multiprocessing · crash-safe
incremental I/O · deduplication at scale · Selenium-based scraping of a JS-heavy site.
