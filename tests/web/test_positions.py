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


def test_a_briefly_locked_file_is_retried_not_lost(book, monkeypatch):
    """On Windows a reader or scanner holding reading.json makes replace fail for a moment."""
    import os

    real, failures = os.replace, [2]

    def flaky(src, dst):
        if failures[0]:
            failures[0] -= 1
            raise PermissionError(5, "Access is denied")
        return real(src, dst)
    monkeypatch.setattr(os, "replace", flaky)

    assert save_position(book, 0, PLACE, now=CLOCK)["revision"] == 1


def test_a_file_that_stays_locked_fails_loudly(book, monkeypatch):
    import os

    monkeypatch.setattr(os, "replace", lambda src, dst: (_ for _ in ()).throw(PermissionError(5, "denied")))

    with pytest.raises(OSError):
        save_position(book, 0, PLACE, now=CLOCK)
    assert [p.name for p in book.folder.iterdir() if p.name.startswith(".reading-")] == []


def test_a_locked_file_is_not_mistaken_for_nothing_saved(book, monkeypatch):
    from pathlib import Path

    save_position(book, 0, PLACE, now=CLOCK)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: (_ for _ in ()).throw(PermissionError(5, "denied")))

    with pytest.raises(OSError):
        read_position(book)


def test_a_position_of_the_wrong_shape_reads_as_nothing_saved(book):
    book.reading_path.write_text('{"revision": 3, "position": {"chapter": "five"}}', encoding="utf-8")

    assert read_position(book) == {"revision": 3, "position": None}
