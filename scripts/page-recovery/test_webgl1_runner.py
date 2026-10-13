#!/usr/bin/env python3
"""Focused, synthetic checks for the Stage B WebGL1 runner."""
from pathlib import Path
import json
import tempfile
import threading
import unittest
import urllib.request
from types import SimpleNamespace
from unittest.mock import patch

import webgl1_runner as runner


class WebGL1RunnerTests(unittest.TestCase):
    def passing_state(self, nonce="a" * 32):
        return {"nonce": nonce, "context_ok": True, "vertex_compile_ok": True,
                "fragment_compile_ok": True, "program_link_ok": True, "draw_ok": True,
                "readback_ok": True, "pixel": [0, 160, 0, 255], "no_gl_error": True,
                "gl_error": 0, "pass": True}

    def test_acceptance_requires_context_compile_link_draw_readback_and_exact_pixel(self):
        nonce = "a" * 32
        state = self.passing_state(nonce)
        self.assertTrue(runner.accepted_state(state, nonce))
        for key, value in (("context_ok", False), ("vertex_compile_ok", False),
                           ("fragment_compile_ok", False), ("program_link_ok", False),
                           ("draw_ok", False), ("readback_ok", False),
                           ("pixel", [0, 159, 0, 255]), ("no_gl_error", False),
                           ("gl_error", 1282), ("pass", False),
                           ("error", "context-error")):
            with self.subTest(key=key):
                failed = dict(state)
                failed[key] = value
                self.assertFalse(runner.accepted_state(failed, nonce))
        self.assertFalse(runner.accepted_state(None, nonce))
        self.assertFalse(runner.accepted_state(state, "b" * 32))

    def test_fixture_uses_only_webgl_shader_readback_as_render_success(self):
        html = runner.webgl_page("c" * 32).decode("utf-8")
        for required in ("getContext('webgl'", "preserveDrawingBuffer:true",
                         "failIfMajorPerformanceCaveat:true", "COMPILE_STATUS", "LINK_STATUS",
                         "drawArrays(gl.TRIANGLES, 0, 3)", "readPixels(48, 48, 1, 1",
                         "getShaderInfoLog", "getProgramInfoLog", "slice(0,4096)",
                         "WEBGL_debug_renderer_info",
                         "DRAW_", "READBACK_", "WEBGL1_BODY_", "WEBGL1_JS_OK_"):
            self.assertIn(required, html)
        self.assertNotIn("getContext('2d'", html)
        self.assertNotIn("background:rgb(0,160,0)", html)

    def test_launch_configuration_is_exact_reviewed_family1_set(self):
        config = runner.family1_launch_configuration(Path("/synthetic/Chromium"),
                                                     Path("/synthetic/fresh-profile"))
        self.assertEqual(config["argv"][-5:-1], list(runner.FAMILY1_ARGUMENTS))
        self.assertEqual(config["runtime_environment"], {runner.OPT_IN_ENV: "1"})
        self.assertNotIn("--use-mock-keychain", config["argv"])
        self.assertFalse(any("swiftshader" in arg.lower() for arg in config["argv"]))

    def test_loopback_fixture_serves_nonce_page_and_only_safe_event_metadata(self):
        nonce = "d" * 32
        server = runner.WebGLFixtureServer(nonce, runner.webgl_page(nonce))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{server.server_port}/{nonce}/webgl1.html") as response:
                payload = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertIsNone(response.headers.get("Set-Cookie"))
            self.assertIn(nonce, payload)
            self.assertEqual(len(server.events), 1)
            self.assertEqual(server.events[0]["nonce"], nonce)
            self.assertEqual(server.events[0]["path"], f"/{nonce}/webgl1.html")
            self.assertEqual(server.events[0]["status"], 200)
            self.assertEqual(set(server.events[0]), {"observed_at", "nonce", "path", "status"})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_invalid_bounds_fail_before_gui_context_or_output_creation(self):
        for startup, navigation, observe in ((4, 60, 20), (61, 60, 20),
                                             (45, 4, 20), (45, 121, 20),
                                             (45, 60, -1), (45, 60, 61)):
            with self.subTest(startup=startup, navigation=navigation, observe=observe), \
                    tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "not-created"
                args = SimpleNamespace(startup_timeout=startup, navigation_timeout=navigation,
                                       observe_seconds=observe, out=str(output), app="unused")
                with patch.object(runner.probe, "mac_context") as context:
                    with self.assertRaises(ValueError):
                        runner.run(args)
                    context.assert_not_called()
                self.assertFalse(output.exists())

    def test_browser_gpu_info_uses_fresh_local_endpoint_filters_fields_and_closes(self):
        class FakeCDP:
            def __init__(self, url, _events):
                self.url = url
                self.calls = []
                self.closed = False
                self.ws = self

            def call(self, method, params=None, timeout=4):
                self.calls.append((method, params, timeout))
                if method == "SystemInfo.getInfo":
                    return {"gpu": {
                        "auxAttributes": {
                            "glRenderer": "R" * 600, "glVendor": "ANGLE",
                            "glVersion": "OpenGL ES 2.0", "displayType": "ANGLE_METAL",
                            "privateAttribute": "must-not-be-recorded"},
                        "featureStatus": {"webgl": "enabled", "webgl2": "disabled",
                                           **{f"feature-{index}": "enabled"
                                              for index in range(128)}},
                        "glRenderer": "top-level decoy",
                        "machineModelName": "must-not-be-recorded"}}
                if method == "SystemInfo.getProcessInfo":
                    return {"processInfo": [
                        {"type": "browser", "id": 123},
                        {"type": "GPU", "id": 456},
                        {"type": "Network Service", "id": 789},
                        {"type": "GPU", "id": "not-an-id"}]}
                raise AssertionError(method)

            def close(self):
                self.closed = True

        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory)
            (profile / "DevToolsActivePort").write_text(
                "9222\n/devtools/browser/owned-profile-id\n", encoding="ascii")
            clients = []

            def factory(url, events):
                client = FakeCDP(url, events)
                clients.append(client)
                return client

            record = runner.capture_browser_gpu_info(profile, 123, factory)
            self.assertEqual(clients[0].url, "ws://127.0.0.1:9222/devtools/browser/owned-profile-id")
            self.assertEqual(record["status"], "captured")
            self.assertEqual(record["browser_pid"], 123)
            self.assertEqual(record["browser_pid_status"], "matched")
            self.assertTrue(record["observed_at"].endswith("Z"))
            self.assertEqual(record["gpu_process_ids"], [456])
            self.assertEqual(record["gpu"]["glRenderer"], "R" * 512)
            self.assertEqual(record["gpu"]["glVendor"], "ANGLE")
            self.assertEqual(record["gpu"]["glVersion"], "OpenGL ES 2.0")
            self.assertEqual(record["gpu"]["displayType"], "ANGLE_METAL")
            self.assertEqual(record["gpu"]["featureStatus"]["webgl"], "enabled")
            self.assertEqual(record["gpu"]["featureStatus"]["webgl2"], "disabled")
            self.assertEqual(len(record["gpu"]["featureStatus"]), 128)
            self.assertTrue(clients[0].closed)
            self.assertEqual([call[0] for call in clients[0].calls],
                             ["SystemInfo.getInfo", "SystemInfo.getProcessInfo"])
            encoded = json.dumps(record)
            self.assertNotIn("must-not-be-recorded", encoded)
            self.assertNotIn("9222", encoded)
            self.assertNotIn("owned-profile-id", encoded)

    def test_browser_gpu_info_discards_data_on_browser_pid_mismatch(self):
        class FakeCDP:
            def __init__(self, _url, _events):
                self.ws = self
                self.closed = False

            def call(self, method, params=None, timeout=4):
                if method == "SystemInfo.getInfo":
                    return {"gpu": {"auxAttributes": {
                        "glRenderer": "must-be-discarded"},
                        "featureStatus": {"webgl": "enabled"}}}
                return {"processInfo": [
                    {"type": "browser", "id": 999},
                    {"type": "GPU", "id": 456}]}

            def close(self):
                self.closed = True

        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory)
            (profile / "DevToolsActivePort").write_text(
                "9224\n/devtools/browser/owned-id\n", encoding="ascii")
            clients = []

            def factory(url, events):
                client = FakeCDP(url, events)
                clients.append(client)
                return client

            record = runner.capture_browser_gpu_info(profile, 321, factory)
            self.assertEqual(record["status"], "failed")
            self.assertEqual(record["browser_pid_status"], "mismatch")
            self.assertEqual(record["gpu"], {})
            self.assertEqual(record["gpu_process_ids"], [])
            self.assertEqual(record["errors"][-1], {
                "stage": "browser-identity", "type": "BrowserIdentityMismatch"})
            self.assertNotIn("must-be-discarded", json.dumps(record))
            self.assertNotIn('"id": 999', json.dumps(record))
            self.assertTrue(clients[0].closed)

    def test_browser_gpu_info_api_failure_is_separate_and_still_closes(self):
        class FakeCDP:
            def __init__(self, _url, _events):
                self.ws = self
                self.closed = False

            def call(self, method, params=None, timeout=4):
                if method == "SystemInfo.getInfo":
                    raise RuntimeError("sensitive endpoint detail")
                return {"processInfo": [{"type": "GPU", "id": 999}]}

            def close(self):
                self.closed = True

        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory)
            (profile / "DevToolsActivePort").write_text(
                "9223\n/devtools/browser/owned-id\n", encoding="ascii")
            clients = []

            def factory(url, events):
                client = FakeCDP(url, events)
                clients.append(client)
                return client

            record = runner.capture_browser_gpu_info(profile, 321, factory)
            self.assertEqual(record["status"], "partial")
            self.assertEqual(record["gpu_process_ids"], [999])
            self.assertEqual(record["errors"], [{
                "method": "SystemInfo.getInfo", "type": "RuntimeError"}])
            self.assertNotIn("sensitive endpoint detail", json.dumps(record))
            self.assertTrue(clients[0].closed)

    def test_browser_gpu_info_rejects_nonlocal_or_malformed_active_port(self):
        for active_port in (
                "0\n/devtools/browser/id\n",
                "65536\n/devtools/browser/id\n",
                "9222\n/devtools/page/id\n",
                "9222\nws://example.invalid/devtools/browser/id\n"):
            with self.subTest(active_port=active_port), tempfile.TemporaryDirectory() as directory:
                profile = Path(directory)
                (profile / "DevToolsActivePort").write_text(active_port, encoding="ascii")
                factory_called = False

                def factory(_url, _events):
                    nonlocal factory_called
                    factory_called = True
                    raise AssertionError("invalid endpoint must not connect")

                record = runner.capture_browser_gpu_info(profile, 654, factory)
                self.assertEqual(record["status"], "failed")
                self.assertEqual(record["errors"][0]["stage"], "active-port")
                self.assertFalse(factory_called)


if __name__ == "__main__":
    unittest.main()
