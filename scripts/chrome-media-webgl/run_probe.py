#!/usr/bin/env python3
"""Run a bounded synthetic CfT media and WebGL probe."""

from __future__ import annotations

import argparse
import hashlib
import http.server
import io
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import uuid


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
PAGE_RECOVERY = REPOSITORY / "scripts" / "page-recovery"
sys.path.insert(0, str(PAGE_RECOVERY))
import probe  # noqa: E402


EXPECTED_VERSION = "154.0.8037.0"
FAMILY1_OPT_IN_ENV = "ANGLE_PHASE5_ENABLE_METAL_FAMILY1"
FAMILY1_ARGUMENTS = (
    "--use-gl=angle",
    "--use-angle=metal",
    "--use-dynamic-angle",
    "--disable-angle-features=requireGpuFamily2",
)
EXPECTED_PIXEL = [0, 160, 0, 255]


def parse_sha256(value: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise argparse.ArgumentTypeError("invalid-sha256")
    return value.lower()


def load_fixture(path_argument: str, expected_hash: str) -> bytes:
    path = Path(path_argument).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError("invalid-fixture")
    data = path.read_bytes()
    if not data or len(data) > 32 * 1024 * 1024:
        raise ValueError("fixture-size-invalid")
    if hashlib.sha256(data).hexdigest() != expected_hash:
        raise ValueError("fixture-integrity-failed")
    return data


def load_browser(app_argument: str) -> tuple[Path, Path, dict]:
    app = Path(app_argument).expanduser().resolve(strict=True)
    if not app.is_dir():
        raise ValueError("invalid-app")
    info_path = app / "Contents" / "Info.plist"
    info = plistlib.loads(info_path.read_bytes())
    executable_name = info.get("CFBundleExecutable")
    if not isinstance(executable_name, str) or Path(executable_name).name != executable_name:
        raise ValueError("invalid-app")
    executable = app / "Contents" / "MacOS" / executable_name
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError("invalid-app")
    return app, executable, info


def verify_signature(app: Path) -> bool:
    try:
        result = subprocess.run(
            ["codesign", "--verify", "--deep", "--strict", str(app)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


class FixtureHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path
        prefix = f"/{self.server.nonce}/"
        if path == prefix:
            payload = self.server.page
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; media-src 'self'; script-src 'unsafe-inline'; "
                "style-src 'unsafe-inline'; connect-src 'none'; object-src 'none'; "
                "base-uri 'none'; form-action 'none'",
            )
            self.end_headers()
            self.wfile.write(payload)
            return

        fixture_name = path.removeprefix(prefix)
        if path != prefix + fixture_name or fixture_name not in self.server.fixtures:
            self.send_error(404)
            return

        payload = self.server.fixtures[fixture_name]
        start, end, status = 0, len(payload) - 1, 200
        range_header = self.headers.get("Range")
        if range_header:
            match = re.fullmatch(r"bytes=(\d+)-(\d*)", range_header)
            if not match:
                self.send_error(416)
                return
            start = int(match.group(1))
            end = min(end, int(match.group(2))) if match.group(2) else end
            if start > end or start >= len(payload):
                self.send_error(416)
                return
            status = 206

        body = payload[start : end + 1]
        content_type = "video/mp4" if fixture_name.endswith(".mp4") else "video/webm"
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(payload)}")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *_args):
        pass


class FixtureServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, nonce: str, page: bytes, fixtures: dict[str, bytes]):
        self.nonce = nonce
        self.page = page
        self.fixtures = fixtures
        super().__init__(("127.0.0.1", 0), FixtureHandler)


def make_page(nonce: str) -> bytes:
    return f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Synthetic media and WebGL probe</title>
<style>
body {{ font: 16px sans-serif; margin: 16px; }}
video {{ display: block; width: 320px; height: 180px; margin: 8px 0; }}
#webgl {{ width: 96px; height: 96px; }}
</style>
<button id="play-control" type="button">Play synthetic videos</button>
<video id="h264" playsinline preload="auto" src="/{nonce}/h264.mp4"></video>
<video id="vp8" playsinline preload="auto" src="/{nonce}/vp8.webm"></video>
<canvas id="webgl" width="96" height="96"></canvas>
<script>
(() => {{
  const state = {{clickCount: 0, webgl: null}};
  const videos = [...document.querySelectorAll('video')];
  document.getElementById('play-control').addEventListener('click', () => {{
    state.clickCount += 1;
    for (const video of videos) {{
      video.dataset.playRequested = 'true';
      video.play().then(() => {{ video.dataset.playResolved = 'true'; }})
        .catch(() => {{ video.dataset.playRejected = 'true'; }});
    }}
  }});
  try {{
    const gl = document.getElementById('webgl').getContext('webgl', {{
      alpha: false, preserveDrawingBuffer: true, failIfMajorPerformanceCaveat: true
    }});
    const result = {{context: !!gl, vertexCompile: false, fragmentCompile: false,
      link: false, draw: false, readback: false, pixel: null, noError: false}};
    if (gl) {{
      const compile = (type, source) => {{
        const shader = gl.createShader(type);
        gl.shaderSource(shader, source);
        gl.compileShader(shader);
        return {{shader, ok: gl.getShaderParameter(shader, gl.COMPILE_STATUS) === true}};
      }};
      const vertex = compile(gl.VERTEX_SHADER,
        'attribute vec2 p; void main() {{ gl_Position=vec4(p,0.0,1.0); }}');
      const fragment = compile(gl.FRAGMENT_SHADER,
        'precision mediump float; void main() {{ gl_FragColor=vec4(0.0,160.0/255.0,0.0,1.0); }}');
      result.vertexCompile = vertex.ok;
      result.fragmentCompile = fragment.ok;
      if (vertex.ok && fragment.ok) {{
        const program = gl.createProgram();
        gl.attachShader(program, vertex.shader);
        gl.attachShader(program, fragment.shader);
        gl.linkProgram(program);
        result.link = gl.getProgramParameter(program, gl.LINK_STATUS) === true;
        if (result.link) {{
          const buffer = gl.createBuffer();
          gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
          gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,3,-1,-1,3]), gl.STATIC_DRAW);
          gl.viewport(0, 0, 96, 96);
          gl.useProgram(program);
          const location = gl.getAttribLocation(program, 'p');
          gl.enableVertexAttribArray(location);
          gl.vertexAttribPointer(location, 2, gl.FLOAT, false, 0, 0);
          gl.drawArrays(gl.TRIANGLES, 0, 3);
          result.draw = true;
          const pixel = new Uint8Array(4);
          gl.readPixels(48, 48, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
          result.pixel = Array.from(pixel);
          result.readback = JSON.stringify(result.pixel) === '[0,160,0,255]';
        }}
      }}
      result.noError = gl.getError() === gl.NO_ERROR;
    }}
    result.pass = result.context && result.vertexCompile && result.fragmentCompile &&
      result.link && result.draw && result.readback && result.noError;
    state.webgl = result;
  }} catch (_) {{
    state.webgl = {{pass: false}};
  }}
  window.__mediaWebglProbe = state;
}})();
</script>""".encode("utf-8")


SNAPSHOT_EXPRESSION = """(() => ({
  clickCount: window.__mediaWebglProbe && window.__mediaWebglProbe.clickCount,
  webgl: window.__mediaWebglProbe && window.__mediaWebglProbe.webgl,
  media: [...document.querySelectorAll('video')].map(video => ({
    fixture: video.id,
    readyState: video.readyState,
    errorCode: video.error ? video.error.code : 0,
    currentTime: video.currentTime,
    paused: video.paused,
    decodedFrames: video.getVideoPlaybackQuality().totalVideoFrames,
    droppedFrames: video.getVideoPlaybackQuality().droppedVideoFrames,
    playResolved: video.dataset.playResolved === 'true',
    playRejected: video.dataset.playRejected === 'true'
  }))
}))()"""


def cdp_value(client, expression: str) -> dict:
    response = client.call(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True},
        timeout=8,
    )
    value = response.get("result", {}).get("value")
    return value if isinstance(value, dict) else {}


def read_browser_endpoint(profile: Path) -> str:
    raw = (profile / "DevToolsActivePort").read_text(encoding="ascii")
    lines = raw.splitlines()
    if len(lines) != 2 or not lines[0].isdigit():
        raise ValueError("invalid-cdp-endpoint")
    port = int(lines[0])
    if not 1 <= port <= 65535 or not re.fullmatch(
        r"/devtools/browser/[A-Za-z0-9_-]{1,128}", lines[1]
    ):
        raise ValueError("invalid-cdp-endpoint")
    return f"ws://127.0.0.1:{port}{lines[1]}"


def collect_gpu_mapping(app: Path, profile: Path, browser_process: subprocess.Popen) -> dict:
    summary = {"browser_process_matched": False, "angle_egl": False,
               "angle_gles": False, "metal": False, "same_gpu_process": False}
    browser_cdp = None
    try:
        browser_cdp = probe.CDP(read_browser_endpoint(profile), io.StringIO())
        response = browser_cdp.call("SystemInfo.getProcessInfo", timeout=8)
        process_info = response.get("processInfo", [])
        browser_ids = {
            item.get("id") for item in process_info
            if isinstance(item, dict) and item.get("type") == "browser"
            and isinstance(item.get("id"), int) and item.get("id") > 0
        }
        gpu_ids = sorted({
            item.get("id") for item in process_info
            if isinstance(item, dict) and item.get("type") == "GPU"
            and isinstance(item.get("id"), int) and item.get("id") > 0
        })
        summary["browser_process_matched"] = browser_process.pid in browser_ids
        if not summary["browser_process_matched"]:
            return summary

        vmmap = shutil.which("vmmap")
        if not vmmap:
            return summary
        for gpu_pid in gpu_ids:
            try:
                result = subprocess.run(
                    [vmmap, "-w", str(gpu_pid)],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=20,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
            if result.returncode != 0:
                continue
            own_lines = [line for line in result.stdout.splitlines() if str(app) in line]
            has_egl = any("libEGL.dylib" in line for line in own_lines)
            has_gles = any("libGLESv2.dylib" in line for line in own_lines)
            has_metal = any("Metal.framework" in line for line in result.stdout.splitlines())
            if has_egl and has_gles and has_metal:
                summary.update({"angle_egl": True, "angle_gles": True,
                                "metal": True, "same_gpu_process": True})
                break
            summary["angle_egl"] = summary["angle_egl"] or has_egl
            summary["angle_gles"] = summary["angle_gles"] or has_gles
            summary["metal"] = summary["metal"] or has_metal
        return summary
    except Exception:
        return summary
    finally:
        if browser_cdp is not None:
            try:
                browser_cdp.ws.close()
            except Exception:
                pass


def stop_browser(process: subprocess.Popen | None, profile: Path | None, client) -> bool:
    if process is None:
        return True

    # Browser.close belongs to the browser target, not the page target used
    # for navigation and input. Ask the browser-level endpoint to exit first.
    browser_cdp = None
    if profile is not None:
        try:
            browser_cdp = probe.CDP(read_browser_endpoint(profile), io.StringIO())
            browser_cdp.call("Browser.close", timeout=4)
        except Exception:
            pass
        finally:
            if browser_cdp is not None:
                try:
                    browser_cdp.ws.close()
                except Exception:
                    pass

    if client is not None:
        try:
            client.ws.close()
        except Exception:
            pass
    try:
        process.wait(timeout=12)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                return False
    return process.returncode == 0


def media_summary(first: dict, second: dict) -> dict:
    first_media = {item.get("fixture"): item for item in first.get("media", [])
                   if isinstance(item, dict)}
    second_media = {item.get("fixture"): item for item in second.get("media", [])
                    if isinstance(item, dict)}
    result = {}
    for name in ("h264", "vp8"):
        before = first_media.get(name, {})
        after = second_media.get(name, {})
        progressed = (isinstance(before.get("currentTime"), (int, float))
                      and isinstance(after.get("currentTime"), (int, float))
                      and after["currentTime"] > before["currentTime"])
        frames = after.get("decodedFrames", 0)
        dropped = after.get("droppedFrames", 0)
        clicked = first.get("clickCount") == 1 and second.get("clickCount") == 1
        resolved = before.get("playResolved") is True and after.get("playResolved") is True
        error_free = before.get("errorCode", 1) == 0 and after.get("errorCode", 1) == 0
        playing = (before.get("readyState", 0) >= 2 and after.get("readyState", 0) >= 2
                   and before.get("paused") is False and after.get("paused") is False)
        result[name] = {
            "play_click_observed": clicked,
            "play_promise_resolved": resolved,
            "progressed": bool(progressed),
            "error_free": error_free,
            "decoded_frames": frames if isinstance(frames, int) else 0,
            "dropped_frames": dropped if isinstance(dropped, int) else 0,
            "pass": bool(clicked and resolved and progressed and error_free and playing
                         and isinstance(frames, int) and frames > 0),
        }
    return result


def base_summary(mode: str) -> dict:
    return {
        "schema": "chrome-media-webgl-summary-v1",
        "browser_version": None,
        "expected_browser_version": EXPECTED_VERSION,
        "mode": mode,
        "signature_valid_before_launch": False,
        "rights_cleared_synthetic_inputs_declared": False,
        "external_navigation_performed": False,
        "media_inputs": {
            "h264": {"sha256": None, "size_bytes": None},
            "vp8": {"sha256": None, "size_bytes": None},
        },
        "media": {
            "h264": {"pass": False},
            "vp8": {"pass": False},
        },
        "webgl1": {"pass": False, "expected_pixel": EXPECTED_PIXEL},
        "same_gpu_process_mapping": {
            "browser_process_matched": False,
            "angle_egl": False,
            "angle_gles": False,
            "metal": False,
            "same_gpu_process": False,
        },
        "probe_completed": False,
        "pass": False,
        "failure_stage": None,
    }


def run(args) -> tuple[dict, Path]:
    output = Path(args.out_dir).expanduser()
    if output.exists():
        raise FileExistsError("output-directory-exists")
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    summary = base_summary(args.mode)
    stage = "browser-input"
    process = client = profile = None
    browser_exit_clean = False
    server = server_thread = None
    temporary_profile = None
    try:
        if not args.confirm_rights_cleared_synthetic_inputs:
            raise ValueError("rights-declaration-required")
        summary["rights_cleared_synthetic_inputs_declared"] = True
        app, executable, info = load_browser(args.app)
        version_matches = info.get("CFBundleShortVersionString") == EXPECTED_VERSION
        summary["browser_version"] = EXPECTED_VERSION if version_matches else None
        if not version_matches:
            raise ValueError("version-mismatch")

        stage = "signature-verification"
        summary["signature_valid_before_launch"] = verify_signature(app)
        if not summary["signature_valid_before_launch"]:
            raise ValueError("signature-invalid")

        stage = "fixture-integrity"
        fixtures = {}
        for fixture_name, path_argument, expected_hash in (
            ("h264.mp4", args.h264_fixture, args.h264_sha256),
            ("vp8.webm", args.vp8_fixture, args.vp8_sha256),
        ):
            data = load_fixture(path_argument, expected_hash)
            fixtures[fixture_name] = data
            media_name = "h264" if fixture_name.endswith(".mp4") else "vp8"
            summary["media_inputs"][media_name] = {
                "sha256": expected_hash,
                "size_bytes": len(data),
            }

        stage = "profile-and-loopback-page"
        nonce = uuid.uuid4().hex
        server = FixtureServer(nonce, make_page(nonce), fixtures)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        temporary_profile = tempfile.TemporaryDirectory(prefix="chrome-media-webgl-")
        profile = Path(temporary_profile.name) / "profile"
        profile.mkdir(mode=0o700)

        stage = "browser-startup"
        environment = os.environ.copy()
        environment.pop(FAMILY1_OPT_IN_ENV, None)
        command = [
            str(executable),
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-sync",
            "--disable-background-networking",
            "--disable-component-update",
            "--remote-debugging-address=127.0.0.1",
            "--remote-debugging-port=0",
            f"--user-data-dir={profile}",
        ]
        if args.mode == "family1":
            command.extend(FAMILY1_ARGUMENTS)
            environment[FAMILY1_OPT_IN_ENV] = "1"
        command.append("about:blank")
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=environment,
            start_new_session=True,
        )
        target = probe.wait_for_page_target(profile, process, 45)
        client = probe.CDP(target["webSocketDebuggerUrl"], io.StringIO())
        client.call("Page.enable", timeout=8)
        client.call("Runtime.enable", timeout=8)

        stage = "synthetic-page"
        page_url = f"http://127.0.0.1:{server.server_port}/{nonce}/"
        client.call("Page.navigate", {"url": page_url}, timeout=30)
        deadline = time.monotonic() + 20
        snapshot = {}
        while time.monotonic() < deadline:
            try:
                snapshot = cdp_value(client, SNAPSHOT_EXPRESSION)
                if snapshot.get("webgl") is not None and len(snapshot.get("media", [])) == 2:
                    break
            except Exception:
                pass
            time.sleep(0.25)
        if len(snapshot.get("media", [])) != 2:
            raise TimeoutError("synthetic-page-timeout")

        stage = "play-button-input"
        client.call("Page.bringToFront", timeout=8)
        button_expression = """(() => {
          const button = document.getElementById('play-control');
          const rect = button && button.getBoundingClientRect();
          return rect && rect.width > 0 && rect.height > 0
            ? {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2}
            : null;
        })()"""
        button_result = client.call(
            "Runtime.evaluate",
            {"expression": button_expression, "returnByValue": True},
            timeout=8,
        )
        button = button_result.get("result", {}).get("value")
        if not isinstance(button, dict):
            raise ValueError("play-control-unavailable")
        x, y = button.get("x"), button.get("y")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise ValueError("play-control-unavailable")
        client.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        client.call("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1
        })
        client.call("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1
        })

        stage = "media-and-webgl-sampling"
        time.sleep(4)
        first = cdp_value(client, SNAPSHOT_EXPRESSION)
        time.sleep(2)
        second = cdp_value(client, SNAPSHOT_EXPRESSION)
        summary["media"] = media_summary(first, second)
        webgl = second.get("webgl") or first.get("webgl") or {}
        pixel = webgl.get("pixel")
        summary["webgl1"] = {
            "shader_compile": webgl.get("vertexCompile") is True
                and webgl.get("fragmentCompile") is True,
            "program_link": webgl.get("link") is True,
            "draw": webgl.get("draw") is True,
            "readback": webgl.get("readback") is True,
            "pixel": pixel if isinstance(pixel, list) and len(pixel) == 4 else None,
            "expected_pixel": EXPECTED_PIXEL,
            "pass": webgl.get("pass") is True and pixel == EXPECTED_PIXEL,
        }

        stage = "same-gpu-process-library-mapping"
        summary["same_gpu_process_mapping"] = collect_gpu_mapping(app, profile, process)
        summary["probe_completed"] = True
        family_mapping_required = args.mode != "family1" or summary[
            "same_gpu_process_mapping"]["same_gpu_process"]
        summary["pass"] = (
            summary["media"]["h264"]["pass"]
            and summary["media"]["vp8"]["pass"]
            and summary["webgl1"]["pass"]
            and family_mapping_required
        )
        stage = None
    except Exception:
        summary["failure_stage"] = stage
    finally:
        browser_exit_clean = stop_browser(process, profile, client)
        if server is not None:
            try:
                server.shutdown()
                server.server_close()
            except Exception:
                pass
        if server_thread is not None:
            server_thread.join(timeout=2)
        if temporary_profile is not None:
            temporary_profile.cleanup()

    summary["browser_exited_cleanly"] = browser_exit_clean
    if summary["failure_stage"] is None and not browser_exit_clean:
        summary["pass"] = False
        summary["failure_stage"] = "browser-cleanup"
    summary_path = output / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary, summary_path


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, _message):
        print(json.dumps({"schema": "chrome-media-webgl-summary-v1",
                          "pass": False, "failure_stage": "arguments"}))
        raise SystemExit(2)


def main() -> int:
    parser = SafeArgumentParser(description="Probe synthetic video and WebGL in Chrome for Testing 154.")
    parser.add_argument("--app", required=True, help="Path to the Chrome for Testing application bundle")
    parser.add_argument("--mode", choices=("default", "family1"), required=True)
    parser.add_argument("--h264-fixture", required=True, help="Path to a rights-cleared H.264 MP4 fixture")
    parser.add_argument("--h264-sha256", required=True, type=parse_sha256)
    parser.add_argument("--vp8-fixture", required=True, help="Path to a rights-cleared VP8 WebM fixture")
    parser.add_argument("--vp8-sha256", required=True, type=parse_sha256)
    parser.add_argument(
        "--confirm-rights-cleared-synthetic-inputs",
        action="store_true",
        help="Confirm both media inputs are synthetic and cleared for use",
    )
    parser.add_argument("--out-dir", required=True, help="New directory for the safe summary")
    args = parser.parse_args()
    if sys.platform != "darwin":
        print(json.dumps({"schema": "chrome-media-webgl-summary-v1",
                          "pass": False, "failure_stage": "unsupported-platform"}))
        return 2
    try:
        summary, _ = run(args)
    except Exception:
        print(json.dumps({"schema": "chrome-media-webgl-summary-v1",
                          "mode": args.mode, "pass": False,
                          "failure_stage": "output-directory"}))
        return 2
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
