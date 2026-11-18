#!/usr/bin/env python3
"""Installed, integrity-checked publication entry point; origin stays disabled."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


CANONICAL_URL = "https://github.com/naokikambe/chromium-angle-family1-experiment.git"
BRANCH = "refs/heads/phase5-page-recovery"
APPROVED_ANCHOR = "49b69c78861750b34ec533dfaa1fdbe3469fe9f2"
BLOCKED_URL = "disabled://phase5-safety-repair-required"
FILES = {"safe-push.py", "check-safe-push.py", "check-publication-privacy.py",
         "pre-push", "pre-commit", "commit-msg"}


def private_path(path: Path, *, directory: bool = False) -> None:
    info = path.lstat()
    valid_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not valid_type or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise RuntimeError("guard path must be an owner-only regular file or directory")


def load_guard(home: Path) -> dict:
    private_path(home, directory=True)
    private_path(home / "manifest.json")
    value = json.loads((home / "manifest.json").read_text())
    if (not isinstance(value, dict) or set(value) != {"schema", "repo", "common_dir", "anchor", "files"}
            or type(value["schema"]) is not int or value["schema"] != 1
            or value["anchor"] != APPROVED_ANCHOR
            or not isinstance(value["files"], dict) or set(value["files"]) != FILES):
        raise RuntimeError("guard manifest invalid")
    for field in ("repo", "common_dir"):
        if not isinstance(value[field], str) or not Path(value[field]).is_absolute():
            raise RuntimeError("guard repository binding invalid")
    for name, expected in value["files"].items():
        private_path(home / name)
        if name in {"pre-push", "pre-commit", "commit-msg"} and not (home / name).stat().st_mode & 0o100:
            raise RuntimeError("hook is not executable")
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise RuntimeError("guard checksum invalid")
        if hashlib.sha256((home / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError("guard checksum mismatch")
    return value


def git(repo: Path, *args: str, missing: bool = False) -> str:
    result = subprocess.run(["git", "-C", str(repo), "--no-replace-objects", *args],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode and not (missing and result.returncode == 1):
        raise RuntimeError("Git preflight failed")
    return result.stdout.strip()


def preflight_config(repo: Path, home: Path, manifest: dict) -> None:
    overrides = ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_NAMESPACE",
                 "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
                 "GIT_SHALLOW_FILE", "GIT_GRAFT_FILE", "GIT_REPLACE_REF_BASE",
                 "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG")
    if any(key in os.environ for key in overrides):
        raise RuntimeError("Git environment override rejected")
    if git(repo, "remote").splitlines() != ["origin"]:
        raise RuntimeError("unexpected remote")
    if git(repo, "remote", "get-url", "--all", "origin").splitlines() != [CANONICAL_URL]:
        raise RuntimeError("origin URL rejected")
    if git(repo, "remote", "get-url", "--push", "--all", "origin").splitlines() != [BLOCKED_URL]:
        raise RuntimeError("ordinary push must remain disabled")
    if git(repo, "config", "--get-regexp", r"^url\..*\.(insteadof|pushinsteadof)$", missing=True):
        raise RuntimeError("URL rewriting rejected")
    required = {"push.default": "nothing", "push.followTags": "false",
                "push.autoSetupRemote": "false", "remote.origin.mirror": "false"}
    for key, expected in required.items():
        if git(repo, "config", "--get-all", key).splitlines() != [expected]:
            raise RuntimeError("push configuration rejected")
    if git(repo, "config", "--get-all", "remote.origin.push", missing=True):
        raise RuntimeError("default push refspec rejected")
    if Path(git(repo, "config", "--get", "core.hooksPath")).resolve() != home.resolve():
        raise RuntimeError("hook directory rejected")
    common = git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if Path(common).resolve() != Path(manifest["common_dir"]).resolve():
        raise RuntimeError("Git common directory rejected")
    if git(repo, "symbolic-ref", "HEAD") != BRANCH:
        raise RuntimeError("working branch rejected")
    if git(repo, "status", "--porcelain"):
        raise RuntimeError("working tree must be clean before publication")


def publish(home: Path, *, dry_run: bool) -> int:
    manifest = load_guard(home)
    repo = Path(manifest["repo"]).resolve()
    preflight_config(repo, home, manifest)
    advertised = git(repo, "ls-remote", CANONICAL_URL, BRANCH).splitlines()
    fields = advertised[0].split() if len(advertised) == 1 else []
    if len(fields) != 2 or fields[1] != BRANCH or not re.fullmatch(r"[0-9a-f]{40}", fields[0]):
        raise RuntimeError("designated existing remote branch missing")
    remote_sha = fields[0]
    local_sha = git(repo, "rev-parse", BRANCH)
    line = f"{BRANCH} {local_sha} {BRANCH} {remote_sha}\n".encode()
    gate = subprocess.run([sys.executable, str(home / "check-safe-push.py"), "--repo", str(repo),
                           CANONICAL_URL, CANONICAL_URL], input=line)
    if gate.returncode:
        return gate.returncode
    # Recheck files and config after the potentially long privacy scan.
    load_guard(home)
    preflight_config(repo, home, manifest)
    if git(repo, "rev-parse", BRANCH) != local_sha:
        raise RuntimeError("candidate changed during preflight")
    if local_sha == remote_sha:
        print("Reviewed branch is already up to date; no ref update.")
        return 0
    command = ["git", "-C", str(repo), "-c", f"core.hooksPath={home}", "push"]
    if dry_run:
        command.append("--dry-run")
    # Fixed explicit URL avoids ever enabling origin's persistent push URL.
    command.extend([CANONICAL_URL, f"{BRANCH}:{BRANCH}"])
    return subprocess.run(command).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        return publish(Path(__file__).absolute().parent, dry_run=args.dry_run)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, subprocess.SubprocessError):
        print("reviewed push failed closed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
