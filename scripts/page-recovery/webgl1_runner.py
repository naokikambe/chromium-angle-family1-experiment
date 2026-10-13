#!/usr/bin/env python3
"""Run a nonce-bound WebGL 1 shader draw/readback against a reviewed ANGLE build.

This prepares automated and GUI evidence; GPU-process library mapping still
requires separate review. It never modifies or signs the app bundle.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid

import probe
import persistent_cookie_runner as cookie_runner


FAMILY1_ARGUMENTS = cookie_runner.FAMILY1_BROWSER_ARGUMENTS
OPT_IN_ENV = cookie_runner.FAMILY1_OPT_IN_ENV
STATE_WAIT_SECONDS = 20


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def validate_options(startup_timeout, navigation_timeout, observe_seconds):
    if not 5 <= startup_timeout <= 60:
        raise ValueError("startup-timeout must be 5..60 seconds")
    if not 5 <= navigation_timeout <= 120:
        raise ValueError("navigation-timeout must be 5..120 seconds")
    if not 0 <= observe_seconds <= 60:
        raise ValueError("observe-seconds must be 0..60")
    cookie_runner.validated_runtime_options(FAMILY1_ARGUMENTS, True)


def family1_launch_configuration(executable, profile):
    return cookie_runner.browser_launch_configuration(executable, profile, FAMILY1_ARGUMENTS, "1")


def webgl_page(nonce):
    # Shader sources are fixed ES 1.00; no remote code, libraries, 2D canvas,
    # CSS-colored success patch, or alternate rendering backend is involved.
    return f"""<!doctype html><meta charset=utf-8>
<title>PHASE5_WEBGL1_{nonce}</title>
<style>body{{font:18px sans-serif;background:#fff;color:#111}}canvas{{width:96px;height:96px;border:1px solid #555}}</style>
<h1 id="body-marker">WEBGL1_BODY_{nonce}</h1><p id="js-marker">WEBGL1_WAITING</p>
<p id="result-marker">DRAW_PENDING READBACK_PENDING PIXEL=none</p>
<canvas id="webgl-canvas" width="96" height="96"></canvas>
<script>
(() => {{
  const nonce = {json.dumps(nonce)};
  const state = {{nonce, context_ok:false, vertex_compile_ok:false, fragment_compile_ok:false,
    program_link_ok:false, draw_ok:false, readback_ok:false, pixel:null,
    no_gl_error:false, gl_error:null, error:null, vertex_shader_info_log:'',
    fragment_shader_info_log:'', program_info_log:'', gl_version:null,
    shading_language_version:null, gl_vendor:null, gl_renderer:null,
    unmasked_vendor:null, unmasked_renderer:null}};
  const canvas = document.getElementById('webgl-canvas');
  const compile = (gl, type, source) => {{
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    return {{shader, ok:gl.getShaderParameter(shader, gl.COMPILE_STATUS) === true,
      info_log:String(gl.getShaderInfoLog(shader) || '').slice(0,4096)}};
  }};
  try {{
    const gl = canvas.getContext('webgl', {{preserveDrawingBuffer:true, alpha:false,
      failIfMajorPerformanceCaveat:true}});
    if (!gl) {{
      state.error = 'webgl-context-unavailable';
    }} else {{
      state.context_ok = true;
      const vertex = compile(gl, gl.VERTEX_SHADER,
        'attribute vec2 a_position; void main(){{gl_Position=vec4(a_position,0.0,1.0);}}');
      const fragment = compile(gl, gl.FRAGMENT_SHADER,
        'precision mediump float; void main(){{gl_FragColor=vec4(0.0,160.0/255.0,0.0,1.0);}}');
      state.vertex_compile_ok = vertex.ok;
      state.fragment_compile_ok = fragment.ok;
      state.vertex_shader_info_log = vertex.info_log;
      state.fragment_shader_info_log = fragment.info_log;
      state.gl_version = String(gl.getParameter(gl.VERSION) || '').slice(0,512);
      state.shading_language_version = String(gl.getParameter(gl.SHADING_LANGUAGE_VERSION) || '').slice(0,512);
      state.gl_vendor = String(gl.getParameter(gl.VENDOR) || '').slice(0,512);
      state.gl_renderer = String(gl.getParameter(gl.RENDERER) || '').slice(0,512);
      const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
      if (debugInfo) {{
        state.unmasked_vendor = String(gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) || '').slice(0,512);
        state.unmasked_renderer = String(gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) || '').slice(0,512);
      }}
      if (vertex.ok && fragment.ok) {{
        const program = gl.createProgram();
        gl.attachShader(program, vertex.shader);
        gl.attachShader(program, fragment.shader);
        gl.linkProgram(program);
        state.program_link_ok = gl.getProgramParameter(program, gl.LINK_STATUS) === true;
        state.program_info_log = String(gl.getProgramInfoLog(program) || '').slice(0,4096);
        if (state.program_link_ok) {{
          const buffer = gl.createBuffer();
          gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
          gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 3,-1, -1,3]), gl.STATIC_DRAW);
          gl.viewport(0, 0, canvas.width, canvas.height);
          gl.useProgram(program);
          const location = gl.getAttribLocation(program, 'a_position');
          gl.enableVertexAttribArray(location);
          gl.vertexAttribPointer(location, 2, gl.FLOAT, false, 0, 0);
          gl.drawArrays(gl.TRIANGLES, 0, 3);
          state.draw_ok = true;
          const pixel = new Uint8Array(4);
          gl.readPixels(48, 48, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
          state.pixel = Array.from(pixel);
          state.readback_ok = state.pixel[0] === 0 && state.pixel[1] === 160 &&
            state.pixel[2] === 0 && state.pixel[3] === 255;
        }} else {{
          state.error = 'program-link-failed';
        }}
      }} else {{
        state.error = 'shader-compile-failed';
      }}
      state.gl_error = gl.getError();
      state.no_gl_error = state.gl_error === gl.NO_ERROR;
      if (!state.no_gl_error && !state.error) state.error = 'gl-error';
    }}
  }} catch (error) {{
    state.error = 'javascript-' + String(error && error.name || 'error').slice(0,48);
  }}
  state.pass = state.context_ok && state.vertex_compile_ok && state.fragment_compile_ok &&
    state.program_link_ok && state.draw_ok && state.readback_ok && state.no_gl_error;
  window.__phase5_webgl1 = state;
  document.getElementById('js-marker').textContent = state.pass ?
    'WEBGL1_JS_OK_' + nonce : 'WEBGL1_JS_FAIL_' + nonce;
  const pixel = state.pixel ? state.pixel.join(',') : 'none';
  document.getElementById('result-marker').textContent =
    'DRAW_' + (state.draw_ok ? 'OK' : 'FAIL') + ' READBACK_' +
    (state.readback_ok ? 'OK' : 'FAIL') + ' PIXEL=' + pixel;
}})();
</script>""".encode("utf-8")


def accepted_state(state, nonce):
    return (isinstance(state, dict) and state.get("nonce") == nonce
            and state.get("context_ok") is True
            and state.get("vertex_compile_ok") is True
            and state.get("fragment_compile_ok") is True
            and state.get("program_link_ok") is True
            and state.get("draw_ok") is True
            and state.get("readback_ok") is True
            and state.get("pixel") == [0, 160, 0, 255]
            and state.get("no_gl_error") is True
            and state.get("gl_error") == 0
            and state.get("error") in (None, "")
            and state.get("pass") is True)


class WebGLFixtureHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == f"/{self.server.nonce}/webgl1.html":
            status, content_type, payload = 200, "text/html; charset=utf-8", self.server.page
        else:
            status, content_type, payload = 404, "text/plain", b"not found"
        with self.server.events_lock:
            self.server.events.append({"observed_at": timestamp(), "nonce": self.server.nonce,
                                       "path": path, "status": status})
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_):
        pass


class WebGLFixtureServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, nonce, page):
        self.nonce, self.page = nonce, page
        self.events, self.events_lock = [], threading.Lock()
        super().__init__(("127.0.0.1", 0), WebGLFixtureHandler)


def read_state(cdp, nonce):
    expression = """(() => {const s=window.__phase5_webgl1||{};const c=document.getElementById('webgl-canvas');const r=c&&c.getBoundingClientRect();return {url:location.href,title:document.title,body:document.body&&document.body.innerText,js_marker:document.getElementById('js-marker')&&document.getElementById('js-marker').textContent,result_marker:document.getElementById('result-marker')&&document.getElementById('result-marker').textContent,rect:r?{x:r.x,y:r.y,width:r.width,height:r.height}:null,state:s};})()"""
    result = cdp.call("Runtime.evaluate", {"expression": expression, "returnByValue": True}, timeout=5)
    value = result.get("result", {}).get("value") or {}
    state = value.get("state") or {}
    return {"document_ok": (value.get("title") == f"PHASE5_WEBGL1_{nonce}"
                            and f"WEBGL1_BODY_{nonce}" in value.get("body", "")),
            "js_ok": value.get("js_marker") == f"WEBGL1_JS_OK_{nonce}",
            "result_marker": value.get("result_marker"),
            "rect": value.get("rect"), "state": state}


def run(args):
    validate_options(args.startup_timeout, args.navigation_timeout, args.observe_seconds)
    output = Path(args.out).expanduser().absolute()
    if output.exists():
        raise FileExistsError("output directory already exists; choose a new evidence directory")
    context = probe.mac_context()
    app, executable, info = probe.app_executable(args.app)
    if info.get("CFBundleIdentifier") != "org.chromium.Chromium":
        raise RuntimeError("WebGL1 runner accepts only an org.chromium.Chromium bundle")
    verified = subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=4", str(app)],
                              capture_output=True, text=True, timeout=60)
    if verified.returncode != 0:
        raise RuntimeError("strict deep codesign verification failed before browser launch")

    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    profile = output / "profile"
    profile.mkdir(mode=0o700)
    nonce = uuid.uuid4().hex
    launch = family1_launch_configuration(executable, profile)
    main_hash_before = probe.sha256(executable)
    context_record = {"context": context, "app": str(app), "bundle_identifier": info.get("CFBundleIdentifier"),
                      "version": info.get("CFBundleShortVersionString"), "main_hash_before": main_hash_before,
                      "codesign_strict_deep_verified": True, "nonce": nonce,
                      "profile": str(profile), "browser_arguments": list(FAMILY1_ARGUMENTS),
                      "browser_argv": launch["argv"], "runtime_environment": launch["runtime_environment"],
                      "startup_timeout_seconds": args.startup_timeout,
                      "navigation_timeout_seconds": args.navigation_timeout,
                      "state_wait_timeout_seconds": STATE_WAIT_SECONDS,
                      "observe_seconds": args.observe_seconds, "raw_netlog_enabled": False,
                      "gui_confirmation_required": True,
                      "same_gpu_pid_library_review_required": True}
    probe.write_json(output / "context.json", context_record)
    probe.write_json(output / "launch.json", launch)

    server = WebGLFixtureServer(nonce, webgl_page(nonce))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/{nonce}/webgl1.html"
    result = {"classification": "WEBGL1_FIXTURE_FAIL_REVIEW_PENDING", "nonce": nonce, "url": url,
              "pid": None, "started_at": timestamp(), "navigated": False,
              "state_wait_timeout_seconds": STATE_WAIT_SECONDS,
              "state_observed_at": None, "gui_observation_started_at": None,
              "gui_observation_finished_at": None,
              "document_ok": False, "js_ok": False, "webgl1_automated_pass": False,
              "same_gpu_pid_library_review_required": True, "gui_confirmation_required": True,
              "errors": []}
    process = cdp = None
    process_environment = os.environ.copy()
    process_environment.pop(OPT_IN_ENV, None)
    process_environment[OPT_IN_ENV] = "1"
    try:
        with (output / "browser-stdout.log").open("wb") as stdout, \
                (output / "browser-stderr.log").open("wb") as stderr, \
                (output / "cdp-events.jsonl").open("w", encoding="utf-8") as events:
            try:
                process = subprocess.Popen(launch["argv"], stdout=stdout, stderr=stderr,
                                           start_new_session=True, env=process_environment)
                result["pid"] = process.pid
                target = probe.wait_for_page_target(profile, process, args.startup_timeout)
                cdp = probe.CDP(target["webSocketDebuggerUrl"], events)
                for method in ("Page.enable", "Network.enable", "Runtime.enable"):
                    cdp.call(method)
                cdp.call("Page.navigate", {"url": url}, timeout=args.navigation_timeout)
                result["navigated"] = True
                deadline = time.monotonic() + STATE_WAIT_SECONDS
                snapshot = {}
                while time.monotonic() < deadline:
                    try:
                        snapshot = read_state(cdp, nonce)
                        if snapshot["state"]:
                            result["state_observed_at"] = timestamp()
                        if snapshot["state"] and (snapshot["document_ok"] or snapshot["state"].get("error")):
                            break
                    except Exception as exc:
                        result["errors"].append(f"runtime-evaluate: {type(exc).__name__}")
                    time.sleep(0.2)
                result["document_ok"] = snapshot.get("document_ok", False)
                result["js_ok"] = snapshot.get("js_ok", False)
                result["result_marker"] = snapshot.get("result_marker")
                result["webgl1_state"] = snapshot.get("state", {})
                result["webgl1_state_accepted"] = accepted_state(result["webgl1_state"], nonce)
                result["rect"] = snapshot.get("rect")
                result["http_document_200"] = any(
                    event.get("method") == "Network.responseReceived" and event.get("type") == "Document"
                    and event.get("status") == 200 for event in cdp.events)
                probe.write_json(output / "document.json", {k: v for k, v in snapshot.items() if k != "state"}
                                 | {"webgl1_state": result["webgl1_state"]})
                try:
                    image = cdp.call("Page.captureScreenshot", {"format": "png"}, timeout=5)
                    (output / "page.png").write_bytes(base64.b64decode(image["data"]))
                    rect = result.get("rect")
                    if rect:
                        clip = {"x": rect["x"] + rect["width"] / 2 - 4,
                                "y": rect["y"] + rect["height"] / 2 - 4,
                                "width": 8, "height": 8, "scale": 1}
                        patch_image = cdp.call("Page.captureScreenshot", {"format": "png", "clip": clip}, timeout=5)
                        patch_data = base64.b64decode(patch_image["data"])
                        (output / "webgl1-readback-patch.png").write_bytes(patch_data)
                        result["screenshot_patch_green"] = probe.png_green(patch_data)
                except Exception as exc:
                    result["errors"].append(f"screenshot: {type(exc).__name__}")
                if args.observe_seconds:
                    result["gui_observation_started_at"] = timestamp()
                    print(f"Observe the WebGL1 page now for {args.observe_seconds} seconds.", flush=True)
                    time.sleep(args.observe_seconds)
                    result["gui_observation_finished_at"] = timestamp()
            except Exception as exc:
                result["errors"].append(f"{type(exc).__name__}: {str(exc)[:300]}")
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
                        result["errors"].append("browser did not exit after Browser.close; process left running")
                    result["returncode"] = process.returncode
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    result["finished_at"] = timestamp()
    result["server_events"] = list(server.events)
    result["main_hash_after"] = probe.sha256(executable)
    result["main_hash_unchanged"] = result["main_hash_after"] == main_hash_before
    if (result.get("returncode") == 0 and result.get("http_document_200") and result.get("document_ok")
            and result.get("js_ok") and result.get("webgl1_state_accepted")
            and result.get("screenshot_patch_green") and result.get("main_hash_unchanged")):
        result["webgl1_automated_pass"] = True
        result["classification"] = "WEBGL1_FIXTURE_PASS_REVIEW_PENDING"
    probe.write_json(output / "result.json", result)
    print(result["classification"])
    print(f"Evidence: {output}")
    return 0 if result["webgl1_automated_pass"] else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True)
    parser.add_argument("--out", required=True, help="New evidence directory; existing directories are refused")
    parser.add_argument("--startup-timeout", type=int, default=45)
    parser.add_argument("--navigation-timeout", type=int, default=60)
    parser.add_argument("--observe-seconds", type=int, default=20)
    args = parser.parse_args()
    try:
        validate_options(args.startup_timeout, args.navigation_timeout, args.observe_seconds)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        return run(args)
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
