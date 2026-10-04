#!/usr/bin/env python3
"""Serve the private loopback fixture used by the Phase 5 unsigned probe."""

from __future__ import annotations

import argparse
import functools
import http.server
import os
import signal
import sys
import urllib.parse


class LoopbackHandler(http.server.SimpleHTTPRequestHandler):
    server_version = "Phase5UnsignedLoopback/1"

    def _route(self) -> str:
        return urllib.parse.urlsplit(self.path).path

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        route = self._route()
        if route == "/healthz":
            body = b"phase5-unsigned-loopback-ok\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if route == "/probe":
            self.path = "/phase5-unsigned-loopback.html"
        super().do_GET()

    def log_message(self, fmt: str, *args: object) -> None:
        message = fmt % args
        self.server.phase5_log.write(f"{message}\n")  # type: ignore[attr-defined]
        self.server.phase5_log.flush()  # type: ignore[attr-defined]


class LoopbackServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--port-file", required=True)
    parser.add_argument("--port", required=True, type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    directory = os.path.abspath(args.directory)
    fixture = os.path.join(directory, "phase5-unsigned-loopback.html")
    if not os.path.isfile(fixture):
        raise SystemExit(f"loopback fixture is missing: {fixture}")

    log_file = open(args.log, "a", encoding="utf-8", buffering=1)
    handler = functools.partial(LoopbackHandler, directory=directory)
    server = LoopbackServer(("127.0.0.1", args.port), handler)
    server.phase5_log = log_file  # type: ignore[attr-defined]
    with open(args.port_file, "w", encoding="utf-8") as port_file:
        port_file.write(f"{server.server_address[1]}\n")
    print(f"loopback_port={server.server_address[1]}", flush=True)

    def stop(_signum: int, _frame: object) -> None:
        server.server_close()
        log_file.close()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()
        log_file.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
