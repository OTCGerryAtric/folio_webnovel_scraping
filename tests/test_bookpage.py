"""Tests for reading a book's details from its main page."""
import re

import pytest

from scraper.bookpage import (
    chapter_from_url,
    parse_book_page,
    site_phrase,
    template_from_chapter_url,
)

PAGE_URL = "https://freewebnovel.com/novel/weakest-beast-tamer-gets-all-sss-dragons"

# The tags as freewebnovel published them for this book on 2026-10-14.
BOOK_PAGE = """<html><head>
<meta property="og:novel:category" content="English Novel">
<meta property="og:novel:author" content="Dagzo">
<meta property="og:novel:novel_name" content="Weakest Beast Tamer Gets All SSS Dragons">
<meta property="og:novel:read_url" content="https://freewebnovel.com/novel/weakest-beast-tamer-gets-all-sss-dragons/chapter-1">
<meta property="og:novel:status" content="OnGoing">
<meta property="og:novel:update_time" content="2026-10-14 00:07:21">
<meta property="og:novel:lastest_chapter_name" content="Chapter 1274 - Taming the Old World - Shadow Dragons - Reinforcements - 7">
<meta property="og:novel:lastest_chapter_url" content="https://freewebnovel.com/novel/weakest-beast-tamer-gets-all-sss-dragons/chapter-1274">
</head><body><h1>Weakest Beast Tamer</h1></body></html>"""


def test_the_book_details_are_read_from_the_meta_tags():
    info = parse_book_page(BOOK_PAGE, PAGE_URL)

    assert info.title == "Weakest Beast Tamer Gets All SSS Dragons"
    assert info.author == "Dagzo"
    assert info.url_template == (
        "https://freewebnovel.com/novel/weakest-beast-tamer-gets-all-sss-dragons/chapter-{n}"
    )
    assert info.latest == 1274
    assert info.status == "OnGoing"
    assert info.updated == "2026-10-14 00:07:21"


def test_a_relative_read_url_is_resolved_against_the_page():
    html = BOOK_PAGE.replace(
        "https://freewebnovel.com/novel/weakest-beast-tamer-gets-all-sss-dragons/chapter-1\"",
        "/novel/weakest-beast-tamer-gets-all-sss-dragons/chapter-1\"",
    )

    assert parse_book_page(html, PAGE_URL).url_template.startswith("https://freewebnovel.com/")


def test_a_page_without_the_tags_says_what_to_do_instead():
    with pytest.raises(ValueError, match="--url"):
        parse_book_page("<html><head><title>x</title></head></html>", PAGE_URL)


def test_the_last_number_in_a_chapter_url_becomes_the_placeholder():
    assert template_from_chapter_url("https://s2.com/b/7/chapter-1") == "https://s2.com/b/7/chapter-{n}"


def test_a_chapter_url_without_a_number_is_rejected():
    with pytest.raises(ValueError, match="number"):
        template_from_chapter_url("https://site.com/book/start")


def test_the_chapter_number_is_read_from_a_url():
    assert chapter_from_url("https://x.com/b/chapter-3214") == 3214
    assert chapter_from_url(None) is None


def test_the_site_phrase_matches_the_ways_the_name_is_written():
    pattern = re.compile(site_phrase("https://www.freewebnovel.com/novel/x"), re.IGNORECASE)

    for text in ("freewebnovel", "Free Web Novel", "freewebnovel.com", "FreeWebNovel"):
        assert pattern.search(text), text
    assert not pattern.search("a free novel on the web")


def test_the_site_phrase_comes_from_the_site_name_not_a_subdomain():
    pattern = re.compile(site_phrase("https://m.wuxiaworld.co/novel/x"), re.IGNORECASE)

    assert pattern.search("Read at WuxiaWorld")
    assert not pattern.search("my mother came home")


def test_a_site_name_too_short_to_be_safe_gives_no_phrase():
    assert site_phrase("https://ab.co/novel/x") is None
