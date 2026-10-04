#!/usr/bin/env python3
"""Launch an unsigned Chromium copy and record a small CDP navigation probe.

This helper intentionally uses only Python's standard library.  It does not
modify the application bundle, its metadata, or its signing state.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shlex
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from typing import Any


SCHEMA = "phase5-unsigned-cdp-probe-v2"


def safe_url_summary(value: Any) -> dict[str, Any] | None:
    """Return URL routing metadata without recording query, cookie, or header data."""

    if not isinstance(value, str):
        return None
    parsed = urllib.parse.urlsplit(value)
    path = parsed.path or "/"
    try:
        port = parsed.port
    except ValueError:
        port = None
    return {
        "scheme": parsed.scheme,
        "host": parsed.hostname,
        "port": port,
        "path_sha256": hashlib.sha256(path.encode("utf-8")).hexdigest(),
    }


def diagnostic_event(message: dict[str, Any]) -> dict[str, Any] | None:
    """Summarize navigation/network events without retaining request contents."""

    method = message.get("method")
    params = message.get("params", {})
    if not isinstance(method, str) or not isinstance(params, dict):
        return None

    if method == "Network.requestWillBeSent":
        request = params.get("request", {})
        initiator = params.get("initiator", {})
        return {
            "method": method,
            "request_id": params.get("requestId"),
            "loader_id": params.get("loaderId"),
            "type": params.get("type"),
            "request_url": safe_url_summary(request.get("url")),
            "document_url": safe_url_summary(params.get("documentURL")),
            "initiator_type": initiator.get("type") if isinstance(initiator, dict) else None,
        }
    if method == "Network.responseReceived":
        response = params.get("response", {})
        return {
            "method": method,
            "request_id": params.get("requestId"),
            "loader_id": params.get("loaderId"),
            "type": params.get("type"),
            "status": response.get("status") if isinstance(response, dict) else None,
            "mime_type": response.get("mimeType") if isinstance(response, dict) else None,
            "protocol": response.get("protocol") if isinstance(response, dict) else None,
            "from_disk_cache": response.get("fromDiskCache") if isinstance(response, dict) else None,
            "from_service_worker": response.get("fromServiceWorker") if isinstance(response, dict) else None,
        }
    if method == "Network.loadingFailed":
        return {
            "method": method,
            "request_id": params.get("requestId"),
            "type": params.get("type"),
            "error_text": params.get("errorText"),
            "canceled": params.get("canceled"),
            "blocked_reason": params.get("blockedReason"),
            "cors_error": params.get("corsError"),
        }
    if method == "Network.loadingFinished":
        return {
            "method": method,
            "request_id": params.get("requestId"),
            "encoded_data_length": params.get("encodedDataLength"),
        }
    if method == "Network.dataReceived":
        return {
            "method": method,
            "request_id": params.get("requestId"),
            "data_length": params.get("dataLength"),
            "encoded_data_length": params.get("encodedDataLength"),
        }
    if method == "Page.frameStartedNavigating":
        return {
            "method": method,
            "frame_id": params.get("frameId"),
            "loader_id": params.get("loaderId"),
            "url": safe_url_summary(params.get("url")),
            "navigation_type": params.get("navigationType"),
        }
    if method == "Page.frameRequestedNavigation":
        return {
            "method": method,
            "frame_id": params.get("frameId"),
            "url": safe_url_summary(params.get("url")),
            "reason": params.get("reason"),
            "disposition": params.get("disposition"),
        }
    if method == "Page.frameNavigated":
        frame = params.get("frame", {})
        return {
            "method": method,
            "frame_id": frame.get("id") if isinstance(frame, dict) else None,
            "parent_id": frame.get("parentId") if isinstance(frame, dict) else None,
            "loader_id": frame.get("loaderId") if isinstance(frame, dict) else None,
            "url": safe_url_summary(frame.get("url")) if isinstance(frame, dict) else None,
            "type": frame.get("type") if isinstance(frame, dict) else None,
        }
    if method in {
        "Page.frameClearedScheduledNavigation",
        "Page.frameStoppedLoading",
        "Page.loadEventFired",
        "Page.domContentEventFired",
    }:
        return {"method": method, **{key: params.get(key) for key in ("frameId", "timestamp")}}
    if method == "Page.lifecycleEvent":
        return {
            "method": method,
            "frame_id": params.get("frameId"),
            "loader_id": params.get("loaderId"),
            "name": params.get("name"),
        }
    if method == "Page.navigatedWithinDocument":
        return {
            "method": method,
            "frame_id": params.get("frameId"),
            "url": safe_url_summary(params.get("url")),
        }
    return None


def record_message(
    event_file: Any,
    message: dict[str, Any],
    diagnostics: dict[str, list[dict[str, Any]]],
) -> None:
    summary = diagnostic_event(message)
    method = message.get("method")
    if isinstance(method, str) and method.startswith("Network."):
        if summary is None:
            params = message.get("params", {})
            summary = {
                "method": method,
                "request_id": params.get("requestId") if isinstance(params, dict) else None,
                "loader_id": params.get("loaderId") if isinstance(params, dict) else None,
            }
        diagnostics["network_events"].append(summary)
        event_file.write(json.dumps(summary, sort_keys=True) + "\n")
        event_file.flush()
        return
    if summary is not None:
        diagnostics["page_events"].append(summary)
    event_file.write(json.dumps(message, sort_keys=True) + "\n")
    event_file.flush()


def write_json(path: str, value: Any) -> None:
    with open(path, "w", encoding="utf-8") as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")


def choose_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe_socket:
        probe_socket.bind(("127.0.0.1", 0))
        return int(probe_socket.getsockname()[1])


def http_json(port: int, endpoint: str) -> Any:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{endpoint}", timeout=1.0) as response:
        return json.loads(response.read().decode("utf-8"))


class WebSocket:
    def __init__(self, url: str, event_log: Any) -> None:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "ws" or not parsed.hostname or not parsed.path:
            raise RuntimeError(f"unsupported DevTools WebSocket URL: {url}")
        self.sock = socket.create_connection((parsed.hostname, parsed.port or 80), timeout=3.0)
        self.sock.settimeout(0.5)
        self.event_log = event_log
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        host = parsed.hostname
        if parsed.port:
            host = f"{host}:{parsed.port}"
        request = (
            f"GET {parsed.path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii")
        self.sock.sendall(request)
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError("DevTools WebSocket handshake ended early")
            response += chunk
        if not response.startswith(b"HTTP/1.1 101"):
            raise RuntimeError(f"DevTools WebSocket handshake failed: {response[:200]!r}")

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        length = len(payload)
        first = 0x80 | opcode
        if length < 126:
            header = bytes([first, 0x80 | length])
        elif length <= 0xFFFF:
            header = bytes([first, 0x80 | 126]) + length.to_bytes(2, "big")
        else:
            header = bytes([first, 0x80 | 127]) + length.to_bytes(8, "big")
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.sock.sendall(header + mask + masked)

    def send_json(self, value: Any) -> None:
        self._send_frame(0x1, json.dumps(value, separators=(",", ":")).encode("utf-8"))

    def _read_exact(self, length: int, deadline: float) -> bytes:
        data = bytearray()
        while len(data) < length:
            if time.monotonic() >= deadline:
                raise TimeoutError("timed out reading DevTools WebSocket frame")
            try:
                chunk = self.sock.recv(length - len(data))
            except socket.timeout:
                continue
            if not chunk:
                raise RuntimeError("DevTools WebSocket closed")
            data.extend(chunk)
        return bytes(data)

    def recv_message(self, deadline: float) -> Any:
        fragments: list[bytes] = []
        while True:
            header = self._read_exact(2, deadline)
            first, second = header
            opcode = first & 0x0F
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = int.from_bytes(self._read_exact(2, deadline), "big")
            elif length == 127:
                length = int.from_bytes(self._read_exact(8, deadline), "big")
            mask = self._read_exact(4, deadline) if masked else b""
            payload = self._read_exact(length, deadline)
            if masked:
                payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
            if opcode == 0x8:
                raise RuntimeError("DevTools WebSocket sent close")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            if opcode == 0x1:
                fragments = [payload]
            elif opcode == 0x0:
                fragments.append(payload)
            else:
                continue
            if first & 0x80:
                return json.loads(b"".join(fragments).decode("utf-8"))


def command(
    ws: WebSocket,
    command_id: int,
    method: str,
    params: dict[str, Any] | None = None,
    navigation_state: dict[str, Any] | None = None,
    diagnostics: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[int, Any]:
    ws.send_json({"id": command_id, "method": method, "params": params or {}})
    deadline = time.monotonic() + 5.0
    while True:
        message = ws.recv_message(deadline)
        if diagnostics is None:
            ws.event_log.write(json.dumps(message, sort_keys=True) + "\n")
            ws.event_log.flush()
        else:
            record_message(ws.event_log, message, diagnostics)
        if navigation_state is not None:
            event_method = message.get("method")
            event_params = message.get("params", {})
            if event_method == "Page.frameNavigated" and event_params.get("frame", {}).get("parentId") is None:
                navigation_state["frame_navigated"] = True
                navigation_state["document_url"] = event_params.get("frame", {}).get("url")
            elif event_method == "Page.loadEventFired":
                navigation_state["load_event_fired"] = True
        if message.get("id") == command_id:
            return command_id + 1, message


def evaluate(
    ws: WebSocket,
    command_id: int,
    expression: str,
    navigation_state: dict[str, Any] | None = None,
    diagnostics: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[int, dict[str, Any]]:
    next_id, response = command(
        ws,
        command_id,
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True, "awaitPromise": True},
        navigation_state,
        diagnostics,
    )
    return next_id, response


def wait_for_target(port: int, deadline: float) -> dict[str, Any]:
    while time.monotonic() < deadline:
        try:
            targets = http_json(port, "/json")
            for target in targets:
                if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                    return target
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        time.sleep(0.2)
    raise TimeoutError("Chromium did not expose a DevTools page target")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--browser-arg", action="append", default=[])
    parser.add_argument("--browser-env", action="append", default=[])
    parser.add_argument("--net-log", default="")
    parser.add_argument("--expected-title", default="")
    parser.add_argument("--expected-title-prefix", default="")
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results_dir = os.path.abspath(args.results_dir)
    os.makedirs(results_dir, exist_ok=True)
    events_path = os.path.join(results_dir, "cdp-events.jsonl")
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "requested_url": args.url,
        "executable": os.path.abspath(args.executable),
        "profile": os.path.abspath(args.profile),
        "browser_args": args.browser_arg,
        "browser_env": args.browser_env,
        "browser_started": False,
        "browser_pid": None,
        "cdp_port": None,
        "frame_navigated": False,
        "load_event_fired": False,
        "navigation_error": None,
        "title": None,
        "document_url": None,
        "document_ready_state": None,
        "runtime_value": None,
        "webgl_result": None,
        "probe_success": False,
        "failure": None,
        "browser_terminated_by_probe": False,
        "browser_returncode": None,
        "net_log_path": os.path.abspath(args.net_log) if args.net_log else None,
        "net_log_exists": False,
        "net_log_bytes": 0,
        "page_events": [],
        "network_events": [],
    }
    diagnostics: dict[str, list[dict[str, Any]]] = {"page_events": [], "network_events": []}
    process: subprocess.Popen[bytes] | None = None
    ws: WebSocket | None = None
    event_file = open(events_path, "w", encoding="utf-8")
    try:
        os.makedirs(args.profile, exist_ok=True)
        port = choose_port()
        result["cdp_port"] = port
        command_line = [
            os.path.abspath(args.executable),
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-sync",
            "--enable-logging=stderr",
            "--remote-debugging-address=127.0.0.1",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={os.path.abspath(args.profile)}",
        ]
        command_line.extend(args.browser_arg)
        if args.net_log:
            net_log_path = os.path.abspath(args.net_log)
            net_log_parent = os.path.dirname(net_log_path)
            if net_log_parent:
                os.makedirs(net_log_parent, exist_ok=True)
            command_line.append(f"--log-net-log={net_log_path}")
        command_line.append("about:blank")
        with open(os.path.join(results_dir, "browser-stdout.log"), "wb") as stdout_file, open(
            os.path.join(results_dir, "browser-stderr.log"), "wb"
        ) as stderr_file:
            environment = os.environ.copy()
            for assignment in args.browser_env:
                key, separator, value = assignment.partition("=")
                if not separator or not key:
                    raise RuntimeError(f"invalid --browser-env assignment: {assignment}")
                environment[key] = value
            with open(os.path.join(results_dir, "launch-command.txt"), "w", encoding="utf-8") as launch_file:
                launch_file.write(f"{shlex.join(command_line)}\n")
                launch_file.write(f"environment_overrides={json.dumps(args.browser_env, sort_keys=True)}\n")
            process = subprocess.Popen(command_line, stdout=stdout_file, stderr=stderr_file, env=environment)
        result["browser_started"] = True
        result["browser_pid"] = process.pid
        with open(os.path.join(results_dir, "launch-pid.txt"), "w", encoding="utf-8") as pid_file:
            pid_file.write(f"{process.pid}\n")

        target = wait_for_target(port, time.monotonic() + 10.0)
        ws = WebSocket(target["webSocketDebuggerUrl"], event_file)
        command_id = 1
        command_id, enable_response = command(ws, command_id, "Page.enable", diagnostics=diagnostics)
        if "error" in enable_response:
            raise RuntimeError(f"Page.enable failed: {enable_response['error']}")
        command_id, network_response = command(ws, command_id, "Network.enable", diagnostics=diagnostics)
        if "error" in network_response:
            raise RuntimeError(f"Network.enable failed: {network_response['error']}")
        command_id, runtime_response = command(ws, command_id, "Runtime.enable", diagnostics=diagnostics)
        if "error" in runtime_response:
            raise RuntimeError(f"Runtime.enable failed: {runtime_response['error']}")
        navigation_state: dict[str, Any] = {
            "frame_navigated": False,
            "load_event_fired": False,
            "document_url": None,
        }
        command_id, navigate_response = command(
            ws, command_id, "Page.navigate", {"url": args.url}, navigation_state, diagnostics
        )
        result["frame_navigated"] = navigation_state["frame_navigated"]
        result["load_event_fired"] = navigation_state["load_event_fired"]
        result["document_url"] = navigation_state["document_url"]
        navigate_result = navigate_response.get("result", {})
        if navigate_result.get("errorText"):
            result["navigation_error"] = navigate_result["errorText"]

        deadline = time.monotonic() + args.timeout_seconds
        expression = "(() => ({title: document.title, readyState: document.readyState, url: location.href, marker: window.__phase5UnsignedProbe || null}))()"
        while time.monotonic() < deadline:
            try:
                message = ws.recv_message(min(deadline, time.monotonic() + 0.5))
                record_message(event_file, message, diagnostics)
                method = message.get("method")
                params = message.get("params", {})
                if method == "Page.frameNavigated" and params.get("frame", {}).get("parentId") is None:
                    result["frame_navigated"] = True
                    result["document_url"] = params.get("frame", {}).get("url")
                elif method == "Page.loadEventFired":
                    result["load_event_fired"] = True
            except TimeoutError:
                pass
            if result["frame_navigated"] or result["load_event_fired"]:
                command_id, evaluation = evaluate(ws, command_id, expression, navigation_state, diagnostics)
                result["frame_navigated"] = result["frame_navigated"] or navigation_state["frame_navigated"]
                result["load_event_fired"] = result["load_event_fired"] or navigation_state["load_event_fired"]
                evaluation_result = evaluation.get("result", {}).get("result", {})
                value = evaluation_result.get("value")
                if isinstance(value, dict):
                    result["runtime_value"] = value
                    result["title"] = value.get("title")
                    result["document_url"] = value.get("url") or result["document_url"]
                    result["document_ready_state"] = value.get("readyState")
                    title = value.get("title") or ""
                    title_matches = bool(args.expected_title and title == args.expected_title)
                    prefix_matches = bool(args.expected_title_prefix and title.startswith(args.expected_title_prefix))
                    no_title_expectation = not args.expected_title and not args.expected_title_prefix
                    if title_matches or prefix_matches or no_title_expectation:
                        if prefix_matches:
                            payload = title[len(args.expected_title_prefix) :]
                            try:
                                result["webgl_result"] = json.loads(payload)
                            except json.JSONDecodeError:
                                result["webgl_result"] = None
                        result["probe_success"] = True
                        break
            time.sleep(0.1)
        if not result["probe_success"]:
            raise RuntimeError("CDP navigation did not reach the expected document/title")
        try:
            ws.send_json({"id": command_id, "method": "Browser.close", "params": {}})
        except OSError:
            pass
    except Exception as error:  # noqa: BLE001 - preserve diagnostics in the result
        result["failure"] = str(error)
    finally:
        if ws is not None:
            ws.close()
        if process is not None:
            try:
                process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                result["browser_terminated_by_probe"] = True
                process.terminate()
                try:
                    process.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3.0)
            result["browser_returncode"] = process.returncode
        event_file.close()
        result["page_events"] = diagnostics["page_events"]
        result["network_events"] = diagnostics["network_events"]
        if args.net_log:
            net_log_path = os.path.abspath(args.net_log)
            result["net_log_exists"] = os.path.isfile(net_log_path)
            if result["net_log_exists"]:
                result["net_log_bytes"] = os.path.getsize(net_log_path)
        write_json(os.path.join(results_dir, "cdp-result.json"), result)
    return 0 if result["probe_success"] else 1


if __name__ == "__main__":
    sys.exit(main())
