#!/usr/bin/env python3
"""Verify one synthetic Chromium cookie survives a clean exit and relaunch.

The runner uses one new, dedicated profile for both launches. It never prints
cookie values, reads passwords, changes Keychain ACLs, or reuses an old profile.
Run it only from the logged-in GUI user's Terminal on the target Mac.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import http.server
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid

import probe


FAMILY1_BROWSER_ARGUMENTS = (
    "--use-gl=angle",
    "--use-angle=metal",
    "--use-dynamic-angle",
    "--disable-angle-features=requireGpuFamily2",
)
FAMILY1_OPT_IN_ENV = "ANGLE_PHASE5_ENABLE_METAL_FAMILY1"


def validated_runtime_options(browser_arguments, metal_family1_experiment):
    """Accept only the fixed ANGLE Family 1 option set used in Stage B."""
    arguments = tuple(browser_arguments or ())
    unknown = sorted(set(arguments) - set(FAMILY1_BROWSER_ARGUMENTS))
    if unknown:
        raise ValueError("unsupported browser argument: " + ", ".join(unknown))
    if len(arguments) != len(set(arguments)):
        raise ValueError("duplicate browser arguments are not accepted")
    if arguments and not metal_family1_experiment:
        raise ValueError("custom browser arguments require --metal-family1-experiment")
    if metal_family1_experiment and set(arguments) != set(FAMILY1_BROWSER_ARGUMENTS):
        raise ValueError("the Family 1 experiment requires all four reviewed ANGLE arguments")
    inherited_opt_in = os.environ.get(FAMILY1_OPT_IN_ENV)
    if inherited_opt_in not in (None, "1"):
        raise ValueError(f"{FAMILY1_OPT_IN_ENV} has an unsupported value")
    if inherited_opt_in == "1" and not metal_family1_experiment:
        raise ValueError(f"{FAMILY1_OPT_IN_ENV}=1 requires --metal-family1-experiment")
    # Retain the reviewed order regardless of the order repeated on the CLI.
    ordered_arguments = tuple(arg for arg in FAMILY1_BROWSER_ARGUMENTS if arg in arguments)
    return ordered_arguments, ("1" if metal_family1_experiment else None)


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def page(nonce: str, phase: str, cookie_ok: bool) -> bytes:
    body_marker = f"BODY_OK_{nonce}"
    return f"""<!doctype html><meta charset=utf-8><title>PAGE_RECOVERY_{nonce}_{phase}</title>
<style>body{{background:white;color:black;font:20px sans-serif}}#patch{{width:96px;height:96px;background:rgb(0,160,0)}}</style>
<h1 id=body-marker>{body_marker}</h1><p id=js-marker>WAITING</p><div id=patch></div>
<canvas id=canvas width=8 height=8></canvas><script>
window.__recovery={{nonce:{json.dumps(nonce)},phase:{json.dumps(phase)},cookie_ok:{str(cookie_ok).lower()},fetch_ok:null,canvas_ok:false}};
document.getElementById('js-marker').textContent='JS_OK_'+window.__recovery.nonce;
try{{let c=document.getElementById('canvas').getContext('2d');c.fillStyle='rgb(255,0,0)';c.fillRect(0,0,8,8);
let p=c.getImageData(0,0,1,1).data;window.__recovery.canvas_ok=p[0]===255&&p[1]===0&&p[2]===0;}}catch(e){{window.__recovery.canvas_error=e.name;}}
fetch('echo.json',{{cache:'no-store'}}).then(r=>r.json()).then(x=>{{window.__recovery.fetch_ok=x.nonce===window.__recovery.nonce&&x.cookie_ok===true;window.__recovery.echo_cookie_ok=x.cookie_ok;}}).catch(e=>{{window.__recovery.fetch_ok=false;window.__recovery.fetch_error=e.name;}});
</script>""".encode("utf-8")


class CookieHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        expected_name = self.server.cookie_name
        expected_value = self.server.cookie_value
        cookie_header = self.headers.get("Cookie", "")
        cookie_present = f"{expected_name}={expected_value}" in cookie_header.split("; ")
        status, content_type, payload, set_cookie = 200, "text/html; charset=utf-8", b"", False
        if path == f"/{self.server.nonce}/seed.html":
            payload = page(self.server.nonce, "seed", False)
            set_cookie = True
        elif path == f"/{self.server.nonce}/check.html":
            payload = page(self.server.nonce, "check", cookie_present)
            if not cookie_present:
                payload = payload.replace(f"BODY_OK_{self.server.nonce}".encode(),
                                           f"COOKIE_MISSING_{self.server.nonce}".encode())
        elif path == f"/{self.server.nonce}/echo.json":
            content_type = "application/json"
            payload = json.dumps({"nonce": self.server.nonce, "cookie_ok": cookie_present}).encode("utf-8")
        else:
            status, content_type, payload = 404, "text/plain", b"not found"
        with self.server.events_lock:
            self.server.events.append({"time_unix": time.time(), "observed_at": timestamp(),
                                       "path": path, "status": status,
                                       "cookie_present": cookie_present})
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        if set_cookie:
            self.send_header("Set-Cookie", f"{expected_name}={expected_value}; Max-Age=3600; Path=/; SameSite=Lax")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_):
        pass


class CookieServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, nonce, cookie_value=None):
        self.nonce = nonce
        self.cookie_name = "phase5_persistence_check"
        self.cookie_value = cookie_value or secrets.token_urlsafe(18)
        self.events = []
        self.events_lock = threading.Lock()
        super().__init__(("127.0.0.1", 0), CookieHandler)


def inspect_cookie_database(profile: Path, cookie_name: str):
    database = profile / "Default" / "Network" / "Cookies"
    if not database.is_file():
        database = profile / "Default" / "Cookies"
    if not database.is_file():
        return {"database_present": False, "encrypted": False, "error": "cookie database not found"}
    uri = database.resolve().as_uri() + "?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=2) as connection:
            rows = connection.execute(
                "SELECT value, encrypted_value, expires_utc FROM cookies WHERE name=? AND host_key IN (?, ?)",
                (cookie_name, "127.0.0.1", ".127.0.0.1"),
            ).fetchall()
    except sqlite3.Error as exc:
        return {"database_present": True, "database_path": str(database), "encrypted": False,
                "error": f"sqlite read failed: {type(exc).__name__}"}
    if len(rows) != 1:
        return {"database_present": True, "database_path": str(database), "encrypted": False,
                "matching_rows": len(rows), "error": "expected exactly one synthetic cookie row"}
    clear_value, encrypted_value, expires_utc = rows[0]
    encrypted = bytes(encrypted_value or b"")
    prefix = encrypted[:3].decode("ascii", errors="replace") if encrypted else ""
    current_chromium_time = int((time.time() + 11644473600) * 1_000_000)
    return {"database_present": True, "database_path": str(database), "encrypted": bool(encrypted),
            "matching_rows": 1, "plain_value_empty": clear_value == "",
            "encrypted_value_length": len(encrypted), "encrypted_value_version_prefix": prefix,
            "expires_in_future": int(expires_utc or 0) > current_chromium_time,
            "error": None if encrypted and clear_value == "" and int(expires_utc or 0) > current_chromium_time
            else "cookie is not encrypted or its persistent expiry is not in the future"}


def runtime_snapshot(cdp, nonce, phase):
    expression = """(() => {const p=window.__recovery||{};const r=document.getElementById('patch').getBoundingClientRect();
return {url:location.href,title:document.title,body:document.body.innerText,rect:{x:r.x,y:r.y,width:r.width,height:r.height},probe:p};})()"""
    result = cdp.call("Runtime.evaluate", {"expression": expression, "returnByValue": True}, timeout=4)
    value = result.get("result", {}).get("value") or {}
    state = value.get("probe") or {}
    return {"url_ok": value.get("url", "").endswith(f"/{nonce}/{phase}.html" if phase != "check" else f"/{nonce}/check.html"),
            "title_ok": value.get("title") == f"PAGE_RECOVERY_{nonce}_{phase}",
            "body_ok": f"BODY_OK_{nonce}" in value.get("body", ""),
            "js_ok": f"JS_OK_{nonce}" in value.get("body", ""),
            "cookie_ok": state.get("cookie_ok") is True,
            "fetch_ok": state.get("fetch_ok") is True,
            "canvas_ok": state.get("canvas_ok") is True,
            "rect": value.get("rect"), "value": value}


def browser_command(executable, profile, browser_arguments=()):
    return [str(executable), "--no-first-run", "--no-default-browser-check", "--disable-sync",
            "--disable-background-networking", "--enable-logging=stderr", "--remote-debugging-address=127.0.0.1",
            "--remote-debugging-port=0", f"--user-data-dir={profile}", *browser_arguments, "about:blank"]


def browser_launch_configuration(executable, profile, browser_arguments=(), metal_family1_opt_in=None):
    return {"argv": browser_command(executable, profile, browser_arguments),
            "runtime_environment": {FAMILY1_OPT_IN_ENV: metal_family1_opt_in}}


def validate_navigation_timeout(value):
    if not 5 <= value <= 120:
        raise ValueError("navigation-timeout must be 5..120 seconds")


def launch_phase(executable, profile, out, server, phase, startup_timeout,
                 observe_seconds=0, page_wait_seconds=60, launch_config=None,
                 navigation_timeout=60):
    out.mkdir(mode=0o700)
    path = "seed.html" if phase == "seed" else "check.html"
    url = f"http://127.0.0.1:{server.server_port}/{server.nonce}/{path}"
    launch_config = launch_config or browser_launch_configuration(executable, profile)
    command = launch_config["argv"]
    metal_family1_opt_in = launch_config["runtime_environment"][FAMILY1_OPT_IN_ENV]
    probe.write_json(out / "launch.json", launch_config)
    result = {"phase": phase, "url": url, "started_at": timestamp(), "pid": None,
              "navigation_timeout_seconds": navigation_timeout,
              "navigated": False, "http_document_200": False, "document_ok": False,
              "js_ok": False, "fetch_ok": False, "canvas_ok": False,
              "visual_patch_ok": False, "cookie_ok": False, "errors": []}
    process, cdp = None, None
    with (out / "browser-stdout.log").open("wb") as stdout, (out / "browser-stderr.log").open("wb") as stderr, (out / "events.jsonl").open("w") as events:
        try:
            process_environment = os.environ.copy()
            process_environment.pop(FAMILY1_OPT_IN_ENV, None)
            if metal_family1_opt_in is not None:
                process_environment[FAMILY1_OPT_IN_ENV] = metal_family1_opt_in
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                       start_new_session=True, env=process_environment)
            result["pid"] = process.pid
            target = probe.wait_for_page_target(profile, process, startup_timeout)
            cdp = probe.CDP(target["webSocketDebuggerUrl"], events)
            for method in ("Page.enable", "Network.enable", "Runtime.enable"):
                cdp.call(method)
            cdp.call("Page.navigate", {"url": url}, timeout=navigation_timeout)
            result["navigated"] = True
            deadline = time.monotonic() + page_wait_seconds
            snapshot = {}
            last_evaluation_error = None
            while time.monotonic() < deadline:
                try:
                    snapshot = runtime_snapshot(cdp, server.nonce, phase)
                    state = snapshot.get("value", {}).get("probe", {})
                    if snapshot["title_ok"] and state.get("fetch_ok") is not None:
                        break
                except Exception as exc:
                    last_evaluation_error = f"{type(exc).__name__}: {exc}"
                time.sleep(0.2)
            if last_evaluation_error:
                result["errors"].append("last runtime evaluation: " + last_evaluation_error)
            result["url_ok"] = snapshot.get("url_ok", False)
            result["title_ok"] = snapshot.get("title_ok", False)
            result["document_ok"] = snapshot.get("body_ok", False)
            result["js_ok"] = snapshot.get("js_ok", False)
            result["fetch_ok"] = snapshot.get("fetch_ok", False)
            result["canvas_ok"] = snapshot.get("canvas_ok", False)
            result["cookie_ok"] = snapshot.get("cookie_ok", False)
            probe.write_json(out / "document.json", snapshot.get("value", {}))
            result["http_document_200"] = any(
                event.get("method") == "Network.responseReceived" and event.get("type") == "Document"
                and event.get("status") == 200 for event in cdp.events)
            try:
                image = cdp.call("Page.captureScreenshot", {"format": "png"}, timeout=5)
                (out / "page.png").write_bytes(base64.b64decode(image["data"]))
                rect = snapshot.get("rect")
                if rect:
                    clip = {"x": rect["x"] + rect["width"] / 2, "y": rect["y"] + rect["height"] / 2,
                            "width": 8, "height": 8, "scale": 1}
                    patch_image = cdp.call("Page.captureScreenshot", {"format": "png", "clip": clip}, timeout=5)
                    data = base64.b64decode(patch_image["data"])
                    (out / "visual-patch.png").write_bytes(data)
                    result["visual_patch_ok"] = probe.png_green(data)
            except Exception as exc:
                result["errors"].append(f"screenshot: {type(exc).__name__}")
            if observe_seconds:
                print(f"Observe {phase} page now for {observe_seconds} seconds.", flush=True)
                time.sleep(observe_seconds)
        except Exception as exc:
            result["errors"].append(f"{type(exc).__name__}: {exc}")
        finally:
            if cdp:
                try:
                    cdp.call("Browser.close", timeout=2)
                except Exception:
                    pass
                try:
                    cdp.ws.close()
                except Exception:
                    pass
            if process:
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    result["errors"].append("browser did not exit after Browser.close; process left running for verified follow-up")
                result["returncode"] = process.returncode
    result["finished_at"] = timestamp()
    probe.write_json(out / "result.json", result)
    return result


def run(args):
    navigation_timeout = getattr(args, "navigation_timeout", 60)
    validate_navigation_timeout(navigation_timeout)
    browser_arguments, metal_family1_opt_in = validated_runtime_options(
        args.browser_arg, args.metal_family1_experiment)
    context = probe.mac_context()
    app, executable, info = probe.app_executable(args.app)
    if info.get("CFBundleIdentifier") != "org.chromium.Chromium":
        raise RuntimeError("persistent cookie runner accepts only org.chromium.Chromium stock builds")
    output = Path(args.out).expanduser().absolute()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    profile = output / "profile"
    profile.mkdir(mode=0o700)
    launch_config = browser_launch_configuration(
        executable, profile, browser_arguments, metal_family1_opt_in)
    nonce = uuid.uuid4().hex
    cookie_name = "phase5_persistence_check"
    context_record = {"context": context, "app": str(app), "main_hash_before": probe.sha256(executable),
                      "bundle_identifier": info.get("CFBundleIdentifier"),
                      "version": info.get("CFBundleShortVersionString"), "nonce": nonce,
                      "profile": str(profile), "browser_arguments": list(browser_arguments),
                      "navigation_timeout_seconds": navigation_timeout,
                      "browser_argv": launch_config["argv"],
                      "runtime_environment": launch_config["runtime_environment"],
        "cookie_name": cookie_name, "cookie_value_logged": False, "raw_netlog_enabled": False}
    probe.write_json(output / "context.json", context_record)
    server = CookieServer(nonce)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        print("If the exact matching Safe Storage prompt appears, answer only after separate owner authorization for this prompt; otherwise leave it unanswered. Never choose Always Allow.", flush=True)
        first = launch_phase(executable, profile, output / "launch-1-seed", server, "seed",
                             args.startup_timeout, args.observe_seconds, args.page_wait_seconds,
                             launch_config, navigation_timeout)
        with server.events_lock:
            first_events = list(server.events)
        expected_seed = any(e["path"] == f"/{nonce}/seed.html" and e["status"] == 200 for e in first_events)
        if not (first.get("returncode") == 0 and first.get("http_document_200") and first.get("document_ok") and first.get("js_ok")
                and first.get("fetch_ok") and first.get("canvas_ok") and first.get("visual_patch_ok") and expected_seed):
            result = {"classification": "SEED_PHASE_FAILED", "phase1": first,
                      "cookie_storage": {"checked": False}, "phase2": None}
            with server.events_lock:
                result["server_events"] = list(server.events)
        else:
            cookie_storage = inspect_cookie_database(profile, cookie_name)
            print("If another Safe Storage prompt appears, do not answer it; record failed continuity.", flush=True)
            second = launch_phase(executable, profile, output / "launch-2-restart", server, "check",
                                  args.startup_timeout, args.observe_seconds, args.page_wait_seconds,
                                  launch_config, navigation_timeout)
            with server.events_lock:
                events = list(server.events)
            check_event = next((e for e in events if e["path"] == f"/{nonce}/check.html"), None)
            echo_event = next((e for e in reversed(events) if e["path"] == f"/{nonce}/echo.json"), None)
            resumed = bool(check_event and check_event["cookie_present"] and echo_event and echo_event["cookie_present"])
            result = {"classification": "PERSISTENT_COOKIE_PASS" if (
                cookie_storage.get("encrypted") and cookie_storage.get("plain_value_empty")
                and cookie_storage.get("expires_in_future")
                and second.get("returncode") == 0 and second.get("http_document_200") and second.get("document_ok") and second.get("js_ok")
                and second.get("fetch_ok") and second.get("canvas_ok") and second.get("visual_patch_ok")
                and second.get("cookie_ok") and resumed) else "PERSISTENT_COOKIE_FAIL",
                "phase1": first, "cookie_storage": cookie_storage, "phase2": second,
                "server_events": events, "restart_cookie_received": resumed}
        with server.events_lock:
            probe.write_json(output / "server-events.json", list(server.events))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    result["main_hash_unchanged"] = probe.sha256(executable) == context_record["main_hash_before"]
    result["completed_at"] = timestamp()
    probe.write_json(output / "result.json", result)
    print(result["classification"])
    print(f"Evidence: {output}")
    return 0 if result["classification"] == "PERSISTENT_COOKIE_PASS" and result.get("main_hash_unchanged") else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True)
    parser.add_argument("--out", required=True, help="New evidence directory; existing directories are refused")
    parser.add_argument("--startup-timeout", type=int, default=45)
    parser.add_argument("--navigation-timeout", type=int, default=60,
                        help="CDP Page.navigate timeout for both launches (5..120 seconds)")
    parser.add_argument("--page-wait-seconds", type=int, default=60,
                        help="Wait for page, JS, and fetch callbacks (5..120 seconds)")
    parser.add_argument("--observe-seconds", type=int, default=0,
                        help="Keep each browser phase visible for a human check (0..60)")
    parser.add_argument("--browser-arg", action="append", default=[],
                        help="Reviewed ANGLE Family 1 argument; repeat all four with --metal-family1-experiment")
    parser.add_argument("--metal-family1-experiment", action="store_true",
                        help="Set ANGLE_PHASE5_ENABLE_METAL_FAMILY1=1 for both launches with all reviewed ANGLE arguments")
    args = parser.parse_args()
    if not 5 <= args.startup_timeout <= 60:
        parser.error("startup-timeout must be 5..60 seconds")
    if not 5 <= args.navigation_timeout <= 120:
        parser.error("navigation-timeout must be 5..120 seconds")
    if not 5 <= args.page_wait_seconds <= 120:
        parser.error("page-wait-seconds must be 5..120 seconds")
    if not 0 <= args.observe_seconds <= 60:
        parser.error("observe-seconds must be 0..60")
    try:
        validated_runtime_options(args.browser_arg, args.metal_family1_experiment)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        return run(args)
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
