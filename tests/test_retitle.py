"""Tests for replacing scraped page titles with a supplied mapping."""
import json

import pytest

from scraper.extract import Page
from scraper.retitle import apply_titles, load_titles


def page(number, title="scraped", body="text"):
    return Page(number=number, title=title, body=body)


# --- applying ---------------------------------------------------------------


def test_a_page_takes_the_supplied_title_for_its_number():
    pages, replaced = apply_titles([page(7)], {7: "Chapter 7 - Taming Ren"})

    assert pages[0].title == "Chapter 7 - Taming Ren"
    assert replaced == 1


def test_a_page_with_no_entry_keeps_the_title_it_was_scraped_with():
    pages, replaced = apply_titles([page(7), page(8, title="kept")], {7: "new"})

    assert pages[1].title == "kept"
    assert replaced == 1


# --- loading ----------------------------------------------------------------


def test_json_keys_are_read_as_page_numbers(tmp_path):
    path = tmp_path / "titles.json"
    path.write_text(json.dumps({"1": "First", "500": "Last"}), encoding="utf-8")

    assert load_titles(path) == {1: "First", 500: "Last"}


def test_titles_keep_their_accented_and_curly_characters(tmp_path):
    path = tmp_path / "titles.json"
    path.write_text(
        json.dumps({"3": "Tamer\u2019s \u201cCampaign\u201d"}, ensure_ascii=False),
        encoding="utf-8",
    )

    assert load_titles(path)[3] == "Tamer\u2019s \u201cCampaign\u201d"


def test_a_key_that_is_not_a_page_number_is_reported_clearly(tmp_path):
    path = tmp_path / "titles.json"
    path.write_text(json.dumps({"prologue": "First"}), encoding="utf-8")

    with pytest.raises(ValueError, match="prologue"):
        load_titles(path)


def test_malformed_json_is_reported_as_a_bad_titles_file(tmp_path):
    path = tmp_path / "titles.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="titles.json"):
        load_titles(path)


def test_a_missing_titles_file_is_reported_clearly(tmp_path):
    with pytest.raises(ValueError, match="absent.json"):
        load_titles(tmp_path / "absent.json")
