"""Tests for keeping the reading place, safely, with several devices."""
import json
import threading
from datetime import datetime, timezone

import pytest

from scraper.book import Book
from scraper.web.positions import Conflict, read_position, save_position

CLOCK = lambda: datetime(2026, 10, 15, 21, 4, 11, tzinfo=timezone.utc)  # noqa: E731
PLACE = {"chapter": 3, "paragraph": 2, "offset": 0.5, "device": "d1", "device_name": "PC"}


@pytest.fixture
def book(tmp_path):
    book = Book(tmp_path / "B")
    book.create({"title": "B", "url_template": "http://x/{n}"})
    return book


def test_nothing_saved_yet(book):
    assert read_position(book) == {"revision": 0, "position": None}


def test_a_save_on_the_current_revision_is_kept_with_the_servers_time(book):
    saved = save_position(book, 0, {**PLACE, "saved_at": "1999-01-01T00:00:00Z"}, now=CLOCK)

    assert saved["revision"] == 1
    assert saved["position"]["saved_at"] == "2026-10-15T21:04:11Z"
    assert read_position(book) == saved


def test_a_stale_save_is_refused_and_changes_nothing(book):
    save_position(book, 0, PLACE, now=CLOCK)
    before = book.reading_path.read_bytes()

    with pytest.raises(Conflict) as caught:
        save_position(book, 0, {**PLACE, "chapter": 1}, now=CLOCK)

    assert caught.value.current["revision"] == 1 and caught.value.current["position"]["chapter"] == 3
    assert book.reading_path.read_bytes() == before


def test_two_devices_saving_at_once_exactly_one_wins(book):
    results, start = [], threading.Barrier(8)

    def device(i):
        start.wait()
        try:
            save_position(book, 0, {**PLACE, "device": f"d{i}"}, now=CLOCK)
            results.append("won")
        except Conflict:
            results.append("refused")

    threads = [threading.Thread(target=device, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("won") == 1 and read_position(book)["revision"] == 1


def test_a_corrupt_file_is_treated_as_empty(book):
    book.reading_path.write_text("{not json", encoding="utf-8")

    assert read_position(book) == {"revision": 0, "position": None}
    assert save_position(book, 0, PLACE, now=CLOCK)["revision"] == 1


def test_no_temporary_files_are_left_behind(book):
    save_position(book, 0, PLACE, now=CLOCK)

    assert sorted(p.name for p in book.folder.iterdir() if p.is_file()) == ["book.toml", "reading.json"]
    assert json.loads(book.reading_path.read_text(encoding="utf-8"))["revision"] == 1
