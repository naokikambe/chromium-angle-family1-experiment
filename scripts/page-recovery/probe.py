#!/usr/bin/env python3
"""Observe existing Mac browser bundles without modifying their contents.

All browser runs use fresh profiles and a local fixture. Imported CDP transport
is pinned to the user's repository; see README.md for provenance.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import os
from pathlib import Path
import plistlib
import re
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
import zlib

from cdp_transport import WebSocket, diagnostic_event

VMODULE = ("process_requirement=2,mach_port_rendezvous_mac=2,"
           "child_process_launcher_helper_mac=2,network_service_instance_impl=2,"
           "url_loader=2,url_loader_factory=2,storage_partition_impl=2")
MACHO_MAGIC = {bytes.fromhex(x) for x in
               ("feedface", "cefaedfe", "feedfacf", "cffaedfe", "cafebabe", "bebafeca", "cafebabf", "bfbafeca")}
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # Loopback CDP only.


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fresh_dir(path):
    path = Path(path).expanduser().absolute()
    path.mkdir(parents=True, exist_ok=False, mode=0o700)
    return path


def mac_context():
    if sys.platform != "darwin":
        raise RuntimeError("Run inventory/probe on the target Mac; this host is not macOS")
    if os.geteuid() == 0:
        raise RuntimeError("Run from the logged-in GUI user's Terminal, not as root")
    console_uid = os.stat("/dev/console").st_uid
    if console_uid != os.geteuid():
        raise RuntimeError("The current user does not own /dev/console; use that GUI user's Terminal")
    return {"uid": os.geteuid(), "console_uid": console_uid,
            "os_version": subprocess.check_output(["/usr/bin/sw_vers"], text=True).strip(),
            "machine": subprocess.check_output(["/usr/bin/uname", "-m"], text=True).strip()}


def app_executable(app):
    app = Path(app).expanduser().resolve(strict=True)
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    name = info.get("CFBundleExecutable", "")
    if not name or Path(name).name != name:
        raise RuntimeError("Invalid CFBundleExecutable")
    executable = app / "Contents/MacOS" / name
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise RuntimeError("Browser executable is missing")
    return app, executable, info


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def macho_files(app):
    result = []
    for root, dirs, files in os.walk(app, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(root) / d).is_symlink()]
        for name in files:
            path = Path(root) / name
            if path.is_symlink():
                continue
            with path.open("rb") as stream:
                if stream.read(4) in MACHO_MAGIC:
                    result.append(path)
    return sorted(result)


def capture(command, destination, timeout=15):
    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        output = process.stdout + process.stderr
        code = process.returncode
    except subprocess.TimeoutExpired:
        output, code = "COMMAND_TIMEOUT\n", 124
    Path(destination).write_text(output, encoding="utf-8")
    return code, output


def inventory(args):
    context = mac_context()
    app, executable, info = app_executable(args.app)
    out = fresh_dir(args.out)
    records = []
    targets = [app] + macho_files(app)
    for index, path in enumerate(targets):
        label = f"{index:03d}"
        code, details = capture(["/usr/bin/codesign", "-dvvv", str(path)], out / f"{label}-signature.txt")
        capture(["/usr/bin/codesign", "-d", "--entitlements", ":-", str(path)], out / f"{label}-entitlements.txt")
        capture(["/usr/bin/codesign", "-d", "-r-", str(path)], out / f"{label}-requirements.txt")
        capture(["/usr/bin/codesign", "--verify", "--strict", "--verbose=4", str(path)], out / f"{label}-verify.txt")
        def value(key):
            match = re.search(r"^" + re.escape(key) + r"=(.*)$", details, re.M)
            return match.group(1) if match else None
        records.append({"path": str(path.relative_to(app)) or ".", "signature_exit": code,
                        "identifier": value("Identifier"), "team": value("TeamIdentifier"),
                        "authorities": re.findall(r"^Authority=(.*)$", details, re.M),
                        "flags": re.findall(r"flags=([^\n]+)", details),
                        "sha256": sha256(path) if path.is_file() else None,
                        "evidence_prefix": label})
    capture(["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=4", str(app)], out / "bundle-verify.txt")
    capture(["/usr/sbin/scutil", "--proxy"], out / "system-proxy.txt")
    capture(["/usr/bin/security", "find-identity", "-v", "-p", "codesigning"], out / "valid-identities.txt")
    write_json(out / "inventory.json", {"schema": "page-recovery-inventory-v1", "app": str(app),
               "executable": str(executable), "main_hash": sha256(executable), "context": context,
               "bundle_identifier": info.get("CFBundleIdentifier"), "version": info.get("CFBundleShortVersionString"),
               "components": records})
    print(out / "inventory.json")
    return 0


def fixture(nonce):
    return ("""<!doctype html><meta charset=utf-8><title>PAGE_RECOVERY_""" + nonce + """</title>
<style>body{background:white;color:black;font:20px sans-serif}#patch{width:96px;height:96px;background:rgb(0,160,0)}</style>
<h1 id=body-marker>BODY_OK_""" + nonce + """</h1><p id=js-marker>WAITING</p><div id=patch></div>
<canvas id=canvas width=8 height=8></canvas><script>
window.__recovery={nonce:'""" + nonce + """',js_ok:true,canvas_ok:false,fetch_ok:null};
document.getElementById('js-marker').textContent='JS_OK_""" + nonce + """';
try{let c=document.getElementById('canvas').getContext('2d');c.fillStyle='rgb(255,0,0)';c.fillRect(0,0,8,8);
let p=c.getImageData(0,0,1,1).data;window.__recovery.canvas_ok=p[0]===255&&p[1]===0&&p[2]===0;}catch(e){window.__recovery.canvas_error=e.name;}
if(location.protocol==='http:')fetch('echo.json',{cache:'no-store'}).then(r=>r.json()).then(x=>window.__recovery.fetch_ok=x.nonce===window.__recovery.nonce).catch(e=>{window.__recovery.fetch_ok=false;window.__recovery.fetch_error=e.name;});
</script>""").encode("utf-8")


class FixtureHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == f"/{self.server.nonce}/page.html":
            payload, content_type, status = self.server.page, "text/html; charset=utf-8", 200
        elif path == f"/{self.server.nonce}/echo.json":
            payload, content_type, status = json.dumps({"nonce": self.server.nonce}).encode(), "application/json", 200
        else:
            payload, content_type, status = b"not found", "text/plain", 404
        with self.server.events_lock:
            self.server.events.append({"time": time.time(), "path": path, "status": status})
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_):
        pass


class FixtureServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, nonce, page):
        self.nonce, self.page = nonce, page
        self.events, self.events_lock = [], threading.Lock()
        super().__init__(("127.0.0.1", 0), FixtureHandler)


class CDP:
    def __init__(self, url, event_file):
        # Close a socket even if the transport's handshake constructor fails.
        transport = WebSocket.__new__(WebSocket)
        try:
            transport.__init__(url, event_file)
        except Exception:
            if getattr(transport, "sock", None):
                transport.close()
            raise
        self.ws = transport
        self.events = []
        self.next_id = 0

    def call(self, method, params=None, timeout=4):
        self.next_id += 1
        call_id = self.next_id
        self.ws.send_json({"id": call_id, "method": method, "params": params or {}})
        deadline = time.monotonic() + timeout
        while True:
            message = self.ws.recv_message(deadline)
            if "method" in message:
                summary = diagnostic_event(message)
                if summary is None and message["method"] in ("Inspector.targetCrashed", "Inspector.detached", "Runtime.exceptionThrown"):
                    summary = {"method": message["method"], "params": message.get("params")}
                if summary:
                    self.events.append(summary)
                    self.ws.event_log.write(json.dumps(summary) + "\n")
                    self.ws.event_log.flush()
            if message.get("id") == call_id:
                if "error" in message:
                    raise RuntimeError(str(message["error"]))
                return message.get("result", {})


def png_green(data):
    """Check the captured interior of the fixture patch, not screenshot existence."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return False
    pos, chunks, width, height, bpp = 8, [], 0, 0, 0
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind, payload = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + length]
        pos += length + 12
        if kind == b"IHDR":
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            if depth != 8 or color not in (2, 6) or interlace != 0 or width * height > 10000:
                return False
            bpp = 3 if color == 2 else 4
        elif kind == b"IDAT":
            chunks.append(payload)
        elif kind == b"IEND":
            break
    if not width or not height or not bpp:
        return False
    raw, stride = zlib.decompress(b"".join(chunks)), width * bpp
    if len(raw) != height * (stride + 1):
        return False
    previous = bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        kind, row = raw[start], bytearray(raw[start + 1:start + 1 + stride])
        for x in range(stride):
            a, b, c = (row[x - bpp] if x >= bpp else 0), previous[x], (previous[x - bpp] if x >= bpp else 0)
            if kind == 1: predictor = a
            elif kind == 2: predictor = b
            elif kind == 3: predictor = (a + b) // 2
            elif kind == 4:
                p = a + b - c
                distances = (abs(p - a), abs(p - b), abs(p - c))
                predictor = (a, b, c)[distances.index(min(distances))]
            elif kind == 0: predictor = 0
            else: return False
            row[x] = (row[x] + predictor) % 256
        for x in range(0, stride, bpp):
            if any(abs(row[x + i] - expected) > 3 for i, expected in enumerate((0, 160, 0))):
                return False
            if bpp == 4 and row[x + 3] != 255:
                return False
        previous = row
    return True


EXPRESSION = """(()=>{let x=window.__recovery;let p=document.getElementById('patch');let r=p&&p.getBoundingClientRect();return {url:location.href,title:document.title,body:document.body&&document.body.textContent,probe:x||null,rect:r?{x:r.x,y:r.y,width:r.width,height:r.height}:null};})()"""


def classify(result):
    if not result.get("cdp_connected"):
        return "CDP_OR_STARTUP_FAILED"
    if not result.get("document_ok"):
        if result["transport"] == "http":
            return "HTTP_RESPONSE_TO_DOCUMENT_FAILED" if result.get("server_page_received") else "HTTP_REQUEST_NOT_RECEIVED"
        return "LOCAL_DOCUMENT_FAILED"
    if result["transport"] == "http" and not (result.get("server_page_received") and result.get("http_document_200")):
        return "HTTP_EVIDENCE_INCOMPLETE"
    if result["transport"] == "http" and not result.get("fetch_ok"):
        return "SUBRESOURCE_FETCH_FAILED"
    if not result.get("visual_patch_ok"):
        return "DOCUMENT_OK_VISUAL_CHECK_FAILED"
    if not result.get("canvas_ok"):
        return "DOCUMENT_OK_CANVAS_FAILED"
    return "FIXTURE_PASS_GUI_CONFIRMATION_PENDING"


def run_one(executable, page, server, out, transport, browser_args, timeout, observe_seconds=0):
    out.mkdir(mode=0o700)
    profile = out / "profile"
    profile.mkdir(mode=0o700)
    local_file = out / "fixture.html"
    local_file.write_bytes(page)
    nonce = server.nonce
    url = {"data": "data:text/html;base64," + base64.b64encode(page).decode(),
           "file": local_file.as_uri(),
           "http": f"http://127.0.0.1:{server.server_port}/{nonce}/page.html"}[transport]
    result = {"schema": "page-recovery-probe-v1", "transport": transport, "nonce": nonce,
              "cdp_connected": False, "document_ok": False, "canvas_ok": False,
              "fetch_ok": False, "visual_patch_ok": False, "http_document_200": False,
              "gui_confirmed": None, "errors": []}
    command = [str(executable), "--no-first-run", "--no-default-browser-check", "--disable-sync",
               "--disable-background-networking", "--enable-logging=stderr", "--v=1", f"--vmodule={VMODULE}",
               "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0",
               f"--user-data-dir={profile}", f"--log-net-log={out / 'netlog.json'}"] + browser_args + ["about:blank"]
    write_json(out / "launch.json", {"argv": command})
    start = time.time()
    process, cdp = None, None
    with (out / "browser-stdout.log").open("wb") as stdout, (out / "browser-stderr.log").open("wb") as stderr, (out / "events.jsonl").open("w") as events:
        try:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
            result["pid"] = process.pid
            deadline = time.monotonic() + min(12, timeout)
            while time.monotonic() < deadline:
                active_port = profile / "DevToolsActivePort"
                if process.poll() is not None:
                    raise RuntimeError(f"Browser exited before CDP: {process.returncode}")
                if active_port.exists():
                    port = int(active_port.read_text().splitlines()[0])
                    try:
                        with OPENER.open(f"http://127.0.0.1:{port}/json/list", timeout=1) as response:
                            targets = json.load(response)
                        target = next((t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")), None)
                        if target: break
                    except (OSError, ValueError):
                        pass
                time.sleep(0.1)
            else:
                raise TimeoutError("No page CDP target within startup budget")
            cdp = CDP(target["webSocketDebuggerUrl"], events)
            result["cdp_connected"] = True
            for method in ("Page.enable", "Network.enable", "Runtime.enable"):
                cdp.call(method)
            deadline = time.monotonic() + timeout
            try:
                result["navigation"] = cdp.call("Page.navigate", {"url": url}, timeout=min(8, timeout))
            except Exception as exc:
                result["errors"].append("navigate: " + str(exc))
            value = {}
            while time.monotonic() < deadline:
                try:
                    evaluation = cdp.call("Runtime.evaluate", {"expression": EXPRESSION, "returnByValue": True}, timeout=min(3, max(0.1, deadline-time.monotonic())))
                    value = evaluation.get("result", {}).get("value") or {}
                    probe = value.get("probe") or {}
                    if probe.get("nonce") == nonce and probe.get("js_ok") and (transport != "http" or probe.get("fetch_ok") is not None):
                        break
                except Exception as exc:
                    result["errors"].append("evaluate: " + str(exc))
                    break
                time.sleep(0.2)
            probe = value.get("probe") or {}
            result["document_ok"] = (value.get("url") == url and value.get("title") == "PAGE_RECOVERY_" + nonce
                                     and "BODY_OK_" + nonce in value.get("body", "") and probe.get("nonce") == nonce and probe.get("js_ok") is True)
            result["canvas_ok"], result["fetch_ok"] = probe.get("canvas_ok") is True, probe.get("fetch_ok") is True
            write_json(out / "document.json", value)
            try:
                screenshot = cdp.call("Page.captureScreenshot", {"format": "png"}, timeout=4)
                (out / "page.png").write_bytes(base64.b64decode(screenshot["data"]))
                rect = value.get("rect")
                if rect and result["document_ok"]:
                    clip = {"x": rect["x"] + rect["width"] / 2, "y": rect["y"] + rect["height"] / 2, "width": 8, "height": 8, "scale": 1}
                    screenshot = cdp.call("Page.captureScreenshot", {"format": "png", "clip": clip}, timeout=4)
                    data = base64.b64decode(screenshot["data"])
                    (out / "visual-patch.png").write_bytes(data)
                    result["visual_patch_ok"] = png_green(data)
            except Exception as exc:
                result["errors"].append("screenshot: " + str(exc))
            result["http_document_200"] = any(e.get("method") == "Network.responseReceived" and e.get("type") == "Document" and e.get("status") == 200 for e in cdp.events)
            result["network_failures"] = [e for e in cdp.events if e.get("method") in ("Network.loadingFailed", "Inspector.targetCrashed", "Inspector.detached")]
            if observe_seconds:
                print(f"Inspect the {transport} page in the GUI; it will close in {observe_seconds} seconds.", flush=True)
                time.sleep(observe_seconds)
        except Exception as exc:
            result["errors"].append(str(exc))
        finally:
            if cdp:
                try: cdp.call("Browser.close", timeout=1)
                except Exception: pass
                cdp.ws.close()
            if process:
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try: os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError: pass
                    try: process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=3)
                result["returncode"] = process.returncode
    result["duration_seconds"] = round(time.time() - start, 2)
    with server.events_lock:
        entries = [e for e in server.events if e["time"] >= start]
    write_json(out / "server-events.json", entries)
    result["server_page_received"] = any(e["path"] == f"/{nonce}/page.html" and e["status"] == 200 for e in entries)
    result["classification"] = classify(result)
    write_json(out / "result.json", result)
    return result


def probe(args):
    context = mac_context()
    app, executable, _ = app_executable(args.app)
    out = fresh_dir(args.out)
    before = sha256(executable)
    write_json(out / "context.json", {"context": context, "app": str(app), "main_hash_before": before, "browser_args": args.browser_arg})
    nonce = uuid.uuid4().hex
    page = fixture(nonce)
    server = FixtureServer(nonce, page)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    results = []
    try:
        for transport in args.transports.split(","):
            results.append(run_one(executable, page, server, out / transport, transport, args.browser_arg, args.timeout, args.observe_seconds))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    write_json(out / "summary.json", {"results": results, "main_hash_unchanged": before == sha256(executable), "gui_confirmation_required": True})
    for result in results:
        print(result["transport"] + ": " + result["classification"])
    print("Evidence: " + str(out))
    return 0 if all(r["classification"] == "FIXTURE_PASS_GUI_CONFIRMATION_PENDING" for r in results) else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("inventory", "probe"):
        command = sub.add_parser(name)
        command.add_argument("--app", required=True)
        command.add_argument("--out", required=True, help="A new result directory; existing directories are refused")
        command.set_defaults(action=inventory if name == "inventory" else probe)
        if name == "probe":
            command.add_argument("--timeout", type=float, default=20)
            command.add_argument("--transports", default="data,file,http")
            command.add_argument("--browser-arg", action="append", default=[])
            command.add_argument("--observe-seconds", type=int, default=0, help="Keep each observed page open for a GUI check (0..60)")
    args = parser.parse_args()
    if args.command == "probe":
        modes = args.transports.split(",")
        if not modes or len(set(modes)) != len(modes) or any(x not in {"data", "file", "http"} for x in modes):
            parser.error("transports must be a unique comma-separated selection of data,file,http")
        if not 5 <= args.timeout <= 60:
            parser.error("timeout must be 5..60 seconds per navigation")
        if not 0 <= args.observe_seconds <= 60:
            parser.error("observe-seconds must be 0..60")
        if any(a.startswith(("--user-data-dir", "--remote-debugging-", "--log-net-log")) for a in args.browser_arg):
            parser.error("browser arguments may not override the isolated profile, CDP, or NetLog")
    try:
        return args.action(args)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
