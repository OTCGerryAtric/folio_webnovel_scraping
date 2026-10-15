"""Where each book was left: books/<name>/reading.json.

Saves are compare-and-set on a revision number, so a device that has not
seen the latest save cannot overwrite it - it is told what the newer place
is instead. Written atomically, under a lock per book, and stamped with
the server's own time.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from datetime import datetime, timezone

from scraper.book import Book

log = logging.getLogger(__name__)
_locks: dict[str, threading.Lock] = {}
# On Windows a file another handle has open (a reader of this file, a virus
# scanner, the search indexer) cannot be read or replaced for a moment.
_ATTEMPTS = 6
_PAUSE = 0.05
_guard = threading.Lock()


class Conflict(Exception):
    """Another device saved since this one last looked."""

    def __init__(self, current: dict):
        super().__init__("Another device has saved a newer place.")
        self.current = current


def _lock(book: Book) -> threading.Lock:
    with _guard:
        return _locks.setdefault(str(book.folder.resolve()), threading.Lock())


def _retry(action):
    """Run `action`, waiting out a file briefly locked by another program."""
    for attempt in range(1, _ATTEMPTS + 1):
        try:
            return action()
        except PermissionError:
            if attempt == _ATTEMPTS:
                raise
            time.sleep(_PAUSE * attempt)


def _valid(position) -> bool:
    return (
        isinstance(position, dict)
        and all(isinstance(position.get(k), int) and not isinstance(position.get(k), bool) for k in ("chapter", "paragraph"))
        and isinstance(position.get("offset"), (int, float))
    )


def read_position(book: Book) -> dict:
    """`{revision, position}`. A missing or corrupt file reads as nothing saved;
    a locked one is waited for, and raises rather than pretend nothing was saved."""
    try:
        data = json.loads(_retry(lambda: book.reading_path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return {"revision": 0, "position": None}
    except ValueError:
        log.warning("Ignoring unreadable %s", book.reading_path)
        return {"revision": 0, "position": None}
    if not isinstance(data, dict) or not isinstance(data.get("revision"), int):
        log.warning("Ignoring unrecognised %s", book.reading_path)
        return {"revision": 0, "position": None}
    position = data.get("position")
    if position is not None and not _valid(position):
        log.warning("Ignoring a malformed place in %s", book.reading_path)
        position = None
    return {"revision": data["revision"], "position": position}


def save_position(book: Book, base_revision: int, position: dict, now=None) -> dict:
    """Keep `position` if `base_revision` is still the latest; else raise Conflict."""
    now = now or (lambda: datetime.now(timezone.utc))
    with _lock(book):
        current = read_position(book)
        if base_revision != current["revision"]:
            raise Conflict(current)
        stamped = {**position, "saved_at": now().strftime("%Y-%m-%dT%H:%M:%SZ")}
        saved = {"revision": current["revision"] + 1, "position": stamped}
        handle, temp = tempfile.mkstemp(dir=book.folder, prefix=".reading-", suffix=".json")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                json.dump(saved, out)
            _retry(lambda: os.replace(temp, book.reading_path))
        except BaseException:
            if os.path.exists(temp):
                os.unlink(temp)
            raise
        return saved
