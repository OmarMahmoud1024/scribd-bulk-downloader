"""Pure-logic tests for models.py and utils.py - no network/browser needed."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import DocumentMetadata
from src.utils import append_jsonl, read_jsonl, load_seen_urls, save_seen_urls, sanitize_filename


def test_document_metadata_roundtrip():
    doc = DocumentMetadata(
        book_name="მთავარი გვერდი",
        uploaded_by="katokokaia08",
        page_numbers="175",
        likes="100% (12)",
        views="11K",
        description=None,
        book_url="https://www.scribd.com/document/123/example",
    )
    as_dict = doc.to_dict()
    restored = DocumentMetadata.from_dict(as_dict)
    assert restored == doc
    # Missing/null fields must round-trip as None, not raise or default oddly.
    assert restored.description is None


def test_append_and_read_jsonl_roundtrip(tmp_path):
    path = tmp_path / "metadata.jsonl"
    append_jsonl(path, {"book_name": "A", "book_url": "u1"})
    append_jsonl(path, {"book_name": "B", "book_url": "u2"})

    records = list(read_jsonl(path))
    assert len(records) == 2
    assert records[0]["book_name"] == "A"
    assert records[1]["book_name"] == "B"


def test_read_jsonl_on_missing_file_returns_empty():
    assert list(read_jsonl(Path("/nonexistent/path.jsonl"))) == []


def test_seen_urls_persist_and_reload(tmp_path):
    path = tmp_path / "seen.json"
    save_seen_urls(path, {"https://scribd.com/a", "https://scribd.com/b"})

    reloaded = load_seen_urls(path)
    assert reloaded == {"https://scribd.com/a", "https://scribd.com/b"}


def test_sanitize_filename_strips_illegal_characters():
    assert sanitize_filename('Report: "Q1/Q2" Review?') == "Report Q1Q2 Review"


def test_sanitize_filename_truncates_long_titles():
    long_title = "A" * 300
    result = sanitize_filename(long_title, max_len=150)
    assert len(result) == 150


def test_sanitize_filename_handles_empty_title():
    assert sanitize_filename("   ") == "untitled"
