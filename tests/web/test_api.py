"""Tests for Folio's web API, against a temporary books folder. No network."""
import threading

from fastapi.testclient import TestClient

from scraper.book import Book
from scraper.web import tasks
from scraper.web.app import create_app
from tests.web.conftest import PAGE_URL


def test_preview_then_add_a_book_with_its_cover(client, root):
    preview = client.post("/api/books/preview", json={"url": PAGE_URL}).json()
    assert preview["title"] == "Bee Book" and preview["latest"] == 4 and preview["name"] == "Bee Book"
    assert not (root / "Bee Book").exists()

    added = client.post("/api/books", json={"url": PAGE_URL, "name": "Bee"})
    assert added.status_code == 201 and added.json()["name"] == "Bee"
    assert Book(root / "Bee").cover_path.name == "cover.png"
    assert client.get("/api/books/Bee/cover").status_code == 200


def test_adding_a_book_twice_is_an_error(client):
    client.post("/api/books", json={"url": PAGE_URL, "name": "Bee"})

    second = client.post("/api/books", json={"url": PAGE_URL, "name": "Bee"})

    assert second.status_code == 400 and "already has a book.toml" in second.json()["error"]


def test_books_list_and_detail(client, book):
    for n in (1, 2, 3):
        book.raw_path(n).write_text("x", encoding="utf-8")

    books = client.get("/api/books").json()
    assert [b["name"] for b in books] == ["B"] and books[0]["cleaned"] == 30

    detail = client.get("/api/books/B").json()
    assert detail["map"] == [["cleaned", 1, 3]]
    assert detail["activity"] == [] and detail["job"] is None


def test_unknown_book_is_404(client):
    response = client.get("/api/books/Nope")
    assert response.status_code == 404 and "Nope" in response.json()["error"]


def test_path_tricks_cannot_reach_outside(client, book):
    (book.output_dir / "B 1-30.epub").write_bytes(b"epub")
    assert client.get("/api/books/B/files/B 1-30.epub").content == b"epub"

    for name in ("book.toml", "..%2Fbook.toml", "%2E%2E%2F%2E%2E%2Fsecret"):
        assert client.get(f"/api/books/B/files/{name}").status_code == 404
    assert client.get("/api/books/..%2FB/files/x").status_code == 404
    assert client.delete("/api/books/B/files/book.toml").status_code == 404
    assert book.config_path.exists()


def test_delete_a_built_file(client, book):
    (book.output_dir / "B 1-30.md").write_text("x", encoding="utf-8")

    assert client.delete("/api/books/B/files/B 1-30.md").status_code == 204
    assert book.outputs() == []


def test_settings_round_trip_and_invalid_is_422(client, book):
    data = client.get("/api/books/B/settings").json()
    assert data["values"]["remove_phrases"] == ["zzz"]

    ok = client.put("/api/books/B/settings", json={"values": {"delay": 2.5}})
    assert ok.status_code == 200 and ok.json()["values"]["delay"] == 2.5

    before = book.config_path.read_bytes()
    bad = client.put("/api/books/B/settings", json={"values": {"remove_phrases": ["(bad"]}})
    assert bad.status_code == 422 and "Invalid remove phrase" in bad.json()["error"]
    assert book.config_path.read_bytes() == before


def test_review_test_suggest_and_ignore(client, book):
    rows = client.get("/api/books/B/review?min=4").json()["rows"]
    mark = next(r for r in rows if "FreeWebNovel" in r["text"])
    assert mark["chapters"] == 30

    pattern = client.post("/api/books/B/review/phrase", json={"sentence": mark["text"]}).json()["pattern"]
    tried = client.post("/api/books/B/review/test", json={"pattern": pattern})
    assert tried.status_code == 200 and tried.json()["sentences"] == 30

    broad = client.post("/api/books/B/review/test", json={"pattern": "tale"})
    assert broad.status_code == 422

    client.post("/api/books/B/review/ignore", json={"sentence": mark["text"]})
    rows = client.get("/api/books/B/review?min=4").json()["rows"]
    assert all("FreeWebNovel" not in r["text"] for r in rows)


def test_review_without_cleaned_chapters_says_so(client, root):
    Book(root / "E").create({"title": "E", "url_template": "http://x/{n}"})

    response = client.get("/api/books/E/review")

    assert response.status_code == 400 and "Run clean first" in response.json()["error"]


def test_start_a_job_and_see_it_finish(client, book):
    job = client.post("/api/books/B/jobs", json={"kind": "build", "format": "md"})
    assert job.status_code == 202

    finished = client.app.state.jobs.wait(job.json()["id"])
    assert finished.status == "done"
    assert client.get("/api/jobs").json()[0]["id"] == finished.id
    assert book.outputs()[0].name == "B 1-30.md"


def test_a_busy_book_gives_409(client, book, monkeypatch):
    gate = threading.Event()
    monkeypatch.setitem(tasks.RUNNERS, "clean", lambda b, p, c: gate.wait(5) and {})
    first = client.post("/api/books/B/jobs", json={"kind": "clean"})

    second = client.post("/api/books/B/jobs", json={"kind": "clean"})

    assert second.status_code == 409 and "busy" in second.json()["error"]
    gate.set()
    client.app.state.jobs.wait(first.json()["id"])


def test_without_a_built_front_end_the_root_explains(client):
    response = client.get("/")
    assert response.status_code == 200 and "npm run build" in response.text


def test_lan_key_is_required_off_this_machine(root):
    app = create_app(root=root, get_page=lambda u: None, lan_key="sesame", static_dir=root / "x")
    remote = TestClient(app, client=("192.168.1.20", 5000))
    assert remote.get("/api/books").status_code == 401
    assert remote.get("/?key=sesame").status_code == 200
    assert remote.get("/api/books").status_code == 200  # the cookie is set now

    local = TestClient(app, client=("127.0.0.1", 5000))
    assert local.get("/api/books").status_code == 200


def test_review_sees_the_text_change_after_a_clean(client, book):
    first = client.get("/api/books/B/review?min=4").json()["rows"]
    assert any("FreeWebNovel" in r["text"] for r in first)

    for n in range(1, 31):  # as a clean does: every file rewritten
        path = book.cleaned_path(n)
        path.write_text(path.read_text(encoding="utf-8").replace(" Read more at FreeWebNovel.Com today.", ""),
                        encoding="utf-8")

    rows = client.get("/api/books/B/review?min=4").json()["rows"]
    assert all("FreeWebNovel" not in r["text"] for r in rows)
    tried = client.post("/api/books/B/review/test", json={"pattern": "freewebnovel"}).json()
    assert tried["sentences"] == 0


def test_a_raw_save_of_the_wrong_type_is_refused_and_the_library_still_loads(client, book):
    book.raw_path(1).write_text("x", encoding="utf-8")
    before = book.config_path.read_bytes()

    bad = client.put("/api/books/B/settings", json={"raw": 'url_template = "http://x/{n}"\nstart = "1"\n'})

    assert bad.status_code == 422 and "start" in bad.json()["error"]
    assert book.config_path.read_bytes() == before
    assert client.get("/api/books").status_code == 200


def test_one_broken_book_does_not_take_down_the_library(client, book, root, monkeypatch):
    Book(root / "Other").create({"title": "Other", "url_template": "http://x/{n}"})
    real = Book.settings

    def broken(self, **overrides):
        if self.name == "B":
            raise TypeError("something unforeseen")
        return real(self, **overrides)
    monkeypatch.setattr(Book, "settings", broken)

    books = {b["name"]: b for b in client.get("/api/books").json()}

    assert books["Other"]["ready"] and not books["B"]["ready"]
    assert "something unforeseen" in books["B"]["error"]


def test_a_folder_made_by_hand_can_be_set_up_from_its_page(client, root):
    (root / "Bee Book" / "01 Raw").mkdir(parents=True)

    preview = client.post("/api/books/preview", json={"url": PAGE_URL}).json()
    assert preview["exists"] is False  # a folder without book.toml is waiting to be set up

    settings = client.get("/api/books/Bee Book/settings")
    assert settings.status_code == 404 and "not set up" in settings.json()["error"]

    added = client.post("/api/books", json={"url": PAGE_URL, "name": "Bee Book"})
    assert added.status_code == 201 and added.json()["ready"]


# --- other web pages cannot drive Folio -----------------------------------------


def hardened(root, **kw):
    return create_app(root=root, get_page=lambda u: None, static_dir=root / "x",
                      allowed_hosts=["127.0.0.1", "localhost"], **kw)


def test_a_request_for_another_host_name_is_refused(root):
    """DNS rebinding: a hostile site pointing its own name at this machine."""
    evil = TestClient(hardened(root), base_url="http://evil.example:8765")
    assert evil.get("/api/books").status_code == 400

    ours = TestClient(hardened(root), base_url="http://127.0.0.1:8765")
    assert ours.get("/api/books").status_code == 200


def test_changes_from_another_site_are_refused(root, book):
    client = TestClient(hardened(root), base_url="http://127.0.0.1:8765")

    cross = client.post("/api/update-all", headers={"Origin": "http://evil.example"})
    assert cross.status_code == 403
    fetched = client.delete("/api/books/B/files/x", headers={"Sec-Fetch-Site": "cross-site"})
    assert fetched.status_code == 403

    same = client.post("/api/update-all", headers={"Origin": "http://127.0.0.1:8765"})
    assert same.status_code == 202
    assert client.get("/api/books", headers={"Origin": "http://evil.example"}).status_code == 200  # reads are harmless


def test_lan_mode_accepts_the_machines_own_address(root):
    app = create_app(root=root, get_page=lambda u: None, static_dir=root / "x", lan_key="k",
                     allowed_hosts=["127.0.0.1", "localhost", "192.168.1.5"])
    phone = TestClient(app, base_url="http://192.168.1.5:8765", client=("192.168.1.20", 5000))
    assert phone.get("/api/books?key=k").status_code == 200
