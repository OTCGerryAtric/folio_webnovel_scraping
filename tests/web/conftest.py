import pytest
from fastapi.testclient import TestClient

from scraper.book import Book
from scraper.web.app import create_app

PAGE_URL = "https://site.example/novel/b"
PAGE = (
    '<html><head><meta property="og:novel:novel_name" content="Bee Book">'
    '<meta property="og:novel:author" content="Ann">'
    '<meta property="og:novel:read_url" content="https://site.example/novel/b/chapter-1">'
    '<meta property="og:novel:lastest_chapter_url" content="https://site.example/novel/b/chapter-4">'
    '<meta property="og:image" content="https://site.example/c.png"></head></html>'
)
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 16


@pytest.fixture
def root(tmp_path):
    return tmp_path


@pytest.fixture
def client(root):
    app = create_app(root=root, get_page={PAGE_URL: PAGE}.get,
                     fetcher_factory=lambda settings: None,
                     get_bytes=lambda url: PNG, static_dir=root / "no-static")
    with TestClient(app) as client:
        yield client


@pytest.fixture
def book(root):
    book = Book(root / "B")
    book.create({"title": "B", "url_template": "http://x/{n}", "remove_phrases": ["zzz"]})
    filler = " ".join(f"Line {k} of the tale." for k in range(60))
    for n in range(1, 31):
        book.cleaned_path(n).write_text(
            f"# C{n}\n\nStory {n} starts in a plain way. Read more at FreeWebNovel.Com today.\n\n"
            f"Then the story {n} goes on. {filler}\n", encoding="utf-8")
    return book
