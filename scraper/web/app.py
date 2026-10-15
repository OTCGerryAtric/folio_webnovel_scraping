"""Folio's web server: the JSON API over the books, the event stream, and
the built front end.

Every book in a URL is found by its exact folder name among the books, and
every file by its exact name among the book's built files, so no request
can reach anything else on disk.
"""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from scraper.book import BOOKS_DIR, Book, list_books, safe_folder_name
from scraper.bookpage import parse_book_page, site_phrase
from scraper.commands import add_book, book_fetcher
from scraper.fetch import fetch_page
from scraper.review import normalise
from scraper.stages import read_cleaned
from scraper.web.jobs import Busy, JobManager, read_activity
from scraper.web.library import SiteCache, chapter_map, ensure_cover, fetch_bytes, save_cover, summary
from scraper.web.settings import read_settings, write_raw, write_settings
from scraper.web.watermarks import review_rows, suggest_pattern, test_pattern

STATIC_DIR = Path(__file__).parent / "static"
KEY_COOKIE = "folio_key"
_LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_CHANGES = {"POST", "PUT", "PATCH", "DELETE"}
_MEDIA = {
    ".epub": "application/epub+zip",
    ".pdf": "application/pdf",
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}


class Invalid(ValueError):
    """Input the person should correct: answered with 422."""


class PreviewIn(BaseModel):
    url: str


class AddIn(BaseModel):
    url: str | None = None
    name: str | None = None
    url_template: str | None = None
    title: str | None = None
    download: bool = False


class JobIn(BaseModel):
    kind: str
    start: int | None = None
    end: int | None = None
    refresh: bool | None = None
    format: str = "epub"
    every: int | None = None


class SettingsIn(BaseModel):
    values: dict | None = None
    raw: str | None = None


class PatternIn(BaseModel):
    pattern: str


class SentenceIn(BaseModel):
    sentence: str


class SentencesIn(BaseModel):
    sentences: list[str]


def create_app(
    root=BOOKS_DIR,
    get_page=fetch_page,
    fetcher_factory=book_fetcher,
    get_bytes=fetch_bytes,
    lan_key: str | None = None,
    static_dir: Path = STATIC_DIR,
    allowed_hosts: list[str] | None = None,
) -> FastAPI:
    root = Path(root)
    app = FastAPI(title="Folio", docs_url=None, redoc_url=None, openapi_url=None)
    site = SiteCache(get_page)
    jobs = JobManager(root, get_page, fetcher_factory)
    app.state.jobs, app.state.site = jobs, site
    covers_tried: set[str] = set()

    # -- errors and access -------------------------------------------------

    def error(status: int, message: str) -> JSONResponse:
        return JSONResponse({"error": message}, status_code=status)

    @app.exception_handler(Invalid)
    async def _invalid(request, exc):
        return error(422, str(exc))

    @app.exception_handler(ValueError)
    async def _value(request, exc):
        return error(400, str(exc))

    @app.exception_handler(Busy)
    async def _busy(request, exc):
        return error(409, str(exc))

    @app.exception_handler(OSError)
    async def _os(request, exc):
        # On Windows, a file open in a reader cannot be replaced or deleted.
        return error(409, str(exc))

    @app.exception_handler(StarletteHTTPException)
    async def _http(request, exc):
        return error(exc.status_code, str(exc.detail))

    # Another web page open in the same browser must not drive Folio. Changes
    # from a different origin are refused, and with `allowed_hosts` a request
    # naming any other host is too - a site that points its own name at this
    # machine (DNS rebinding) would otherwise count as same-origin.
    @app.middleware("http")
    async def _same_origin_only(request: Request, call_next):
        if request.method in _CHANGES:
            origin = request.headers.get("origin")
            cross = request.headers.get("sec-fetch-site") == "cross-site"
            if cross or (origin and urlparse(origin).netloc != request.headers.get("host")):
                return error(403, "Changes can only come from Folio's own pages.")
        return await call_next(request)

    if allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    if lan_key:
        @app.middleware("http")
        async def _require_key(request: Request, call_next):
            host = request.client.host if request.client else ""
            given = request.query_params.get("key")
            allowed = host in _LOOPBACK or given == lan_key or request.cookies.get(KEY_COOKIE) == lan_key
            if not allowed and request.url.path.startswith("/api"):
                return error(401, "This Folio needs its access key. Open the link printed when it started.")
            response = await call_next(request)
            if given == lan_key:
                response.set_cookie(KEY_COOKIE, lan_key, httponly=True, samesite="strict",
                                    max_age=60 * 60 * 24 * 365)
            return response

    def find(name: str) -> Book:
        for book in list_books(root):
            if book.name == name:
                return book
        raise HTTPException(404, f"No book called {name!r}")

    def output(book: Book, name: str) -> Path:
        for path in book.outputs():
            if path.name == name:
                return path
        raise HTTPException(404, f"{book.name} has no built file called {name!r}")

    # Reading a long book's cleaned chapters and counting its sentences takes
    # seconds, so both are kept until the cleaned folder changes.
    cleaned_cache: dict[str, tuple] = {}
    review_cache: dict[tuple, list] = {}

    def stamp(book: Book) -> tuple:
        files = list(book.cleaned_dir.glob("*.md")) if book.cleaned_dir.is_dir() else []
        return len(files), max((f.stat().st_mtime_ns for f in files), default=0)

    def cleaned(book: Book):
        now = stamp(book)
        held = cleaned_cache.get(book.name)
        if held is None or held[0] != now:
            held = (now, read_cleaned(book))
            cleaned_cache[book.name] = held
        if not held[1]:
            raise ValueError(f"{book.name} has no cleaned chapters. Run clean first.")
        return held[1]

    def reviewed(book: Book, minimum: int, ignore: list[str]) -> list:
        pages = cleaned(book)
        key = (book.name, cleaned_cache[book.name][0], minimum, tuple(ignore))
        if key not in review_cache:
            review_cache.clear()  # only the latest view is worth keeping
            review_cache[key] = review_rows(pages, minimum, ignore)
        return review_cache[key]

    def with_job(data: dict) -> dict:
        running = jobs.running_for(data["name"])
        data["job"] = running.id if running else None
        return data

    # -- books -------------------------------------------------------------

    @app.get("/api/books")
    def books():
        result = []
        for book in list_books(root):
            data = with_job(summary(book, site))
            if data["ready"] and not data["has_cover"] and data["source"] and book.name not in covers_tried:
                covers_tried.add(book.name)
                threading.Thread(target=ensure_cover, args=(book, get_page, get_bytes), daemon=True).start()
            result.append(data)
        return result

    @app.post("/api/books/preview")
    def preview(body: PreviewIn):
        html = get_page(body.url)
        if html is None:
            raise ValueError(f"Could not fetch {body.url}")
        info = parse_book_page(html, body.url)
        name = safe_folder_name(info.title)
        return {
            "title": info.title, "author": info.author, "status": info.status,
            "updated": info.updated, "latest": info.latest, "url_template": info.url_template,
            "cover": info.cover, "site_phrase": site_phrase(body.url) is not None,
            # A folder without book.toml is one waiting to be set up, not a clash.
            "name": name, "exists": bool(name) and Book(root / name).has_config(),
        }

    @app.post("/api/books", status_code=201)
    def add(body: AddIn):
        book, info, _ = add_book(
            root, get_page, page_url=None if body.url_template else body.url,
            name=body.name, url_template=body.url_template, title=body.title,
        )
        if info and info.cover:
            save_cover(book, info.cover, get_bytes)
        if body.download:
            jobs.start(book.name, "download")
        return with_job(summary(book, site))

    @app.get("/api/books/{name}")
    def detail(name: str):
        book = find(name)
        data = with_job(summary(book, site))
        data["map"] = []
        if data["ready"]:
            data["map"] = chapter_map(book.raw_numbers(), book.cleaned_numbers(),
                                      book.settings().start, data["latest"])
        data["activity"] = read_activity(book)
        return data

    @app.get("/api/books/{name}/site")
    def check_site(name: str, fresh: bool = False):
        book = find(name)
        latest = site.check(book, book.settings(), fresh=fresh)
        return {"latest": latest, "summary": with_job(summary(book, site))}

    @app.get("/api/books/{name}/cover")
    def cover(name: str):
        path = find(name).cover_path
        if path is None:
            raise HTTPException(404, "No cover")
        return FileResponse(path, headers={"Cache-Control": "max-age=3600"})

    # -- jobs --------------------------------------------------------------

    @app.post("/api/books/{name}/jobs", status_code=202)
    def start_job(name: str, body: JobIn):
        book = find(name)
        params = body.model_dump(exclude={"kind"}, exclude_none=True)
        return jobs.start(book.name, body.kind, params).to_dict()

    @app.post("/api/update-all", status_code=202)
    def update_all():
        return [job.to_dict(log=False) for job in jobs.start_update_all()]

    @app.get("/api/jobs")
    def list_jobs():
        return [job.to_dict() for job in jobs.recent()]

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: str):
        try:
            return jobs.cancel(job_id).to_dict(log=False)
        except KeyError:
            raise HTTPException(404, "No such job") from None

    @app.get("/api/events")
    async def events(request: Request):
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=2000)

        def put(event):
            if not queue.full():
                queue.put_nowait(event)

        def listener(event):
            loop.call_soon_threadsafe(put, event)

        jobs.add_listener(listener)

        async def stream():
            try:
                yield "retry: 2000\n\n"
                while not await request.is_disconnected():
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15)
                    except asyncio.TimeoutError:
                        yield ": keep-alive\n\n"
                        continue
                    yield f"data: {json.dumps(event)}\n\n"
            finally:
                jobs.remove_listener(listener)

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # -- watermarks --------------------------------------------------------

    @app.get("/api/books/{name}/review")
    def review(name: str, min: int = 4):
        book = find(name)
        settings = book.settings()
        rows = reviewed(book, max(min, 2), settings.review_ignore)
        return {
            "chapters": len(cleaned(book)),
            "rows": rows,
            "phrases": settings.remove_phrases,
        }

    @app.post("/api/books/{name}/review/test")
    def try_pattern(name: str, body: PatternIn):
        pages = cleaned(find(name))
        try:
            return test_pattern(pages, body.pattern)
        except ValueError as exc:
            raise Invalid(str(exc)) from None

    @app.post("/api/books/{name}/review/phrase")
    def phrase(name: str, body: SentenceIn):
        find(name)
        try:
            return {"pattern": suggest_pattern(body.sentence)}
        except ValueError as exc:
            raise Invalid(str(exc)) from None

    @app.post("/api/books/{name}/review/ignore")
    def ignore(name: str, body: SentenceIn):
        book = find(name)
        current = book.settings().review_ignore
        key = normalise(body.sentence)
        if key and key not in current:
            write_settings(book, {"review_ignore": [*current, key]})
        return {"ignored": key}

    @app.post("/api/books/{name}/review/ignore-all")
    def ignore_all(name: str, body: SentencesIn):
        """Keep many sentences as the author's own, in one write."""
        book = find(name)
        current = book.settings().review_ignore
        keys = [k for k in dict.fromkeys(normalise(s) for s in body.sentences) if k and k not in current]
        if keys:
            write_settings(book, {"review_ignore": [*current, *keys]})
        return {"ignored": len(keys)}

    # -- settings and files ------------------------------------------------

    @app.get("/api/books/{name}/settings")
    def get_settings(name: str):
        book = find(name)
        if not book.has_config():
            raise HTTPException(404, f"{book.name} is not set up yet: add it from its book page to create its settings.")
        return read_settings(book)

    @app.put("/api/books/{name}/settings")
    def put_settings(name: str, body: SettingsIn):
        book = find(name)
        try:
            if body.raw is not None:
                write_raw(book, body.raw)
            else:
                write_settings(book, body.values or {})
        except ValueError as exc:
            raise Invalid(str(exc)) from None
        return read_settings(book)

    @app.get("/api/books/{name}/files/{file}")
    def download_file(name: str, file: str):
        path = output(find(name), file)
        return FileResponse(path, filename=path.name, media_type=_MEDIA.get(path.suffix.lower()))

    @app.delete("/api/books/{name}/files/{file}", status_code=204)
    def delete_file(name: str, file: str):
        output(find(name), file).unlink()
        return Response(status_code=204)

    # -- the front end -----------------------------------------------------

    if (static_dir / "index.html").exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    else:
        @app.get("/", response_class=HTMLResponse)
        def not_built():
            return (
                "<!doctype html><title>Folio</title><h1>Folio</h1>"
                "<p>The front end has not been built. Run <code>npm install</code> "
                "and <code>npm run build</code> in <code>web/</code>.</p>"
            )

    return app
