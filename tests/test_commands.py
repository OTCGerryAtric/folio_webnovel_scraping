"""Tests for the book subcommands. Network access is stubbed throughout."""
import pytest

from scrape import main
from scraper.book import Book
from scraper.commands import run_command
from scraper.fetch import FetchResult

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


# --- the stages -------------------------------------------------------------


def chapter(text, title="Chapter"):
    return f"<html><head><title>{title}</title></head><body><div id='c'><p>{text}</p></div></body></html>"


class StubFetcher:
    def __init__(self, book, pages):
        self.book, self.pages = book, pages

    def fetch(self, url, number):
        html = self.pages.get(number)
        if html is None:
            return None
        self.book.raw_path(number).write_text(html, encoding="utf-8")
        return FetchResult(number=number, url=url, html=html, from_cache=False)


def added_book(tmp_path, latest=3):
    page = BOOK_PAGE.replace("chapter-1274", f"chapter-{latest}")
    run(["add", PAGE_URL, "--name", "B"], tmp_path, {PAGE_URL: page})
    book = Book(tmp_path / "B")
    with book.config_path.open("a", encoding="utf-8") as handle:
        handle.write('content_selector = "#c"\ndelay = 0.0\n')
    return book, {PAGE_URL: page}


def test_download_fetches_up_to_the_sites_latest_chapter(tmp_path):
    book, site = added_book(tmp_path, latest=3)
    pages = {n: chapter(f"Text {n}.") for n in range(1, 6)}

    code, out = run(["download", "B"], tmp_path, site, lambda s: StubFetcher(book, pages))

    assert code == 0
    assert book.raw_numbers() == [1, 2, 3]
    assert "Downloaded 3 chapter(s)" in out


def test_clean_reports_what_it_removed(tmp_path):
    book, _ = added_book(tmp_path)
    for n in range(1, 4):
        book.raw_path(n).write_text(chapter(f"Text {n}. Read more at freewebnovel"), encoding="utf-8")

    code, out = run(["clean", "B"], tmp_path)

    assert code == 0
    assert book.cleaned_numbers() == [1, 2, 3]
    assert "sentence(s) matching" in out
    assert "Cleaned 3 chapter(s)" in out


def test_review_lists_repeated_sentences(tmp_path):
    book, _ = added_book(tmp_path)
    for n in range(1, 6):
        book.raw_path(n).write_text(
            chapter(f"Story number {n} continues. Give it a power stone, please!"), encoding="utf-8"
        )
    run(["clean", "B", "--no-dedupe"], tmp_path)

    code, out = run(["review", "B", "--min-chapters", "3"], tmp_path)

    assert code == 0
    assert "Give it a power stone, please!" in out


def test_review_before_clean_says_to_clean(tmp_path):
    added_book(tmp_path)

    code, out = run(["review", "B"], tmp_path)

    assert code == 2
    assert "clean" in out


def test_build_writes_the_whole_book_by_default(tmp_path):
    book, _ = added_book(tmp_path)
    for n in range(1, 4):
        book.raw_path(n).write_text(chapter(f"Text {n}."), encoding="utf-8")
    run(["clean", "B"], tmp_path)

    code, out = run(["build", "B", "--format", "md"], tmp_path)

    assert code == 0
    assert (book.output_dir / "B 1-3.md").exists()
    assert "Wrote 3 chapter(s)" in out


def test_update_builds_just_the_new_chapters(tmp_path):
    book, site = added_book(tmp_path, latest=4)
    pages = {n: chapter(f"Text {n}.") for n in range(1, 5)}
    for n in (1, 2):
        book.raw_path(n).write_text(pages[n], encoding="utf-8")

    code, out = run(["update", "B", "--format", "md"], tmp_path, site, lambda s: StubFetcher(book, pages))

    assert code == 0
    assert [p.name for p in book.outputs()] == ["B 3-4.md"]
    assert book.cleaned_numbers() == [1, 2, 3, 4]


def test_update_with_nothing_new_says_so_and_builds_nothing(tmp_path):
    book, site = added_book(tmp_path, latest=2)
    pages = {n: chapter(f"Text {n}.") for n in range(1, 3)}
    for n in (1, 2):
        book.raw_path(n).write_text(pages[n], encoding="utf-8")

    code, out = run(["update", "B"], tmp_path, site, lambda s: StubFetcher(book, pages))

    assert code == 0
    assert "Up to date" in out
    assert book.outputs() == []


def test_add_seeds_no_phrase_for_a_site_name_too_short_to_be_safe(tmp_path):
    code, out = run(["add", "https://ab.co/novel/b", "--name", "B"], tmp_path, {"https://ab.co/novel/b": BOOK_PAGE})

    assert code == 0
    assert Book(tmp_path / "B").settings().remove_phrases == []
    assert "remove_phrases" in out


def test_a_file_in_use_is_a_clear_error_not_a_crash(tmp_path, monkeypatch):
    added_book(tmp_path)

    def locked(*args, **kwargs):
        raise PermissionError(13, "The file is in use by another program", "B 1-3.epub")

    monkeypatch.setattr("scraper.commands.build", locked)

    code, out = run(["build", "B"], tmp_path)

    assert code == 2
    assert "error:" in out and "in use" in out


def three_cleaned_chapters(tmp_path, extra=""):
    book, _ = added_book(tmp_path)
    if extra:
        with book.config_path.open("a", encoding="utf-8") as handle:
            handle.write(extra)
    for n in range(1, 4):
        book.raw_path(n).write_text(chapter(f"Text {n}."), encoding="utf-8")
    run(["clean", "B"], tmp_path)
    return book


def test_build_every_writes_blocks(tmp_path):
    book = three_cleaned_chapters(tmp_path)

    code, out = run(["build", "B", "--format", "md", "--every", "2"], tmp_path)

    assert code == 0
    assert [p.name for p in book.outputs()] == ["B 1-2.md", "B 3-3.md"]
    assert "Wrote 2 file(s)" in out


def test_build_every_can_be_the_books_default(tmp_path):
    book = three_cleaned_chapters(tmp_path, "build_every = 2\n")

    run(["build", "B", "--format", "md"], tmp_path)

    assert [p.name for p in book.outputs()] == ["B 1-2.md", "B 3-3.md"]


def test_every_zero_overrides_the_default_with_one_book(tmp_path):
    book = three_cleaned_chapters(tmp_path, "build_every = 2\n")

    run(["build", "B", "--format", "md", "--every", "0"], tmp_path)

    assert [p.name for p in book.outputs()] == ["B 1-3.md"]


def test_a_negative_block_size_is_a_clear_error(tmp_path):
    three_cleaned_chapters(tmp_path)

    code, out = run(["build", "B", "--every", "-5"], tmp_path)

    assert code == 2
    assert "every" in out
