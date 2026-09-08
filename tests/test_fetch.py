"""Tests for the fetcher.

A fake session stands in for requests, so nothing here touches the network.
"""
import pytest

from scraper.fetch import Fetcher


class FakeResponse:
    def __init__(self, status_code=200, text="<html>ok</html>", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


class FakeSession:
    """Replays a queue of responses (or exceptions) and records the calls."""

    def __init__(self, *responses):
        self.queued = list(responses)
        self.requests = []

    def get(self, url, **kwargs):
        self.requests.append((url, kwargs))
        if not self.queued:
            raise AssertionError(f"unexpected extra request for {url}")
        item = self.queued.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClock:
    def __init__(self):
        self.slept = []

    def __call__(self, seconds):
        self.slept.append(seconds)


@pytest.fixture
def cache(tmp_path):
    return tmp_path / "cache"


def make(session, cache, **kwargs):
    kwargs.setdefault("delay", 0)
    kwargs.setdefault("sleep", FakeClock())
    return Fetcher(cache_dir=cache, session=session, **kwargs)


# --- the happy path ---------------------------------------------------------


def test_returns_the_page_body(cache):
    fetcher = make(FakeSession(FakeResponse(text="<p>hello</p>")), cache)

    result = fetcher.fetch("http://example.com/1", number=1)

    assert result.html == "<p>hello</p>"
    assert result.number == 1
    assert result.from_cache is False


def test_sends_a_descriptive_user_agent(cache):
    session = FakeSession(FakeResponse())
    make(session, cache).fetch("http://example.com/1", number=1)

    _, kwargs = session.requests[0]
    assert "User-Agent" in kwargs["headers"]
    assert kwargs["headers"]["User-Agent"].strip()


# --- caching ----------------------------------------------------------------


def test_a_fetched_page_is_written_to_the_cache(cache):
    make(FakeSession(FakeResponse(text="<p>saved</p>")), cache).fetch(
        "http://example.com/7", number=7
    )

    assert (cache / "7.html").read_text(encoding="utf-8") == "<p>saved</p>"


def test_a_cached_page_is_returned_without_a_request(cache):
    cache.mkdir(parents=True)
    (cache / "3.html").write_text("<p>from disk</p>", encoding="utf-8")
    session = FakeSession()  # any request would raise

    result = make(session, cache).fetch("http://example.com/3", number=3)

    assert result.html == "<p>from disk</p>"
    assert result.from_cache is True
    assert session.requests == []


def test_refresh_ignores_the_cache_and_overwrites_it(cache):
    cache.mkdir(parents=True)
    (cache / "3.html").write_text("<p>stale</p>", encoding="utf-8")
    session = FakeSession(FakeResponse(text="<p>fresh</p>"))

    result = make(session, cache, refresh=True).fetch("http://example.com/3", number=3)

    assert result.html == "<p>fresh</p>"
    assert result.from_cache is False
    assert (cache / "3.html").read_text(encoding="utf-8") == "<p>fresh</p>"


# --- misses -----------------------------------------------------------------


def test_a_404_is_a_miss(cache):
    result = make(FakeSession(FakeResponse(status_code=404)), cache).fetch(
        "http://example.com/99", number=99
    )

    assert result is None


def test_a_404_is_not_cached(cache):
    make(FakeSession(FakeResponse(status_code=404)), cache).fetch(
        "http://example.com/99", number=99
    )

    assert not (cache / "99.html").exists()


# --- retries ----------------------------------------------------------------


def test_a_server_error_is_retried_then_succeeds(cache):
    session = FakeSession(
        FakeResponse(status_code=503),
        FakeResponse(status_code=503),
        FakeResponse(text="<p>finally</p>"),
    )

    result = make(session, cache).fetch("http://example.com/1", number=1)

    assert result.html == "<p>finally</p>"
    assert len(session.requests) == 3


def test_rate_limiting_is_retried(cache):
    session = FakeSession(FakeResponse(status_code=429), FakeResponse(text="<p>ok</p>"))

    result = make(session, cache).fetch("http://example.com/1", number=1)

    assert result.html == "<p>ok</p>"


def test_backoff_grows_between_retries(cache):
    clock = FakeClock()
    session = FakeSession(
        FakeResponse(status_code=503),
        FakeResponse(status_code=503),
        FakeResponse(text="<p>ok</p>"),
    )

    make(session, cache, sleep=clock, backoff=2.0).fetch("http://example.com/1", number=1)

    waits = [s for s in clock.slept if s > 0]
    assert waits == [2.0, 4.0]


def test_retry_after_header_is_honoured(cache):
    clock = FakeClock()
    session = FakeSession(
        FakeResponse(status_code=429, headers={"Retry-After": "7"}),
        FakeResponse(text="<p>ok</p>"),
    )

    make(session, cache, sleep=clock, backoff=2.0).fetch("http://example.com/1", number=1)

    assert 7.0 in clock.slept


def test_giving_up_after_max_retries_is_a_miss(cache):
    session = FakeSession(*[FakeResponse(status_code=503) for _ in range(3)])

    result = make(session, cache, max_retries=3).fetch("http://example.com/1", number=1)

    assert result is None
    assert len(session.requests) == 3


def test_connection_errors_are_retried(cache):
    session = FakeSession(OSError("connection reset"), FakeResponse(text="<p>ok</p>"))

    result = make(session, cache).fetch("http://example.com/1", number=1)

    assert result.html == "<p>ok</p>"


def test_persistent_connection_errors_are_a_miss(cache):
    session = FakeSession(*[OSError("down") for _ in range(3)])

    result = make(session, cache, max_retries=3).fetch("http://example.com/1", number=1)

    assert result is None


# --- politeness -------------------------------------------------------------


def test_a_delay_is_applied_between_network_requests(cache):
    clock = FakeClock()
    session = FakeSession(FakeResponse(), FakeResponse())
    fetcher = make(session, cache, delay=1.5, sleep=clock)

    fetcher.fetch("http://example.com/1", number=1)
    fetcher.fetch("http://example.com/2", number=2)

    assert clock.slept.count(1.5) == 1, "delay applies before the second request only"


def test_no_delay_is_paid_for_a_cache_hit(cache):
    cache.mkdir(parents=True)
    (cache / "1.html").write_text("<p>cached</p>", encoding="utf-8")
    clock = FakeClock()

    make(FakeSession(), cache, delay=1.5, sleep=clock).fetch(
        "http://example.com/1", number=1
    )

    assert clock.slept == []
