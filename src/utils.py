"""Small shared helpers: JSONL I/O, filename sanitizing, polite delays."""
import json
import random
import re
import time
from pathlib import Path
from typing import Iterator

from . import config


def append_jsonl(path: Path, record: dict) -> None:
    """Append a single JSON record as its own line. Crash-safe: each write
    is flushed immediately so a killed process never corrupts prior lines."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()


def read_jsonl(path: Path) -> Iterator[dict]:
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_seen_urls(path: Path) -> set:
    if not path.exists():
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return set(json.load(f))


def save_seen_urls(path: Path, seen: set) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=2)


def sanitize_filename(name: str, max_len: int = 150) -> str:
    """Turn a book title into a filesystem-safe filename, matching the
    original document name as closely as possible rather than a generic
    id, so files stay human-identifiable on disk."""
    name = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    name = re.sub(r"\s+", " ", name)
    return name[:max_len] if name else "untitled"


def polite_delay() -> None:
    """Randomized delay between requests so traffic doesn't look like a
    fixed-interval bot pattern."""
    time.sleep(random.uniform(config.MIN_REQUEST_DELAY, config.MAX_REQUEST_DELAY))
