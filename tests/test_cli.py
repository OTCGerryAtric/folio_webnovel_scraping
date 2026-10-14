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


# --- overlap trimming -------------------------------------------------------


def test_overlap_trimming_is_on_unless_switched_off():
    base = ["--url", "http://x/{n}", "--out", "b.md"]

    assert parse_args(base)["trim_overlap"] is None
    assert parse_args(base + ["--no-trim-overlap"])["trim_overlap"] is False


def test_the_overlap_window_is_parsed():
    args = parse_args(["--url", "http://x/{n}", "--out", "b.md", "--overlap-window", "30"])

    assert args["overlap_window"] == 30


def recap_pages():
    """Page 2 opens by restating how page 1 ended."""
    ending = "The path home had never felt so long that evening."
    return {
        1: f"<html><body><div id='c'><p>Page one opens on its own business entirely.</p>"
           f"<p>{ending}</p></div></body></html>",
        2: f"<html><body><div id='c'><p>{ending}</p>"
           f"<p>Cobblestone streets gave way to dirt roads outside the city.</p>"
           f"</div></body></html>",
    }


def test_a_recap_is_gone_from_the_finished_document(tmp_path):
    out = tmp_path / "book.md"

    code = main(
        ["--url", "http://x/{n}", "--out", str(out), "--start", "1", "--end", "2",
         "--selector", "#c"],
        fetcher_factory=lambda settings: StubFetcher(recap_pages()),
    )

    text = out.read_text(encoding="utf-8")
    assert code == 0
    assert text.count("The path home had never felt so long") == 1
    assert "Cobblestone streets" in text


def test_no_trim_overlap_keeps_the_recap(tmp_path):
    out = tmp_path / "book.md"

    main(
        ["--url", "http://x/{n}", "--out", str(out), "--start", "1", "--end", "2",
         "--selector", "#c", "--no-trim-overlap"],
        fetcher_factory=lambda settings: StubFetcher(recap_pages()),
    )

    assert out.read_text(encoding="utf-8").count("The path home had never felt so long") == 2


def test_the_trimmed_recap_is_reported(tmp_path, capsys):
    out = tmp_path / "book.md"

    main(
        ["--url", "http://x/{n}", "--out", str(out), "--start", "1", "--end", "2",
         "--selector", "#c"],
        fetcher_factory=lambda settings: StubFetcher(recap_pages()),
    )

    assert "path home" in capsys.readouterr().err


# --- supplied titles --------------------------------------------------------


def titled_page(title, text):
    return (
        f"<html><head><title>{title}</title></head>"
        f"<body><div id='c'><p>{text}</p></div></body></html>"
    )


def test_the_titles_flag_is_parsed():
    args = parse_args(["--url", "http://x/{n}", "--out", "b.md", "--titles", "t.json"])

    assert args["titles"] == "t.json"


def test_supplied_titles_replace_the_scraped_ones(tmp_path):
    titles = tmp_path / "titles.json"
    titles.write_text('{"1": "Proper One", "2": "Proper Two"}', encoding="utf-8")
    out = tmp_path / "book.md"

    code = main(
        [
            "--url", "http://x/{n}", "--out", str(out), "--selector", "#c",
            "--start", "1", "--end", "2", "--titles", str(titles),
        ],
        fetcher_factory=lambda settings: StubFetcher(
            {1: titled_page("Scraped junk 1", "one"), 2: titled_page("Scraped junk 2", "two")}
        ),
    )

    text = out.read_text(encoding="utf-8")
    assert code == 0
    assert "Proper One" in text and "Proper Two" in text
    assert "Scraped junk" not in text


def test_a_broken_titles_file_exits_non_zero_without_writing(tmp_path):
    titles = tmp_path / "titles.json"
    titles.write_text("{not json", encoding="utf-8")
    out = tmp_path / "book.md"

    code = main(
        [
            "--url", "http://x/{n}", "--out", str(out), "--selector", "#c",
            "--start", "1", "--end", "1", "--titles", str(titles),
        ],
        fetcher_factory=lambda settings: StubFetcher({1: titled_page("t", "one")}),
    )

    assert code != 0
    assert not out.exists()


# --- output name placeholders -----------------------------------------------


def test_first_and_last_in_the_output_name_are_the_pages_collected(tmp_path):
    pages = {n: body(f"Body {n}.") for n in (5, 6, 7)}

    code = main(
        ["--url", "http://x/{n}", "--out", str(tmp_path / "book-{first}-{last}.md"),
         "--start", "5", "--max-misses", "1", "--selector", "#c"],
        fetcher_factory=lambda settings: StubFetcher(pages),
    )

    assert code == 0
    assert (tmp_path / "book-5-7.md").exists()
    assert not (tmp_path / "book-{first}-{last}.md").exists()


def test_an_output_name_without_placeholders_is_used_as_given(tmp_path):
    out = tmp_path / "book.md"

    main(
        ["--url", "http://x/{n}", "--out", str(out), "--start", "1", "--end", "1",
         "--selector", "#c"],
        fetcher_factory=lambda settings: StubFetcher({1: body("Body.")}),
    )

    assert out.exists()
