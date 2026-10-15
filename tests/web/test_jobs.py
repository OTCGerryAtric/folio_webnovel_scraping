"""Tests for background jobs. The fetcher and site are stubbed."""
import threading

import pytest

from scraper.book import Book
from scraper.fetch import FetchResult
from scraper.web.jobs import Busy, JobManager, read_activity

CHAPTER = (
    "<html><head><title>T</title></head><body><div id='c'>"
    "<p>Chapter {n} has a good long story sentence in it.</p></div></body></html>"
)
PAGE = (
    '<html><head><meta property="og:novel:novel_name" content="B">'
    '<meta property="og:novel:read_url" content="http://x/1">'
    '<meta property="og:novel:lastest_chapter_url" content="http://x/{latest}"></head></html>'
)


class Fetcher:
    def __init__(self, book, gate=None):
        self.book, self.gate = book, gate

    def fetch(self, url, number):
        if self.gate is not None:
            self.gate.wait(5)
        html = CHAPTER.format(n=number)
        self.book.raw_path(number).write_text(html, encoding="utf-8")
        return FetchResult(number=number, url=url, html=html, from_cache=False)


def setup(tmp_path, latest=3, gate=None):
    book = Book(tmp_path / "B")
    book.create({"title": "B", "url_template": "http://x/{n}", "source": "http://x/book",
                 "content_selector": "#c"})
    manager = JobManager(tmp_path, {"http://x/book": PAGE.format(latest=latest)}.get,
                         lambda settings: Fetcher(book, gate))
    events = []
    manager.add_listener(events.append)
    return book, manager, events


def test_update_downloads_cleans_and_builds(tmp_path):
    book, manager, events = setup(tmp_path)

    job = manager.wait(manager.start("B", "update", {"format": "md"}).id)

    assert job.status == "done"
    assert job.summary["fetched"] == 3 and job.summary["files"] == ["B 1-3.md"]
    kinds = [e["type"] for e in events]
    assert kinds[0] == "job" and "progress" in kinds and "log" in kinds and kinds[-1] == "job"
    chapters = [e["progress"] for e in events
                if e["type"] == "progress" and e["progress"]["label"].startswith("Chapter")]
    assert chapters[-1]["done"] == 3 and chapters[-1]["total"] == 3


def test_a_second_job_on_the_same_book_is_refused(tmp_path):
    gate = threading.Event()
    book, manager, _ = setup(tmp_path, gate=gate)
    first = manager.start("B", "download")

    with pytest.raises(Busy):
        manager.start("B", "clean")

    gate.set()
    assert manager.wait(first.id).status == "done"


def test_cancel_keeps_what_was_fetched_and_the_next_run_carries_on(tmp_path):
    gate = threading.Event()
    book, manager, events = setup(tmp_path, latest=5, gate=gate)
    job = manager.start("B", "download")

    def stop_after_two(event):
        if event["type"] == "progress" and event["progress"]["done"] == 2:
            manager.cancel(job.id)
    manager.add_listener(stop_after_two)
    gate.set()
    job = manager.wait(job.id)

    assert job.status == "cancelled"
    assert book.raw_numbers() == [1, 2]
    again = manager.wait(manager.start("B", "download").id)
    assert again.summary["fetched"] == 3
    assert book.raw_numbers() == [1, 2, 3, 4, 5]


def test_errors_end_the_job_with_the_message(tmp_path):
    book, manager, _ = setup(tmp_path)

    job = manager.wait(manager.start("B", "build").id)

    assert job.status == "error" and "no cleaned chapters" in job.error


def test_finished_jobs_are_recorded_in_the_activity_file(tmp_path):
    book, manager, _ = setup(tmp_path)
    manager.wait(manager.start("B", "download").id)
    manager.wait(manager.start("B", "clean").id)

    activity = read_activity(book)

    assert [a["kind"] for a in activity] == ["clean", "download"]
    assert activity[0]["status"] == "done"


def test_unknown_books_and_kinds_are_refused(tmp_path):
    _, manager, _ = setup(tmp_path)

    with pytest.raises(ValueError, match="No book"):
        manager.start("Nope", "clean")
    with pytest.raises(ValueError, match="Unknown job"):
        manager.start("B", "explode")


def test_a_stopped_update_still_cleans_and_builds_what_it_fetched(tmp_path):
    """As Ctrl-C does in the CLI, so those chapters reach a file."""
    gate = threading.Event()
    book, manager, _ = setup(tmp_path, latest=5, gate=gate)
    job = manager.start("B", "update", {"format": "md"})

    def stop_after_two(event):
        if event["type"] == "progress" and event["progress"]["label"].startswith("Chapter") and event["progress"]["done"] == 2:
            manager.cancel(job.id)
    manager.add_listener(stop_after_two)
    gate.set()
    job = manager.wait(job.id)

    assert job.summary["fetched"] == 2
    assert job.summary["files"] == ["B 1-2.md"]
    assert book.cleaned_numbers() == [1, 2]
