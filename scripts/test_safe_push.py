#!/usr/bin/env python3
"""Focused synthetic tests for the restrictive pre-push policy."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("check-safe-push.py")
SPEC = importlib.util.spec_from_file_location("safe_push", MODULE_PATH)
safe_push = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(safe_push)


class SafePushTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "phase5-page-recovery")
        self.git("config", "user.name", "Synthetic-User")
        self.git("config", "user.email", "123+synthetic-user@users.noreply.github.com")
        (self.repo / "file.txt").write_text("fixture\n", encoding="utf-8")
        self.git("add", "file.txt")
        self.git("commit", "-qm", "synthetic fixture")
        self.anchor = self.head()
        self.git("update-ref", "refs/remotes/origin/phase5-page-recovery", self.anchor)
        self.candidate = self.commit_child("clean continuation")
        self.denied = self.commit_child("synthetic denied ancestry", parent=self.anchor)
        # Create a descendant that merges denied history after a clean anchor.
        tree = self.git("rev-parse", f"{self.candidate}^{{tree}}")
        self.merged = subprocess.check_output(
            ["git", "-C", str(self.repo), "-c", "user.name=Synthetic-User",
             "-c", "user.email=123+synthetic-user@users.noreply.github.com",
             "commit-tree", tree, "-p", self.candidate, "-p", self.denied],
            input=b"synthetic merge\n", text=False).decode().strip()
        self.git("update-ref", "refs/remotes/origin/phase5-page-recovery", self.anchor)
        self.metadata = self.repo.parent / "metadata.json"
        self.mapping = self.repo.parent / "mapping.tsv"
        self.write_metadata([self.denied])

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str) -> str:
        env = os.environ.copy()
        env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"})
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True,
                                       timeout=10, env=env).strip()

    def head(self) -> str:
        return self.git("rev-parse", "HEAD")

    def commit_child(self, message: str, parent: str | None = None) -> str:
        self.git("checkout", "-q", "--detach", parent or self.head())
        filename = message.replace(" ", "-") + ".txt"
        (self.repo / filename).write_text(message + "\n", encoding="utf-8")
        self.git("add", filename)
        self.git("commit", "-qam", message)
        return self.head()

    def write_metadata(self, denied: list[str]) -> None:
        target = self.candidate
        self.mapping.write_text("".join(f"{old}\t{target}\n" for old in denied), encoding="ascii")
        value = {
            "clean_anchor": self.anchor,
            "old_commits": denied,
            "old_commits_count": len(denied),
            "old_commits_sha256": hashlib.sha256(("\n".join(denied) + "\n").encode()).hexdigest(),
            "mapping_sha256": hashlib.sha256(self.mapping.read_bytes()).hexdigest(),
        }
        self.metadata.write_text(json.dumps(value), encoding="utf-8")

    def input(self, local: str, remote: str | None = None, local_ref: str = safe_push.BRANCH,
              remote_ref: str = safe_push.BRANCH) -> bytes:
        return f"{local_ref} {local} {remote_ref} {remote or self.anchor}\n".encode()

    def check(self, data: bytes, *, url: str = safe_push.CANONICAL_URL) -> None:
        safe_push.validate(self.repo, "origin", url, data, self.metadata, self.mapping)

    def test_allowed_fast_forward(self) -> None:
        self.check(self.input(self.candidate))

    def test_old_ancestry_hidden_in_merged_descendant_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            self.check(self.input(self.merged))
        with self.assertRaises(RuntimeError):
            self.check(self.input(self.merged, remote=self.denied))

    def test_missing_and_corrupt_metadata_rejected(self) -> None:
        self.metadata.unlink()
        with self.assertRaises((OSError, RuntimeError)):
            self.check(self.input(self.candidate))
        self.write_metadata([self.denied])
        payload = json.loads(self.metadata.read_text())
        payload["old_commits_sha256"] = "b" * 64
        self.metadata.write_text(json.dumps(payload))
        with self.assertRaises(RuntimeError):
            self.check(self.input(self.candidate))

    def test_missing_corrupt_and_semantically_invalid_mapping_rejected(self) -> None:
        self.mapping.unlink()
        with self.assertRaises(OSError):
            self.check(self.input(self.candidate))
        self.write_metadata([self.denied])
        self.mapping.write_text("x\ty\n", encoding="ascii")
        with self.assertRaises(RuntimeError):
            self.check(self.input(self.candidate))
        self.write_metadata([self.denied])
        payload = json.loads(self.metadata.read_text())
        payload["old_commits"] = []
        payload["old_commits_count"] = 0
        payload["old_commits_sha256"] = hashlib.sha256(b"").hexdigest()
        self.metadata.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(RuntimeError):
            self.check(self.input(self.candidate))
        self.write_metadata([self.denied])
        payload = json.loads(self.metadata.read_text())
        payload["old_commits_count"] += 1
        self.metadata.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(RuntimeError):
            self.check(self.input(self.candidate))

    def test_zero_metadata_count_and_mapping_denial_mismatch_rejected(self) -> None:
        self.write_metadata([self.denied])
        payload = json.loads(self.metadata.read_text())
        payload["old_commits_count"] = 0
        self.metadata.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(RuntimeError):
            self.check(self.input(self.candidate))
        self.write_metadata([self.denied])
        self.mapping.write_text(f"{self.candidate}\t{self.anchor}\n", encoding="ascii")
        payload = json.loads(self.metadata.read_text())
        payload["mapping_sha256"] = hashlib.sha256(self.mapping.read_bytes()).hexdigest()
        self.metadata.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(RuntimeError):
            self.check(self.input(self.candidate))

    def test_creation_deletion_other_ref_tag_and_non_ff_rejected(self) -> None:
        zero = safe_push.ZERO
        cases = [
            self.input(self.candidate, remote=zero),
            self.input(zero),
            self.input(self.candidate, remote_ref="refs/heads/other"),
            self.input(self.candidate, remote_ref="refs/tags/release"),
            self.input(self.candidate, local_ref="refs/tags/release"),
            self.input(self.anchor, remote=self.candidate),
            self.input(self.denied),
        ]
        for case in cases:
            with self.subTest(case=case.decode().strip()):
                with self.assertRaises(RuntimeError):
                    self.check(case)

    def test_wrong_destination_and_multiple_updates_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            self.check(self.input(self.candidate), url="https://example.invalid/repo.git")
        with self.assertRaises(RuntimeError):
            self.check(self.input(self.candidate) + self.input(self.candidate))
        with self.assertRaises(RuntimeError):
            self.check(b"")
        with self.assertRaises(RuntimeError):
            safe_push.validate(self.repo, "upstream", safe_push.CANONICAL_URL,
                               self.input(self.candidate), self.metadata, self.mapping)

    def test_history_override_environment_rejected(self) -> None:
        for name in ("GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_OBJECT_DIRECTORY",
                     "GIT_SHALLOW_FILE", "GIT_GRAFT_FILE", "GIT_REPLACE_REF_BASE"):
            with self.subTest(name=name), patch.dict(os.environ, {name: "synthetic-override"}):
                with self.assertRaises(RuntimeError):
                    self.check(self.input(self.candidate))

    def test_grafts_alternates_shallow_and_replacement_refs_rejected(self) -> None:
        git_dir = Path(self.git("rev-parse", "--git-dir"))
        if not git_dir.is_absolute():
            git_dir = (self.repo / git_dir).resolve()
        grafts = git_dir / "info" / "grafts"
        grafts.parent.mkdir(parents=True, exist_ok=True)
        grafts.write_text("synthetic\n", encoding="ascii")
        with self.assertRaises(RuntimeError):
            self.check(self.input(self.candidate))
        grafts.unlink()

        alternates = git_dir / "objects" / "info" / "alternates"
        alternates.parent.mkdir(parents=True, exist_ok=True)
        alternates.write_text("/synthetic/alternate\n", encoding="ascii")
        with self.assertRaises(RuntimeError):
            self.check(self.input(self.candidate))
        alternates.unlink()

        shallow = git_dir / "shallow"
        shallow.write_text(self.anchor + "\n", encoding="ascii")
        with self.assertRaises(RuntimeError):
            self.check(self.input(self.candidate))
        shallow.unlink()

        self.git("update-ref", f"refs/replace/{self.anchor}", self.candidate)
        with self.assertRaises(RuntimeError):
            self.check(self.input(self.candidate))
        self.git("update-ref", "-d", f"refs/replace/{self.anchor}")

    def test_no_refspec_push_default_nothing_fails_in_local_fixture(self) -> None:
        bare = self.repo.parent / "bare.git"
        self.git("init", "--bare", "--initial-branch=main", str(bare))
        self.git("remote", "add", "fixture", str(bare))
        self.git("config", "push.default", "nothing")
        result = subprocess.run(["git", "-C", str(self.repo), "push", "fixture"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=False, timeout=20, env={**os.environ,
                                    "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                                    "GIT_TERMINAL_PROMPT": "0"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"nothing", result.stderr.lower())

    def gate_process(self, local_sha: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, str(MODULE_PATH), "--repo", str(self.repo),
             "--metadata", str(self.metadata), "--mapping", str(self.mapping),
             "origin", safe_push.CANONICAL_URL],
            input=self.input(local_sha), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=120,
        )

    def test_main_replays_scanner_across_introduced_commits(self) -> None:
        self.assertEqual(self.gate_process(self.candidate).returncode, 0)
        self.git("checkout", "-q", "--detach", self.candidate)
        # Build a bad intermediate tree, then remove it so the candidate tip is clean.
        fake_token = "gh" + "p_" + ("A" * 24)
        unsafe_file = self.repo / "transient.txt"
        unsafe_file.write_text(fake_token + "\n", encoding="utf-8")
        self.git("add", "transient.txt")
        self.git("commit", "-qm", "synthetic intermediate")
        self.head()
        unsafe_file.unlink()
        self.git("add", "-u")
        self.git("commit", "-qm", "synthetic clean tip")
        clean_tip = self.head()
        self.assertNotEqual(self.gate_process(clean_tip).returncode, 0)

        tree = self.git("rev-parse", f"{self.candidate}^{{tree}}")
        invalid_identity = subprocess.check_output(
            ["git", "-C", str(self.repo), "--no-replace-objects", "commit-tree", tree,
             "-p", self.candidate], input=b"synthetic identity\n", text=False,
            env={**os.environ, "GIT_AUTHOR_NAME": "Synthetic Person",
                 "GIT_AUTHOR_EMAIL": "synthetic-person@example.invalid",
                 "GIT_COMMITTER_NAME": "Synthetic-User",
                 "GIT_COMMITTER_EMAIL": "123+synthetic-user@users.noreply.github.com"},
        ).decode().strip()
        self.assertNotEqual(self.gate_process(invalid_identity).returncode, 0)

        message_token = "gh" + "p_" + ("B" * 24)
        bad_message = subprocess.check_output(
            ["git", "-C", str(self.repo), "--no-replace-objects", "commit-tree", tree,
             "-p", self.candidate], input=(message_token + "\n").encode(),
            env={**os.environ, "GIT_AUTHOR_NAME": "Synthetic-User",
                 "GIT_AUTHOR_EMAIL": "123+synthetic-user@users.noreply.github.com",
                 "GIT_COMMITTER_NAME": "Synthetic-User",
                 "GIT_COMMITTER_EMAIL": "123+synthetic-user@users.noreply.github.com"},
        ).decode().strip()
        self.assertNotEqual(self.gate_process(bad_message).returncode, 0)


if __name__ == "__main__":
    unittest.main()
