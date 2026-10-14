#!/usr/bin/env python3
"""Restrict one pre-push update to the reviewed clean branch lineage."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path


CANONICAL_URL = "https://github.com/naokikambe/chromium-angle-family1-experiment.git"
BRANCH = "refs/heads/phase5-page-recovery"
ZERO = "0" * 40
SCRIPT_DIR = Path(__file__).resolve().parent


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), "--no-replace-objects", *args], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise RuntimeError("git validation failed")
    return result.stdout


def load_metadata(path: Path, mapping_path: Path) -> tuple[str, list[str]]:
    """Metadata checksums bind the private list and mapping file contents."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {
        "clean_anchor", "old_commits", "old_commits_count", "old_commits_sha256", "mapping_sha256"
    }:
        raise RuntimeError("metadata schema invalid")
    anchor, commits = value["clean_anchor"], value["old_commits"]
    if not isinstance(anchor, str) or not re.fullmatch(r"[0-9a-f]{40}", anchor):
        raise RuntimeError("metadata anchor invalid")
    if not isinstance(commits, list) or not commits or any(
        not isinstance(item, str) or not re.fullmatch(r"[0-9a-f]{40}", item) for item in commits
    ) or len(set(commits)) != len(commits):
        raise RuntimeError("metadata old commit list invalid")
    if type(value["old_commits_count"]) is not int or value["old_commits_count"] != len(commits):
        raise RuntimeError("metadata count invalid")
    actual = hashlib.sha256(("\n".join(commits) + "\n").encode("ascii")).hexdigest()
    if not isinstance(value["old_commits_sha256"], str) or value["old_commits_sha256"] != actual:
        raise RuntimeError("metadata list checksum invalid")
    if not isinstance(value["mapping_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["mapping_sha256"]):
        raise RuntimeError("metadata mapping checksum invalid")
    mapping_bytes = mapping_path.read_bytes()
    if hashlib.sha256(mapping_bytes).hexdigest() != value["mapping_sha256"]:
        raise RuntimeError("mapping checksum mismatch")
    try:
        mapping_lines = mapping_bytes.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise RuntimeError("mapping encoding invalid") from exc
    pairs: list[tuple[str, str]] = []
    for line in mapping_lines:
        fields = line.split("\t")
        if len(fields) != 2 or any(not re.fullmatch(r"[0-9a-f]{40}", item) for item in fields):
            raise RuntimeError("mapping format invalid")
        pairs.append((fields[0], fields[1]))
    if not pairs or len({old for old, _new in pairs}) != len(pairs):
        raise RuntimeError("mapping entries invalid")
    if {old for old, new in pairs if old != new} != set(commits):
        raise RuntimeError("mapping denial set mismatch")
    return anchor, commits


def reject_alternate_history(repo: Path) -> None:
    history_overrides = (
        "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_OBJECT_DIRECTORY", "GIT_SHALLOW_FILE",
        "GIT_GRAFT_FILE", "GIT_REPLACE_REF_BASE",
    )
    if any(name in os.environ for name in history_overrides):
        raise RuntimeError("history override environment rejected")
    if git(repo, "rev-parse", "--is-shallow-repository").strip() != "false":
        raise RuntimeError("shallow repository rejected")
    common = Path(git(repo, "rev-parse", "--git-common-dir").strip())
    if not common.is_absolute():
        common = (repo / common).resolve()
    gitdir = Path(git(repo, "rev-parse", "--git-dir").strip())
    if not gitdir.is_absolute():
        gitdir = (repo / gitdir).resolve()
    for directory in {common, gitdir}:
        if (directory / "shallow").exists() and (directory / "shallow").stat().st_size:
            raise RuntimeError("shallow repository rejected")
        if (directory / "info" / "grafts").exists() and (directory / "info" / "grafts").stat().st_size:
            raise RuntimeError("grafts rejected")
        if (directory / "objects" / "info" / "alternates").exists():
            raise RuntimeError("object alternates rejected")
    if git(repo, "for-each-ref", "--format=%(refname)", "refs/replace").strip():
        raise RuntimeError("replacement refs rejected")


def reachable(repo: Path, rev: str) -> set[str]:
    return set(git(repo, "rev-list", rev).split())


def is_ancestor(repo: Path, older: str, newer: str) -> bool:
    result = subprocess.run(["git", "-C", str(repo), "--no-replace-objects",
                             "merge-base", "--is-ancestor", older, newer],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError("ancestry check failed")
    return result.returncode == 0


def validate(repo: Path, remote_name: str, remote_url: str, data: bytes,
             metadata: Path, mapping_path: Path) -> tuple[str, str, str]:
    if remote_name != "origin" or remote_url != CANONICAL_URL:
        raise RuntimeError("push destination rejected")
    lines = data.splitlines()
    if len(lines) != 1:
        raise RuntimeError("exactly one ref update required")
    fields = lines[0].decode("ascii").split()
    if len(fields) != 4:
        raise RuntimeError("invalid pre-push input")
    local_ref, local_sha, remote_ref, remote_sha = fields
    if local_ref != BRANCH or remote_ref != BRANCH:
        raise RuntimeError("only the designated existing branch is allowed")
    if not re.fullmatch(r"[0-9a-f]{40}", local_sha) or not re.fullmatch(r"[0-9a-f]{40}", remote_sha):
        raise RuntimeError("creation, deletion, and invalid object IDs are rejected")
    if local_sha == ZERO or remote_sha == ZERO:
        raise RuntimeError("branch creation or deletion rejected")
    anchor, denied = load_metadata(metadata, mapping_path)
    reject_alternate_history(repo)
    result = subprocess.run(["git", "-C", str(repo), "--no-replace-objects",
                             "cat-file", "-e", f"{local_sha}^{{commit}}"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise RuntimeError("candidate missing")
    if not is_ancestor(repo, remote_sha, local_sha):
        raise RuntimeError("non-fast-forward rejected")
    for rev in (remote_sha, local_sha):
        if not is_ancestor(repo, anchor, rev):
            raise RuntimeError("clean anchor ancestry rejected")
        if reachable(repo, rev).intersection(denied):
            raise RuntimeError("denied old history detected")
    return local_ref, local_sha, remote_sha


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True,
                        help="private old-to-new mapping whose checksum is in metadata")
    parser.add_argument("remote_name")
    parser.add_argument("remote_url")
    args = parser.parse_args()
    try:
        local_ref, local_sha, remote_sha = validate(args.repo.resolve(), args.remote_name,
                                        args.remote_url, sys.stdin.buffer.read(), args.metadata, args.mapping)
        scan = subprocess.run([sys.executable, str(SCRIPT_DIR / "check-publication-privacy.py"),
                               "--repo", str(args.repo.resolve()), "--pre-push"],
                              input=f"{local_ref} {local_sha} {BRANCH} {remote_sha}\n".encode(), check=False)
        return scan.returncode
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError, UnicodeError):
        print("safe push validation failed closed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
