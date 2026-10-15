"""Tests for starting Folio. Nothing is actually served."""
import socket

from scraper.commands import run_command
from scraper.web.serve import free_port, serve


def test_free_port_skips_a_port_in_use():
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        port = taken.getsockname()[1]
        taken.listen()
        assert free_port("127.0.0.1", port) != port


def test_serve_binds_locally_by_default(tmp_path):
    calls = {}
    serve(tmp_path, open_browser=False, port=9999, run=lambda app, **kw: calls.update(kw), report=lambda m: None)
    assert calls["host"] == "127.0.0.1" and calls["port"] == 9999


def test_lan_mode_binds_everywhere_and_prints_a_keyed_link(tmp_path):
    calls, lines = {}, []
    serve(tmp_path, lan=True, open_browser=False, port=9999,
          run=lambda app, **kw: calls.update(kw), report=lines.append)
    assert calls["host"] == "0.0.0.0"
    assert any("?key=" in line for line in lines)


def test_serve_is_a_command(tmp_path, monkeypatch):
    from scraper.web import serve as serve_module

    seen = {}
    monkeypatch.setattr(serve_module, "serve", lambda root, **kw: seen.update(kw, root=root) or 0)

    code = run_command(["serve", "--lan", "--no-browser", "--port", "8800"], root=tmp_path, report=lambda m: None)

    assert code == 0
    assert seen["lan"] is True and seen["open_browser"] is False and seen["port"] == 8800
