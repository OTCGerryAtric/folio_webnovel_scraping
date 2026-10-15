"""Tests for a book's folder: paths, finding it by name, its settings."""
import pytest

from scraper.book import (
    Book,
    chapter_file,
    describe_ranges,
    find_book,
    list_books,
    missing_numbers,
    safe_folder_name,
)


def make_book(root, name, config='url_template = "http://x/{n}"\n'):
    book = Book(root / name)
    book.folder.mkdir(parents=True)
    if config is not None:
        book.config_path.write_text(config, encoding="utf-8")
    return book


# --- naming -----------------------------------------------------------------


def test_chapter_files_are_padded_to_four_digits():
    assert chapter_file(7, ".md") == "0007.md"
    assert chapter_file(1274, ".html") == "1274.html"
    assert chapter_file(12345, ".html") == "12345.html"


def test_folder_names_lose_characters_windows_forbids():
    assert safe_folder_name("Re:Zero - What? <Part 1>") == "ReZero - What Part 1"
    assert safe_folder_name("  Trailing dots...  ") == "Trailing dots"


def test_ranges_are_described_compactly():
    assert describe_ranges([1, 2, 3, 7, 9, 10]) == "1-3, 7, 9-10"
    assert describe_ranges([]) == "none"


def test_missing_numbers_are_the_gaps_in_a_span():
    assert missing_numbers([1, 2, 5], start=1, end=6) == [3, 4, 6]


# --- the folder -------------------------------------------------------------


def test_stage_folders_are_numbered(tmp_path):
    book = Book(tmp_path / "Weakest Beast Tamer")

    assert book.name == "Weakest Beast Tamer"
    assert book.raw_dir.name == "01 Raw"
    assert book.cleaned_dir.name == "02 Cleaned"
    assert book.output_dir.name == "03 Output"
    assert book.raw_path(3).name == "0003.html"
    assert book.cleaned_path(3).name == "0003.md"


def test_chapters_held_are_read_from_the_stage_folders(tmp_path):
    book = Book(tmp_path / "B")
    book.raw_dir.mkdir(parents=True)
    for name in ("0002.html", "0010.html", "notes.txt", "0003.md"):
        (book.raw_dir / name).write_text("x", encoding="utf-8")

    assert book.raw_numbers() == [2, 10]
    assert book.cleaned_numbers() == []


def test_create_writes_the_settings_and_the_stage_folders(tmp_path):
    book = Book(tmp_path / "B")

    book.create({"title": 'A "quoted" title', "url_template": "http://x/{n}",
                 "remove_phrases": [r"free[\W_]*web"], "author": None})

    assert book.raw_dir.is_dir() and book.cleaned_dir.is_dir() and book.output_dir.is_dir()
    settings = book.settings()
    assert settings.title == 'A "quoted" title'
    assert settings.remove_phrases == [r"free[\W_]*web"]
    assert settings.author is None


def test_create_uses_a_folder_made_by_hand(tmp_path):
    (tmp_path / "B" / "01 Raw").mkdir(parents=True)

    Book(tmp_path / "B").create({"url_template": "http://x/{n}"})

    assert (tmp_path / "B" / "book.toml").exists()


def test_create_refuses_to_overwrite_existing_settings(tmp_path):
    book = make_book(tmp_path, "B")

    with pytest.raises(ValueError, match="already has a book.toml"):
        book.create({"url_template": "http://y/{n}"})


def test_settings_read_from_raw_and_override_from_arguments(tmp_path):
    book = make_book(tmp_path, "B", 'url_template = "http://x/{n}"\ndelay = 2.0\n')

    settings = book.settings(delay=0.5, start=None)

    assert settings.delay == 0.5
    assert settings.start == 1
    assert settings.cache_path == book.raw_dir


def test_a_book_without_settings_says_how_to_add_them(tmp_path):
    book = make_book(tmp_path, "B", config=None)

    with pytest.raises(ValueError, match="scrape.py add"):
        book.settings()


# --- finding books ----------------------------------------------------------


def test_books_are_listed_by_folder(tmp_path):
    make_book(tmp_path, "Shadow Slave")
    make_book(tmp_path, "Weakest Beast Tamer")
    (tmp_path / "stray.txt").write_text("x", encoding="utf-8")

    assert [b.name for b in list_books(tmp_path)] == ["Shadow Slave", "Weakest Beast Tamer"]


def test_no_books_folder_means_no_books(tmp_path):
    assert list_books(tmp_path / "missing") == []


def test_a_book_is_found_by_the_start_of_its_name_in_any_case(tmp_path):
    make_book(tmp_path, "Shadow Slave")
    make_book(tmp_path, "Weakest Beast Tamer")

    assert find_book("weakest", tmp_path).name == "Weakest Beast Tamer"
    assert find_book("WEAKEST BEAST TAMER", tmp_path).name == "Weakest Beast Tamer"


def test_an_exact_name_wins_over_a_longer_one(tmp_path):
    make_book(tmp_path, "Dragons")
    make_book(tmp_path, "Dragons Two")

    assert find_book("dragons", tmp_path).name == "Dragons"


def test_an_ambiguous_name_lists_the_candidates(tmp_path):
    make_book(tmp_path, "Shadow Slave")
    make_book(tmp_path, "Shadow Realm")

    with pytest.raises(ValueError, match="Shadow Realm, Shadow Slave"):
        find_book("shadow", tmp_path)


def test_an_unknown_name_lists_the_books(tmp_path):
    make_book(tmp_path, "Shadow Slave")

    with pytest.raises(ValueError, match="Books: Shadow Slave"):
        find_book("dragons", tmp_path)


def test_cover_path_finds_whichever_image_is_there(tmp_path):
    book = Book(tmp_path / "B")
    book.folder.mkdir()
    assert book.cover_path is None

    (book.folder / "cover.webp").write_bytes(b"x")

    assert book.cover_path == book.folder / "cover.webp"
