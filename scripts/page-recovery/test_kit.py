#!/usr/bin/env python3
"""Portable checks for false-positive prevention and signing-plan boundaries."""
import base64
import io
import json
from pathlib import Path
import plistlib
import sqlite3
import struct
import tempfile
import threading
import time
import unittest
import zlib
from unittest.mock import patch

import probe
import persistent_cookie_runner as persistence
import sign_once


def png(rgb, filter_type=0):
    width, height, bpp = 8, 8, 3
    row = bytes(rgb) * width
    rows, previous = [], bytes(len(row))
    for _ in range(height):
        encoded = bytearray()
        for x, value in enumerate(row):
            a, b, c = (row[x-bpp] if x >= bpp else 0), previous[x], (previous[x-bpp] if x >= bpp else 0)
            p = a+b-c
            delta = (abs(p-a), abs(p-b), abs(p-c))
            predictors = (0, a, b, (a+b)//2, (a,b,c)[delta.index(min(delta))])
            encoded.append((value-predictors[filter_type]) % 256)
        rows.append(bytes([filter_type]) + encoded)
        previous = row
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind+data))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width,height,8,2,0,0,0)) + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b"")


class ProbeTests(unittest.TestCase):
    def passing(self):
        return {"transport":"http", "cdp_connected":True, "document_ok":True,
                "server_page_received":True,"http_document_200":True,"fetch_ok":True,
                "visual_patch_ok":True,"canvas_ok":True}

    def test_http_status_or_dom_alone_never_proves_rendering(self):
        for field in ("server_page_received","http_document_200","document_ok","fetch_ok","visual_patch_ok","canvas_ok"):
            result = self.passing()
            result[field] = False
            self.assertNotEqual(probe.classify(result), "FIXTURE_PASS_GUI_CONFIRMATION_PENDING", field)
        self.assertEqual(probe.classify(self.passing()), "FIXTURE_PASS_GUI_CONFIRMATION_PENDING")

    def test_page_target_wait_can_continue_past_legacy_twelve_second_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory)
            (profile / "DevToolsActivePort").write_text("9222\n/devtools/browser/test\n")

            class RunningProcess:
                returncode = None

                def poll(self):
                    return None

            payload = json.dumps([{
                "type": "page",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/test",
            }]).encode()
            with patch("probe.time.monotonic", side_effect=[0, 0, 12.5]), \
                    patch("probe.time.sleep"), \
                    patch("probe.OPENER.open", side_effect=[OSError("not ready"), io.BytesIO(payload)]):
                target = probe.wait_for_page_target(profile, RunningProcess(), 13)
            self.assertEqual(target["type"], "page")
            self.assertTrue(target["webSocketDebuggerUrl"].endswith("/test"))

    def test_no_http_request_is_distinct_from_response_without_document(self):
        result = self.passing()
        result["document_ok"] = False
        result["server_page_received"] = False
        self.assertEqual(probe.classify(result), "HTTP_REQUEST_NOT_RECEIVED")
        result["server_page_received"] = True
        self.assertEqual(probe.classify(result), "HTTP_RESPONSE_TO_DOCUMENT_FAILED")

    def test_visual_check_rejects_blank_or_wrong_color_for_all_png_filters(self):
        for filter_type in range(5):
            self.assertTrue(probe.png_green(png((0,160,0), filter_type)), filter_type)
            self.assertFalse(probe.png_green(png((255,255,255), filter_type)), filter_type)
        self.assertFalse(probe.png_green(b"not a screenshot"))

    def test_post_observation_is_separate_timestamped_sample_with_network_evidence(self):
        nonce = "b" * 32
        screenshot = base64.b64encode(png((0,160,0))).decode("ascii")

        class FakeCDP:
            events = [
                {"method": "Network.responseReceived", "type": "Document", "status": 200},
                {"method": "Network.loadingFailed", "type": "Fetch", "error_text": "blocked"},
            ]

            def call(self, method, params=None, timeout=None):
                if method == "Runtime.evaluate":
                    return {"result": {"value": {
                        "url": "http://fixture.test/" + nonce,
                        "title": "PAGE_RECOVERY_" + nonce,
                        "body": "BODY_OK_" + nonce,
                        "rect": {"x": 0, "y": 0, "width": 8, "height": 8},
                        "probe": {"nonce": nonce, "js_ok": True, "canvas_ok": True, "fetch_ok": True},
                    }}}
                if method == "Page.captureScreenshot":
                    return {"data": screenshot}
                raise AssertionError(method)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pre_result = {"classification": "HTTP_REQUEST_NOT_RECEIVED", "document_ok": False}
            (root / "result.json").write_text(json.dumps(pre_result))
            post = probe.capture_post_observation(
                FakeCDP(), "http", "http://fixture.test/" + nonce, nonce,
                root / "post-observation", 0, "2026-10-12T00:00:00Z",
            )
            saved = json.loads((root / "post-observation/result.json").read_text())
            self.assertEqual(post, saved)
            self.assertEqual(json.loads((root / "result.json").read_text()), pre_result)
            self.assertEqual(saved["sample"], "post-observation-wait")
            self.assertTrue(saved["capture_started_at"].endswith("Z"))
            self.assertTrue(saved["capture_finished_at"].endswith("Z"))
            self.assertTrue(saved["document_ok"])
            self.assertTrue(saved["canvas_ok"])
            self.assertTrue(saved["fetch_ok"])
            self.assertTrue(saved["http_document_200_event_during_wait"])
            self.assertEqual(len(saved["network_events"]), 2)
            self.assertTrue(saved["network_events_snapshot_at"].endswith("Z"))
            self.assertTrue(all("collected_at" not in event for event in saved["network_events"]))
            self.assertTrue((root / "post-observation/page.png").is_file())
            self.assertTrue((root / "post-observation/visual-patch.png").is_file())

            # If the only document 200 predates the wait, it is not copied into
            # the post-wait delta or reported as an event during the wait.
            earlier_only = probe.capture_post_observation(
                FakeCDP(), "http", "http://fixture.test/" + nonce, nonce,
                root / "earlier-only", 2, "2026-10-12T00:00:00Z",
            )
            self.assertEqual(earlier_only["network_events"], [])
            self.assertFalse(earlier_only["http_document_200_event_during_wait"])

    def test_post_observation_records_cdp_errors_and_continues_capture(self):
        screenshot = base64.b64encode(png((0,160,0))).decode("ascii")

        class FailingCDP:
            events = [{"method": "Network.loadingFailed", "error_text": "blocked"}]

            def call(self, method, params=None, timeout=None):
                if method == "Runtime.evaluate":
                    raise TimeoutError("runtime did not respond")
                if method == "Page.captureScreenshot":
                    return {"data": screenshot}
                raise AssertionError(method)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = probe.capture_post_observation(
                FailingCDP(), "http", "http://fixture.test/", "c" * 32,
                root / "post-observation", 0, "2026-10-12T00:00:00Z",
            )
            self.assertEqual(record["capture_errors"][0]["step"], "runtime-evaluate")
            self.assertTrue(record["capture_errors"][0]["observed_at"].endswith("Z"))
            self.assertTrue(record["screenshot"]["captured"])
            self.assertEqual(record["network_events"][0]["method"], "Network.loadingFailed")
            self.assertTrue((root / "post-observation/result.json").is_file())

    def test_fixture_server_distinguishes_case_nonce_and_response(self):
        server = probe.FixtureServer("active", probe.fixture("active"))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with probe.OPENER.open(f"http://127.0.0.1:{server.server_port}/active/echo.json", timeout=2) as response:
                self.assertEqual(json.load(response), {"nonce":"active"})
            with self.assertRaises(Exception):
                probe.OPENER.open(f"http://127.0.0.1:{server.server_port}/old/page.html", timeout=2)
            self.assertEqual([(e["path"],e["status"]) for e in server.events], [("/active/echo.json",200),("/old/page.html",404)])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_full_probe_lifecycle_records_success_and_missing_http_separately(self):
        nonce = "a"*32
        page = probe.fixture(nonce)
        server = probe.FixtureServer(nonce,page)
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        mock = Path(__file__).parent / "mock_browser.py"
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                success = probe.run_one(mock,page,server,root / "pass","http",[],5)
                self.assertEqual(success["classification"],"FIXTURE_PASS_GUI_CONFIRMATION_PENDING",success)
                self.assertTrue((root / "pass/page.png").is_file())
                failed = probe.run_one(mock,page,server,root / "fail","http",["--simulate-http-blocked"],5)
                self.assertEqual(failed["classification"],"HTTP_REQUEST_NOT_RECEIVED",failed)
                self.assertTrue((root / "fail/result.json").is_file())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


class SigningTests(unittest.TestCase):
    def fake_app(self, root):
        app = root / "Chromium.app"
        def bundle(path, name):
            directory = path / "Contents/MacOS"
            directory.mkdir(parents=True)
            (path / "Contents/Info.plist").write_bytes(plistlib.dumps({"CFBundleExecutable":name}))
            # Thin x86_64 MH_EXECUTE header, enough for plan construction only.
            (directory / name).write_bytes(bytes.fromhex("cffaedfe") + struct.pack("<III", 0x01000007,3,2))
        bundle(app, "Chromium")
        for suffix in ("", " (Renderer)", " (GPU)", " (Aperitif Renderer)", " (Aperitif GPU)"):
            name = "Chromium Helper" + suffix
            bundle(app / "Contents/Helpers" / (name+".app"), name)
        return app

    def test_chromium_helpers_receive_distinct_policy_and_each_host_is_signed_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = self.fake_app(root)
            steps = sign_once.build_commands(app, "0"*40, root / "entitlements")
            self.assertEqual(len(steps), 6)
            self.assertEqual(steps[-1]["target"], ".")
            self.assertEqual(len({s["target"] for s in steps}), len(steps))
            for step in steps:
                argv = step["argv"]
                self.assertNotIn("--force", argv)
                flags = argv[argv.index("--options")+1]
                if step["role"] in ("renderer","gpu"):
                    self.assertNotIn("library", flags)
                    self.assertIn("--entitlements", argv)
                else:
                    self.assertIn("library", flags)

    def test_resource_change_invalidates_frozen_assembly(self):
        with tempfile.TemporaryDirectory() as directory:
            app = self.fake_app(Path(directory))
            resource = app / "Contents/Resources.txt"
            resource.write_text("before")
            before = sign_once.freeze_files(app)
            resource.write_text("after")
            self.assertNotEqual(sign_once.freeze_files(app), before)

    def test_framework_style_internal_links_are_allowed_external_links_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = self.fake_app(root)
            internal = app / "Contents/LinkToMain"
            internal.symlink_to("MacOS/Chromium")
            sign_once.validate_links(app)
            external = app / "Contents/External"
            external.symlink_to(root)
            with self.assertRaises(RuntimeError):
                sign_once.validate_links(app)

    def test_internal_link_is_allowed_when_app_root_uses_a_symlink_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real_parent = root / "real"
            real_parent.mkdir()
            app = self.fake_app(real_parent)
            (app / "Contents/LinkToMain").symlink_to("MacOS/Chromium")
            alias_parent = root / "alias"
            alias_parent.symlink_to(real_parent, target_is_directory=True)

            sign_once.validate_links(alias_parent / app.name)

    def test_broken_bundle_links_are_not_signed(self):
        with tempfile.TemporaryDirectory() as directory:
            app = self.fake_app(Path(directory))
            (app / "Contents/Broken").symlink_to("missing")
            with self.assertRaises(FileNotFoundError):
                sign_once.validate_links(app)

    def test_adhoc_or_invalid_signature_is_not_accepted_as_unsigned(self):
        with tempfile.TemporaryDirectory() as directory:
            app = self.fake_app(Path(directory))
            for output in ((0,"Signature=adhoc"),(1,"invalid signature"),(124,"COMMAND_TIMEOUT")):
                with patch.object(sign_once,"capture",return_value=output):
                    with self.assertRaises(RuntimeError):
                        sign_once.unsigned(app, Path(directory))


class PersistentCookieTests(unittest.TestCase):
    def test_browser_command_keeps_stock_gpu_and_normal_keychain_defaults(self):
        executable = Path("/test/Chromium")
        profile = Path("/test/new-profile")
        command = persistence.browser_command(executable, profile)
        self.assertIn(f"--user-data-dir={profile}", command)
        self.assertFalse(any(argument.startswith("--disable-gpu") for argument in command))
        self.assertNotIn("--use-mock-keychain", command)
        self.assertFalse(any(argument.startswith("--log-net-log") for argument in command))
        self.assertNotIn("--v=1", command)

    def test_fixture_sets_and_checks_a_nonsecret_cookie_without_logging_its_value(self):
        nonce = "d" * 32
        cookie_name = "phase5_persistence_check"

        class FakeServer:
            def __init__(self):
                self.nonce, self.cookie_name = nonce, cookie_name
                self.cookie_value = "synthetic-cookie-value"
                self.events, self.events_lock = [], threading.Lock()

        class FakeHandler(persistence.CookieHandler):
            def __init__(self, path, cookie=""):
                self.path = path
                self.headers = {"Cookie": cookie}
                self.server = FakeServer()
                self.wfile = __import__("io").BytesIO()
                self.sent_headers = {}
                self.status = None

            def send_response(self, status):
                self.status = status

            def send_header(self, key, value):
                self.sent_headers[key] = value

            def end_headers(self):
                pass

        seed = FakeHandler(f"/{nonce}/seed.html")
        seed.do_GET()
        self.assertIn(f"BODY_OK_{nonce}".encode(), seed.wfile.getvalue())
        self.assertIn(f"{cookie_name}=synthetic-cookie-value", seed.sent_headers["Set-Cookie"])
        cookie = f"{cookie_name}=synthetic-cookie-value"
        check = FakeHandler(f"/{nonce}/check.html", cookie)
        check.do_GET()
        self.assertIn(f"BODY_OK_{nonce}".encode(), check.wfile.getvalue())
        echo = FakeHandler(f"/{nonce}/echo.json", cookie)
        echo.do_GET()
        self.assertEqual(json.loads(echo.wfile.getvalue()), {"nonce": nonce, "cookie_ok": True})
        self.assertEqual([x["cookie_present"] for x in (seed.server.events + check.server.events + echo.server.events)],
                         [False, True, True])
        self.assertNotIn(cookie, json.dumps(seed.server.events + check.server.events + echo.server.events))
        self.assertNotIn("synthetic-cookie-value", json.dumps(seed.server.events + check.server.events + echo.server.events))
        self.assertEqual(set(seed.server.events[0]), {"time_unix", "observed_at", "path", "status", "cookie_present"})

    def test_cookie_database_check_reports_only_encryption_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory)
            cookie_dir = profile / "Default" / "Network"
            cookie_dir.mkdir(parents=True)
            database = cookie_dir / "Cookies"
            with sqlite3.connect(database) as connection:
                connection.execute("CREATE TABLE cookies (name TEXT, value TEXT, encrypted_value BLOB, host_key TEXT, expires_utc INTEGER)")
                expiry = int((time.time() + 11644473600 + 3600) * 1_000_000)
                connection.execute("INSERT INTO cookies VALUES (?, ?, ?, ?, ?)",
                                   ("phase5_persistence_check", "", b"v10synthetic-ciphertext", "127.0.0.1", expiry))
            result = persistence.inspect_cookie_database(profile, "phase5_persistence_check")
            self.assertTrue(result["encrypted"])
            self.assertTrue(result["plain_value_empty"])
            self.assertTrue(result["expires_in_future"])
            self.assertEqual(result["encrypted_value_version_prefix"], "v10")
            serialized = json.dumps(result)
            self.assertNotIn("synthetic-ciphertext", serialized)


if __name__ == "__main__":
    unittest.main()
