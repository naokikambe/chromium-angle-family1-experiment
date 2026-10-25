#!/usr/bin/env python3
"""Focused synthetic tests for the staged publication privacy guard."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import runpy


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check-publication-privacy.py"


def run_git(root: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[bytes]:
    if env is None:
        env = os.environ.copy()
        for key in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
            env.pop(key, None)
    return subprocess.run(["git", "-C", str(root), *args], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True, env=env)


class PublicationPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        run_git(self.root, "init", "-q")
        run_git(self.root, "config", "user.name", "synthetic-reviewer")
        run_git(self.root, "config", "user.email", "12345+synthetic@users.noreply.github.com")
        (self.root / "safe.md").write_text("Model: SyntheticHardware7,3; source pin: 0123456789abcdef\n", encoding="utf-8")
        run_git(self.root, "add", "safe.md")
        run_git(self.root, "commit", "-qm", "synthetic baseline")

    def tearDown(self):
        self.temp.cleanup()

    def scan(self, *args: str, env: dict[str, str] | None = None):
        if env is None:
            env = os.environ.copy()
            for key in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
                env.pop(key, None)
        return subprocess.run([sys.executable, str(SCRIPT), "--repo", str(self.root), *args],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, check=False)

    def test_default_scans_staged_blob_not_unstaged_or_untracked_content(self):
        (self.root / "safe.md").write_text("/" + "Users/" + "synthetic-owner/private\n", encoding="utf-8")
        (self.root / "untracked.log").write_text("synthetic log\n", encoding="utf-8")
        result = self.scan()
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_new_policy_sources_and_fixtures_are_clean_under_their_own_rules(self):
        module = runpy.run_path(str(SCRIPT), run_name="publication_privacy_test")
        root = SCRIPT.parents[1]
        paths = [
            root / "AGENTS.md", root / ".gitignore", root / "README.md",
            root / "docs/publication-privacy.md", SCRIPT,
            root / "tests/test_publication_privacy.py",
            root / ".githooks/pre-commit", root / ".githooks/commit-msg", root / ".githooks/pre-push",
        ]
        findings = []
        for path in paths:
            relative = path.relative_to(root).as_posix()
            findings.extend(module["scan_path"](relative))
            text = path.read_text(encoding="utf-8")
            for number, line in enumerate(text.splitlines(), 1):
                findings.extend(module["scan_line"](relative, number, line, []))
        self.assertEqual(findings, [])

    def test_staged_private_path_fails_without_echoing_the_value(self):
        synthetic_path = "/" + "Users/" + "synthetic-owner/private"
        (self.root / "safe.md").write_text("Evidence from " + synthetic_path + "\n", encoding="utf-8")
        run_git(self.root, "add", "safe.md")
        result = self.scan()
        output = result.stdout.decode() + result.stderr.decode()
        self.assertEqual(result.returncode, 1)
        self.assertIn("safe.md:1: home-path", output)
        self.assertNotIn("synthetic-owner", output)

    def test_staged_snapshot_is_checked_even_if_worktree_was_cleaned(self):
        synthetic_email = "dev@" + "local.test"
        (self.root / "safe.md").write_text("Synthetic mailbox: " + synthetic_email + "\n", encoding="utf-8")
        run_git(self.root, "add", "safe.md")
        (self.root / "safe.md").write_text("safe staged replacement\n", encoding="utf-8")
        result = self.scan()
        output = result.stdout.decode() + result.stderr.decode()
        self.assertEqual(result.returncode, 1)
        self.assertIn("email", output)
        self.assertNotIn(synthetic_email, output)

    def test_metadata_requires_noreply_for_author_and_committer(self):
        (self.root / "safe.md").write_text("safe\n", encoding="utf-8")
        run_git(self.root, "add", "safe.md")
        env = os.environ.copy()
        env["GIT_AUTHOR_NAME"] = "Synthetic Reviewer"
        fake_email = "synthetic@" + "local.test"
        env["GIT_AUTHOR_EMAIL"] = fake_email
        result = self.scan(env=env)
        output = result.stdout.decode() + result.stderr.decode()
        self.assertEqual(result.returncode, 1)
        self.assertIn("author-email", output)
        self.assertIn("author-name", output)
        self.assertNotIn(fake_email, output)
        env["GIT_AUTHOR_EMAIL"] = "12345+synthetic@users.noreply.github.com"
        env["GIT_AUTHOR_NAME"] = "synthetic-reviewer"
        env["GIT_COMMITTER_NAME"] = "synthetic-reviewer"
        env["GIT_COMMITTER_EMAIL"] = "12345+synthetic@users.noreply.github.com"
        self.assertEqual(self.scan(env=env).returncode, 0)

    def test_tree_mode_checks_committed_blob_and_identity(self):
        synthetic_mac = "02:11:" + "22:33:44:55"
        (self.root / "safe.md").write_text("MAC " + synthetic_mac + "\n", encoding="utf-8")
        run_git(self.root, "add", "safe.md")
        run_git(self.root, "commit", "-qm", "synthetic address")
        result = self.scan("--tree", "HEAD")
        output = result.stdout.decode() + result.stderr.decode()
        self.assertEqual(result.returncode, 1)
        self.assertIn("mac-address", output)
        self.assertNotIn(synthetic_mac, output)

    def test_file_and_binary_evidence_are_rejected(self):
        (self.root / "capture.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (self.root / "device.log").write_text("synthetic", encoding="utf-8")
        (self.root / "profile" / "state.json").parent.mkdir()
        (self.root / "profile" / "state.json").write_text("synthetic test marker", encoding="utf-8")
        run_git(self.root, "add", "capture.png", "device.log")
        run_git(self.root, "add", "profile/state.json")
        result = self.scan()
        output = result.stdout.decode() + result.stderr.decode()
        self.assertEqual(result.returncode, 1)
        self.assertIn("evidence-file-type", output)
        self.assertIn("evidence-file-name", output)
        self.assertIn("non-text-content", output)

    def test_private_record_filenames_are_rejected_even_with_plain_synthetic_content(self):
        files = {
            "typescript": "synthetic terminal record",
            "Cookies": "synthetic browser database marker",
            "signing-receipt.json": "synthetic receipt marker",
            "identity.keychain-db": "synthetic keychain marker",
            "identity.p12": "synthetic certificate marker",
        }
        for name, content in files.items():
            (self.root / name).write_text(content, encoding="utf-8")
        run_git(self.root, "add", *files.keys())
        result = self.scan()
        output = result.stdout.decode() + result.stderr.decode()
        self.assertEqual(result.returncode, 1)
        for category in ("evidence-file-name", "evidence-file-type"):
            self.assertIn(category, output)
        for name in files:
            self.assertIn(name, output)

    def test_commit_message_scan_reports_category_without_echoing_match(self):
        message = "Synthetic note: " + "dev@" + "local.test" + "\n"
        message_file = self.root / "message.txt"
        message_file.write_text(message, encoding="utf-8")
        result = self.scan("--commit-message", str(message_file))
        output = result.stdout.decode() + result.stderr.decode()
        self.assertEqual(result.returncode, 1)
        self.assertIn("<commit-message>:1: email", output)
        self.assertNotIn("dev@" + "local.test", output)

    def test_ipv6_token_team_and_device_markers_are_detected_without_echo(self):
        fake_ipv6 = "ffff:" + ":2"
        fake_pat = "github_pat_" + "A" * 24
        fake_team = "ABCDE" + "12345"
        serial_label = "serial" + "_number="
        fake_serial = "SYNTHETIC" + "123"
        (self.root / "safe.md").write_text(
            f"Address {fake_ipv6}\nToken {fake_pat}\nTeam ID={fake_team}\n{serial_label}{fake_serial}\n",
            encoding="utf-8",
        )
        run_git(self.root, "add", "safe.md")
        result = self.scan()
        output = result.stdout.decode() + result.stderr.decode()
        self.assertEqual(result.returncode, 1)
        for category in ("ipv6", "credential-token", "team-identifier", "device-identifier"):
            self.assertIn(category, output)
        for value in (fake_ipv6, fake_pat, fake_team, fake_serial):
            self.assertNotIn(value, output)

    def test_only_public_upstream_signing_fixture_team_identifier_is_allowed(self):
        public_fixture_team = "EQHXZ8" + "M8AV"
        (self.root / "safe.md").write_text(
            "Upstream fixture TeamIdentifier=" + public_fixture_team + "\n", encoding="utf-8")
        run_git(self.root, "add", "safe.md")
        self.assertEqual(self.scan().returncode, 0)
        private_like_team = "ABCDE" + "12345"
        (self.root / "safe.md").write_text(
            "Unapproved Team Identifier=" + private_like_team + "\n", encoding="utf-8")
        run_git(self.root, "add", "safe.md")
        result = self.scan()
        self.assertEqual(result.returncode, 1)
        self.assertIn("team-identifier", result.stdout.decode())
        self.assertNotIn(private_like_team, result.stdout.decode() + result.stderr.decode())

    def test_quoted_json_identity_metadata_is_detected_without_echoing_values(self):
        fake_team = "ABCDE" + "12345"
        fake_serial = "SYNTHETIC" + "987"
        fake_fingerprint = "A1" * 20
        team_key = '"team' + '_id"'
        serial_key = '"serial' + '_number"'
        fingerprint_key = '"certificate' + '_fingerprint"'
        json_value = '"' + fake_team + '"'
        serial_value = '"' + fake_serial + '"'
        fingerprint_value = '"' + fake_fingerprint + '"'
        content = "{" + team_key + ":" + json_value + "," + serial_key + ":" + serial_value
        content += "," + fingerprint_key + ":" + fingerprint_value + "}"
        (self.root / "safe.md").write_text(content, encoding="utf-8")
        run_git(self.root, "add", "safe.md")
        result = self.scan()
        output = result.stdout.decode() + result.stderr.decode()
        self.assertEqual(result.returncode, 1)
        for category in ("team-identifier", "device-identifier", "certificate-fingerprint"):
            self.assertIn(category, output)
        for value in (fake_team, fake_serial, fake_fingerprint):
            self.assertNotIn(value, output)

    def test_nonloopback_nonexample_address_and_owner_deny_value_are_hidden(self):
        synthetic_ip = "255.255." + "255.255"
        (self.root / "safe.md").write_text("Synthetic endpoint " + synthetic_ip + "\n", encoding="utf-8")
        run_git(self.root, "add", "safe.md")
        result = self.scan()
        self.assertEqual(result.returncode, 1)
        output = result.stdout.decode() + result.stderr.decode()
        self.assertIn("ipv4", output)
        self.assertNotIn(synthetic_ip, output)
        (self.root / "safe.md").write_text("synthetic-endpoint-marker\n", encoding="utf-8")
        run_git(self.root, "add", "safe.md")
        denied = self.scan("--deny-value", "synthetic-endpoint-marker")
        self.assertEqual(denied.returncode, 1)
        self.assertIn("owner-deny-value", denied.stdout.decode())
        self.assertNotIn("synthetic-endpoint-marker", denied.stdout.decode() + denied.stderr.decode())

        allowed_addresses = [
            "127." + "0.0.1", "0.0.0." + "0", "192.0." + "2.8",
            "198.51." + "100.7", "203.0." + "113.9",
            ":" + ":1", ":" + ":", "2001:" + "db8:" + ":1",
        ]
        (self.root / "safe.md").write_text("\n".join(allowed_addresses), encoding="utf-8")
        run_git(self.root, "add", "safe.md")
        self.assertEqual(self.scan().returncode, 0)

    def test_pre_push_scans_old_commits_even_when_tip_tree_matches_clean_squash(self):
        (self.root / "safe.md").write_text("/" + "Users/" + "synthetic-owner/private\n", encoding="utf-8")
        run_git(self.root, "add", "safe.md")
        run_git(self.root, "commit", "-qm", "synthetic unsafe historical input")
        run_git(self.root, "config", "user.email", "12345+synthetic@users.noreply.github.com")
        (self.root / "safe.md").write_text("clean tip with same tree as squash\n", encoding="utf-8")
        run_git(self.root, "add", "safe.md")
        run_git(self.root, "commit", "-qm", "clean current tip")
        local_tip = run_git(self.root, "rev-parse", "HEAD").stdout.decode().strip()
        tree = run_git(self.root, "rev-parse", "HEAD^{tree}").stdout.decode().strip()
        squash = run_git(self.root, "commit-tree", tree, "-m", "synthetic clean squash").stdout.decode().strip()
        ref_input = f"refs/heads/topic {local_tip} refs/heads/topic {squash}\n".encode()
        result = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(self.root), "--pre-push"],
                                input=ref_input, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        output = result.stdout.decode() + result.stderr.decode()
        self.assertEqual(result.returncode, 1)
        self.assertIn("home-path", output)
        self.assertNotIn("synthetic-owner", output)

    def test_pre_push_accepts_new_clean_noreply_history(self):
        base = run_git(self.root, "rev-parse", "HEAD").stdout.decode().strip()
        (self.root / "safe.md").write_text("New clean synthetic code\n", encoding="utf-8")
        run_git(self.root, "add", "safe.md")
        run_git(self.root, "commit", "-qm", "clean synthetic addition")
        local_tip = run_git(self.root, "rev-parse", "HEAD").stdout.decode().strip()
        ref_input = f"refs/heads/topic {local_tip} refs/heads/topic {base}\n".encode()
        result = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(self.root), "--pre-push"],
                                input=ref_input, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_pre_push_scans_a_reused_clean_path_blob_once(self):
        base = run_git(self.root, "rev-parse", "HEAD").stdout.decode().strip()
        (self.root / "first.md").write_text("first clean synthetic file\n", encoding="utf-8")
        run_git(self.root, "add", "first.md")
        run_git(self.root, "commit", "-qm", "first clean addition")
        (self.root / "second.md").write_text("second clean synthetic file\n", encoding="utf-8")
        run_git(self.root, "add", "second.md")
        run_git(self.root, "commit", "-qm", "second clean addition")
        local_tip = run_git(self.root, "rev-parse", "HEAD").stdout.decode().strip()
        ref_input = f"refs/heads/topic {local_tip} refs/heads/topic {base}\n".encode()

        module = runpy.run_path(str(SCRIPT), run_name="publication_privacy_cache_test")
        original_git = module["git"]
        safe_blob_oid = run_git(self.root, "rev-parse", "HEAD:safe.md").stdout.decode().strip()
        safe_blob_reads = 0

        def counted_git(root: Path, *args: str, data: bytes | None = None) -> bytes:
            nonlocal safe_blob_reads
            if len(args) == 3 and args[0:2] == ("cat-file", "blob") and args[2] == safe_blob_oid:
                safe_blob_reads += 1
            return original_git(root, *args, data=data)

        module["pre_push_findings"].__globals__["git"] = counted_git
        findings = module["pre_push_findings"](self.root, ref_input, [])
        self.assertEqual(findings, [])
        self.assertEqual(safe_blob_reads, 1)

    def test_pre_push_still_checks_older_commit_message_after_blob_cache_hit(self):
        base = run_git(self.root, "rev-parse", "HEAD").stdout.decode().strip()
        message = "Synthetic historical note " + "dev@" + "local" + ".test"
        run_git(self.root, "commit", "--allow-empty", "-m", message)
        run_git(self.root, "commit", "--allow-empty", "-m", "clean newer commit")
        local_tip = run_git(self.root, "rev-parse", "HEAD").stdout.decode().strip()
        ref_input = f"refs/heads/topic {local_tip} refs/heads/topic {base}\n".encode()
        result = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(self.root), "--pre-push"],
                                input=ref_input, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        output = result.stdout.decode() + result.stderr.decode()
        self.assertEqual(result.returncode, 1)
        self.assertIn("<commit-message>:1: email", output)
        self.assertNotIn("dev@" + "local.test", output)

    def test_pre_push_still_checks_older_commit_metadata_after_blob_cache_hit(self):
        base = run_git(self.root, "rev-parse", "HEAD").stdout.decode().strip()
        env = os.environ.copy()
        env["GIT_AUTHOR_NAME"] = "Synthetic Reviewer"
        env["GIT_AUTHOR_EMAIL"] = "reviewer@local" + ".test"
        run_git(self.root, "commit", "--allow-empty", "-m", "clean tree invalid identity", env=env)
        run_git(self.root, "commit", "--allow-empty", "-m", "clean newer commit")
        local_tip = run_git(self.root, "rev-parse", "HEAD").stdout.decode().strip()
        ref_input = f"refs/heads/topic {local_tip} refs/heads/topic {base}\n".encode()
        result = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(self.root), "--pre-push"],
                                input=ref_input, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        output = result.stdout.decode() + result.stderr.decode()
        self.assertEqual(result.returncode, 1)
        self.assertIn("author-email", output)
        self.assertNotIn("reviewer@local" + ".test", output)

    def test_pre_push_checks_commit_messages_even_when_tree_is_clean(self):
        base = run_git(self.root, "rev-parse", "HEAD").stdout.decode().strip()
        message = "Synthetic review record " + "dev@" + "local.test"
        run_git(self.root, "commit", "--allow-empty", "-m", message)
        local_tip = run_git(self.root, "rev-parse", "HEAD").stdout.decode().strip()
        ref_input = f"refs/heads/topic {local_tip} refs/heads/topic {base}\n".encode()
        result = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(self.root), "--pre-push"],
                                input=ref_input, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        output = result.stdout.decode() + result.stderr.decode()
        self.assertEqual(result.returncode, 1)
        self.assertIn("<commit-message>:1: email", output)
        self.assertNotIn("dev@" + "local.test", output)


if __name__ == "__main__":
    unittest.main()
