#!/usr/bin/env python3
"""Focused, synthetic checks for the Stage B WebGL1 runner."""
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
