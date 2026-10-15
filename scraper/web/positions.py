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
from datetime import datetime, timezone

from scraper.book import Book

log = logging.getLogger(__name__)
_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()


class Conflict(Exception):
    """Another device saved since this one last looked."""

    def __init__(self, current: dict):
        super().__init__("Another device has saved a newer place.")
        self.current = current


def _lock(book: Book) -> threading.Lock:
    with _guard:
        return _locks.setdefault(str(book.folder.resolve()), threading.Lock())


def read_position(book: Book) -> dict:
    """`{revision, position}`; a missing or unreadable file reads as nothing saved."""
    try:
        data = json.loads(book.reading_path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("revision"), int):
            return {"revision": data["revision"], "position": data.get("position")}
        log.warning("Ignoring unrecognised %s", book.reading_path)
    except FileNotFoundError:
        pass
    except (OSError, ValueError):
        log.warning("Ignoring unreadable %s", book.reading_path)
    return {"revision": 0, "position": None}


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
            os.replace(temp, book.reading_path)
        except BaseException:
            if os.path.exists(temp):
                os.unlink(temp)
            raise
        return saved
