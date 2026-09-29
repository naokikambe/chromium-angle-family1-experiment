#!/usr/bin/env python3
"""Serve the fixed WebGL smoke page and retain one same-origin result."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


SMOKE_SCHEMA = "phase3d-webgl-smoke-v1"
PAGE_PATH = "/phase3d-webgl-smoke.html"
RESULT_PATH = "/result"


def atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        json.dump(value, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page-file", required=True, type=Path)
    parser.add_argument("--ready-file", required=True, type=Path)
    parser.add_argument("--result-file", required=True, type=Path)
    parser.add_argument("--port", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    page_file = args.page_file.resolve()
    if not page_file.is_file():
        raise SystemExit(f"WebGL smoke page is not a file: {page_file}")
    page_bytes = page_file.read_bytes()

    class Handler(BaseHTTPRequestHandler):
        server_version = "phase3d-webgl-smoke/1"

        def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            if urlsplit(self.path).path == PAGE_PATH:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(page_bytes)))
                self.end_headers()
                self.wfile.write(page_bytes)
                return
            if urlsplit(self.path).path == "/health":
                body = b"ready\n"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

        def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            if urlsplit(self.path).path != RESULT_PATH:
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "-1"))
            except ValueError:
                length = -1
            if length < 0 or length > 128 * 1024:
                self.send_error(413)
                return
            try:
                payload = json.loads(self.rfile.read(length))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self.send_error(400)
                return
            if not isinstance(payload, dict) or payload.get("schema") != SMOKE_SCHEMA:
                self.send_error(400)
                return
            atomic_write_json(args.result_file, payload)
            self.send_response(204)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

        def log_message(self, format: str, *values: object) -> None:
            print(f"webgl-smoke-server: {format % values}", flush=True)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    args.ready_file.parent.mkdir(parents=True, exist_ok=True)
    args.ready_file.write_text(f"port={server.server_port}\n", encoding="utf-8")

    def stop(_signum: int, _frame: object) -> None:
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
