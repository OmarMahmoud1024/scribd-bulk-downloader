"""
Exercises the real scraper.py._extract_metadata against fixture HTML via
FakeDriver, covering both a fully-populated document page and one missing
several fields (which is common - e.g. no description, no visible rating
yet on a freshly uploaded doc).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scraper import _extract_metadata
from tests.fake_driver import FakeDriver

FULL_DOC_PAGE = """
<html><head><title>Fallback Title</title></head><body>
<h1 data-e2e="doc-title">მთავარი გვერდის ისტორია</h1>
<div data-e2e="uploaded-by"><a href="/user/1">katokokaia08</a></div>
<span data-e2e="page-count">175</span>
<span data-e2e="rating-summary">100% (12)</span>
<span data-e2e="view-count">11K</span>
<p data-e2e="doc-description">ისტორიული მიმოხილვა.</p>
</body></html>
"""

MINIMAL_DOC_PAGE = """
<html><head><title>Untitled Document</title></head><body>
<h1 data-e2e="doc-title">Untitled Document</h1>
</body></html>
"""


def test_extract_metadata_full_document():
    driver = FakeDriver(pages={"http://fake/doc1": FULL_DOC_PAGE})
    driver.get("http://fake/doc1")

    metadata = _extract_metadata(driver, "http://fake/doc1")

    assert metadata.book_name == "მთავარი გვერდის ისტორია"
    assert metadata.uploaded_by == "katokokaia08"
    assert metadata.page_numbers == "175"
    assert metadata.likes == "100% (12)"
    assert metadata.views == "11K"
    assert metadata.description == "ისტორიული მიმოხილვა."
    assert metadata.book_url == "http://fake/doc1"


def test_extract_metadata_missing_fields_degrade_to_none_not_crash():
    driver = FakeDriver(pages={"http://fake/doc2": MINIMAL_DOC_PAGE})
    driver.get("http://fake/doc2")

    metadata = _extract_metadata(driver, "http://fake/doc2")

    assert metadata.book_name == "Untitled Document"
    assert metadata.uploaded_by is None
    assert metadata.page_numbers is None
    assert metadata.likes is None
    assert metadata.views is None
    assert metadata.description is None
