#!/usr/bin/env python3
"""Synthetic tests for the narrow OSCrypt histogram reader."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import keychain_histogram as kh
import persistent_cookie_runner as runner


class FakeCDP:
    def __init__(self, processes=None, histograms=None, fail_method=None):
        self.processes = processes if processes is not None else [{"type": "browser", "id": 123}]
        self.histograms = histograms
        self.fail_method = fail_method

    def call(self, method, params=None, timeout=4):
        if method == self.fail_method:
            raise RuntimeError("synthetic CDP failure")
        if method == "SystemInfo.getProcessInfo":
            return {"processInfo": self.processes}
        if method == "Browser.getHistograms":
            return {"histograms": self.histograms}
        raise AssertionError("unexpected CDP method")


def histogram(buckets):
    count = sum(bucket["count"] for bucket in buckets)
    sample_sum = sum(bucket["low"] * bucket["count"] for bucket in buckets)
    return [{"name": kh.HISTOGRAM, "count": count, "sum": sample_sum, "buckets": buckets}]


class HistogramTests(unittest.TestCase):
    def test_verified_found(self):
        record = kh.capture(FakeCDP(histograms=histogram([
            {"low": 0, "high": 1, "count": 2}])), 123, "/synthetic/profile")
        self.assertEqual(record["status"], "verified_found")
        self.assertTrue(record["found"])

    def test_other_is_not_found(self):
        record = kh.capture(FakeCDP(histograms=histogram([
            {"low": 1, "high": 2, "count": 1}])), 123, "/synthetic/profile")
        self.assertEqual(record["status"], "verified_other")
        self.assertFalse(record["found"])

    def test_malformed_and_contradictory_buckets_unavailable(self):
        cases = [
            [{"low": 0, "high": 1, "count": 0}],
            [{"low": 0, "high": 2, "count": 1}],
            [{"low": 1, "high": 2, "count": -1}],
            [{"low": 0, "high": 1, "count": 1}, {"low": 0, "high": 1, "count": 2}],
            [{"low": 0, "high": 1, "count": 1}, {"low": 1, "high": 2, "count": 1}],
            [{"low": 0, "high": 2, "count": 1}],
            [{"low": 3, "high": 4, "count": 1}],
        ]
        for buckets in cases:
            with self.subTest(buckets=buckets):
                record = kh.capture(FakeCDP(histograms=histogram(buckets)), 123, "/synthetic/profile")
                self.assertEqual(record["status"], "unavailable")
                self.assertIsNone(record["found"])

    def test_missing_histogram_and_cdp_error(self):
        for cdp in (FakeCDP(histograms=[]), FakeCDP(fail_method="Browser.getHistograms")):
            self.assertEqual(kh.capture(cdp, 123, "/synthetic/profile")["status"], "unavailable")

    def test_histogram_totals_and_sum_must_match(self):
        for edits in ({"count": 2}, {"sum": 1}, {"count": True}, {"sum": True}, {"sum": None}):
            with self.subTest(edits=edits):
                hist = histogram([{"low": 0, "high": 1, "count": 1}])[0]
                hist.update(edits)
                record = kh.capture(FakeCDP(histograms=[hist]), 123, "/synthetic/profile")
                self.assertEqual(record["status"], "unavailable")

    def test_wrong_pid_rejected(self):
        record = kh.capture(FakeCDP(histograms=histogram([
            {"low": 0, "high": 1, "count": 1}])), 124, "/synthetic/profile")
        self.assertEqual(record["status"], "unavailable")
        self.assertIn("does not match", record["error"])

    def test_both_phases_must_have_verified_found_evidence(self):
        found = {"keychain_histogram": {"status": "verified_found"}}
        self.assertEqual(runner.keychain_histogram_acceptance(found, found),
                         "VERIFIED_FOUND_BOTH_PHASES")
        for incomplete in ({}, {"keychain_histogram": {"status": "unavailable"}},
                           {"keychain_histogram": {"status": "verified_other"}}):
            with self.subTest(incomplete=incomplete):
                self.assertEqual(runner.keychain_histogram_acceptance(incomplete, found),
                                 "INCOMPLETE_OR_NOT_FOUND")
                self.assertEqual(runner.keychain_histogram_acceptance(found, incomplete),
                                 "INCOMPLETE_OR_NOT_FOUND")

    def test_active_port_endpoint_is_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "DevToolsActivePort"
            path.write_text("9222\n/devtools/browser/Synthetic_123\n", encoding="ascii")
            from webgl1_runner import browser_websocket_url
            self.assertEqual(browser_websocket_url(directory), "ws://127.0.0.1:9222/devtools/browser/Synthetic_123")
            fake = FakeCDP(histograms=histogram([{"low": 0, "high": 1, "count": 1}]))
            fake.ws = type("Socket", (), {"close": lambda self: None})()
            with patch.object(runner.probe, "CDP", return_value=fake) as connect:
                observed = runner.capture_keychain_histogram(directory, None, 123)
            connect.assert_called_once_with("ws://127.0.0.1:9222/devtools/browser/Synthetic_123", None)
            self.assertEqual(observed["status"], "verified_found")
            path.write_text("9222\n/devtools/page/not-browser\n", encoding="ascii")
            with self.assertRaises(ValueError):
                browser_websocket_url(directory)


if __name__ == "__main__":
    unittest.main()
