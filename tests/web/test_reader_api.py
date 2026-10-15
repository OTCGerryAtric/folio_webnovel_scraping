"""Tests for the reader's API, including that Folio's protections cover it."""
from fastapi.testclient import TestClient

from scraper.book import Book
from scraper.commands import run_command
from scraper.web.app import create_app


def make_book(root):
    book = Book(root / "B")
    book.create({"title": "B", "url_template": "http://x/{n}"})
    for n in (1, 2, 4):
        paras = "\n\n".join(f"Chapter {n} paragraph {i} says its own particular thing here." for i in range(10))
        book.cleaned_path(n).write_text(f"# C{n}\n\n{paras}\n", encoding="utf-8")
    return book


def client_for(root, base_url="http://testserver", **kw):
    return TestClient(create_app(root=root, get_page=lambda u: None, static_dir=root / "x", **kw), base_url=base_url)


def put(client, base=0, chapter=2, paragraph=3, offset=0.5, **headers):
    body = {"base_revision": base, "chapter": chapter, "paragraph": paragraph, "offset": offset,
            "device": "d1", "device_name": "PC"}
    return client.put("/api/books/B/position", json=body, headers=headers)


def test_chapters_and_one_chapter(tmp_path):
    make_book(tmp_path)
    client = client_for(tmp_path)

    listing = client.get("/api/books/B/chapters").json()
    assert [c["number"] for c in listing["chapters"]] == [1, 2, 4]
    assert (listing["first"], listing["last"]) == (1, 4)
    chapter = client.get("/api/books/B/chapters/2").json()
    assert (chapter["prev"], chapter["next"], len(chapter["paragraphs"])) == (1, 4, 10)
    assert client.get("/api/books/B/chapters/3").status_code == 404
    assert client.get("/api/books/B/chapters/abc").status_code == 404


def test_save_fills_in_the_rest_and_resolves(tmp_path):
    make_book(tmp_path)
    client = client_for(tmp_path)

    saved = put(client).json()

    assert saved["revision"] == 1
    position = saved["position"]
    assert position["anchor"].startswith("chapter 2 paragraph 3")
    assert position["paragraphs"] == 10 and len(position["version"]) == 12 and position["saved_at"]
    assert position["excerpt"] == "Chapter 2 paragraph 3 says its own particular thing here."
    got = client.get("/api/books/B/position").json()
    assert got["resolved"]["recovered"] == "exact" and got["resolved"]["paragraph"] == 3


def test_nothing_saved_yet(tmp_path):
    make_book(tmp_path)
    got = client_for(tmp_path).get("/api/books/B/position").json()
    assert (got["revision"], got["position"], got["resolved"]) == (0, None, None)


def test_a_stale_save_gets_409_with_the_newer_place(tmp_path):
    make_book(tmp_path)
    client = client_for(tmp_path)
    put(client, base=0, chapter=1)

    stale = put(client, base=0, chapter=4)

    assert stale.status_code == 409
    assert stale.json()["revision"] == 1 and stale.json()["position"]["chapter"] == 1
    assert stale.json()["resolved"]["chapter"] == 1


def test_a_place_in_a_chapter_that_is_not_there_is_refused_and_values_are_clamped(tmp_path):
    make_book(tmp_path)
    client = client_for(tmp_path)

    assert put(client, chapter=3).status_code == 422  # a gap, or mid re-clean
    clamped = put(client, paragraph=999, offset=7).json()["position"]
    assert clamped["paragraph"] == 9 and clamped["offset"] == 1.0


def test_a_missing_book_is_404_on_every_reader_route(tmp_path):
    client = client_for(tmp_path)
    for path in ("/api/books/Gone/chapters", "/api/books/Gone/chapters/1", "/api/books/Gone/position"):
        assert client.get(path).status_code == 404
    gone = client.put("/api/books/Gone/position", json={"base_revision": 0, "chapter": 1, "paragraph": 0,
                                                         "offset": 0, "device": "x", "device_name": "x"})
    assert gone.status_code == 404


def test_reader_routes_need_the_key_off_this_machine(tmp_path):
    make_book(tmp_path)
    app = create_app(root=tmp_path, get_page=lambda u: None, static_dir=tmp_path / "x", lan_key="k")
    phone = TestClient(app, client=("192.168.1.20", 5000))

    assert phone.get("/api/books/B/chapters").status_code == 401
    assert phone.get("/api/books/B/chapters/1").status_code == 401
    assert phone.get("/api/books/B/position").status_code == 401
    assert phone.put("/api/books/B/position", json={}).status_code == 401


def test_a_place_cannot_be_changed_from_another_site(tmp_path):
    make_book(tmp_path)
    client = client_for(tmp_path, base_url="http://127.0.0.1:8765", allowed_hosts=["127.0.0.1"])

    assert put(client, Origin="http://evil.example").status_code == 403
    assert put(client, Origin="http://127.0.0.1:8765").status_code == 200


def test_allow_host_admits_a_named_host(tmp_path):
    from scraper.web.serve import serve

    calls = {}
    serve(tmp_path, open_browser=False, port=9999, report=lambda m: None, extra_hosts=["pc.tailnet.ts.net"],
          run=lambda app, **kw: calls.update(app=app))

    assert TestClient(calls["app"], base_url="http://pc.tailnet.ts.net:9999").get("/api/books").status_code == 200
    assert TestClient(calls["app"], base_url="http://other.ts.net:9999").get("/api/books").status_code == 400


def test_allow_host_is_a_serve_option(tmp_path, monkeypatch):
    from scraper.web import serve as serve_module

    seen = {}
    monkeypatch.setattr(serve_module, "serve", lambda root, **kw: seen.update(kw) or 0)

    run_command(["serve", "--no-browser", "--allow-host", "a.ts.net", "--allow-host", "100.64.0.7"],
                root=tmp_path, report=lambda m: None)

    assert seen["extra_hosts"] == ["a.ts.net", "100.64.0.7"]


def test_the_chapter_list_sees_new_chapters(tmp_path):
    book = make_book(tmp_path)
    client = client_for(tmp_path)
    assert client.get("/api/books/B/chapters").json()["last"] == 4

    book.cleaned_path(9).write_text("# C9\n\nNew.\n", encoding="utf-8")

    assert client.get("/api/books/B/chapters").json()["last"] == 9


def test_a_save_the_disk_refuses_is_503_not_a_conflict(tmp_path, monkeypatch):
    from scraper.web import app as app_module

    make_book(tmp_path)
    client = client_for(tmp_path)
    monkeypatch.setattr(app_module, "save_position", lambda *a, **k: (_ for _ in ()).throw(PermissionError(5, "denied")))

    response = put(client)

    assert response.status_code == 503 and "error" in response.json()


def test_the_server_says_what_time_it_is(tmp_path):
    make_book(tmp_path)
    client = client_for(tmp_path)

    assert client.get("/api/books/B/position").json()["now"].endswith("Z")
    assert put(client).json()["now"].endswith("Z")


def test_allow_host_refuses_wildcards(tmp_path):
    import pytest
    from scraper.web.serve import serve

    for bad in ("*", "*.ts.net"):
        with pytest.raises(ValueError, match="wildcard"):
            serve(tmp_path, open_browser=False, port=9999, report=lambda m: None, extra_hosts=[bad], run=lambda app, **kw: None)
