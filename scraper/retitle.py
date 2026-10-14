"""Replace scraped page titles with ones supplied from a file."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path


def load_titles(path):
    """Read a {number: title} mapping from a JSON file.

    Keys arrive as strings - JSON has no integer keys - so they are
    converted back to the page numbers they stand for.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"could not read {path}: {exc.strerror.lower()}") from exc

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"{path} must hold a JSON object of number: title")
    return {int(key): value for key, value in raw.items()}


def apply_titles(pages, titles):
    """Give each page the supplied title for its number."""
    out = []
    replaced = 0
    for page in pages:
        new = titles.get(page.number)
        if new:
            page = dataclasses.replace(page, title=new)
            replaced += 1
        out.append(page)
    return out, replaced
