#!/usr/bin/env python3
"""Synthetic checks for missing/corrupt guards and the fixed publication command."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("launcher", Path(__file__).with_name("safe-push.py"))
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.home.chmod(0o700)
        self.anchor_patch = patch.object(launcher, "APPROVED_ANCHOR", "a" * 40)
        self.anchor_patch.start()
        for name in launcher.FILES:
            p = self.home / name
            p.write_text("# synthetic reviewed guard\n")
            p.chmod(0o700 if name in {"pre-push", "pre-commit", "commit-msg"} else 0o600)
        self.manifest = {"schema": 1, "repo": "/synthetic/repo", "common_dir": "/synthetic/repo/.git",
                         "anchor": "a" * 40, "files": {
                             name: hashlib.sha256((self.home / name).read_bytes()).hexdigest()
                             for name in launcher.FILES}}
        self.write_manifest()

    def write_manifest(self):
        p = self.home / "manifest.json"
        p.write_text(json.dumps(self.manifest))
        p.chmod(0o600)

    def tearDown(self):
        self.anchor_patch.stop()
        self.temp.cleanup()

    def test_reviewed_manifest_loads(self):
        self.assertEqual(launcher.load_guard(self.home), self.manifest)

    def test_missing_guard_blocks_before_git_or_network(self):
        for name in sorted(launcher.FILES | {"manifest.json"}):
            p = self.home / name
            content = p.read_bytes()
            p.unlink()
            with self.subTest(name=name), patch.object(launcher, "git") as git, \
                    patch.object(launcher.subprocess, "run") as run:
                with self.assertRaises(OSError):
                    launcher.publish(self.home, dry_run=True)
                git.assert_not_called()
                run.assert_not_called()
            p.write_bytes(content)
            p.chmod(0o700 if name in {"pre-push", "pre-commit", "commit-msg"} else 0o600)

    def test_corruption_wrong_anchor_and_unsafe_permissions_rejected(self):
        p = self.home / "pre-push"
        original = p.read_bytes()
        p.write_text("# synthetic changed guard\n")
        with self.assertRaises(RuntimeError):
            launcher.load_guard(self.home)
        p.write_bytes(original)
        p.chmod(0o644)
        with self.assertRaises(RuntimeError):
            launcher.load_guard(self.home)
        p.chmod(0o700)
        self.manifest["anchor"] = "b" * 40
        self.write_manifest()
        with self.assertRaises(RuntimeError):
            launcher.load_guard(self.home)

    def test_symlink_guard_rejected(self):
        p = self.home / "pre-push"
        p.unlink()
        p.symlink_to(self.home / "pre-commit")
        with self.assertRaises(RuntimeError):
            launcher.load_guard(self.home)

    def fake_git(self, _repo, *args, **_kwargs):
        if args[0] == "ls-remote":
            return "b" * 40 + "\t" + launcher.BRANCH
        if args[0] == "rev-parse":
            return "c" * 40
        raise AssertionError("unexpected synthetic command")

    def test_guard_disappearing_during_scan_prevents_push(self):
        def gate(_args, **_kwargs):
            (self.home / "pre-push").unlink()
            return subprocess.CompletedProcess([], 0)
        with patch.object(launcher, "preflight_config"), \
                patch.object(launcher, "git", side_effect=self.fake_git), \
                patch.object(launcher.subprocess, "run", side_effect=gate) as run:
            with self.assertRaises(OSError):
                launcher.publish(self.home, dry_run=True)
            self.assertEqual(run.call_count, 1)

    def test_fixed_dry_run_and_failed_scan(self):
        with patch.object(launcher, "preflight_config"), \
                patch.object(launcher, "git", side_effect=self.fake_git), \
                patch.object(launcher.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(launcher.publish(self.home, dry_run=True), 0)
            command = run.call_args_list[-1].args[0]
            self.assertEqual(command[-3:], ["--dry-run", launcher.CANONICAL_URL,
                                           f"{launcher.BRANCH}:{launcher.BRANCH}"])
            self.assertFalse(any(arg.startswith("--force") for arg in command))
        with patch.object(launcher, "preflight_config"), \
                patch.object(launcher, "git", side_effect=self.fake_git), \
                patch.object(launcher.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)) as run:
            self.assertEqual(launcher.publish(self.home, dry_run=False), 1)
            self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
