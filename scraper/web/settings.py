"""Reading and writing a book's settings for the web app.

Writes go through tomlkit so the comments a person wrote in `book.toml`
survive, and every change is checked by `build_settings` first: an
invalid change leaves the file exactly as it was.
"""

from __future__ import annotations

import os
import tempfile

import tomlkit

from scraper.book import Book
from scraper.config import DEFAULTS, build_settings, parse_site_config

EDITABLE = (
    "title", "author", "source", "url_template", "start", "step",
    "content_selector", "title_selector", "remove_selectors",
    "dedupe", "dedupe_threshold", "strip_patterns", "trim_overlap", "overlap_window",
    "remove_phrases", "review_ignore", "build_every",
    "delay", "max_misses", "max_retries", "timeout",
)

_BOOLS = {k for k in EDITABLE if isinstance(DEFAULTS[k], bool)}
_INTS = {k for k in EDITABLE if isinstance(DEFAULTS[k], int) and k not in _BOOLS}
_FLOATS = {k for k in EDITABLE if isinstance(DEFAULTS[k], float)}
_LISTS = {k for k in EDITABLE if isinstance(DEFAULTS[k], list)}


def read_settings(book: Book) -> dict:
    text = book.config_path.read_text(encoding="utf-8")
    config = parse_site_config(text, str(book.config_path))
    return {
        "values": {k: config.get(k) for k in EDITABLE},
        "defaults": {k: DEFAULTS[k] for k in EDITABLE},
        "raw": text,
    }


def write_settings(book: Book, changes: dict) -> None:
    """Change some settings. A value of None or "" removes the key, so its default applies."""
    unknown = sorted(set(changes) - set(EDITABLE))
    if unknown:
        raise ValueError(f"These settings cannot be changed here: {', '.join(unknown)}")

    text = book.config_path.read_text(encoding="utf-8")
    config = parse_site_config(text, str(book.config_path))
    coerced = {key: _coerce(key, value) for key, value in changes.items()}
    for key, value in coerced.items():
        if value is None:
            config.pop(key, None)
        else:
            config[key] = value
    _check(book, config)

    doc = tomlkit.parse(text)
    for key, value in coerced.items():
        if value is None:
            if key in doc:
                del doc[key]
        elif key in _LISTS and isinstance(doc.get(key), list):
            _sync_array(doc[key], value)
        else:
            doc[key] = _item(value)
    _write(book, tomlkit.dumps(doc))


def write_raw(book: Book, text: str) -> None:
    """Replace the whole file, once the text has passed the same checks."""
    _check(book, parse_site_config(text, str(book.config_path)))
    _write(book, text)


def _check(book: Book, config: dict) -> None:
    build_settings({"cache_dir": str(book.raw_dir)}, config, require_out=False)


def _coerce(key: str, value):
    if value is None or value == "":
        return None
    try:
        if key in _BOOLS:
            if not isinstance(value, bool):
                raise TypeError
            return value
        if isinstance(value, bool) and key not in _LISTS:
            raise TypeError
        if key in _INTS:
            number = float(value)
            if number != int(number):
                raise TypeError
            return int(number)
        if key in _FLOATS:
            return float(value)
        if key in _LISTS:
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise TypeError
            return [v for v in value if v.strip()]
        if not isinstance(value, str):
            raise TypeError
        return value.strip()
    except (TypeError, ValueError):
        raise ValueError(f"{key} cannot be set to {value!r}") from None


def _string(value: str):
    """A pattern with backslashes reads best in single quotes, which keep them as typed."""
    if "\\" in value and "'" not in value and "\n" not in value:
        return tomlkit.string(value, literal=True)
    return tomlkit.string(value)


def _item(value):
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, list):
        array = tomlkit.array()
        for entry in value:
            array.append(_string(entry))
        if len(value) > 1:
            array.multiline(True)
        return array
    return value


def _sync_array(array, wanted: list[str]) -> None:
    """Change a list in place, so comments between its items stay put."""
    for index in reversed(range(len(array))):
        if str(array[index]) not in wanted:
            del array[index]
    have = [str(v) for v in array]
    for entry in wanted:
        if entry not in have:
            array.append(_string(entry))


def _write(book: Book, text: str) -> None:
    handle, temp = tempfile.mkstemp(dir=book.config_path.parent, prefix=".book-", suffix=".toml")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as out:
            out.write(text)
        os.replace(temp, book.config_path)
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise
