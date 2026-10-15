"""Tests for reading and writing a book's settings from the web app."""
import pytest

from scraper.book import Book
from scraper.web.settings import read_settings, write_raw, write_settings

TOML = """title = "Shadow Slave"
url_template = "https://x/chapter-{n}"

# a gentle pace
delay = 2.0

# Sentences matching any of these are removed.
remove_phrases = [
  # the site's own name
  'f[\\W_]*r[\\W_]*e',
]
"""


@pytest.fixture
def book(tmp_path):
    book = Book(tmp_path / "S")
    book.folder.mkdir()
    book.config_path.write_text(TOML, encoding="utf-8")
    return book


def test_read_gives_values_defaults_and_raw(book):
    data = read_settings(book)

    assert data["values"]["delay"] == 2.0
    assert data["values"]["author"] is None
    assert data["defaults"]["delay"] == 1.5
    assert data["raw"] == TOML


def test_changing_a_value_keeps_the_comments(book):
    write_settings(book, {"delay": 3, "author": "Guiltythree"})

    text = book.config_path.read_text(encoding="utf-8")
    assert "# a gentle pace" in text and "delay = 3.0" in text
    assert 'author = "Guiltythree"' in text
    assert book.settings().delay == 3.0


def test_adding_a_phrase_keeps_the_comment_inside_the_list(book):
    write_settings(book, {"remove_phrases": ["f[\\W_]*r[\\W_]*e", "n0vel1st"]})

    text = book.config_path.read_text(encoding="utf-8")
    assert "# the site's own name" in text
    assert '"n0vel1st"' in text
    assert book.settings().remove_phrases == ["f[\\W_]*r[\\W_]*e", "n0vel1st"]


def test_removing_a_phrase(book):
    write_settings(book, {"remove_phrases": []})

    assert book.settings().remove_phrases == []


def test_clearing_a_field_removes_the_key(book):
    write_settings(book, {"delay": None})

    assert "delay" not in book.config_path.read_text(encoding="utf-8")
    assert book.settings().delay == 1.5


def test_an_invalid_regex_changes_nothing(book):
    before = book.config_path.read_bytes()

    with pytest.raises(ValueError, match="Invalid remove phrase"):
        write_settings(book, {"remove_phrases": ["(unclosed"]})

    assert book.config_path.read_bytes() == before


def test_a_value_of_the_wrong_kind_is_refused(book):
    with pytest.raises(ValueError, match="delay"):
        write_settings(book, {"delay": "soon"})


def test_unknown_keys_are_refused(book):
    with pytest.raises(ValueError, match="cannot be changed"):
        write_settings(book, {"out": "x.md"})


def test_raw_text_is_validated_before_writing(book):
    before = book.config_path.read_bytes()

    with pytest.raises(ValueError, match="Unknown setting"):
        write_raw(book, TOML + "\nnonsense = 1\n")
    assert book.config_path.read_bytes() == before

    write_raw(book, TOML.replace("2.0", "4.0"))
    assert book.settings().delay == 4.0
