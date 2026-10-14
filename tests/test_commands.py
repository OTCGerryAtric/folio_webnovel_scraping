"""Tests for the book subcommands. Network access is stubbed throughout."""
import pytest

from scrape import main
from scraper.book import Book
from scraper.commands import run_command

PAGE_URL = "https://freewebnovel.com/novel/weakest-beast-tamer-gets-all-sss-dragons"

BOOK_PAGE = """<html><head>
<meta property="og:novel:author" content="Dagzo">
<meta property="og:novel:novel_name" content="Weakest Beast Tamer Gets All SSS Dragons">
<meta property="og:novel:read_url" content="https://freewebnovel.com/novel/weakest-beast-tamer-gets-all-sss-dragons/chapter-1">
<meta property="og:novel:status" content="OnGoing">
<meta property="og:novel:update_time" content="2026-10-14 00:07:21">
<meta property="og:novel:lastest_chapter_url" content="https://freewebnovel.com/novel/weakest-beast-tamer-gets-all-sss-dragons/chapter-1274">
</head></html>"""


def run(argv, root, pages=None, fetcher_factory=None):
    lines = []
    kwargs = {"get_page": (pages or {}).get, "root": root, "report": lines.append}
    if fetcher_factory is not None:
        kwargs["fetcher_factory"] = fetcher_factory
    code = run_command(argv, **kwargs)
    return code, "\n".join(lines)


# --- add --------------------------------------------------------------------


def test_add_creates_the_book_from_its_page(tmp_path):
    code, out = run(["add", PAGE_URL, "--name", "Weakest Beast Tamer"], tmp_path, {PAGE_URL: BOOK_PAGE})

    assert code == 0
    book = Book(tmp_path / "Weakest Beast Tamer")
    settings = book.settings()
    assert settings.title == "Weakest Beast Tamer Gets All SSS Dragons"
    assert settings.author == "Dagzo"
    assert settings.source == PAGE_URL
    assert settings.url_template.endswith("/chapter-{n}")
    assert len(settings.remove_phrases) == 1
    assert "1274 chapters" in out


def test_add_without_a_name_uses_the_title(tmp_path):
    run(["add", PAGE_URL], tmp_path, {PAGE_URL: BOOK_PAGE})

    assert (tmp_path / "Weakest Beast Tamer Gets All SSS Dragons" / "book.toml").exists()


def test_add_makes_a_title_with_forbidden_characters_into_a_folder(tmp_path):
    page = BOOK_PAGE.replace("Weakest Beast Tamer Gets All SSS Dragons", "Re:Zero? Part 1")

    code, _ = run(["add", PAGE_URL], tmp_path, {PAGE_URL: page})

    assert code == 0
    assert (tmp_path / "ReZero Part 1" / "book.toml").exists()


def test_add_refuses_to_overwrite_a_book(tmp_path):
    run(["add", PAGE_URL, "--name", "B"], tmp_path, {PAGE_URL: BOOK_PAGE})

    code, out = run(["add", PAGE_URL, "--name", "B"], tmp_path, {PAGE_URL: BOOK_PAGE})

    assert code == 2
    assert "already has a book.toml" in out


def test_add_reports_a_page_that_cannot_be_fetched(tmp_path):
    code, out = run(["add", PAGE_URL], tmp_path, {})

    assert code == 2
    assert "Could not fetch" in out


def test_add_by_hand_takes_a_template_and_a_title(tmp_path):
    code, _ = run(["add", "--url", "http://x/{n}", "--title", "Hand Made"], tmp_path)

    assert code == 0
    assert Book(tmp_path / "Hand Made").settings().url_template == "http://x/{n}"


def test_add_needs_a_page_or_a_template(tmp_path):
    code, out = run(["add"], tmp_path)

    assert code == 2
    assert "book page" in out


# --- books and status -------------------------------------------------------


def test_books_lists_each_book_and_what_it_holds(tmp_path):
    run(["add", "--url", "http://x/{n}", "--title", "Alpha"], tmp_path)
    Book(tmp_path / "Alpha").raw_path(1).write_text("x", encoding="utf-8")

    code, out = run(["books"], tmp_path)

    assert code == 0
    assert "Alpha" in out and "downloaded 1" in out


def test_books_with_none_says_how_to_add_one(tmp_path):
    _, out = run(["books"], tmp_path)

    assert "scrape.py add" in out


def test_status_shows_what_is_held_missing_and_new(tmp_path):
    run(["add", PAGE_URL, "--name", "B"], tmp_path, {PAGE_URL: BOOK_PAGE})
    book = Book(tmp_path / "B")
    for n in (1, 2, 3, 1273):
        book.raw_path(n).write_text("x", encoding="utf-8")

    code, out = run(["status", "b"], tmp_path, {PAGE_URL: BOOK_PAGE})

    assert code == 0
    assert "downloaded  1-3, 1273" in out
    assert "missing     4-1272, 1274" in out
    assert "latest 1274, 1 new" in out


def test_status_offline_makes_no_request(tmp_path):
    run(["add", PAGE_URL, "--name", "B"], tmp_path, {PAGE_URL: BOOK_PAGE})

    def refuse(url):
        raise AssertionError("no request expected")

    lines = []
    code = run_command(["status", "B", "--offline"], get_page=refuse, root=tmp_path, report=lines.append)

    assert code == 0
    assert "not checked" in "\n".join(lines)


def test_an_unknown_book_is_a_clear_error(tmp_path):
    code, out = run(["status", "nothing"], tmp_path)

    assert code == 2
    assert "No book called" in out


def test_scrape_main_hands_commands_over(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    code = main(["books"])

    assert code == 0
    assert "scrape.py add" in capsys.readouterr().err
