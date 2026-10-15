"""Tests for reading cleaned chapters for the reader."""
from scraper.assemble import _to_html, block_html
from scraper.book import Book
from scraper.web.chapters import chapter_version, list_chapters, read_chapter, split_chapter


def make(tmp_path, chapters):
    book = Book(tmp_path / "B")
    book.create({"title": "B", "url_template": "http://x/{n}"})
    for n, text in chapters.items():
        book.cleaned_path(n).write_text(text, encoding="utf-8")
    return book


def test_block_html_is_what_the_epub_renders():
    text = "One *em*.\n\nTwo **strong**.\n\n---\n\n> quoted\n\n- a\n- b"
    assert _to_html(text) == "\n".join(h for h in map(block_html, text.split("\n\n")) if h)


def test_split_chapter_takes_the_title_line_off():
    assert split_chapter("# C1: Start\n\nFirst para.\n\n\n\nSecond para.\n") == ("C1: Start", ["First para.", "Second para."])
    assert split_chapter("No title here.\n\nNext.") == (None, ["No title here.", "Next."])


def test_list_has_only_cleaned_chapters_with_gaps_absent(tmp_path):
    book = make(tmp_path, {1: "# One\n\nA b c.\n", 3: "# Three\n\nD e.\n"})

    assert list_chapters(book) == [
        {"number": 1, "title": "One", "words": 3},
        {"number": 3, "title": "Three", "words": 2},
    ]


def test_a_chapter_with_neighbours_across_a_gap(tmp_path):
    book = make(tmp_path, {1: "# One\n\nA.\n", 3: "# Three\n\nB.\n\nC.\n", 7: "# Seven\n\nD.\n"})

    chapter = read_chapter(book, 3)

    assert chapter["title"] == "Three" and chapter["paragraphs"] == ["<p>B.</p>", "<p>C.</p>"]
    assert (chapter["prev"], chapter["next"]) == (1, 7)
    assert read_chapter(book, 2) is None
    assert read_chapter(book, 1)["prev"] is None and read_chapter(book, 7)["next"] is None


def test_one_html_paragraph_per_text_paragraph(tmp_path):
    """Positions count paragraphs; the HTML must line up with the text."""
    book = make(tmp_path, {1: "# One\n\nA.\n\n---\n\n#### Aside\n\n> Q\n\nB.\n"})

    assert len(read_chapter(book, 1)["paragraphs"]) == 5


def test_scraped_markup_arrives_inert(tmp_path):
    book = make(tmp_path, {1: "# <b>T</b>\n\nHi <script>alert(1)</script> <img src=x onerror=alert(1)>\n"})

    chapter = read_chapter(book, 1)

    assert "<script>" not in chapter["paragraphs"][0] and "&lt;script&gt;" in chapter["paragraphs"][0]
    assert "<img" not in chapter["paragraphs"][0]
    assert chapter["title"] == "<b>T</b>"  # plain text; the page shows it as text, never HTML


def test_the_version_follows_the_text(tmp_path):
    book = make(tmp_path, {1: "# One\n\nA.\n"})
    before = read_chapter(book, 1)["version"]
    book.cleaned_path(1).write_text("# One\n\nA changed.\n", encoding="utf-8")

    assert read_chapter(book, 1)["version"] != before
    assert before == chapter_version("# One\n\nA.\n")


def test_a_book_with_nothing_built_can_still_be_read(tmp_path):
    book = make(tmp_path, {5: "# Five\n\nText.\n"})
    assert book.outputs() == [] and read_chapter(book, 5)["number"] == 5


def test_the_reading_file_lives_in_the_book_folder(tmp_path):
    book = make(tmp_path, {})
    assert book.reading_path == book.folder / "reading.json"
