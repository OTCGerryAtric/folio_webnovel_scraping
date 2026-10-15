"""What each kind of job does: the same steps the CLI runs, reported as
they happen."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from scraper.book import Book
from scraper.commands import build_files, clean_and_report, fetch_new
from scraper.stages import build


@dataclass
class Context:
    report: Callable[[str], None]
    progress: Callable[[int, "int | None", str], None]
    should_stop: Callable[[], bool]
    get_page: Callable
    fetcher_factory: Callable


def _fetch(book: Book, settings, ctx: Context) -> list[int]:
    held = set() if settings.refresh else set(book.raw_numbers())
    state = {"count": 0, "total": None, "end": object()}

    def on_chapter(number, end, outcome):
        state["count"] += 1
        if end != state["end"]:
            state["end"] = end
            state["total"] = None if end is None else len(
                [n for n in range(settings.start, end + 1, settings.step) if n not in held]
            )
        ctx.progress(state["count"], state["total"], f"Chapter {number}: {outcome}")

    return fetch_new(book, settings, ctx.fetcher_factory, ctx.get_page, ctx.report,
                     progress=on_chapter, should_stop=ctx.should_stop)


def _clean(book: Book, settings, ctx: Context):
    return clean_and_report(book, settings, ctx.report,
                            progress=lambda done, total: ctx.progress(done, total, "Cleaning"))


def run_download(book: Book, params: dict, ctx: Context) -> dict:
    settings = book.settings(start=params.get("start"), end=params.get("end"),
                             refresh=params.get("refresh") or None)
    return {"fetched": len(_fetch(book, settings, ctx))}


def run_clean(book: Book, params: dict, ctx: Context) -> dict:
    result = _clean(book, book.settings(), ctx)
    return {"cleaned": len(result.pages), "skipped": len(result.skipped)}


def run_build(book: Book, params: dict, ctx: Context) -> dict:
    settings = book.settings(build_every=params.get("every"))
    ctx.progress(0, None, "Building")
    paths = build_files(book, settings, fmt=params.get("format") or "epub",
                        start=params.get("start"), end=params.get("end"))
    for path in paths:
        ctx.report(f"Wrote {path.name}")
    return {"files": [p.name for p in paths]}


def run_update(book: Book, params: dict, ctx: Context) -> dict:
    settings = book.settings()
    fetched = _fetch(book, settings, ctx)
    if not fetched:
        ctx.report("Up to date: no new chapters.")
        return {"fetched": 0, "files": []}
    if ctx.should_stop():
        return {"fetched": len(fetched), "files": []}
    result = _clean(book, settings, ctx)
    path = build(book, settings, fmt=params.get("format") or "epub",
                 start=min(fetched), end=max(fetched))
    ctx.report(f"Wrote {len(fetched)} new chapter(s) to {path.name}")
    return {"fetched": len(fetched), "cleaned": len(result.pages), "files": [path.name]}


RUNNERS = {"download": run_download, "clean": run_clean, "build": run_build, "update": run_update}
