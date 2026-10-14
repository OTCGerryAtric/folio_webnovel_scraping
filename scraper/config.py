"""Settings for a run: command-line arguments over an optional TOML file.

Every setting has a command-line flag, so the site file is a convenience
for sources you use repeatedly - never a requirement.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from scraper.overlap import DEFAULT_WINDOW

PLACEHOLDER = "{n}"

DEFAULTS: dict = {
    "url_template": None,
    "out": None,
    "start": 1,
    "end": None,
    "step": 1,
    "content_selector": None,
    "title_selector": None,
    "remove_selectors": [],
    "delay": 1.5,
    "max_misses": 3,
    "max_retries": 3,
    "backoff": 2.0,
    "timeout": 30.0,
    "dedupe": True,
    "dedupe_threshold": 0.6,
    "strip_patterns": [],
    "trim_overlap": True,
    "overlap_window": DEFAULT_WINDOW,
    "refresh": False,
    "title": None,
    "titles": None,
    "author": None,
    "source": None,
    "remove_phrases": [],
    "cache_dir": None,
    "verbose": False,
}

KNOWN_KEYS = frozenset(DEFAULTS)

_UNSAFE_PATH_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class Settings:
    url_template: str
    out: str
    start: int = 1
    end: int | None = None
    step: int = 1
    content_selector: str | None = None
    title_selector: str | None = None
    remove_selectors: list[str] = field(default_factory=list)
    delay: float = 1.5
    max_misses: int = 3
    dedupe: bool = True
    dedupe_threshold: float = 0.6
    strip_patterns: list[str] = field(default_factory=list)
    trim_overlap: bool = True
    overlap_window: int = DEFAULT_WINDOW
    max_retries: int = 3
    backoff: float = 2.0
    timeout: float = 30.0
    refresh: bool = False
    title: str | None = None
    titles: str | None = None
    author: str | None = None
    source: str | None = None
    remove_phrases: list[str] = field(default_factory=list)
    cache_dir: str | None = None
    verbose: bool = False

    def url_for(self, number: int) -> str:
        return self.url_template.replace(PLACEHOLDER, str(number))

    @property
    def cache_path(self) -> Path:
        """Where this source's raw pages live.

        Derived from the template so two sources never share a cache, and
        so the same source reuses its cache across runs.
        """
        if self.cache_dir:
            return Path(self.cache_dir)
        host = urlparse(self.url_template).netloc or "local"
        host = _UNSAFE_PATH_CHARS.sub("-", host).strip("-") or "source"
        digest = hashlib.sha1(self.url_template.encode("utf-8")).hexdigest()[:8]
        return Path(".cache") / f"{host}-{digest}"

    @property
    def numbers(self):
        """The sequence to walk. Unbounded when `end` is not set."""
        number = self.start
        while self.end is None or number <= self.end:
            yield number
            number += self.step


def load_site_config(path: Path | str) -> dict:
    """Read a TOML site file, rejecting keys we would silently ignore."""
    path = Path(path)
    if not path.exists():
        raise ValueError(f"Site config not found: {path}")

    try:
        with path.open("rb") as handle:
            config = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Could not parse {path}: {exc}") from exc

    unknown = sorted(set(config) - KNOWN_KEYS)
    if unknown:
        raise ValueError(
            f"Unknown setting(s) in {path}: {', '.join(unknown)}. "
            f"Valid keys: {', '.join(sorted(KNOWN_KEYS))}"
        )
    return config


def build_settings(args: dict, config: dict | None = None, require_out: bool = True) -> Settings:
    """Merge defaults, an optional site file, and CLI arguments, in that order.

    A book's stages choose their own output paths, so they pass
    `require_out=False`.
    """
    merged = dict(DEFAULTS)
    merged["remove_selectors"] = []
    merged["strip_patterns"] = []
    merged["remove_phrases"] = []

    for source in (config or {}, args or {}):
        merged.update({k: v for k, v in source.items() if v is not None})

    _validate(merged, require_out)
    return Settings(**{k: merged[k] for k in DEFAULTS})


def _validate(values: dict, require_out: bool = True) -> None:
    template = values.get("url_template")
    if not template:
        raise ValueError(
            "No url template given. Pass --url with a {n} placeholder, "
            "e.g. --url \"https://example.com/page-{n}\""
        )
    if PLACEHOLDER not in template:
        raise ValueError(
            f"The url template must contain the {{n}} placeholder: {template!r}"
        )
    if require_out and not values.get("out"):
        raise ValueError("No output path given. Pass --out, e.g. --out book.md")

    start, end, step = values["start"], values["end"], values["step"]
    if step is None or step < 1:
        raise ValueError(f"--step must be 1 or more, got {step!r}")
    if end is not None and end < start:
        raise ValueError(f"--end ({end}) is before --start ({start})")
    threshold = values["dedupe_threshold"]
    if not 0 < threshold <= 1:
        raise ValueError(
            f"--dedupe-threshold must be above 0 and at most 1, got {threshold!r}"
        )

    window = values["overlap_window"]
    if window is None or window < 1:
        raise ValueError(f"--overlap-window must be 1 or more, got {window!r}")

    for pattern in values.get("strip_patterns") or []:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"Invalid strip pattern {pattern!r}: {exc}") from exc

    for pattern in values.get("remove_phrases") or []:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"Invalid remove phrase {pattern!r}: {exc}") from exc

    if values["max_misses"] < 1:
        raise ValueError(f"--max-misses must be 1 or more, got {values['max_misses']!r}")
