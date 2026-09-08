"""Sequential, polite HTTP fetching with an on-disk cache.

Knows nothing about HTML structure or chapters - it turns a URL into a
string of markup, or `None` if the page is not there.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_USER_AGENT = (
    "paginated-text-scraper/1.0 (+https://github.com/; polite, sequential, cached)"
)

# Transient conditions: worth another go after a wait.
_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class FetchResult:
    number: int
    url: str
    html: str
    from_cache: bool


class Fetcher:
    """Fetches numbered pages, one at a time, and remembers what it saw.

    Every successful response is written to `cache_dir` so a rerun costs
    nothing and an interrupted run can pick up where it stopped.
    """

    def __init__(
        self,
        cache_dir: Path | str,
        session=None,
        delay: float = 1.5,
        max_retries: int = 3,
        backoff: float = 2.0,
        refresh: bool = False,
        timeout: float = 30.0,
        user_agent: str = DEFAULT_USER_AGENT,
        sleep=time.sleep,
    ):
        self.cache_dir = Path(cache_dir)
        self.delay = delay
        self.max_retries = max(1, max_retries)
        self.backoff = backoff
        self.refresh = refresh
        self.timeout = timeout
        self.user_agent = user_agent
        self._sleep = sleep
        self._session = session
        self._has_hit_network = False

    # -- public ------------------------------------------------------------

    def fetch(self, url: str, number: int) -> FetchResult | None:
        """Return the page, or `None` if it is missing or unreachable."""
        cached = self._read_cache(number)
        if cached is not None:
            return FetchResult(number=number, url=url, html=cached, from_cache=True)

        html = self._fetch_over_network(url)
        if html is None:
            return None

        self._write_cache(number, html)
        return FetchResult(number=number, url=url, html=html, from_cache=False)

    # -- network -----------------------------------------------------------

    def _fetch_over_network(self, url: str) -> str | None:
        for attempt in range(1, self.max_retries + 1):
            self._wait_our_turn()

            try:
                response = self._get(url)
            except Exception:
                # Connection reset, DNS failure, timeout: all worth retrying.
                self._back_off(attempt)
                continue

            status = getattr(response, "status_code", 200)

            if status == 404:
                return None  # Definitively absent - retrying would be rude.

            if status in _RETRYABLE_STATUS:
                self._back_off(attempt, retry_after=self._retry_after(response))
                continue

            if status >= 400:
                return None

            return response.text

        return None

    def _get(self, url: str):
        self._has_hit_network = True
        return self.session.get(
            url,
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout,
        )

    @property
    def session(self):
        if self._session is None:
            import requests

            self._session = requests.Session()
        return self._session

    def _wait_our_turn(self) -> None:
        """Space out network requests. Cache hits never pay this cost."""
        if self._has_hit_network and self.delay > 0:
            self._sleep(self.delay)

    def _back_off(self, attempt: int, retry_after: float | None = None) -> None:
        if attempt >= self.max_retries:
            return  # About to give up; no point sleeping first.
        wait = retry_after if retry_after is not None else self.backoff * 2 ** (attempt - 1)
        if wait > 0:
            self._sleep(wait)

    @staticmethod
    def _retry_after(response) -> float | None:
        raw = getattr(response, "headers", {}).get("Retry-After")
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None  # An HTTP-date; fall back to our own backoff.

    # -- cache -------------------------------------------------------------

    def _cache_path(self, number: int) -> Path:
        return self.cache_dir / f"{number}.html"

    def _read_cache(self, number: int) -> str | None:
        if self.refresh:
            return None
        path = self._cache_path(number)
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None

    def _write_cache(self, number: int, html: str) -> None:
        path = self._cache_path(number)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
