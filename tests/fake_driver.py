"""
A minimal fake Selenium WebDriver that implements just enough of the real
interface (find_element, find_elements, page_source, get, current_url) for
extractor.py and downloader.py to run against unmodified - backed by
BeautifulSoup over fixture HTML instead of an actual browser.

This exists because the sandbox this project was verified in has no
Chrome/Chromium binary available and no root access to install one, so a
real Selenium session can't be started here. The production code under
test (src/extractor.py, src/downloader.py) is exercised exactly as
written - only the driver underneath is swapped out.
"""
from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException


class FakeElement:
    def __init__(self, tag):
        self._tag = tag

    @property
    def text(self):
        return self._tag.get_text(strip=True)

    def get_attribute(self, name):
        return self._tag.get(name)

    def click(self):
        # Downloading is simulated by the test itself (see FakeDriver.get),
        # which drops the "downloaded" file into the target directory when
        # a download-link click is detected.
        pass

    def is_displayed(self):
        return True

    def is_enabled(self):
        return True


_CSS_TO_BS4 = str  # BeautifulSoup's .select already speaks CSS selectors


class FakeDriver:
    def __init__(self, pages: dict, download_dir=None, simulate_download_as=None):
        """
        pages: {url: html_string}
        simulate_download_as: filename to "produce" in download_dir when a
            download link is clicked, so downloader.py's file-watch logic
            has something real to detect.
        """
        self._pages = pages
        self._current_url = None
        self._soup = None
        self.download_dir = download_dir
        self.simulate_download_as = simulate_download_as
        self.page_source = ""
        self.title = ""

    def get(self, url):
        self._current_url = url
        html = self._pages.get(url, "<html><body></body></html>")
        self._soup = BeautifulSoup(html, "lxml")
        self.page_source = html
        self.title = self._soup.title.get_text() if self._soup.title else ""

    def find_element(self, by, selector):
        tag = self._soup.select_one(_CSS_TO_BS4(selector))
        if tag is None:
            raise NoSuchElementException(f"No element for {selector}")
        element = FakeElement(tag)
        if "download" in selector.lower():
            # Wrap click() so it actually drops the simulated file.
            original_click = element.click
            def click_and_download():
                original_click()
                if self.simulate_download_as and self.download_dir:
                    (self.download_dir / self.simulate_download_as).write_bytes(b"%PDF-1.4 fake")
            element.click = click_and_download
        return element

    def find_elements(self, by, selector):
        return [FakeElement(tag) for tag in self._soup.select(_CSS_TO_BS4(selector))]

    def quit(self):
        pass
