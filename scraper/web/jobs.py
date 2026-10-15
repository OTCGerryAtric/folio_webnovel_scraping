"""Background jobs for the web app: one at a time per book, with every
line of output and every step of progress sent to whoever is listening."""

from __future__ import annotations

import json
import threading
import time
import traceback
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from scraper.book import Book, list_books
from scraper.web.tasks import RUNNERS, Context

_LOG_LINES = 500
_KEEP_ACTIVITY = 100
_KEEP_JOBS = 50
# Cleaning reports every page; a browser needs a few updates a second, not thousands.
_PROGRESS_EVERY = 0.1


class Busy(Exception):
    """The book already has a job running."""


@dataclass
class Job:
    book: str
    kind: str
    params: dict
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = "queued"
    created: float = field(default_factory=time.time)
    started: float | None = None
    finished: float | None = None
    progress: dict | None = None
    summary: dict = field(default_factory=dict)
    error: str | None = None
    log: deque = field(default_factory=lambda: deque(maxlen=_LOG_LINES))
    stop: threading.Event = field(default_factory=threading.Event)
    done: threading.Event = field(default_factory=threading.Event)

    @property
    def active(self) -> bool:
        return self.status in ("queued", "running")

    def to_dict(self, log: bool = True) -> dict:
        data = {k: getattr(self, k) for k in (
            "id", "book", "kind", "params", "status", "created", "started",
            "finished", "progress", "summary", "error")}
        if log:
            data["log"] = list(self.log)
        return data


class JobManager:
    def __init__(self, root, get_page, fetcher_factory):
        self.root = Path(root)
        self.get_page, self.fetcher_factory = get_page, fetcher_factory
        self._jobs: dict[str, Job] = {}
        self._listeners: list = []
        self._lock = threading.Lock()
        self._queue_lock = threading.Lock()  # update-all visits one book at a time

    # -- listeners ---------------------------------------------------------

    def add_listener(self, listener) -> None:
        with self._lock:
            self._listeners.append(listener)

    def remove_listener(self, listener) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def _emit(self, event: dict) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(event)
            except Exception:  # a broken listener must not break the job
                pass

    # -- starting and stopping ---------------------------------------------

    def start(self, book_name: str, kind: str, params: dict | None = None) -> Job:
        job = self._create(book_name, kind, params)
        threading.Thread(target=self._run, args=(job,), daemon=True).start()
        return job

    def start_update_all(self) -> list[Job]:
        """Queue an update for every book with a source page, run one after another."""
        jobs = []
        for book in list_books(self.root):
            try:
                if not book.settings().source:
                    continue
                jobs.append(self._create(book.name, "update", {}))
            except (ValueError, Busy):
                continue

        def run_all():
            for job in jobs:
                with self._queue_lock:
                    if job.stop.is_set():
                        self._finish(job, "cancelled")
                    else:
                        self._run(job)

        threading.Thread(target=run_all, daemon=True).start()
        return jobs

    def cancel(self, job_id: str) -> Job:
        job = self.get(job_id)
        job.stop.set()
        return job

    def get(self, job_id: str) -> Job:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job

    def recent(self) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created, reverse=True)

    def running_for(self, book_name: str) -> Job | None:
        with self._lock:
            return next((j for j in self._jobs.values() if j.book == book_name and j.active), None)

    def wait(self, job_id: str, timeout: float = 10.0) -> Job:
        job = self.get(job_id)
        job.done.wait(timeout)
        return job

    # -- running -----------------------------------------------------------

    def _create(self, book_name: str, kind: str, params: dict | None) -> Job:
        if kind not in RUNNERS:
            raise ValueError(f"Unknown job {kind!r}. Use one of: {', '.join(RUNNERS)}")
        self._book(book_name)
        with self._lock:
            busy = next((j for j in self._jobs.values() if j.book == book_name and j.active), None)
            if busy is not None:
                raise Busy(f"{book_name} is already busy with {busy.kind}.")
            job = Job(book=book_name, kind=kind, params=dict(params or {}))
            self._jobs[job.id] = job
            finished = [j for j in sorted(self._jobs.values(), key=lambda j: j.created) if j.done.is_set()]
            for old in finished[:max(len(self._jobs) - _KEEP_JOBS, 0)]:
                del self._jobs[old.id]
        self._emit({"type": "job", "job": job.to_dict(log=False)})
        return job

    def _book(self, name: str) -> Book:
        for book in list_books(self.root):
            if book.name == name:
                return book
        raise ValueError(f"No book called {name!r}")

    def _run(self, job: Job) -> None:
        job.status, job.started = "running", time.time()
        self._emit({"type": "job", "job": job.to_dict(log=False)})
        last = [0.0]

        def report(line: str) -> None:
            job.log.append(line)
            self._emit({"type": "log", "job": job.id, "book": job.book, "line": line})

        def progress(done: int, total: int | None, label: str) -> None:
            job.progress = {"done": done, "total": total, "label": label}
            if label == "Cleaning" and total is not None and done < total:
                now = time.monotonic()
                if now - last[0] < _PROGRESS_EVERY:
                    return
                last[0] = now
            self._emit({"type": "progress", "job": job.id, "book": job.book, "progress": job.progress})

        ctx = Context(report=report, progress=progress, should_stop=job.stop.is_set,
                      get_page=self.get_page, fetcher_factory=self.fetcher_factory)
        try:
            job.summary = RUNNERS[job.kind](self._book(job.book), job.params, ctx) or {}
            self._finish(job, "cancelled" if job.stop.is_set() else "done")
        except (ValueError, OSError) as exc:
            # OSError: on Windows, an epub open in a reader cannot be replaced.
            job.error = str(exc)
            report(f"error: {exc}")
            self._finish(job, "error")
        except Exception as exc:  # report the unexpected rather than lose it in a thread
            job.error = f"Unexpected error: {exc}"
            for line in traceback.format_exc().splitlines():
                job.log.append(line)
            self._finish(job, "error")

    def _finish(self, job: Job, status: str) -> None:
        job.status, job.finished = status, time.time()
        try:
            _append_activity(self._book(job.book), job)
        except (ValueError, OSError):
            pass
        job.done.set()
        self._emit({"type": "job", "job": job.to_dict(log=False)})


def read_activity(book: Book, limit: int = 20) -> list[dict]:
    """The book's finished jobs, newest first."""
    path = book.activity_path
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(records))[:limit]


def _append_activity(book: Book, job: Job) -> None:
    record = {k: v for k, v in job.to_dict(log=False).items() if k != "progress"}
    path = book.activity_path
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [*lines, json.dumps(record)][-_KEEP_ACTIVITY:]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
