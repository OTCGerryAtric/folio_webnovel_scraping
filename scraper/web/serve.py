"""Start Folio: pick a port, open the browser, and with --lan print a link
(carrying its access key) for phones and tablets on the same network."""

from __future__ import annotations

import secrets
import socket
import sys
import threading
import webbrowser

import uvicorn

from scraper.web.app import create_app

DEFAULT_PORT = 8765


def free_port(host: str, start: int = DEFAULT_PORT) -> int:
    for port in range(start, start + 50):
        with socket.socket() as probe:
            try:
                probe.bind((host, port))
            except OSError:
                continue
            return port
    raise OSError(f"No free port between {start} and {start + 49}")


def lan_address() -> str:
    """This machine's address on the local network, or loopback if there is none."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("10.255.255.255", 1))  # chooses a route; sends nothing
            return probe.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def serve(root, lan: bool = False, port: int | None = None, open_browser: bool = True,
          run=uvicorn.run, report=None, extra_hosts=()) -> int:
    report = report or (lambda message: print(message, file=sys.stderr))
    for name in extra_hosts:
        if "*" in name:
            # A wildcard would answer to any name, undoing the guard against
            # sites that point their own name at this machine.
            raise ValueError(f"--allow-host takes a name or address, not a wildcard: {name!r}")
    host = "0.0.0.0" if lan else "127.0.0.1"
    port = port or free_port(host)
    key = secrets.token_urlsafe(12) if lan else None
    address = lan_address() if lan else None
    # Names given with --allow-host, such as a Tailscale address, are
    # answered too; devices there still need the access key with --lan.
    hosts = ["127.0.0.1", "localhost", *([address] if address else []), *extra_hosts]
    app = create_app(root=root, lan_key=key, allowed_hosts=hosts)

    local = f"http://127.0.0.1:{port}/"
    report(f"Folio is running at {local}")
    if lan:
        remote = f"http://{address}:{port}/?key={key}"
        report(f"On a phone or tablet on the same Wi-Fi, open: {remote}")
        _report_qr(remote, report)
    report("Press Ctrl-C to stop.")

    if open_browser:
        threading.Timer(1.0, webbrowser.open, args=(local,)).start()
    # Open tabs hold an event stream that never ends by itself; without a
    # time limit, Ctrl-C would wait on them for good.
    run(app, host=host, port=port, log_level="warning", timeout_graceful_shutdown=2)
    return 0


def _report_qr(text: str, report) -> None:
    """A QR code of the link, drawn with half-block characters, if the console can show them."""
    try:
        import qrcode
    except ImportError:
        return
    qr = qrcode.QRCode(border=1)
    qr.add_data(text)
    qr.make()
    rows = qr.get_matrix()
    if len(rows) % 2:
        rows.append([False] * len(rows[0]))
    lines = [
        "".join("█" if a and b else "▀" if a else "▄" if b else " " for a, b in zip(top, bottom))
        for top, bottom in zip(rows[::2], rows[1::2])
    ]
    try:
        for line in lines:
            report(line)
    except UnicodeEncodeError:  # a legacy Windows code page; the link is enough
        pass
