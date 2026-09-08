"""Tests for PDF output.

Each test builds a real PDF and reads it back with pypdf, so the
assertions are about what actually landed on the page.
"""
import re

from pypdf import PdfReader

from scraper.assemble import SUPPORTED_FORMATS, write_document
from scraper.extract import Page


def page(number, title, body):
    return Page(number=number, title=title, body=body)


def pdf_text(path) -> str:
    """All text in the document, with whitespace normalised.

    PDF extraction breaks lines wherever the layout did, so collapsing
    whitespace is what makes an assertion about wording meaningful.
    """
    reader = PdfReader(str(path))
    return re.sub(r"\s+", " ", " ".join(p.extract_text() for p in reader.pages))


def build(tmp_path, pages, **kwargs):
    out = tmp_path / "book.pdf"
    write_document(pages, out, **kwargs)
    return out


# --- the file itself --------------------------------------------------------


def test_pdf_is_an_offered_format():
    assert ".pdf" in SUPPORTED_FORMATS


def test_the_file_is_a_real_pdf(tmp_path):
    out = build(tmp_path, [page(1, "One", "Body text.")])

    assert out.read_bytes().startswith(b"%PDF-")


def test_missing_parent_directories_are_created(tmp_path):
    out = tmp_path / "deep" / "nested" / "book.pdf"
    write_document([page(1, "One", "Body.")], out)

    assert out.exists()


# --- content ----------------------------------------------------------------


def test_the_body_of_every_page_is_present(tmp_path):
    out = build(
        tmp_path, [page(1, "One", "The first body."), page(2, "Two", "The second body.")]
    )

    text = pdf_text(out)
    assert "The first body." in text
    assert "The second body." in text


def test_page_headings_are_present(tmp_path):
    out = build(tmp_path, [page(1, "Chapter One", "Body.")])

    assert "Chapter One" in pdf_text(out)


def test_an_untitled_page_falls_back_to_its_number(tmp_path):
    out = build(tmp_path, [page(4, None, "Body.")])

    assert "Page 4" in pdf_text(out)


def test_a_document_title_gets_its_own_page(tmp_path):
    out = build(tmp_path, [page(1, "One", "Body.")], title="My Collection")

    reader = PdfReader(str(out))
    first = re.sub(r"\s+", " ", reader.pages[0].extract_text())
    assert "My Collection" in first
    assert "Body." not in first, "the title page should stand alone"


def test_the_document_title_is_set_in_the_metadata(tmp_path):
    out = build(tmp_path, [page(1, "One", "Body.")], title="My Collection")

    assert PdfReader(str(out)).metadata.title == "My Collection"


# --- formatting -------------------------------------------------------------


def test_emphasis_markers_do_not_leak_into_the_text(tmp_path):
    out = build(tmp_path, [page(1, "One", "An *emphasised* and **strong** word.")])

    assert "An emphasised and strong word." in pdf_text(out)


def test_escaped_metacharacters_are_restored(tmp_path):
    out = build(tmp_path, [page(1, "One", r"5 \* 3 and a\_b")])

    assert "5 * 3 and a_b" in pdf_text(out)


def test_paragraphs_stay_separate(tmp_path):
    out = build(tmp_path, [page(1, "One", "First para.\n\nSecond para.")])

    text = pdf_text(out)
    assert "First para." in text
    assert "Second para." in text


def test_list_items_survive(tmp_path):
    out = build(tmp_path, [page(1, "One", "- alpha\n- beta")])

    text = pdf_text(out)
    assert "alpha" in text
    assert "beta" in text


def test_markup_special_characters_are_not_rendered_as_tags(tmp_path):
    out = build(tmp_path, [page(1, "One", "a < b and c > d and Smith & Sons")])

    text = pdf_text(out)
    assert "a < b and c > d and Smith & Sons" in text


# --- structure --------------------------------------------------------------


def test_each_source_page_starts_a_new_pdf_page(tmp_path):
    out = build(
        tmp_path,
        [page(1, "One", "First body."), page(2, "Two", "Second body."), page(3, "Three", "Third body.")],
    )

    reader = PdfReader(str(out))
    assert len(reader.pages) >= 3
    first = reader.pages[0].extract_text()
    assert "First body." in first
    assert "Second body." not in first


def test_pages_are_bookmarked_for_navigation(tmp_path):
    out = build(tmp_path, [page(1, "One", "Body."), page(2, "Two", "Body.")])

    titles = [str(item.title) for item in PdfReader(str(out)).outline if hasattr(item, "title")]
    assert "One" in titles
    assert "Two" in titles


def test_pages_are_numbered_in_the_footer(tmp_path):
    long_body = "\n\n".join(f"Paragraph {i} of some length." for i in range(60))
    out = build(tmp_path, [page(1, "One", long_body)])

    reader = PdfReader(str(out))
    assert len(reader.pages) > 1, "fixture should overflow onto a second page"
    # A distinctive marker, so body text containing digits cannot pass this.
    assert "- 2 -" in re.sub(r"\s+", " ", reader.pages[1].extract_text())
