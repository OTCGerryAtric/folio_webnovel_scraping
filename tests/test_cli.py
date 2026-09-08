"""Tests for argument parsing and the top-level entry point."""
import pytest

from scrape import main, parse_args
from scraper.fetch import FetchResult


def body(text):
    return f"<html><body><div id='c'><p>{text}</p></div></body></html>"


class StubFetcher:
    def __init__(self, pages):
        self.pages = pages

    def fetch(self, url, number):
        html = self.pages.get(number)
        if html is None:
            return None
        return FetchResult(number=number, url=url, html=html, from_cache=False)


# --- parsing ----------------------------------------------------------------


def test_the_core_flags_are_mapped():
    args = parse_args(
        ["--url", "http://x/{n}", "--out", "b.md", "--start", "2", "--end", "9"]
    )

    assert args["url_template"] == "http://x/{n}"
    assert args["out"] == "b.md"
    assert args["start"] == 2
    assert args["end"] == 9


def test_unset_flags_are_none_so_a_site_file_can_supply_them():
    args = parse_args(["--url", "http://x/{n}", "--out", "b.md"])

    assert args["delay"] is None
    assert args["content_selector"] is None
    assert args["refresh"] is None


def test_remove_can_be_repeated():
    args = parse_args(
        ["--url", "http://x/{n}", "--out", "b.md", "--remove", ".ad", "--remove", ".nav"]
    )

    assert args["remove_selectors"] == [".ad", ".nav"]


def test_selector_flags_are_mapped():
    args = parse_args(
        ["--url", "http://x/{n}", "--out", "b.md", "--selector", "#c", "--title-selector", "h1"]
    )

    assert args["content_selector"] == "#c"
    assert args["title_selector"] == "h1"


# --- running ----------------------------------------------------------------


def test_a_successful_run_writes_the_document(tmp_path):
    out = tmp_path / "book.md"
    code = main(
        ["--url", "http://x/{n}", "--out", str(out), "--start", "1", "--end", "2",
         "--selector", "#c"],
        fetcher_factory=lambda settings: StubFetcher({1: body("one"), 2: body("two")}),
    )

    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "one" in text and "two" in text


def test_a_run_that_collects_nothing_exits_non_zero(tmp_path):
    out = tmp_path / "book.md"
    code = main(
        ["--url", "http://x/{n}", "--out", str(out), "--start", "1", "--end", "2",
         "--selector", "#c"],
        fetcher_factory=lambda settings: StubFetcher({}),
    )

    assert code != 0
    assert not out.exists()


def test_a_bad_template_exits_non_zero_without_fetching(tmp_path):
    code = main(
        ["--url", "http://x/no-placeholder", "--out", str(tmp_path / "b.md")],
        fetcher_factory=lambda settings: pytest.fail("should not have fetched"),
    )

    assert code != 0


def test_a_site_file_supplies_defaults(tmp_path):
    site = tmp_path / "site.toml"
    site.write_text(
        'url_template = "http://x/{n}"\ncontent_selector = "#c"\n', encoding="utf-8"
    )
    out = tmp_path / "book.md"

    code = main(
        ["--site", str(site), "--out", str(out), "--start", "1", "--end", "1"],
        fetcher_factory=lambda settings: StubFetcher({1: body("only")}),
    )

    assert code == 0
    assert "only" in out.read_text(encoding="utf-8")


# --- boilerplate removal ----------------------------------------------------


def test_dedupe_is_on_unless_switched_off():
    assert parse_args(["--url", "http://x/{n}", "--out", "b.md"])["dedupe"] is None
    assert parse_args(["--url", "http://x/{n}", "--out", "b.md", "--no-dedupe"])["dedupe"] is False


def test_strip_regex_can_be_repeated():
    args = parse_args(
        ["--url", "http://x/{n}", "--out", "b.md", "--strip-regex", "^Nav", "--strip-regex", "^Ad"]
    )

    assert args["strip_patterns"] == ["^Nav", "^Ad"]


def test_the_dedupe_threshold_is_parsed():
    args = parse_args(["--url", "http://x/{n}", "--out", "b.md", "--dedupe-threshold", "0.8"])

    assert args["dedupe_threshold"] == 0.8


def chrome_page(text):
    return f"<html><body><div id='c'><p>Prev Chapter</p><p>{text}</p></div></body></html>"


def test_repeated_chrome_is_gone_from_the_finished_document(tmp_path):
    out = tmp_path / "book.md"
    pages = {n: chrome_page(f"Body {n}.") for n in (1, 2, 3)}

    code = main(
        ["--url", "http://x/{n}", "--out", str(out), "--start", "1", "--end", "3",
         "--selector", "#c"],
        fetcher_factory=lambda settings: StubFetcher(pages),
    )

    text = out.read_text(encoding="utf-8")
    assert code == 0
    assert "Prev Chapter" not in text
    assert "Body 1." in text and "Body 3." in text


def test_no_dedupe_keeps_the_chrome(tmp_path):
    out = tmp_path / "book.md"
    pages = {n: chrome_page(f"Body {n}.") for n in (1, 2, 3)}

    main(
        ["--url", "http://x/{n}", "--out", str(out), "--start", "1", "--end", "3",
         "--selector", "#c", "--no-dedupe"],
        fetcher_factory=lambda settings: StubFetcher(pages),
    )

    assert "Prev Chapter" in out.read_text(encoding="utf-8")


def test_a_strip_pattern_is_applied(tmp_path):
    out = tmp_path / "book.md"
    pages = {n: f"<html><body><div id='c'><p>Chapter {n} - Title</p><p>Body {n}.</p></div></body></html>" for n in (1, 2)}

    main(
        ["--url", "http://x/{n}", "--out", str(out), "--start", "1", "--end", "2",
         "--selector", "#c", "--strip-regex", r"^Chapter \d+ - "],
        fetcher_factory=lambda settings: StubFetcher(pages),
    )

    text = out.read_text(encoding="utf-8")
    assert "- Title" not in text
    assert "Body 1." in text


def test_an_invalid_strip_pattern_exits_non_zero(tmp_path):
    code = main(
        ["--url", "http://x/{n}", "--out", str(tmp_path / "b.md"), "--strip-regex", "[unclosed"],
        fetcher_factory=lambda settings: StubFetcher({}),
    )

    assert code == 2
