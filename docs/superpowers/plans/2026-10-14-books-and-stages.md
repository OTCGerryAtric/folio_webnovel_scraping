# Books and Stages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the book the unit of work: each book in its own folder under `books/`, added from its page on the source site, and processed in separate download, clean and build stages driven by `scrape.py` subcommands.

**Architecture:** New pure modules do the new text work (`bookpage` reads a book page, `phrases` removes watermark sentences, `titles` tidies chapter titles, `review` finds repeated sentences). `book` owns a book folder's paths and settings. `stages` runs download / clean / build over a `Book`, reusing the existing `Fetcher`, `extract_page`, `clean_pages`, `trim_overlap` and `write_document` unchanged. `commands` parses the subcommands and does the reporting; `scrape.py` hands off to it when the first argument is a command name, so the existing flag mode is untouched.

**Tech Stack:** Python 3.11+ (stdlib `tomllib`), requests, BeautifulSoup + lxml, EbookLib, reportlab, pytest.

**Spec:** `docs/superpowers/specs/2026-10-14-books-and-stages-design.md`

## Global Constraints

- No test touches the network. Network access is injected (`fetcher_factory`, `get_page`) and stubbed in tests.
- Book folder layout is exactly: `books/<name>/book.toml`, `books/<name>/01 Raw/`, `books/<name>/02 Cleaned/`, `books/<name>/03 Output/`.
- Chapter files are named `f"{number:04d}{suffix}"` - `0001.html`, `0001.md`, `12345.html`.
- The whole of `books/` is git-ignored (already done in `.gitignore`).
- The existing flag mode (`python scrape.py --url ... --out ...`) keeps working, and its 184 existing tests keep passing.
- Console report text that echoes page content is made ASCII-safe (a Windows console in a legacy code page raises on characters it cannot encode).
- Run tests with `.\.venv\Scripts\python.exe -m pytest` from the project root (Git Bash: `.venv/Scripts/python.exe -m pytest`).
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. A site that answers a missing chapter with a normal page saying "chapter not found" (HTTP 200) - download must count it as a miss and not keep the file. Test in Task 7.
2. A book title containing characters Windows forbids in folder names (`Re:Zero`, `What?`) - `add` must still make a folder. Test in Task 9.
3. A watermark glued to the end of a story sentence, in odd capitalisation (`... he ran. Read more at FreeWebNovel.Com`) - only the watermark sentence goes; the story sentence stays. Test in Task 4.
4. Rules change so a chapter disappears, or a raw page is deleted - the next clean must not leave a stale `.md` behind that `build` would then include. Test in Task 8.
5. A shortened or wrongly-cased book name on the command line (`weakest`, `WEAKEST BEAST`) and an ambiguous one - found, or a clear error listing the books. Test in Task 3.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `scraper/fetch.py` (modify) | page-file naming becomes a parameter; `fetch_url` for one uncached page; `fetch_page(url)` helper |
| `scraper/run.py` (modify) | `build_fetcher` passes a file-name function through |
| `scraper/config.py` (modify) | new keys `author`, `source`, `remove_phrases`; `build_settings(..., require_out=False)` |
| `scraper/book.py` (new) | a book folder: paths, finding by name, writing/reading `book.toml`, which chapters each stage holds, range descriptions |
| `scraper/bookpage.py` (new, pure) | `og:novel:*` meta tags into a `BookInfo`; URL template; site-name phrase |
| `scraper/phrases.py` (new, pure) | sentence-level phrase removal |
| `scraper/titles.py` (new, pure) | chapter title tidying |
| `scraper/review.py` (new, pure) | repeated-sentence report |
| `scraper/stages.py` (new) | `download`, `clean`, `read_cleaned`, `build`, `site_latest` |
| `scraper/reporting.py` (new) | removal / trim / emptied-page report lines, moved out of `scrape.py` so `commands` can share them |
| `scraper/commands.py` (new) | subcommand parsing and handlers: add, books, status, download, clean, review, build, update |
| `scrape.py` (modify) | hand off to `commands` when the first argument is a command |
| `README.md` (modify) | document books and commands |

---

### Task 1: Fetcher file naming and single-page fetch

**Files:**
- Modify: `scraper/fetch.py`
- Modify: `scraper/run.py:16-24`
- Test: `tests/test_fetch.py`

**Interfaces:**
- Produces: `Fetcher(..., file_name: Callable[[int], str] | None = None)` - default keeps `f"{n}.html"`; `Fetcher.fetch_url(url: str) -> str | None` (network only, no cache, same retries); `fetch_page(url: str) -> str | None`; `build_fetcher(settings, file_name=None) -> Fetcher`.

- [ ] **Step 1: Write the failing tests** - append to `tests/test_fetch.py`:

```python
# --- naming and single pages --------------------------------------------------


def test_cache_file_naming_can_be_chosen(tmp_path):
    session = FakeSession(FakeResponse(text="<p>saved</p>"))
    fetcher = Fetcher(
        tmp_path, session=session, sleep=FakeClock(),
        file_name=lambda number: f"{number:04d}.html",
    )

    fetcher.fetch("http://x/7", number=7)

    assert (tmp_path / "0007.html").read_text(encoding="utf-8") == "<p>saved</p>"
    assert not (tmp_path / "7.html").exists()


def test_fetch_url_returns_the_page_without_caching_it(tmp_path):
    session = FakeSession(FakeResponse(text="<p>book page</p>"))
    fetcher = Fetcher(tmp_path, session=session, sleep=FakeClock())

    assert fetcher.fetch_url("http://x/book") == "<p>book page</p>"
    assert list(tmp_path.iterdir()) == []


def test_fetch_url_gives_none_for_a_missing_page(tmp_path):
    fetcher = Fetcher(tmp_path, session=FakeSession(FakeResponse(status_code=404)), sleep=FakeClock())

    assert fetcher.fetch_url("http://x/gone") is None
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fetch.py -k "naming or fetch_url" -v`
Expected: FAIL - `TypeError: ... unexpected keyword argument 'file_name'` and `AttributeError: 'Fetcher' object has no attribute 'fetch_url'`.

- [ ] **Step 3: Implement** - in `scraper/fetch.py`:

Add to `__init__`'s parameters, after `sleep=time.sleep,`:

```python
        file_name=None,
```

and at the end of `__init__`:

```python
        self._file_name = file_name or (lambda number: f"{number}.html")
```

Add to the public section, after `fetch`:

```python
    def fetch_url(self, url: str) -> str | None:
        """Fetch one page that is not part of the numbered run. Never cached."""
        return self._fetch_over_network(url)
```

Change `_cache_path`:

```python
    def _cache_path(self, number: int) -> Path:
        return self.cache_dir / self._file_name(number)
```

Add at the end of the module:

```python
def fetch_page(url: str) -> str | None:
    """Fetch a single page, such as a book's main page, politely and uncached."""
    return Fetcher(cache_dir=Path(), delay=0).fetch_url(url)
```

In `scraper/run.py` replace `build_fetcher` with:

```python
def build_fetcher(settings: Settings, file_name=None) -> Fetcher:
    return Fetcher(
        cache_dir=settings.cache_path,
        delay=settings.delay,
        max_retries=settings.max_retries,
        backoff=settings.backoff,
        refresh=settings.refresh,
        timeout=settings.timeout,
        file_name=file_name,
    )
```

- [ ] **Step 4: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest`
Expected: all pass (184 existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add scraper/fetch.py scraper/run.py tests/test_fetch.py
git commit -m "Let the fetcher name its files and fetch a single page"
```

---

### Task 2: Settings for books

**Files:**
- Modify: `scraper/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings.author: str | None`, `Settings.source: str | None`, `Settings.remove_phrases: list[str]`; these are valid keys in a TOML file; `build_settings(args, config=None, require_out=True) -> Settings`.

- [ ] **Step 1: Write the failing tests** - append to `tests/test_config.py` (it already imports `build_settings` and `pytest`; add `from scraper.config import load_site_config` if not present):

```python
# --- book settings ----------------------------------------------------------


def test_book_keys_are_accepted_from_a_file(tmp_path):
    path = tmp_path / "book.toml"
    path.write_text(
        'url_template = "http://x/{n}"\n'
        'author = "Dagzo"\n'
        'source = "http://x/book"\n'
        "remove_phrases = ['free\\s*web']\n",
        encoding="utf-8",
    )

    settings = build_settings({}, load_site_config(path), require_out=False)

    assert settings.author == "Dagzo"
    assert settings.source == "http://x/book"
    assert settings.remove_phrases == ["free\\s*web"]


def test_out_can_be_left_unset_when_not_required():
    settings = build_settings({"url_template": "http://x/{n}"}, require_out=False)

    assert settings.out is None


def test_out_is_still_required_by_default():
    with pytest.raises(ValueError, match="--out"):
        build_settings({"url_template": "http://x/{n}"})


def test_an_invalid_remove_phrase_is_reported_clearly():
    with pytest.raises(ValueError, match="remove phrase"):
        build_settings(
            {"url_template": "http://x/{n}", "remove_phrases": ["(unclosed"]},
            require_out=False,
        )
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_config.py -k "book_keys or out_can or out_is_still or remove_phrase" -v`
Expected: FAIL - unknown setting `author`, and `unexpected keyword argument 'require_out'`.

- [ ] **Step 3: Implement** - in `scraper/config.py`:

In `DEFAULTS`, after `"titles": None,` add:

```python
    "author": None,
    "source": None,
    "remove_phrases": [],
```

In `Settings`, after `titles: str | None = None` add:

```python
    author: str | None = None
    source: str | None = None
    remove_phrases: list[str] = field(default_factory=list)
```

Replace `build_settings`:

```python
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
```

Change `_validate`'s signature and its `out` check:

```python
def _validate(values: dict, require_out: bool = True) -> None:
```

```python
    if require_out and not values.get("out"):
        raise ValueError("No output path given. Pass --out, e.g. --out book.md")
```

After the `strip_patterns` loop in `_validate`, add:

```python
    for pattern in values.get("remove_phrases") or []:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"Invalid remove phrase {pattern!r}: {exc}") from exc
```

- [ ] **Step 4: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scraper/config.py tests/test_config.py
git commit -m "Add book settings: author, source, remove_phrases"
```

---

### Task 3: The book folder

**Files:**
- Create: `scraper/book.py`
- Test: `tests/test_book.py`

**Interfaces:**
- Consumes: `build_settings(args, config, require_out=False)`, `load_site_config(path)` from Task 2.
- Produces:
  - `BOOKS_DIR = Path("books")`
  - `chapter_file(number: int, suffix: str) -> str` - `chapter_file(7, ".md") == "0007.md"`
  - `raw_file_name(number: int) -> str` - `"0007.html"`
  - `safe_folder_name(name: str) -> str`
  - `describe_ranges(numbers) -> str` - `"1-3, 7"`, or `"none"`
  - `missing_numbers(numbers, start: int, end: int) -> list[int]`
  - `class Book(folder: Path)` with `.name`, `.config_path`, `.raw_dir`, `.cleaned_dir`, `.output_dir`, `.titles_path`, `.raw_path(n)`, `.cleaned_path(n)`, `.raw_numbers()`, `.cleaned_numbers()`, `.outputs()`, `.has_config()`, `.create(values: dict)`, `.settings(**overrides) -> Settings`
  - `list_books(root=BOOKS_DIR) -> list[Book]`
  - `find_book(name: str, root=BOOKS_DIR) -> Book`

- [ ] **Step 1: Write the failing tests** - create `tests/test_book.py`:

```python
"""Tests for a book's folder: paths, finding it by name, its settings."""
import pytest

from scraper.book import (
    Book,
    chapter_file,
    describe_ranges,
    find_book,
    list_books,
    missing_numbers,
    safe_folder_name,
)


def make_book(root, name, config='url_template = "http://x/{n}"\n'):
    book = Book(root / name)
    book.folder.mkdir(parents=True)
    if config is not None:
        book.config_path.write_text(config, encoding="utf-8")
    return book


# --- naming -----------------------------------------------------------------


def test_chapter_files_are_padded_to_four_digits():
    assert chapter_file(7, ".md") == "0007.md"
    assert chapter_file(1274, ".html") == "1274.html"
    assert chapter_file(12345, ".html") == "12345.html"


def test_folder_names_lose_characters_windows_forbids():
    assert safe_folder_name("Re:Zero - What? <Part 1>") == "ReZero - What Part 1"
    assert safe_folder_name("  Trailing dots...  ") == "Trailing dots"


def test_ranges_are_described_compactly():
    assert describe_ranges([1, 2, 3, 7, 9, 10]) == "1-3, 7, 9-10"
    assert describe_ranges([]) == "none"


def test_missing_numbers_are_the_gaps_in_a_span():
    assert missing_numbers([1, 2, 5], start=1, end=6) == [3, 4, 6]


# --- the folder -------------------------------------------------------------


def test_stage_folders_are_numbered(tmp_path):
    book = Book(tmp_path / "Weakest Beast Tamer")

    assert book.name == "Weakest Beast Tamer"
    assert book.raw_dir.name == "01 Raw"
    assert book.cleaned_dir.name == "02 Cleaned"
    assert book.output_dir.name == "03 Output"
    assert book.raw_path(3).name == "0003.html"
    assert book.cleaned_path(3).name == "0003.md"


def test_chapters_held_are_read_from_the_stage_folders(tmp_path):
    book = Book(tmp_path / "B")
    book.raw_dir.mkdir(parents=True)
    for name in ("0002.html", "0010.html", "notes.txt", "0003.md"):
        (book.raw_dir / name).write_text("x", encoding="utf-8")

    assert book.raw_numbers() == [2, 10]
    assert book.cleaned_numbers() == []


def test_create_writes_the_settings_and_the_stage_folders(tmp_path):
    book = Book(tmp_path / "B")

    book.create({"title": 'A "quoted" title', "url_template": "http://x/{n}",
                 "remove_phrases": [r"free[\W_]*web"], "author": None})

    assert book.raw_dir.is_dir() and book.cleaned_dir.is_dir() and book.output_dir.is_dir()
    settings = book.settings()
    assert settings.title == 'A "quoted" title'
    assert settings.remove_phrases == [r"free[\W_]*web"]
    assert settings.author is None


def test_create_uses_a_folder_made_by_hand(tmp_path):
    (tmp_path / "B" / "01 Raw").mkdir(parents=True)

    Book(tmp_path / "B").create({"url_template": "http://x/{n}"})

    assert (tmp_path / "B" / "book.toml").exists()


def test_create_refuses_to_overwrite_existing_settings(tmp_path):
    book = make_book(tmp_path, "B")

    with pytest.raises(ValueError, match="already has a book.toml"):
        book.create({"url_template": "http://y/{n}"})


def test_settings_read_from_raw_and_override_from_arguments(tmp_path):
    book = make_book(tmp_path, "B", 'url_template = "http://x/{n}"\ndelay = 2.0\n')

    settings = book.settings(delay=0.5, start=None)

    assert settings.delay == 0.5
    assert settings.start == 1
    assert settings.cache_path == book.raw_dir


def test_a_book_without_settings_says_how_to_add_them(tmp_path):
    book = make_book(tmp_path, "B", config=None)

    with pytest.raises(ValueError, match="scrape.py add"):
        book.settings()


# --- finding books ----------------------------------------------------------


def test_books_are_listed_by_folder(tmp_path):
    make_book(tmp_path, "Shadow Slave")
    make_book(tmp_path, "Weakest Beast Tamer")
    (tmp_path / "stray.txt").write_text("x", encoding="utf-8")

    assert [b.name for b in list_books(tmp_path)] == ["Shadow Slave", "Weakest Beast Tamer"]


def test_no_books_folder_means_no_books(tmp_path):
    assert list_books(tmp_path / "missing") == []


def test_a_book_is_found_by_the_start_of_its_name_in_any_case(tmp_path):
    make_book(tmp_path, "Shadow Slave")
    make_book(tmp_path, "Weakest Beast Tamer")

    assert find_book("weakest", tmp_path).name == "Weakest Beast Tamer"
    assert find_book("WEAKEST BEAST TAMER", tmp_path).name == "Weakest Beast Tamer"


def test_an_exact_name_wins_over_a_longer_one(tmp_path):
    make_book(tmp_path, "Dragons")
    make_book(tmp_path, "Dragons Two")

    assert find_book("dragons", tmp_path).name == "Dragons"


def test_an_ambiguous_name_lists_the_candidates(tmp_path):
    make_book(tmp_path, "Shadow Slave")
    make_book(tmp_path, "Shadow Realm")

    with pytest.raises(ValueError, match="Shadow Realm, Shadow Slave"):
        find_book("shadow", tmp_path)


def test_an_unknown_name_lists_the_books(tmp_path):
    make_book(tmp_path, "Shadow Slave")

    with pytest.raises(ValueError, match="Books: Shadow Slave"):
        find_book("dragons", tmp_path)
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_book.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'scraper.book'`.

- [ ] **Step 3: Implement** - create `scraper/book.py`:

```python
"""A book's folder: where its stages keep their files, and its settings.

    books/<name>/
      book.toml     settings
      01 Raw/       pages as the site sent them
      02 Cleaned/   cleaned chapters
      03 Output/    built documents

The folder name is the user's to choose; the full title lives in
`book.toml`. Stage folders are numbered so Explorer lists them in the
order the work flows.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from scraper.config import Settings, build_settings, load_site_config

BOOKS_DIR = Path("books")

CONFIG_FILE = "book.toml"
TITLES_FILE = "titles.json"
RAW_DIR = "01 Raw"
CLEANED_DIR = "02 Cleaned"
OUTPUT_DIR = "03 Output"

_FORBIDDEN_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_SPACES_RE = re.compile(r"\s+")


def chapter_file(number: int, suffix: str) -> str:
    """Padded so a folder of chapters sorts correctly in Explorer."""
    return f"{number:04d}{suffix}"


def raw_file_name(number: int) -> str:
    return chapter_file(number, ".html")


def safe_folder_name(name: str) -> str:
    """Drop what Windows will not allow in a folder name."""
    name = _SPACES_RE.sub(" ", _FORBIDDEN_RE.sub("", name))
    return name.strip(" .")


def describe_ranges(numbers) -> str:
    """`[1, 2, 3, 7]` reads as `1-3, 7`."""
    numbers = sorted(numbers)
    if not numbers:
        return "none"
    spans = []
    first = last = numbers[0]
    for number in numbers[1:]:
        if number == last + 1:
            last = number
            continue
        spans.append((first, last))
        first = last = number
    spans.append((first, last))
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in spans)


def missing_numbers(numbers, start: int, end: int) -> list[int]:
    held = set(numbers)
    return [n for n in range(start, end + 1) if n not in held]


class Book:
    def __init__(self, folder: Path | str):
        self.folder = Path(folder)

    def __repr__(self) -> str:
        return f"Book({self.folder!r})"

    @property
    def name(self) -> str:
        return self.folder.name

    @property
    def config_path(self) -> Path:
        return self.folder / CONFIG_FILE

    @property
    def titles_path(self) -> Path:
        return self.folder / TITLES_FILE

    @property
    def raw_dir(self) -> Path:
        return self.folder / RAW_DIR

    @property
    def cleaned_dir(self) -> Path:
        return self.folder / CLEANED_DIR

    @property
    def output_dir(self) -> Path:
        return self.folder / OUTPUT_DIR

    def raw_path(self, number: int) -> Path:
        return self.raw_dir / chapter_file(number, ".html")

    def cleaned_path(self, number: int) -> Path:
        return self.cleaned_dir / chapter_file(number, ".md")

    def raw_numbers(self) -> list[int]:
        return _numbers_in(self.raw_dir, ".html")

    def cleaned_numbers(self) -> list[int]:
        return _numbers_in(self.cleaned_dir, ".md")

    def outputs(self) -> list[Path]:
        if not self.output_dir.is_dir():
            return []
        return sorted(p for p in self.output_dir.iterdir() if p.is_file())

    def has_config(self) -> bool:
        return self.config_path.exists()

    def create(self, values: dict) -> None:
        """Write `book.toml` and make the stage folders.

        A folder made by hand is fine; settings already there are not
        overwritten.
        """
        if self.has_config():
            raise ValueError(f"{self.name} already has a book.toml: {self.config_path}")
        for folder in (self.raw_dir, self.cleaned_dir, self.output_dir):
            folder.mkdir(parents=True, exist_ok=True)
        lines = [f"{key} = {_toml_value(value)}" for key, value in values.items() if value is not None]
        self.config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def settings(self, **overrides) -> Settings:
        """This book's settings, with any non-None overrides on top.

        Pages always go to and come from the book's own raw folder.
        """
        if not self.has_config():
            raise ValueError(
                f"{self.name} has no book.toml yet. Create it with: "
                f'python scrape.py add <book page url> --name "{self.name}"'
            )
        args = {k: v for k, v in overrides.items() if v is not None}
        args["cache_dir"] = str(self.raw_dir)
        return build_settings(args, load_site_config(self.config_path), require_out=False)


def list_books(root: Path | str = BOOKS_DIR) -> list[Book]:
    root = Path(root)
    if not root.is_dir():
        return []
    return [
        Book(p) for p in sorted(root.iterdir(), key=lambda p: p.name.casefold())
        if p.is_dir() and not p.name.startswith(".")
    ]


def find_book(name: str, root: Path | str = BOOKS_DIR) -> Book:
    """Find a book by its folder name, or any unambiguous start of it, in any case."""
    books = list_books(root)
    wanted = name.casefold().strip()

    exact = [b for b in books if b.name.casefold() == wanted]
    if exact:
        return exact[0]

    matches = [b for b in books if b.name.casefold().startswith(wanted)]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise ValueError(f"{name!r} could mean: {', '.join(b.name for b in matches)}")

    known = ", ".join(b.name for b in books) or "none yet"
    raise ValueError(f"No book called {name!r}. Books: {known}")


def _numbers_in(folder: Path, suffix: str) -> list[int]:
    if not folder.is_dir():
        return []
    return sorted(int(p.stem) for p in folder.glob(f"*{suffix}") if p.stem.isdigit())


def _toml_value(value) -> str:
    """Enough TOML for a settings file. A JSON string is a valid TOML basic string."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    raise TypeError(f"Cannot write {value!r} to book.toml")
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_book.py -v`
Expected: all pass. Then `.venv/Scripts/python.exe -m pytest` - all pass.

- [ ] **Step 5: Commit**

```bash
git add scraper/book.py tests/test_book.py
git commit -m "Add the book folder"
```

---

### Task 4: Sentence-level phrase removal

**Files:**
- Create: `scraper/phrases.py`
- Test: `tests/test_phrases.py`

**Interfaces:**
- Consumes: `Page` from `scraper.extract`; `Removal(text, pages, reason)` from `scraper.boilerplate`.
- Produces: `remove_phrases(pages: list[Page], patterns) -> tuple[list[Page], list[Removal]]`. Patterns match case-insensitively.

- [ ] **Step 1: Write the failing tests** - create `tests/test_phrases.py`:

```python
"""Tests for removing watermark sentences while keeping the story around them."""
import pytest

from scraper.extract import Page
from scraper.phrases import remove_phrases

SITE = r"f[\W_]*r[\W_]*e[\W_]*e[\W_]*w[\W_]*e[\W_]*b[\W_]*n[\W_]*o[\W_]*v[\W_]*e[\W_]*l"


def page(body, number=1):
    return Page(number=number, title=f"Chapter {number}", body=body)


def test_a_watermark_on_its_own_goes_with_its_block():
    pages, _ = remove_phrases(
        [page("He ran.\n\nExplore more at freewebnovel\n\nShe followed.")], [SITE]
    )

    assert pages[0].body == "He ran.\n\nShe followed."


def test_a_watermark_glued_to_a_story_paragraph_takes_only_its_sentence():
    pages, _ = remove_phrases(
        [page("His fingers tensed. The phoenix rose. Read more at FreeWebNovel.Com")], [SITE]
    )

    assert pages[0].body == "His fingers tensed. The phoenix rose."


def test_spaced_and_capitalised_spellings_match():
    pages, _ = remove_phrases(
        [page("Story. Stay tuned to Free Web Novel! More story.")], [SITE]
    )

    assert pages[0].body == "Story. More story."


def test_hard_line_breaks_in_kept_text_survive():
    pages, _ = remove_phrases(
        [page("Line one.\nLine two. Visit freewebnovel.com")], [SITE]
    )

    assert pages[0].body == "Line one.\nLine two."


def test_pages_without_a_match_are_untouched():
    original = page("Nothing to see.\n\n\nOdd spacing kept.")

    pages, removals = remove_phrases([original], [SITE])

    assert pages[0] is original
    assert removals == []


def test_no_patterns_changes_nothing():
    original = page("Explore more at freewebnovel")

    pages, removals = remove_phrases([original], [])

    assert pages == [original]
    assert removals == []


def test_removals_count_sentences_and_pages():
    pages, removals = remove_phrases(
        [
            page("A. Explore more at freewebnovel", 1),
            page("Stay tuned to Freewebnovel. B. Find adventures on freewebnovel", 2),
            page("Clean.", 3),
        ],
        [SITE],
    )

    assert len(removals) == 1
    assert removals[0].pages == 2
    assert removals[0].text.startswith("3 sentence(s) matching")


def test_an_invalid_pattern_is_reported_clearly():
    with pytest.raises(ValueError, match="remove phrase"):
        remove_phrases([page("x")], ["(unclosed"])
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_phrases.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'scraper.phrases'`.

- [ ] **Step 3: Implement** - create `scraper/phrases.py`:

```python
"""Remove watermark sentences, keeping the story around them.

Sites splice their name into the text in ever-changing wording - "Explore
more at freewebnovel", "Stay connected with freewebnovel.com" - and often
onto the end of a real paragraph. Dropping the whole block, as
`boilerplate`'s patterns do, would take story text with it. So this works
a sentence at a time: a sentence matching any pattern goes, the rest of
its block stays, and a block left with nothing in it goes too.

Pure functions over a list of `Page`. No network, no filesystem.
"""

from __future__ import annotations

import dataclasses
import re

from scraper.boilerplate import Removal
from scraper.extract import Page

# Split after sentence-ending punctuation, keeping the whitespace so a hard
# line break between kept sentences survives.
_SPLIT_RE = re.compile(r'(?<=[.!?"”’…])(\s+)')


def remove_phrases(pages: list[Page], patterns) -> tuple[list[Page], list[Removal]]:
    """Drop every sentence matching one of `patterns`, case-insensitively."""
    compiled = _compile(patterns)
    if not compiled or not pages:
        return list(pages), []

    sentences = {p.pattern: 0 for p in compiled}
    on_pages = {p.pattern: 0 for p in compiled}
    cleaned = []

    for page in pages:
        hit_here: set[str] = set()
        blocks = []
        for block in page.body.split("\n\n"):
            text, hits = _clean_block(block, compiled)
            for pattern in hits:
                sentences[pattern] += 1
                hit_here.add(pattern)
            if text.strip():
                blocks.append(text)
        for pattern in hit_here:
            on_pages[pattern] += 1
        cleaned.append(dataclasses.replace(page, body="\n\n".join(blocks)) if hit_here else page)

    removals = [
        Removal(
            text=f"{sentences[pattern]} sentence(s) matching {pattern}",
            pages=on_pages[pattern],
            reason="phrase",
        )
        for pattern in sentences
        if sentences[pattern]
    ]
    removals.sort(key=lambda r: r.pages, reverse=True)
    return cleaned, removals


def _clean_block(block: str, compiled: list) -> tuple[str, list[str]]:
    parts = _SPLIT_RE.split(block)
    kept: list[tuple[str, str]] = []
    hits: list[str] = []
    for index in range(0, len(parts), 2):
        sentence = parts[index]
        hit = next((p for p in compiled if p.search(sentence)), None)
        if hit is None:
            kept.append((parts[index - 1] if index else "", sentence))
        else:
            hits.append(hit.pattern)
    if not hits:
        return block, []
    return "".join(sep + sentence for sep, sentence in kept).strip(), hits


def _compile(patterns) -> list:
    compiled = []
    for pattern in patterns or ():
        try:
            compiled.append(re.compile(pattern, re.IGNORECASE))
        except re.error as exc:
            raise ValueError(f"Invalid remove phrase {pattern!r}: {exc}") from exc
    return compiled
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_phrases.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scraper/phrases.py tests/test_phrases.py
git commit -m "Remove watermark sentences, keeping the story around them"
```

---

### Task 5: Book page and title tidying

**Files:**
- Create: `scraper/bookpage.py`, `scraper/titles.py`
- Test: `tests/test_bookpage.py`, `tests/test_titles.py`

**Interfaces:**
- Produces:
  - `BookInfo(title: str, author: str | None, url_template: str, latest: int | None, status: str | None, updated: str | None)`
  - `parse_book_page(html: str, page_url: str) -> BookInfo` - raises `ValueError` when the page has no `og:novel` name or read URL
  - `template_from_chapter_url(url: str) -> str`, `chapter_from_url(url: str | None) -> int | None`, `site_phrase(url: str) -> str`
  - `tidy_title(title: str | None, book_title: str | None = None) -> str | None`, `tidy_titles(pages: list[Page], book_title: str | None) -> list[Page]`

- [ ] **Step 1: Write the failing tests** - create `tests/test_bookpage.py`. The fixture repeats the real tags from freewebnovel's page for this book, as fetched on 2026-10-14:

```python
"""Tests for reading a book's details from its main page."""
import re

import pytest

from scraper.bookpage import (
    chapter_from_url,
    parse_book_page,
    site_phrase,
    template_from_chapter_url,
)

PAGE_URL = "https://freewebnovel.com/novel/weakest-beast-tamer-gets-all-sss-dragons"

BOOK_PAGE = """<html><head>
<meta property="og:novel:category" content="English Novel">
<meta property="og:novel:author" content="Dagzo">
<meta property="og:novel:novel_name" content="Weakest Beast Tamer Gets All SSS Dragons">
<meta property="og:novel:read_url" content="https://freewebnovel.com/novel/weakest-beast-tamer-gets-all-sss-dragons/chapter-1">
<meta property="og:novel:status" content="OnGoing">
<meta property="og:novel:update_time" content="2026-10-14 00:07:21">
<meta property="og:novel:lastest_chapter_name" content="Chapter 1274 - Taming the Old World - Shadow Dragons - Reinforcements - 7">
<meta property="og:novel:lastest_chapter_url" content="https://freewebnovel.com/novel/weakest-beast-tamer-gets-all-sss-dragons/chapter-1274">
</head><body><h1>Weakest Beast Tamer</h1></body></html>"""


def test_the_book_details_are_read_from_the_meta_tags():
    info = parse_book_page(BOOK_PAGE, PAGE_URL)

    assert info.title == "Weakest Beast Tamer Gets All SSS Dragons"
    assert info.author == "Dagzo"
    assert info.url_template == (
        "https://freewebnovel.com/novel/weakest-beast-tamer-gets-all-sss-dragons/chapter-{n}"
    )
    assert info.latest == 1274
    assert info.status == "OnGoing"
    assert info.updated == "2026-10-14 00:07:21"


def test_a_relative_read_url_is_resolved_against_the_page():
    html = BOOK_PAGE.replace(
        "https://freewebnovel.com/novel/weakest-beast-tamer-gets-all-sss-dragons/chapter-1\"",
        "/novel/weakest-beast-tamer-gets-all-sss-dragons/chapter-1\"",
    )

    assert parse_book_page(html, PAGE_URL).url_template.startswith("https://freewebnovel.com/")


def test_a_page_without_the_tags_says_what_to_do_instead():
    with pytest.raises(ValueError, match="--url"):
        parse_book_page("<html><head><title>x</title></head></html>", PAGE_URL)


def test_the_last_number_in_a_chapter_url_becomes_the_placeholder():
    assert template_from_chapter_url("https://s2.com/b/7/chapter-1") == "https://s2.com/b/7/chapter-{n}"


def test_a_chapter_url_without_a_number_is_rejected():
    with pytest.raises(ValueError, match="number"):
        template_from_chapter_url("https://site.com/book/start")


def test_the_chapter_number_is_read_from_a_url():
    assert chapter_from_url("https://x.com/b/chapter-3214") == 3214
    assert chapter_from_url(None) is None


def test_the_site_phrase_matches_the_ways_the_name_is_written():
    pattern = re.compile(site_phrase("https://www.freewebnovel.com/novel/x"), re.IGNORECASE)

    for text in ("freewebnovel", "Free Web Novel", "freewebnovel.com", "FreeWebNovel"):
        assert pattern.search(text), text
    assert not pattern.search("a free novel on the web")
```

Create `tests/test_titles.py`:

```python
"""Tests for tidying chapter titles."""
from scraper.extract import Page
from scraper.titles import tidy_title, tidy_titles

BOOK = "Weakest Beast Tamer Gets All SSS Dragons"


def test_the_full_decoration_is_removed():
    title = (
        "Weakest Beast Tamer Gets All SSS Dragons - Chapter 1264 - "
        "Taming the Old World - Shadow Dragons - 11 | Free Web Novel"
    )

    assert tidy_title(title, BOOK) == "Chapter 1264 - Taming the Old World - Shadow Dragons - 11"


def test_a_doubled_chapter_number_is_collapsed():
    assert tidy_title("Chapter 1 - 1 - Beast Tamer Ren Patinder") == "Chapter 1 - Beast Tamer Ren Patinder"
    assert tidy_title("Chapter 10 - 10 - Taming Fate") == "Chapter 10 - Taming Fate"


def test_a_number_that_only_starts_the_same_is_not_collapsed():
    assert tidy_title("Chapter 1 - 15 Swords") == "Chapter 1 - 15 Swords"


def test_the_book_title_is_matched_in_any_case():
    assert tidy_title("weakest beast tamer gets all sss dragons - Chapter 2", BOOK) == "Chapter 2"


def test_a_clean_title_is_left_alone():
    assert tidy_title("Chapter 1: Nightmare Begins", BOOK) == "Chapter 1: Nightmare Begins"


def test_a_title_that_is_only_the_book_title_is_kept():
    assert tidy_title(BOOK, BOOK) == BOOK


def test_no_title_stays_no_title():
    assert tidy_title(None, BOOK) is None


def test_every_page_is_tidied():
    pages = [Page(1, "Chapter 1 - 1 - A | Free Web Novel", "x"), Page(2, None, "y")]

    assert [p.title for p in tidy_titles(pages, BOOK)] == ["Chapter 1 - A", None]
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_bookpage.py tests/test_titles.py -v`
Expected: FAIL - `ModuleNotFoundError` for both modules.

- [ ] **Step 3: Implement** - create `scraper/bookpage.py`:

```python
"""Read a book's details from its main page on the source site.

Many novel sites publish them as `og:novel:*` meta tags: the name, the
author, where chapter 1 is, and the latest chapter. (The site spells it
`lastest_chapter_url`; the correct spelling is accepted too.)

Pure functions of HTML text. No network, no filesystem.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scraper.config import PLACEHOLDER

_LAST_NUMBER_RE = re.compile(r"\d+(?!.*\d)")


@dataclass(frozen=True)
class BookInfo:
    title: str
    author: str | None
    url_template: str
    latest: int | None
    status: str | None
    updated: str | None


def parse_book_page(html: str, page_url: str) -> BookInfo:
    soup = BeautifulSoup(html, "lxml")

    def meta(key: str) -> str | None:
        tag = soup.find("meta", attrs={"property": f"og:novel:{key}"})
        value = (tag.get("content") or "").strip() if tag else ""
        return value or None

    title, read_url = meta("novel_name"), meta("read_url")
    if not title or not read_url:
        raise ValueError(
            f"{page_url} does not list the book's details, so it cannot be "
            f"added from its page. Add it with --url (a chapter URL with {{n}} "
            f"for the number) and --title instead."
        )

    return BookInfo(
        title=title,
        author=meta("author"),
        url_template=template_from_chapter_url(urljoin(page_url, read_url)),
        latest=chapter_from_url(meta("lastest_chapter_url") or meta("latest_chapter_url")),
        status=meta("status"),
        updated=meta("update_time"),
    )


def template_from_chapter_url(url: str) -> str:
    """`.../chapter-1` becomes `.../chapter-{n}`: the last number is the chapter."""
    if not _LAST_NUMBER_RE.search(url):
        raise ValueError(f"No chapter number in {url!r}")
    return _LAST_NUMBER_RE.sub(PLACEHOLDER, url, count=1)


def chapter_from_url(url: str | None) -> int | None:
    match = _LAST_NUMBER_RE.search(url or "")
    return int(match.group()) if match else None


def site_phrase(url: str) -> str:
    """A pattern for the site's own name, however the watermark spaces it.

    `freewebnovel.com` gives a pattern matching "freewebnovel", "Free Web
    Novel" and "freewebnovel.com" alike.
    """
    host = (urlparse(url).hostname or "").removeprefix("www.")
    letters = [c for c in host.split(".")[0] if c.isalnum()]
    return r"[\W_]*".join(re.escape(c) for c in letters)
```

Create `scraper/titles.py`:

```python
"""Tidy chapter titles taken from a page's <title>.

A scraped title arrives wrapped in the book's name and the site's:

    <Book Title> - Chapter 1 - 1 - Beast Tamer Ren Patinder | Free Web Novel

Tidying leaves the author's own chapter name whole, however long:

    Chapter 1 - Beast Tamer Ren Patinder

Pure functions. No network, no filesystem.
"""

from __future__ import annotations

import dataclasses
import re

from scraper.extract import Page

_SEPARATORS = " -–—:|"
_SITE_SUFFIX_RE = re.compile(r"\s+\|\s+[^|]*$")
_DOUBLED_NUMBER_RE = re.compile(r"^(Chapter\s+(\d+))\s*[-:]\s*\2\s*[-:]\s*", re.IGNORECASE)


def tidy_title(title: str | None, book_title: str | None = None) -> str | None:
    if not title:
        return title
    text = title.strip()

    if book_title and text.casefold().startswith(book_title.casefold()):
        rest = text[len(book_title):].lstrip(_SEPARATORS)
        if rest:
            text = rest

    text = _SITE_SUFFIX_RE.sub("", text)
    text = _DOUBLED_NUMBER_RE.sub(r"\1 - ", text)
    return text.strip() or title.strip()


def tidy_titles(pages: list[Page], book_title: str | None) -> list[Page]:
    return [dataclasses.replace(p, title=tidy_title(p.title, book_title)) for p in pages]
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_bookpage.py tests/test_titles.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scraper/bookpage.py scraper/titles.py tests/test_bookpage.py tests/test_titles.py
git commit -m "Read a book from its page, and tidy chapter titles"
```

---

### Task 6: Repeated-sentence review

**Files:**
- Create: `scraper/review.py`
- Test: `tests/test_review.py`

**Interfaces:**
- Produces: `Repeat(text: str, chapters: int, first: int | None)`; `repeated_sentences(pages: list[Page], min_chapters: int = 4, limit: int = 60) -> list[Repeat]`, most chapters first.

- [ ] **Step 1: Write the failing tests** - create `tests/test_review.py`:

```python
"""Tests for the repeated-sentence report."""
from scraper.extract import Page
from scraper.review import repeated_sentences

NOTE = "Give it a power stone, please!"


def page(number, body):
    return Page(number=number, title=None, body=body)


def test_sentences_in_enough_chapters_are_listed_with_their_first_chapter():
    pages = [page(n, f"Story {n} goes on and on. {NOTE}") for n in range(3, 8)]

    repeats = repeated_sentences(pages, min_chapters=4)

    assert [(r.text, r.chapters, r.first) for r in repeats] == [(NOTE, 5, 3)]


def test_chapters_are_counted_not_occurrences():
    pages = [page(1, f"{NOTE}\n\n{NOTE}\n\n{NOTE}"), page(2, NOTE)]

    assert repeated_sentences(pages, min_chapters=3) == []
    assert repeated_sentences(pages, min_chapters=2)[0].chapters == 2


def test_differences_in_punctuation_and_case_still_match():
    pages = [page(1, "Give it a power stone, please!"), page(2, "give it a POWER stone please")]

    assert repeated_sentences(pages, min_chapters=2)[0].chapters == 2


def test_short_sentences_are_not_evidence():
    pages = [page(n, "He nodded.") for n in range(1, 10)]

    assert repeated_sentences(pages, min_chapters=2) == []


def test_the_most_repeated_come_first_and_the_list_is_capped():
    pages = [page(n, "Alpha sentence repeated often. " + ("Beta sentence here too." if n < 3 else ""))
             for n in range(1, 6)]

    repeats = repeated_sentences(pages, min_chapters=2, limit=1)

    assert [r.text for r in repeats] == ["Alpha sentence repeated often."]


def test_report_text_is_ascii_safe():
    pages = [page(n, "“It’s not enough at all…”") for n in range(1, 3)]

    text = repeated_sentences(pages, min_chapters=2)[0].text

    assert text == "\"It's not enough at all...\""
    assert text.isascii()
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_review.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'scraper.review'`.

- [ ] **Step 3: Implement** - create `scraper/review.py`:

```python
"""Find sentences that recur across many chapters.

Repetition alone cannot tell junk from an author's habits - "Ren shook his
head." recurs in 18 chapters of one book - so this is a report for the
user to read, not something that removes text. Anything unwanted goes into
the book's `remove_phrases`.

Pure functions over a list of `Page`. No network, no filesystem.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from scraper.extract import Page

# Shorter than this and a sentence recurs in any book by chance.
_MIN_LENGTH = 15

_SPLIT_RE = re.compile(r'(?<=[.!?"”’…])\s+')
_NOT_PLAIN_RE = re.compile(r"[^a-z0-9 ]+")
_WHITESPACE_RE = re.compile(r"\s+")
_TYPOGRAPHIC = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "…": "...", "–": "-", "—": "-",
})


@dataclass(frozen=True)
class Repeat:
    text: str
    chapters: int
    first: int | None


def repeated_sentences(pages: list[Page], min_chapters: int = 4, limit: int = 60) -> list[Repeat]:
    counts: Counter = Counter()
    first_seen: dict[str, tuple[str, int | None]] = {}

    for page in pages:
        keys = set()
        for block in page.body.split("\n\n"):
            for sentence in _SPLIT_RE.split(block):
                key = _normalise(sentence)
                if len(key) < _MIN_LENGTH:
                    continue
                keys.add(key)
                first_seen.setdefault(key, (sentence.strip(), page.number))
        counts.update(keys)

    repeats = [
        Repeat(text=_console_safe(first_seen[key][0]), chapters=count, first=first_seen[key][1])
        for key, count in counts.most_common()
        if count >= min_chapters
    ]
    return repeats[:limit]


def _normalise(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", _NOT_PLAIN_RE.sub(" ", text.lower())).strip()


def _console_safe(text: str) -> str:
    """Typographic punctuation to ASCII; anything else unprintable becomes '?'."""
    return text.translate(_TYPOGRAPHIC).encode("ascii", "replace").decode("ascii")
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_review.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scraper/review.py tests/test_review.py
git commit -m "Report sentences repeated across chapters"
```

---

### Task 7: Download stage

**Files:**
- Create: `scraper/stages.py`
- Test: `tests/test_stages.py`

**Interfaces:**
- Consumes: `Book` (Task 3), `Settings`, `extract_page`, `parse_book_page` (Task 5).
- Produces:
  - `download(book: Book, settings: Settings, fetcher, latest: int | None = None, log=None) -> list[int]` - numbers newly downloaded. `fetcher` has `fetch(url, number) -> FetchResult | None` and writes the raw file itself (the real `Fetcher` does, via its cache).
  - `site_latest(settings: Settings, get_page) -> int | None` - `get_page(url) -> str | None`.

- [ ] **Step 1: Write the failing tests** - create `tests/test_stages.py`:

```python
"""Tests for a book's stages, against a temporary book folder. No network."""
import pytest

from scraper.book import Book
from scraper.fetch import FetchResult
from scraper.stages import download, site_latest


def chapter(text, title="T"):
    return f"<html><head><title>{title}</title></head><body><div id='c'><p>{text}</p></div></body></html>"


NOT_FOUND = "<html><body><div id='c'></div><p>Chapter not found.</p></body></html>"


def make_book(tmp_path, extra=""):
    book = Book(tmp_path / "B")
    book.create({"title": "Book", "url_template": "http://x/{n}", "content_selector": "#c"})
    if extra:
        with book.config_path.open("a", encoding="utf-8") as handle:
            handle.write(extra)
    return book


class StubFetcher:
    """Serves canned HTML and writes it to the raw folder, as the real fetcher does."""

    def __init__(self, book, pages, interrupt_on=None):
        self.book, self.pages, self.interrupt_on = book, pages, interrupt_on
        self.asked = []

    def fetch(self, url, number):
        self.asked.append(number)
        if number == self.interrupt_on:
            raise KeyboardInterrupt
        html = self.pages.get(number)
        if html is None:
            return None
        path = self.book.raw_path(number)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        return FetchResult(number=number, url=url, html=html, from_cache=False)


# --- download ---------------------------------------------------------------


def test_download_fetches_up_to_the_latest_chapter(tmp_path):
    book = make_book(tmp_path)
    fetcher = StubFetcher(book, {n: chapter(n) for n in range(1, 4)})

    got = download(book, book.settings(), fetcher, latest=3)

    assert got == [1, 2, 3]
    assert book.raw_numbers() == [1, 2, 3]


def test_chapters_already_held_are_not_asked_for(tmp_path):
    book = make_book(tmp_path)
    book.raw_path(1).write_text(chapter("old"), encoding="utf-8")
    fetcher = StubFetcher(book, {n: chapter(n) for n in range(1, 4)})

    got = download(book, book.settings(), fetcher, latest=3)

    assert got == [2, 3]
    assert fetcher.asked == [2, 3]


def test_refresh_asks_for_held_chapters_again(tmp_path):
    book = make_book(tmp_path)
    book.raw_path(1).write_text(chapter("old"), encoding="utf-8")
    fetcher = StubFetcher(book, {1: chapter("new")})

    download(book, book.settings(refresh=True), fetcher, latest=1)

    assert fetcher.asked == [1]


def test_without_a_latest_chapter_it_stops_after_the_misses(tmp_path):
    book = make_book(tmp_path, "max_misses = 2\n")
    fetcher = StubFetcher(book, {1: chapter(1), 2: chapter(2)})

    got = download(book, book.settings(), fetcher)

    assert got == [1, 2]
    assert fetcher.asked == [1, 2, 3, 4]


def test_a_not_found_page_served_as_a_normal_page_is_a_miss_and_not_kept(tmp_path):
    book = make_book(tmp_path, "max_misses = 1\n")
    fetcher = StubFetcher(book, {1: chapter(1), 2: NOT_FOUND})

    got = download(book, book.settings(), fetcher)

    assert got == [1]
    assert book.raw_numbers() == [1]


def test_end_overrides_the_latest_chapter(tmp_path):
    book = make_book(tmp_path)
    fetcher = StubFetcher(book, {n: chapter(n) for n in range(1, 6)})

    got = download(book, book.settings(start=2, end=3), fetcher, latest=5)

    assert got == [2, 3]


def test_an_interrupted_download_keeps_what_it_has(tmp_path):
    book = make_book(tmp_path)
    fetcher = StubFetcher(book, {n: chapter(n) for n in range(1, 6)}, interrupt_on=3)
    lines = []

    got = download(book, book.settings(), fetcher, latest=5, log=lines.append)

    assert got == [1, 2]
    assert book.raw_numbers() == [1, 2]
    assert any("Interrupted" in line for line in lines)


# --- the site's latest chapter -----------------------------------------------

BOOK_PAGE = (
    '<meta property="og:novel:novel_name" content="Book">'
    '<meta property="og:novel:read_url" content="http://x/1">'
    '<meta property="og:novel:lastest_chapter_url" content="http://x/1274">'
)


def test_the_latest_chapter_comes_from_the_book_page(tmp_path):
    book = make_book(tmp_path, 'source = "http://x/book"\n')

    assert site_latest(book.settings(), {"http://x/book": BOOK_PAGE}.get) == 1274


def test_no_source_or_no_answer_means_no_latest_chapter(tmp_path):
    book = make_book(tmp_path)
    assert site_latest(book.settings(), lambda url: BOOK_PAGE) is None

    with_source = make_book(tmp_path / "other", 'source = "http://x/book"\n')
    assert site_latest(with_source.settings(), lambda url: None) is None
    assert site_latest(with_source.settings(), lambda url: "<html></html>") is None
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stages.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'scraper.stages'`.

- [ ] **Step 3: Implement** - create `scraper/stages.py`:

```python
"""A book's stages: download, clean, build.

Each works on a `Book` folder. Download is the only one that touches the
network; clean and build are local, so they can be re-run freely.
"""

from __future__ import annotations

from scraper.book import Book
from scraper.bookpage import parse_book_page
from scraper.config import Settings
from scraper.extract import extract_page


# --- download -----------------------------------------------------------------


def download(book: Book, settings: Settings, fetcher, latest: int | None = None, log=None) -> list[int]:
    """Fetch the chapters not yet in the raw folder. Returns the numbers fetched.

    With an end (`--end`, or the site's latest chapter) every number up to it
    is tried and gaps are skipped. Without one, the run stops after
    `max_misses` misses in a row.
    """
    report = log or (lambda message: None)
    held = set() if settings.refresh else set(book.raw_numbers())
    end = settings.end if settings.end is not None else latest
    fetched: list[int] = []
    misses = 0
    number = settings.start

    try:
        while end is None or number <= end:
            if number not in held:
                result = fetcher.fetch(settings.url_for(number), number=number)
                if result is None or _is_blank(result.html, settings):
                    if result is not None:
                        # A "not found" page served as a normal one: not a chapter.
                        book.raw_path(number).unlink(missing_ok=True)
                    misses += 1
                    report(f"  {number}: {'not found' if result is None else 'no text found'}")
                    if end is None and misses >= settings.max_misses:
                        report(f"Stopping: {misses} pages in a row came back empty.")
                        break
                else:
                    misses = 0
                    fetched.append(number)
                    report(f"  {number}{f'/{end}' if end else ''}: downloaded")
            number += settings.step
    except KeyboardInterrupt:
        report(f"\nInterrupted. Keeping the {len(fetched)} chapter(s) already downloaded.")

    return fetched


def site_latest(settings: Settings, get_page) -> int | None:
    """The newest chapter the site lists, or None if that cannot be found out."""
    if not settings.source:
        return None
    html = get_page(settings.source)
    if html is None:
        return None
    try:
        return parse_book_page(html, settings.source).latest
    except ValueError:
        return None


def _is_blank(html: str, settings: Settings) -> bool:
    return extract_page(
        html,
        content_selector=settings.content_selector,
        title_selector=settings.title_selector,
        remove_selectors=settings.remove_selectors,
    ).is_empty
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stages.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scraper/stages.py tests/test_stages.py
git commit -m "Add the download stage"
```

---

### Task 8: Clean and build stages

**Files:**
- Modify: `scraper/stages.py`
- Test: `tests/test_stages.py`

**Interfaces:**
- Consumes: `remove_phrases` (Task 4), `tidy_titles` (Task 5), `clean_pages`, `trim_overlap`, `load_titles`, `apply_titles`, `write_document`.
- Produces:
  - `CleanResult(pages: list[Page], removals: list[Removal], trims: list[Trim], retitled: int, skipped: list[int])`
  - `clean(book: Book, settings: Settings) -> CleanResult` - rewrites the whole cleaned folder
  - `read_cleaned(book: Book, start: int | None = None, end: int | None = None) -> list[Page]`
  - `build(book: Book, settings: Settings, fmt: str = "epub", start: int | None = None, end: int | None = None) -> Path`

- [ ] **Step 1: Write the failing tests** - in `tests/test_stages.py`, change the stages import to:

```python
from scraper.stages import build, clean, download, read_cleaned, site_latest
```

and append:

```python
# --- clean ------------------------------------------------------------------


def hold(book, chapters):
    """Put raw pages straight into the raw folder."""
    for number, html in chapters.items():
        book.raw_path(number).write_text(html, encoding="utf-8")


def test_clean_writes_one_file_per_chapter_with_its_title(tmp_path):
    book = make_book(tmp_path)
    hold(book, {1: chapter("One.", "Book - Chapter 1 - 1 - Start | Free Web Novel"),
                2: chapter("Two.", "Book - Chapter 2 - Next | Free Web Novel")})

    clean(book, book.settings())

    assert book.cleaned_numbers() == [1, 2]
    assert book.cleaned_path(1).read_text(encoding="utf-8") == "# Chapter 1 - Start\n\nOne.\n"


def test_clean_removes_phrases_and_reports_them(tmp_path):
    book = make_book(tmp_path, "remove_phrases = ['freewebnovel']\n")
    hold(book, {1: chapter("He ran. Read more at freewebnovel"), 2: chapter("Fine.")})

    result = clean(book, book.settings())

    assert read_cleaned(book)[0].body == "He ran."
    assert result.removals[0].pages == 1


def test_clean_drops_furniture_repeated_on_most_chapters(tmp_path):
    book = make_book(tmp_path)
    hold(book, {n: chapter(f"Story {n}.</p><p>Prev Chapter") for n in range(1, 5)})

    result = clean(book, book.settings())

    assert [p.body for p in read_cleaned(book)] == [f"Story {n}." for n in range(1, 5)]
    assert result.removals


def test_a_chapter_with_no_text_is_skipped_and_reported(tmp_path):
    book = make_book(tmp_path)
    hold(book, {1: chapter("One."), 2: NOT_FOUND})

    result = clean(book, book.settings())

    assert result.skipped == [2]
    assert book.cleaned_numbers() == [1]


def test_clean_leaves_no_stale_chapters_behind(tmp_path):
    book = make_book(tmp_path)
    hold(book, {1: chapter("One."), 2: chapter("Two.")})
    clean(book, book.settings())

    book.raw_path(2).unlink()
    clean(book, book.settings())

    assert book.cleaned_numbers() == [1]


def test_a_titles_file_in_the_book_folder_wins(tmp_path):
    book = make_book(tmp_path)
    hold(book, {1: chapter("One.", "Chapter 1 - Start")})
    book.titles_path.write_text('{"1": "Chapter 1 - The Real Start"}', encoding="utf-8")

    result = clean(book, book.settings())

    assert read_cleaned(book)[0].title == "Chapter 1 - The Real Start"
    assert result.retitled == 1


# --- build ------------------------------------------------------------------


def test_build_joins_the_cleaned_chapters_named_by_book_and_range(tmp_path):
    book = make_book(tmp_path)
    hold(book, {n: chapter(f"Text {n}.", f"Chapter {n}") for n in range(1, 4)})
    clean(book, book.settings())

    path = build(book, book.settings(), fmt="md")

    assert path == book.output_dir / "B 1-3.md"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Book\n")
    assert "## Chapter 2\n\nText 2." in text


def test_build_can_take_a_range(tmp_path):
    book = make_book(tmp_path)
    hold(book, {n: chapter(f"Text {n}.") for n in range(1, 5)})
    clean(book, book.settings())

    path = build(book, book.settings(), fmt="md", start=2, end=3)

    assert path.name == "B 2-3.md"
    assert "Text 1." not in path.read_text(encoding="utf-8")


def test_build_with_nothing_cleaned_says_to_clean_first(tmp_path):
    book = make_book(tmp_path)

    with pytest.raises(ValueError, match="clean"):
        build(book, book.settings())


def test_build_rejects_an_unknown_format(tmp_path):
    book = make_book(tmp_path)
    hold(book, {1: chapter("One.")})
    clean(book, book.settings())

    with pytest.raises(ValueError, match="Unsupported"):
        build(book, book.settings(), fmt="docx")
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stages.py -v`
Expected: FAIL - `ImportError: cannot import name 'build'`.

- [ ] **Step 3: Implement** - in `scraper/stages.py`, replace the imports with:

```python
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path

from scraper.assemble import write_document
from scraper.boilerplate import Removal, clean_pages
from scraper.book import Book
from scraper.bookpage import parse_book_page
from scraper.config import Settings
from scraper.extract import Page, extract_page
from scraper.overlap import Trim, trim_overlap
from scraper.phrases import remove_phrases
from scraper.retitle import apply_titles, load_titles
from scraper.titles import tidy_titles
```

and append:

```python
# --- clean --------------------------------------------------------------------


@dataclass(frozen=True)
class CleanResult:
    pages: list[Page]
    removals: list[Removal]
    trims: list[Trim]
    retitled: int
    skipped: list[int]


def clean(book: Book, settings: Settings) -> CleanResult:
    """Rebuild the cleaned folder from the raw one.

    Works over the whole book at once, because furniture is recognised by
    repeating across chapters and a recap by matching the chapter before.
    Everything in the cleaned folder is replaced, so a change of rules
    applies everywhere and nothing stale is left for build to pick up.
    """
    pages, skipped = [], []
    for number in book.raw_numbers():
        page = extract_page(
            book.raw_path(number).read_text(encoding="utf-8"),
            content_selector=settings.content_selector,
            title_selector=settings.title_selector,
            remove_selectors=settings.remove_selectors,
        )
        if page.is_empty:
            skipped.append(number)
            continue
        pages.append(dataclasses.replace(page, number=number))

    pages, phrase_removals = remove_phrases(pages, settings.remove_phrases)
    pages, furniture = clean_pages(
        pages,
        dedupe=settings.dedupe,
        threshold=settings.dedupe_threshold,
        patterns=settings.strip_patterns,
    )
    trims = []
    if settings.trim_overlap:
        pages, trims = trim_overlap(pages, window=settings.overlap_window)
    pages = tidy_titles(pages, settings.title)
    retitled = 0
    if book.titles_path.exists():
        pages, retitled = apply_titles(pages, load_titles(book.titles_path))

    _write_cleaned(book, pages)
    return CleanResult(pages, phrase_removals + furniture, trims, retitled, skipped)


def read_cleaned(book: Book, start: int | None = None, end: int | None = None) -> list[Page]:
    """Read cleaned chapters back. The first line of each is `# <title>`."""
    pages = []
    for number in book.cleaned_numbers():
        if (start is not None and number < start) or (end is not None and number > end):
            continue
        text = book.cleaned_path(number).read_text(encoding="utf-8")
        first, _, rest = text.partition("\n")
        if first.startswith("# "):
            title, body = first[2:].strip() or None, rest
        else:
            title, body = None, text
        pages.append(Page(number=number, title=title, body=body.strip("\n")))
    return pages


def _write_cleaned(book: Book, pages: list[Page]) -> None:
    book.cleaned_dir.mkdir(parents=True, exist_ok=True)
    for old in book.cleaned_dir.glob("*.md"):
        old.unlink()
    for page in pages:
        title = page.title or f"Chapter {page.number}"
        book.cleaned_path(page.number).write_text(f"# {title}\n\n{page.body}\n", encoding="utf-8")


# --- build --------------------------------------------------------------------


def build(
    book: Book,
    settings: Settings,
    fmt: str = "epub",
    start: int | None = None,
    end: int | None = None,
) -> Path:
    """Join cleaned chapters into `03 Output/<name> <first>-<last>.<fmt>`."""
    pages = read_cleaned(book, start, end)
    if not pages:
        span = "" if start is None and end is None else f" in {start or 1}-{end or 'end'}"
        raise ValueError(f"{book.name} has no cleaned chapters{span}. Run clean first.")
    path = book.output_dir / f"{book.name} {pages[0].number}-{pages[-1].number}.{fmt.lower().lstrip('.')}"
    return write_document(pages, path, title=settings.title or book.name)
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stages.py -v`
Expected: all pass. Then `.venv/Scripts/python.exe -m pytest` - all pass.

- [ ] **Step 5: Commit**

```bash
git add scraper/stages.py tests/test_stages.py
git commit -m "Add the clean and build stages"
```

---

### Task 9: Commands - add, books, status

**Files:**
- Create: `scraper/reporting.py`, `scraper/commands.py`
- Modify: `scrape.py`
- Test: `tests/test_commands.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `scraper/reporting.py`: `report_removals(removals, total, report)`, `report_trims(trims, report)`, `warn_if_emptied(pages, report)` - moved verbatim from `scrape.py`'s `_report_removals`, `_report_trims`, `_warn_if_emptied`.
  - `scraper/commands.py`: `COMMANDS: tuple[str, ...]`; `run_command(argv: list[str], fetcher_factory=book_fetcher, get_page=fetch_page, root=BOOKS_DIR, report=None) -> int` - returns 0 on success, 2 on a usage error (message printed as `error: ...`). `report` defaults to printing to stderr.
  - `scrape.main(argv)` hands off to `run_command(argv)` when `argv[0] in COMMANDS`.

- [ ] **Step 1: Move the report helpers.** Create `scraper/reporting.py`:

```python
"""Report lines for what cleaning removed. Text vanishing silently is how trust goes."""

from __future__ import annotations


def report_removals(removals, total: int, report) -> None:
    if not removals:
        return
    report(f"Removed {len(removals)} boilerplate block(s):")
    for removal in removals:
        report(f"  on {removal.pages}/{total} pages: {removal.text}")


def report_trims(trims, report) -> None:
    """Say which pages opened with a recap, and what went with it."""
    if not trims:
        return
    blocks = sum(trim.blocks for trim in trims)
    report(f"Trimmed {blocks} repeated block(s) from the start of {len(trims)} page(s):")
    for trim in trims:
        report(f"  page {trim.number}: {trim.text}")


def warn_if_emptied(pages, report) -> None:
    """An emptied page means the threshold was too aggressive. Say so."""
    emptied = [p.number for p in pages if p.is_empty]
    if emptied:
        report(
            f"warning: {len(emptied)} page(s) were left with no text "
            f"(first: {emptied[0]}). Try --dedupe-threshold with a higher "
            f"value, or --no-dedupe. Re-running costs nothing: the pages "
            f"are cached."
        )
```

In `scrape.py`, delete `_report_removals`, `_report_trims` and `_warn_if_emptied`, add
`from scraper.reporting import report_removals, report_trims, warn_if_emptied`, and change the three call sites in `main` to `report_removals(removals, collected, report)`, `report_trims(trims, report)`, `warn_if_emptied(pages, report)`.

Run: `.venv/Scripts/python.exe -m pytest` - Expected: all pass (behaviour unchanged).

- [ ] **Step 2: Write the failing tests** - create `tests/test_commands.py`:

```python
"""Tests for the book subcommands. Network access is stubbed throughout."""
import pytest

from scrape import main
from scraper.book import Book
from scraper.commands import run_command

PAGE_URL = "https://freewebnovel.com/novel/weakest-beast-tamer-gets-all-sss-dragons"

BOOK_PAGE = """<html><head>
<meta property="og:novel:author" content="Dagzo">
<meta property="og:novel:novel_name" content="Weakest Beast Tamer Gets All SSS Dragons">
<meta property="og:novel:read_url" content="https://freewebnovel.com/novel/weakest-beast-tamer-gets-all-sss-dragons/chapter-1">
<meta property="og:novel:status" content="OnGoing">
<meta property="og:novel:update_time" content="2026-10-14 00:07:21">
<meta property="og:novel:lastest_chapter_url" content="https://freewebnovel.com/novel/weakest-beast-tamer-gets-all-sss-dragons/chapter-1274">
</head></html>"""


def run(argv, root, pages=None, fetcher_factory=None):
    lines = []
    kwargs = {"get_page": (pages or {}).get, "root": root, "report": lines.append}
    if fetcher_factory is not None:
        kwargs["fetcher_factory"] = fetcher_factory
    code = run_command(argv, **kwargs)
    return code, "\n".join(lines)


# --- add --------------------------------------------------------------------


def test_add_creates_the_book_from_its_page(tmp_path):
    code, out = run(["add", PAGE_URL, "--name", "Weakest Beast Tamer"], tmp_path, {PAGE_URL: BOOK_PAGE})

    assert code == 0
    book = Book(tmp_path / "Weakest Beast Tamer")
    settings = book.settings()
    assert settings.title == "Weakest Beast Tamer Gets All SSS Dragons"
    assert settings.author == "Dagzo"
    assert settings.source == PAGE_URL
    assert settings.url_template.endswith("/chapter-{n}")
    assert len(settings.remove_phrases) == 1
    assert "1274 chapters" in out


def test_add_without_a_name_uses_the_title(tmp_path):
    run(["add", PAGE_URL], tmp_path, {PAGE_URL: BOOK_PAGE})

    assert (tmp_path / "Weakest Beast Tamer Gets All SSS Dragons" / "book.toml").exists()


def test_add_makes_a_title_with_forbidden_characters_into_a_folder(tmp_path):
    page = BOOK_PAGE.replace("Weakest Beast Tamer Gets All SSS Dragons", "Re:Zero? Part 1")

    code, _ = run(["add", PAGE_URL], tmp_path, {PAGE_URL: page})

    assert code == 0
    assert (tmp_path / "ReZero Part 1" / "book.toml").exists()


def test_add_refuses_to_overwrite_a_book(tmp_path):
    run(["add", PAGE_URL, "--name", "B"], tmp_path, {PAGE_URL: BOOK_PAGE})

    code, out = run(["add", PAGE_URL, "--name", "B"], tmp_path, {PAGE_URL: BOOK_PAGE})

    assert code == 2
    assert "already has a book.toml" in out


def test_add_reports_a_page_that_cannot_be_fetched(tmp_path):
    code, out = run(["add", PAGE_URL], tmp_path, {})

    assert code == 2
    assert "Could not fetch" in out


def test_add_by_hand_takes_a_template_and_a_title(tmp_path):
    code, _ = run(["add", "--url", "http://x/{n}", "--title", "Hand Made"], tmp_path)

    assert code == 0
    assert Book(tmp_path / "Hand Made").settings().url_template == "http://x/{n}"


def test_add_needs_a_page_or_a_template(tmp_path):
    code, out = run(["add"], tmp_path)

    assert code == 2
    assert "book page" in out


# --- books and status -------------------------------------------------------


def test_books_lists_each_book_and_what_it_holds(tmp_path):
    run(["add", "--url", "http://x/{n}", "--title", "Alpha"], tmp_path)
    Book(tmp_path / "Alpha").raw_path(1).write_text("x", encoding="utf-8")

    code, out = run(["books"], tmp_path)

    assert code == 0
    assert "Alpha" in out and "downloaded 1" in out


def test_books_with_none_says_how_to_add_one(tmp_path):
    _, out = run(["books"], tmp_path)

    assert "scrape.py add" in out


def test_status_shows_what_is_held_missing_and_new(tmp_path):
    run(["add", PAGE_URL, "--name", "B"], tmp_path, {PAGE_URL: BOOK_PAGE})
    book = Book(tmp_path / "B")
    for n in (1, 2, 3, 1273):
        book.raw_path(n).write_text("x", encoding="utf-8")

    code, out = run(["status", "b"], tmp_path, {PAGE_URL: BOOK_PAGE})

    assert code == 0
    assert "downloaded  1-3, 1273" in out
    assert "missing     4-1272, 1274" in out
    assert "latest 1274, 1 new" in out


def test_status_offline_makes_no_request(tmp_path):
    run(["add", PAGE_URL, "--name", "B"], tmp_path, {PAGE_URL: BOOK_PAGE})

    def refuse(url):
        raise AssertionError("no request expected")

    lines = []
    code = run_command(["status", "B", "--offline"], get_page=refuse, root=tmp_path, report=lines.append)

    assert code == 0
    assert "not checked" in "\n".join(lines)


def test_an_unknown_book_is_a_clear_error(tmp_path):
    code, out = run(["status", "nothing"], tmp_path)

    assert code == 2
    assert "No book called" in out


def test_scrape_main_hands_commands_over(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    code = main(["books"])

    assert code == 0
    assert "scrape.py add" in capsys.readouterr().err
```

- [ ] **Step 3: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_commands.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'scraper.commands'`.

- [ ] **Step 4: Implement** - create `scraper/commands.py`:

```python
"""The book subcommands: `python scrape.py <command> <book> ...`.

Parsing and reporting live here; the work itself is in `stages`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scraper.book import (
    BOOKS_DIR,
    Book,
    describe_ranges,
    find_book,
    list_books,
    missing_numbers,
    raw_file_name,
    safe_folder_name,
)
from scraper.bookpage import parse_book_page, site_phrase
from scraper.fetch import fetch_page
from scraper.run import build_fetcher

COMMANDS = ("add", "books", "status", "download", "clean", "review", "build", "update")


def book_fetcher(settings):
    return build_fetcher(settings, file_name=raw_file_name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scrape.py",
        description="Work with the books kept in the books folder.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="create a book from its page on the source site")
    add.add_argument("page_url", nargs="?", help="the book's main page")
    add.add_argument("--name", help="folder name (default: the book's title)")
    add.add_argument("--url", dest="url_template", help="chapter URL with {n}, for sites without book details")
    add.add_argument("--title", help="the book's title, when adding with --url")

    sub.add_parser("books", help="list the books")

    status = sub.add_parser("status", help="what is downloaded, cleaned and built")
    status.add_argument("book")
    status.add_argument("--offline", action="store_true", help="do not check the site")

    return parser


def run_command(
    argv: list[str],
    fetcher_factory=book_fetcher,
    get_page=fetch_page,
    root: Path | str = BOOKS_DIR,
    report=None,
) -> int:
    report = report or (lambda message: print(message, file=sys.stderr))
    args = build_parser().parse_args(argv)
    root = Path(root)
    handler = _HANDLERS[args.command]
    try:
        return handler(args, root=root, fetcher_factory=fetcher_factory, get_page=get_page, report=report)
    except ValueError as exc:
        report(f"error: {exc}")
        return 2


# --- add ----------------------------------------------------------------------


def _add(args, root, get_page, report, **_):
    if args.url_template:
        title = args.title or args.name
        if not title:
            raise ValueError("Adding with --url needs --title (or --name).")
        values = {"title": title, "url_template": args.url_template}
        latest = None
        summary = title
    elif args.page_url:
        html = get_page(args.page_url)
        if html is None:
            raise ValueError(f"Could not fetch {args.page_url}")
        info = parse_book_page(html, args.page_url)
        title = info.title
        values = {
            "title": info.title,
            "author": info.author,
            "source": args.page_url,
            "url_template": info.url_template,
            "remove_phrases": [site_phrase(args.page_url)],
        }
        latest = info.latest
        by = f", by {info.author}" if info.author else ""
        state = f" ({info.status})" if info.status else ""
        summary = f"{info.title}{by}{state}"
        if latest:
            updated = f", last updated {info.updated}" if info.updated else ""
            summary += f"\n  {latest} chapters on the site{updated}"
    else:
        raise ValueError("Give the book page URL, or --url with a {n} template and --title.")

    folder = safe_folder_name(args.name or title)
    if not folder:
        raise ValueError(f"Cannot make a folder name from {args.name or title!r}. Pass --name.")
    book = Book(root / folder)
    book.create(values)

    report(f"Added {book.name}")
    report(f"  {summary}")
    report(f"  {book.config_path}")
    report(f'Next: python scrape.py download "{book.name}"')
    return 0


# --- books and status ---------------------------------------------------------


def _books(args, root, report, **_):
    books = list_books(root)
    if not books:
        report("No books yet. Add one with: python scrape.py add <book page url>")
        return 0
    for book in books:
        raw, cleaned = book.raw_numbers(), book.cleaned_numbers()
        report(f"{book.name}: downloaded {describe_ranges(raw)}, cleaned {len(cleaned)} chapter(s)")
    return 0


def _status(args, root, get_page, report, **_):
    from scraper.stages import site_latest

    book = find_book(args.book, root)
    settings = book.settings()
    raw, cleaned = book.raw_numbers(), book.cleaned_numbers()

    latest = None if args.offline else site_latest(settings, get_page)
    last_known = max([*raw, latest or 0])

    report(book.name)
    if settings.title or settings.author:
        by = f", by {settings.author}" if settings.author else ""
        report(f"  {settings.title or book.name}{by}")
    report(f"  downloaded  {describe_ranges(raw)}")
    missing = missing_numbers(raw, settings.start, last_known) if last_known else []
    if missing:
        report(f"  missing     {describe_ranges(missing)}")
    report(f"  cleaned     {describe_ranges(cleaned)}")
    outputs = book.outputs()
    report(f"  built       {', '.join(p.name for p in outputs) if outputs else 'nothing yet'}")

    if args.offline:
        report("  site        not checked (--offline)")
    elif not settings.source:
        report("  site        not checked: book.toml has no source page")
    elif latest is None:
        report("  site        could not be reached, or lists no latest chapter")
    else:
        new = len([n for n in missing_numbers(raw, settings.start, latest) if n > max(raw, default=0)])
        report(f"  site        latest {latest}, {new} new")
    return 0


_HANDLERS = {
    "add": _add,
    "books": _books,
    "status": _status,
}
```

In `scrape.py`, add the import `from scraper.commands import COMMANDS, run_command`, and make `main` start:

```python
def main(argv: list[str] | None = None, fetcher_factory=build_fetcher) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in COMMANDS:
        return run_command(argv)

    args = parse_args(argv)
```

Add to the top of `EXAMPLES` in `scrape.py`:

```
books (PowerShell):

  python scrape.py add https://example.com/novel/some-book --name "Some Book"
  python scrape.py status "Some Book"
  python scrape.py update some          # any unambiguous start of the name

  python scrape.py <command> --help     # add, books, status, download,
                                        # clean, review, build, update

one-off runs:
```

and change its last line to `The output format follows the extension: .md, .txt, .pdf or .epub.`

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_commands.py -v`
Expected: all pass. Then `.venv/Scripts/python.exe -m pytest` - all pass.

- [ ] **Step 6: Commit**

```bash
git add scraper/reporting.py scraper/commands.py scrape.py tests/test_commands.py
git commit -m "Add book commands: add, books, status"
```

---

### Task 10: Commands - download, clean, review, build, update

**Files:**
- Modify: `scraper/commands.py`
- Test: `tests/test_commands.py`

**Interfaces:**
- Consumes: `download`, `clean`, `read_cleaned`, `build`, `site_latest` (Tasks 7-8); `repeated_sentences` (Task 6); `report_removals`, `report_trims`, `warn_if_emptied` (Task 9).
- Produces: the remaining five commands. `update` = download, then (only if something new arrived) clean, then build the new chapters' range.

- [ ] **Step 1: Write the failing tests** - append to `tests/test_commands.py`:

```python
# --- the stages -------------------------------------------------------------

from scraper.fetch import FetchResult


def chapter(text, title="Chapter"):
    return f"<html><head><title>{title}</title></head><body><div id='c'><p>{text}</p></div></body></html>"


class StubFetcher:
    def __init__(self, book, pages):
        self.book, self.pages = book, pages

    def fetch(self, url, number):
        html = self.pages.get(number)
        if html is None:
            return None
        self.book.raw_path(number).write_text(html, encoding="utf-8")
        return FetchResult(number=number, url=url, html=html, from_cache=False)


def added_book(tmp_path, latest=3):
    page = BOOK_PAGE.replace("chapter-1274", f"chapter-{latest}")
    run(["add", PAGE_URL, "--name", "B"], tmp_path, {PAGE_URL: page})
    book = Book(tmp_path / "B")
    with book.config_path.open("a", encoding="utf-8") as handle:
        handle.write('content_selector = "#c"\ndelay = 0.0\n')
    return book, {PAGE_URL: page}


def test_download_fetches_up_to_the_sites_latest_chapter(tmp_path):
    book, site = added_book(tmp_path, latest=3)
    pages = {n: chapter(f"Text {n}.") for n in range(1, 6)}

    code, out = run(["download", "B"], tmp_path, site, lambda s: StubFetcher(book, pages))

    assert code == 0
    assert book.raw_numbers() == [1, 2, 3]
    assert "Downloaded 3 chapter(s)" in out


def test_clean_reports_what_it_removed(tmp_path):
    book, _ = added_book(tmp_path)
    for n in range(1, 4):
        book.raw_path(n).write_text(chapter(f"Text {n}. Read more at freewebnovel"), encoding="utf-8")

    code, out = run(["clean", "B"], tmp_path)

    assert code == 0
    assert book.cleaned_numbers() == [1, 2, 3]
    assert "sentence(s) matching" in out
    assert "Cleaned 3 chapter(s)" in out


def test_review_lists_repeated_sentences(tmp_path):
    book, _ = added_book(tmp_path)
    for n in range(1, 6):
        book.raw_path(n).write_text(
            chapter(f"Story number {n} continues. Give it a power stone, please!"), encoding="utf-8"
        )
    run(["clean", "B", "--no-dedupe"], tmp_path)

    code, out = run(["review", "B", "--min-chapters", "3"], tmp_path)

    assert code == 0
    assert "Give it a power stone, please!" in out


def test_review_before_clean_says_to_clean(tmp_path):
    added_book(tmp_path)

    code, out = run(["review", "B"], tmp_path)

    assert code == 2
    assert "clean" in out


def test_build_writes_the_whole_book_by_default(tmp_path):
    book, _ = added_book(tmp_path)
    for n in range(1, 4):
        book.raw_path(n).write_text(chapter(f"Text {n}."), encoding="utf-8")
    run(["clean", "B"], tmp_path)

    code, out = run(["build", "B", "--format", "md"], tmp_path)

    assert code == 0
    assert (book.output_dir / "B 1-3.md").exists()
    assert "Wrote 3 chapter(s)" in out


def test_update_builds_just_the_new_chapters(tmp_path):
    book, site = added_book(tmp_path, latest=4)
    pages = {n: chapter(f"Text {n}.") for n in range(1, 5)}
    for n in (1, 2):
        book.raw_path(n).write_text(pages[n], encoding="utf-8")

    code, out = run(["update", "B", "--format", "md"], tmp_path, site, lambda s: StubFetcher(book, pages))

    assert code == 0
    assert [p.name for p in book.outputs()] == ["B 3-4.md"]
    assert book.cleaned_numbers() == [1, 2, 3, 4]


def test_update_with_nothing_new_says_so_and_builds_nothing(tmp_path):
    book, site = added_book(tmp_path, latest=2)
    pages = {n: chapter(f"Text {n}.") for n in range(1, 3)}
    for n in (1, 2):
        book.raw_path(n).write_text(pages[n], encoding="utf-8")

    code, out = run(["update", "B"], tmp_path, site, lambda s: StubFetcher(book, pages))

    assert code == 0
    assert "Up to date" in out
    assert book.outputs() == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_commands.py -v`
Expected: FAIL - argparse exits with `invalid choice: 'download'` (SystemExit 2).

- [ ] **Step 3: Implement** - in `scraper/commands.py`:

Add to the imports:

```python
from scraper.reporting import report_removals, report_trims, warn_if_emptied
from scraper.review import repeated_sentences
from scraper.stages import build, clean, download, read_cleaned, site_latest
```

and remove the local `from scraper.stages import site_latest` inside `_status`.

In `build_parser`, before `return parser`, add:

```python
    down = sub.add_parser("download", help="fetch the chapters not yet downloaded")
    down.add_argument("book")
    down.add_argument("--start", type=int, help="first chapter (default: from book.toml, else 1)")
    down.add_argument("--end", type=int, help="last chapter (default: the site's latest)")
    down.add_argument("--refresh", action="store_true", default=None, help="fetch held chapters again")

    cleaner = sub.add_parser("clean", help="rebuild the cleaned chapters from the raw pages")
    cleaner.add_argument("book")
    cleaner.add_argument("--no-dedupe", dest="dedupe", action="store_false", default=None,
                         help="keep blocks that repeat across chapters")

    review = sub.add_parser("review", help="list sentences repeated across chapters")
    review.add_argument("book")
    review.add_argument("--min-chapters", type=int, default=4,
                        help="how many chapters a sentence must appear in (default 4)")

    builder = sub.add_parser("build", help="join the cleaned chapters into one file")
    builder.add_argument("book")
    builder.add_argument("--format", default="epub", help="epub, pdf, md or txt (default epub)")
    builder.add_argument("--from", dest="start", type=int, help="first chapter")
    builder.add_argument("--to", dest="end", type=int, help="last chapter")

    update = sub.add_parser("update", help="download what is new, clean, and build the new chapters")
    update.add_argument("book")
    update.add_argument("--format", default="epub", help="epub, pdf, md or txt (default epub)")
```

Add the handlers above `_HANDLERS`:

```python
# --- the stages ---------------------------------------------------------------


def _download(args, root, fetcher_factory, get_page, report, **_):
    book = find_book(args.book, root)
    settings = book.settings(start=args.start, end=args.end, refresh=args.refresh)
    fetched = _fetch_new(book, settings, fetcher_factory, get_page, report)
    report(f"Downloaded {len(fetched)} chapter(s). Held: {describe_ranges(book.raw_numbers())}")
    return 0


def _clean(args, root, report, **_):
    book = find_book(args.book, root)
    _run_clean(book, book.settings(dedupe=args.dedupe), report)
    return 0


def _review(args, root, report, **_):
    book = find_book(args.book, root)
    pages = read_cleaned(book)
    if not pages:
        raise ValueError(f"{book.name} has no cleaned chapters. Run clean first.")
    repeats = repeated_sentences(pages, min_chapters=args.min_chapters)
    if not repeats:
        report(f"No sentence appears in {args.min_chapters} or more chapters.")
        return 0
    report(f"Sentences in {args.min_chapters}+ of {len(pages)} chapters (first chapter in brackets):")
    for repeat in repeats:
        report(f"  {repeat.chapters:5}  {repeat.text}  [{repeat.first}]")
    report("Anything here that is not the story can go in remove_phrases in book.toml.")
    return 0


def _build(args, root, report, **_):
    book = find_book(args.book, root)
    path = build(book, book.settings(), fmt=args.format, start=args.start, end=args.end)
    count = len(read_cleaned(book, args.start, args.end))
    report(f"Wrote {count} chapter(s) to {path}")
    return 0


def _update(args, root, fetcher_factory, get_page, report, **_):
    book = find_book(args.book, root)
    settings = book.settings()
    fetched = _fetch_new(book, settings, fetcher_factory, get_page, report)
    if not fetched:
        report(f"Up to date: no new chapters. Held: {describe_ranges(book.raw_numbers())}")
        return 0
    _run_clean(book, settings, report)
    path = build(book, settings, fmt=args.format, start=min(fetched), end=max(fetched))
    report(f"Wrote {len(fetched)} new chapter(s) to {path}")
    return 0


def _fetch_new(book, settings, fetcher_factory, get_page, report) -> list[int]:
    latest = None
    if settings.end is None:
        latest = site_latest(settings, get_page)
        if latest:
            report(f"The site lists {latest} chapters.")
    return download(book, settings, fetcher_factory(settings), latest=latest, log=report)


def _run_clean(book, settings, report) -> None:
    result = clean(book, settings)
    if result.skipped:
        report(f"Skipped {len(result.skipped)} raw page(s) with no text: {describe_ranges(result.skipped)}")
    report_removals(result.removals, len(result.pages), report)
    report_trims(result.trims, report)
    if result.retitled:
        report(f"Titles: {result.retitled} chapter(s) took a title from titles.json.")
    warn_if_emptied(result.pages, report)
    report(f"Cleaned {len(result.pages)} chapter(s) into {book.cleaned_dir}")
```

Replace `_HANDLERS`:

```python
_HANDLERS = {
    "add": _add,
    "books": _books,
    "status": _status,
    "download": _download,
    "clean": _clean,
    "review": _review,
    "build": _build,
    "update": _update,
}
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_commands.py -v`
Expected: all pass. Then `.venv/Scripts/python.exe -m pytest` - all pass.

- [ ] **Step 5: Commit**

```bash
git add scraper/commands.py tests/test_commands.py
git commit -m "Add book commands: download, clean, review, build, update"
```

---

### Task 11: README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a "Books" section** directly after `## Setup`, before `## Usage`:

````markdown
## Books

Each book lives in its own folder under `books/`:

```
books\
  Weakest Beast Tamer\
    book.toml       settings: title, author, URL pattern, phrases to remove
    01 Raw\         0001.html ...  pages exactly as downloaded
    02 Cleaned\     0001.md ...    one cleaned chapter per file
    03 Output\      Weakest Beast Tamer 1228-1274.epub ...
```

The whole `books` folder stays out of git.

Add a book from its main page on the site. The title, author, chapter URL
pattern and latest chapter are read from the page:

```powershell
python scrape.py add https://freewebnovel.com/novel/shadow-slave --name "Shadow Slave"
```

A site that doesn't publish those details can be added by hand:
`add --url "https://example.com/book/chapter-{n}" --title "Some Book"`.

Then, naming the book by its folder - any unambiguous start of the name
will do:

| Command | Does |
|---------|------|
| `status shadow` | What is downloaded, cleaned and built, and how many chapters are new on the site |
| `download shadow` | Fetches chapters not yet in `01 Raw`. Stop with Ctrl-C and run again to carry on |
| `clean shadow` | Rebuilds `02 Cleaned` from `01 Raw` and reports everything it removed |
| `review shadow` | Lists sentences that recur across many chapters, to spot junk |
| `build shadow` | Joins every cleaned chapter into an epub (`--format pdf/md/txt`, `--from`/`--to`) |
| `update shadow` | The everyday one: download what's new, clean, and build just the new chapters |
| `books` | Lists the books |

`clean` is local and quick, so re-run it whenever you change `book.toml`.
It replaces everything in `02 Cleaned`, so a hand edit there won't last -
put lasting fixes in `book.toml` as rules.

### Removing watermarks

Sites splice their name into the text in ever-changing wording, often onto
the end of a real paragraph. `remove_phrases` in `book.toml` lists regular
expressions; any *sentence* matching one is removed and the rest of its
paragraph kept. `add` starts the list with a pattern for the site's name:

```toml
remove_phrases = ["f[\\W_]*r[\\W_]*e...", "n0vel1st", "Give it a power stone"]
```

Matching ignores case. Run `review` to find more, add them, and `clean`
again.

### Chapter titles

Titles lose the decoration the site adds - the book's name in front, the
site's name after a `|`, and a doubled chapter number - leaving the
author's chapter name whole. To replace titles outright, put a
`titles.json` of `{"number": "title"}` in the book's folder.
````

Change the first line under `## Usage` from "Fifty numbered pages into one Markdown file:" to:

```markdown
For a one-off run that doesn't need a book folder, pass everything on the
command line. Fifty numbered pages into one Markdown file:
```

In `## Development`, replace `184 tests` with the number reported by `.venv/Scripts/python.exe -m pytest`.

- [ ] **Step 2: Check it reads correctly**

Run: `.venv/Scripts/python.exe -m pytest` and confirm the count you wrote matches.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Document books and their commands"
```

---

### Task 12: Move the current book across

This task works on the user's real files and makes network requests.
**Confirm each step marked (ask) with the user before running it.**

**Files:** none in the repo. Works in `books/Weakest Beast Tamer/` (already created by the user, with its three empty stage folders).

- [ ] **Step 1: Add the book (one request)**

```powershell
.\.venv\Scripts\python.exe scrape.py add https://freewebnovel.com/novel/weakest-beast-tamer-gets-all-sss-dragons --name "Weakest Beast Tamer"
```

Expected: `Added Weakest Beast Tamer`, about 1274 chapters on the site.

- [ ] **Step 2: Copy the 544 cached pages into `01 Raw`, padded**

```powershell
.\.venv\Scripts\python.exe -c "import shutil, pathlib; dst = pathlib.Path('books/Weakest Beast Tamer/01 Raw'); n = 0
for src in pathlib.Path('.cache').glob('freewebnovel.com-*/*.html'):
    shutil.copy2(src, dst / f'{int(src.stem):04d}.html'); n += 1
print(n, 'copied')"
```

Expected: `544 copied`. Copy, not move: `.cache/` is left as it is until the user decides.

- [ ] **Step 3: Add this book's settings** - append to `books/Weakest Beast Tamer/book.toml`:

```toml
content_selector = "div#article"
delay = 2.0
remove_phrases = [
  # the site's own name, as seeded by add - keep that line and add these:
  'n[\W_]*0[\W_]*v[\W_]*e[\W_]*l[\W_]*1[\W_]*s[\W_]*t',
  'Thank you so much for reading',
  'Give it a power stone',
  'Have some idea about my story',
  'Comment it and let me know',
  'you help me a lot',
  'Anyway, as always',
]
```

`add` already wrote a `remove_phrases` line; merge the two into one list
(TOML rejects a key defined twice).

- [ ] **Step 4: Clean and review**

```powershell
.\.venv\Scripts\python.exe scrape.py clean weakest
.\.venv\Scripts\python.exe scrape.py review weakest
```

Expected: about 119 site-name sentences and 36 chapters of author's notes
reported removed; titles in `02 Cleaned` read like `# Chapter 1 - Beast Tamer Ren Patinder`.
Show the user the report and a sample chapter.

- [ ] **Step 5: (ask) Move old output into the book** - the root's `book*.epub`, `book*.pdf`, `book*.md` and `book 1 - 500.epub` into `books/Weakest Beast Tamer/03 Output/`. Ask what to do with `titles.json`, `RUNNING.md` and `.cache/` (suggest: delete `RUNNING.md`; keep `titles.json` and `.cache/` until the new book has been checked, then delete).

- [ ] **Step 6: (ask) Download the 730 missing chapters** - about 25 minutes at a 2-second delay; run in the background:

```powershell
.\.venv\Scripts\python.exe scrape.py download weakest
```

Then `clean weakest`, `status weakest` (expect nothing missing, 0 new), and `build weakest` for the whole book.
