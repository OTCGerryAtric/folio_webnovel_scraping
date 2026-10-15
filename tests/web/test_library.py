"""Tests for what the library and book pages show. No network."""
from scraper.book import Book
from scraper.web.library import SiteCache, chapter_map, file_info, save_cover, summary

PAGE = (
    '<html><head><meta property="og:novel:novel_name" content="B">'
    '<meta property="og:novel:read_url" content="http://x/1">'
    '<meta property="og:novel:lastest_chapter_url" content="http://x/9"></head></html>'
)


def make(tmp_path, source=True):
    book = Book(tmp_path / "B")
    values = {"title": "B", "url_template": "http://x/{n}"}
    if source:
        values["source"] = "http://x/book"
    book.create(values)
    return book


def test_chapter_map_runs():
    assert chapter_map([1, 2, 3, 5], [1, 2], 1, 7) == [
        ["cleaned", 1, 2], ["raw", 3, 3], ["missing", 4, 4], ["raw", 5, 5], ["new", 6, 7],
    ]


def test_chapter_map_with_nothing_held():
    assert chapter_map([], [], 1, 3) == [["new", 1, 3]]
    assert chapter_map([], [], 1, None) == []


def test_file_info_reads_the_range_from_the_name(tmp_path):
    path = tmp_path / "Shadow Slave 1001-1274.epub"
    path.write_bytes(b"x" * 10)

    info = file_info(path)

    assert (info["first"], info["last"], info["format"], info["size"]) == (1001, 1274, "epub", 10)


def test_site_cache_checks_once_within_its_ttl(tmp_path):
    book = make(tmp_path)
    calls = []
    now = [0.0]

    def get_page(url):
        calls.append(url)
        return PAGE

    site = SiteCache(get_page, ttl=60, clock=lambda: now[0])
    assert site.peek("B") is None
    assert site.check(book, book.settings()) == 9
    assert site.check(book, book.settings()) == 9
    assert len(calls) == 1
    now[0] = 61
    site.check(book, book.settings())
    assert len(calls) == 2
    assert site.peek("B") == 9


def test_summary_counts_and_new(tmp_path):
    book = make(tmp_path)
    for n in (1, 2, 4):
        book.raw_path(n).write_text("x", encoding="utf-8")
    site = SiteCache(lambda url: PAGE)
    site.check(book, book.settings())

    data = summary(book, site)

    assert data["ready"] and data["downloaded"] == 3 and data["missing"] == 1
    assert data["latest"] == 9 and data["new"] == 5


def test_a_folder_without_book_toml_is_listed_as_needing_setup(tmp_path):
    (tmp_path / "Loose").mkdir()

    data = summary(Book(tmp_path / "Loose"), SiteCache(lambda url: None))

    assert data["ready"] is False and "book.toml" in data["error"]


def test_save_cover_sniffs_the_image_type(tmp_path):
    book = make(tmp_path)

    path = save_cover(book, "http://x/c", lambda url: b"\x89PNG\r\n\x1a\n" + b"0" * 8)

    assert path.name == "cover.png" and book.cover_path == path


def test_save_cover_ignores_what_is_not_an_image(tmp_path):
    book = make(tmp_path)

    assert save_cover(book, "http://x/c", lambda url: b"<html>") is None
    assert book.cover_path is None


def test_summary_says_where_reading_got_to(tmp_path):
    from scraper.web.positions import save_position

    book = make(tmp_path)
    assert summary(book, SiteCache(lambda url: None))["reading"] is None

    save_position(book, 0, {"chapter": 7, "paragraph": 2, "offset": 0.1, "device": "d", "device_name": "PC"})

    assert summary(book, SiteCache(lambda url: None))["reading"] == {"chapter": 7}
