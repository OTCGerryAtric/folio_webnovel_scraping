"""Tests for tidying chapter titles."""
from scraper.extract import Page
from scraper.titles import tidy_title, tidy_titles

BOOK = "Weakest Beast Tamer Gets All SSS Dragons"


def test_the_full_decoration_is_removed():
    title = (
        "Weakest Beast Tamer Gets All SSS Dragons - Chapter 1264 - "
        "Taming the Old World - Shadow Dragons - 11 | Free Web Novel"
    )

    assert tidy_title(title, BOOK) == "Chapter 1264 - Taming the Old World - Shadow Dragons - 11"


def test_a_doubled_chapter_number_is_collapsed():
    assert tidy_title("Chapter 1 - 1 - Beast Tamer Ren Patinder") == "Chapter 1 - Beast Tamer Ren Patinder"
    assert tidy_title("Chapter 10 - 10 - Taming Fate") == "Chapter 10 - Taming Fate"


def test_a_number_that_only_starts_the_same_is_not_collapsed():
    assert tidy_title("Chapter 1 - 15 Swords") == "Chapter 1 - 15 Swords"


def test_the_book_title_is_matched_in_any_case():
    assert tidy_title("weakest beast tamer gets all sss dragons - Chapter 2", BOOK) == "Chapter 2"


def test_a_clean_title_is_left_alone():
    assert tidy_title("Chapter 1: Nightmare Begins", BOOK) == "Chapter 1: Nightmare Begins"


def test_a_title_that_is_only_the_book_title_is_kept():
    assert tidy_title(BOOK, BOOK) == BOOK


def test_no_title_stays_no_title():
    assert tidy_title(None, BOOK) is None


def test_every_page_is_tidied():
    pages = [Page(1, "Chapter 1 - 1 - A | Free Web Novel", "x"), Page(2, None, "y")]

    assert [p.title for p in tidy_titles(pages, BOOK)] == ["Chapter 1 - A", None]
