"""Tests for joining extracted pages into one document."""
import zipfile

import pytest

from scraper.assemble import write_document
from scraper.extract import Page


def page(number, title, body):
    return Page(number=number, title=title, body=body)


# --- markdown ---------------------------------------------------------------


def test_markdown_joins_pages_under_their_titles(tmp_path):
    out = tmp_path / "book.md"
    write_document([page(1, "One", "First body."), page(2, "Two", "Second body.")], out)

    assert out.read_text(encoding="utf-8") == (
        "# One\n\nFirst body.\n\n# Two\n\nSecond body.\n"
    )


def test_markdown_falls_back_to_the_page_number_for_an_untitled_page(tmp_path):
    out = tmp_path / "book.md"
    write_document([page(4, None, "Body.")], out)

    assert out.read_text(encoding="utf-8").startswith("# Page 4\n")


def test_markdown_keeps_inline_formatting_untouched(tmp_path):
    out = tmp_path / "book.md"
    write_document([page(1, "T", "An *emphasised* and **strong** word.")], out)

    assert "An *emphasised* and **strong** word." in out.read_text(encoding="utf-8")


def test_a_document_title_becomes_a_leading_heading(tmp_path):
    out = tmp_path / "book.md"
    write_document([page(1, "One", "Body.")], out, title="My Book")

    assert out.read_text(encoding="utf-8").startswith("# My Book\n\n## One\n")


# --- plain text -------------------------------------------------------------


def test_plain_text_strips_emphasis_markers(tmp_path):
    out = tmp_path / "book.txt"
    write_document([page(1, "T", "An *emphasised* and **strong** word.")], out)

    assert "An emphasised and strong word." in out.read_text(encoding="utf-8")


def test_plain_text_unescapes_markdown_metacharacters(tmp_path):
    out = tmp_path / "book.txt"
    write_document([page(1, "T", r"5 \* 3 and a\_b")], out)

    assert "5 * 3 and a_b" in out.read_text(encoding="utf-8")


def test_plain_text_leaves_a_literal_asterisk_alone(tmp_path):
    out = tmp_path / "book.txt"
    write_document([page(1, "T", r"a \* b \* c")], out)

    assert "a * b * c" in out.read_text(encoding="utf-8")


def test_plain_text_underlines_page_titles(tmp_path):
    out = tmp_path / "book.txt"
    write_document([page(1, "Chapter One", "Body.")], out)

    text = out.read_text(encoding="utf-8")
    assert "Chapter One\n===========" in text


# --- epub -------------------------------------------------------------------


def test_epub_is_a_readable_archive_with_one_chapter_per_page(tmp_path):
    out = tmp_path / "book.epub"
    write_document([page(1, "One", "First body."), page(2, "Two", "Second body.")], out)

    assert out.exists()
    with zipfile.ZipFile(out) as archive:
        contents = "".join(
            archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.endswith((".xhtml", ".html"))
        )
    assert "First body." in contents
    assert "Second body." in contents


def test_epub_renders_emphasis_as_markup(tmp_path):
    out = tmp_path / "book.epub"
    write_document([page(1, "One", "An *emphasised* word.")], out)

    with zipfile.ZipFile(out) as archive:
        contents = "".join(
            archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.endswith((".xhtml", ".html"))
        )
    assert "<em>emphasised</em>" in contents


# --- errors -----------------------------------------------------------------


def test_an_unknown_extension_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="format"):
        write_document([page(1, "One", "Body.")], tmp_path / "book.docx")


def test_writing_nothing_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="no pages"):
        write_document([], tmp_path / "book.md")


def test_missing_parent_directories_are_created(tmp_path):
    out = tmp_path / "deep" / "nested" / "book.md"
    write_document([page(1, "One", "Body.")], out)

    assert out.exists()


# --- nested emphasis --------------------------------------------------------
#
# The extractor emits ***text*** when <strong> wraps <em>. Rendering that
# naively produces mis-nested tags, which reportlab rejects outright and
# which makes EPUB XHTML invalid.


def test_the_extractor_really_does_emit_triple_asterisks():
    from scraper.extract import extract_page

    page = extract_page(
        "<div id='c'><p><strong><em>Both</em></strong></p></div>", content_selector="#c"
    )

    assert page.body == "***Both***"


def test_bold_italic_is_well_formed_in_epub(tmp_path):
    import xml.etree.ElementTree as ET

    out = tmp_path / "book.epub"
    write_document([page(1, "One", "***Both*** and plain.")], out)

    with zipfile.ZipFile(out) as archive:
        documents = [
            archive.read(n).decode("utf-8")
            for n in archive.namelist()
            if n.endswith((".xhtml", ".html"))
        ]
    body = next(d for d in documents if "Both" in d)
    ET.fromstring(body)  # raises on mis-nested tags


def test_bold_italic_becomes_nested_tags_in_epub(tmp_path):
    out = tmp_path / "book.epub"
    write_document([page(1, "One", "***Both***")], out)

    with zipfile.ZipFile(out) as archive:
        contents = "".join(
            archive.read(n).decode("utf-8")
            for n in archive.namelist()
            if n.endswith((".xhtml", ".html"))
        )
    assert "<strong><em>Both</em></strong>" in contents


def test_bold_italic_reduces_to_plain_words_in_text(tmp_path):
    out = tmp_path / "book.txt"
    write_document([page(1, "One", "***Both*** and *one* and **two**.")], out)

    assert "Both and one and two." in out.read_text(encoding="utf-8")


def test_existing_nesting_still_works_in_epub(tmp_path):
    out = tmp_path / "book.epub"
    write_document(
        [page(1, "One", "**bold with *it* in**"), page(2, "Two", "*it with **bold** in*")],
        out,
    )

    with zipfile.ZipFile(out) as archive:
        contents = "".join(
            archive.read(n).decode("utf-8")
            for n in archive.namelist()
            if n.endswith((".xhtml", ".html"))
        )
    assert "<strong>bold with <em>it</em> in</strong>" in contents
    assert "<em>it with <strong>bold</strong> in</em>" in contents
