"""Tests for a book's stages, against a temporary book folder. No network."""
import pytest

from scraper.book import Book
from scraper.fetch import FetchResult
from scraper.stages import download, site_latest


def chapter(text, title="T"):
    return f"<html><head><title>{title}</title></head><body><div id='c'><p>{text}</p></div></body></html>"


NOT_FOUND = "<html><body><div id='c'></div><p>Chapter not found.</p></body></html>"


def make_book(tmp_path, extra=""):
    book = Book(tmp_path / "B")
    book.create({"title": "Book", "url_template": "http://x/{n}", "content_selector": "#c"})
    if extra:
        with book.config_path.open("a", encoding="utf-8") as handle:
            handle.write(extra)
    return book


class StubFetcher:
    """Serves canned HTML and writes it to the raw folder, as the real fetcher does."""

    def __init__(self, book, pages, interrupt_on=None):
        self.book, self.pages, self.interrupt_on = book, pages, interrupt_on
        self.asked = []

    def fetch(self, url, number):
        self.asked.append(number)
        if number == self.interrupt_on:
            raise KeyboardInterrupt
        html = self.pages.get(number)
        if html is None:
            return None
        path = self.book.raw_path(number)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        return FetchResult(number=number, url=url, html=html, from_cache=False)


# --- download ---------------------------------------------------------------


def test_download_fetches_up_to_the_latest_chapter(tmp_path):
    book = make_book(tmp_path)
    fetcher = StubFetcher(book, {n: chapter(n) for n in range(1, 4)})

    got = download(book, book.settings(), fetcher, latest=3)

    assert got == [1, 2, 3]
    assert book.raw_numbers() == [1, 2, 3]


def test_chapters_already_held_are_not_asked_for(tmp_path):
    book = make_book(tmp_path)
    book.raw_path(1).write_text(chapter("old"), encoding="utf-8")
    fetcher = StubFetcher(book, {n: chapter(n) for n in range(1, 4)})

    got = download(book, book.settings(), fetcher, latest=3)

    assert got == [2, 3]
    assert fetcher.asked == [2, 3]


def test_refresh_asks_for_held_chapters_again(tmp_path):
    book = make_book(tmp_path)
    book.raw_path(1).write_text(chapter("old"), encoding="utf-8")
    fetcher = StubFetcher(book, {1: chapter("new")})

    download(book, book.settings(refresh=True), fetcher, latest=1)

    assert fetcher.asked == [1]


def test_without_a_latest_chapter_it_stops_after_the_misses(tmp_path):
    book = make_book(tmp_path, "max_misses = 2\n")
    fetcher = StubFetcher(book, {1: chapter(1), 2: chapter(2)})

    got = download(book, book.settings(), fetcher)

    assert got == [1, 2]
    assert fetcher.asked == [1, 2, 3, 4]


def test_a_not_found_page_served_as_a_normal_page_is_a_miss_and_not_kept(tmp_path):
    book = make_book(tmp_path, "max_misses = 1\n")
    fetcher = StubFetcher(book, {1: chapter(1), 2: NOT_FOUND})

    got = download(book, book.settings(), fetcher)

    assert got == [1]
    assert book.raw_numbers() == [1]


def test_end_overrides_the_latest_chapter(tmp_path):
    book = make_book(tmp_path)
    fetcher = StubFetcher(book, {n: chapter(n) for n in range(1, 6)})

    got = download(book, book.settings(start=2, end=3), fetcher, latest=5)

    assert got == [2, 3]


def test_an_interrupted_download_keeps_what_it_has(tmp_path):
    book = make_book(tmp_path)
    fetcher = StubFetcher(book, {n: chapter(n) for n in range(1, 6)}, interrupt_on=3)
    lines = []

    got = download(book, book.settings(), fetcher, latest=5, log=lines.append)

    assert got == [1, 2]
    assert book.raw_numbers() == [1, 2]
    assert any("Interrupted" in line for line in lines)


# --- the site's latest chapter -----------------------------------------------

BOOK_PAGE = (
    '<meta property="og:novel:novel_name" content="Book">'
    '<meta property="og:novel:read_url" content="http://x/1">'
    '<meta property="og:novel:lastest_chapter_url" content="http://x/1274">'
)


def test_the_latest_chapter_comes_from_the_book_page(tmp_path):
    book = make_book(tmp_path, 'source = "http://x/book"\n')

    assert site_latest(book.settings(), {"http://x/book": BOOK_PAGE}.get) == 1274


def test_no_source_or_no_answer_means_no_latest_chapter(tmp_path):
    book = make_book(tmp_path)
    assert site_latest(book.settings(), lambda url: BOOK_PAGE) is None

    with_source = make_book(tmp_path / "other", 'source = "http://x/book"\n')
    assert site_latest(with_source.settings(), lambda url: None) is None
    assert site_latest(with_source.settings(), lambda url: "<html></html>") is None
