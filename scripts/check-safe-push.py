#!/usr/bin/env python3
"""Restrict one pre-push update to the reviewed clean branch lineage."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


CANONICAL_URL = "https://github.com/naokikambe/chromium-angle-family1-experiment.git"
BRANCH = "refs/heads/phase5-page-recovery"
APPROVED_ANCHOR = "49b69c78861750b34ec533dfaa1fdbe3469fe9f2"
ZERO = "0" * 40
SCRIPT_DIR = Path(__file__).resolve().parent


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), "--no-replace-objects", *args], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise RuntimeError("git validation failed")
    return result.stdout


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


def is_ancestor(repo: Path, older: str, newer: str) -> bool:
    result = subprocess.run(["git", "-C", str(repo), "--no-replace-objects",
                             "merge-base", "--is-ancestor", older, newer],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError("ancestry check failed")
    return result.returncode == 0


def require_linear_history(repo: Path, anchor: str, tip: str) -> None:
    if git(repo, "cat-file", "-t", anchor).strip() != "commit":
        raise RuntimeError("approved anchor missing")
    if git(repo, "cat-file", "-t", tip).strip() != "commit":
        raise RuntimeError("commit missing")
    if not is_ancestor(repo, anchor, tip):
        raise RuntimeError("approved anchor ancestry rejected")
    # Inspect the complete reachable difference, not just --first-parent or the tip.
    for row in git(repo, "rev-list", "--parents", f"{anchor}..{tip}").splitlines():
        if len(row.split()) != 2:
            raise RuntimeError("every post-anchor commit must have exactly one parent")


def validate(repo: Path, remote_name: str, remote_url: str, data: bytes,
             *, anchor: str | None = None) -> tuple[str, str, str]:
    # The dedicated launcher uses the canonical URL as the remote token so that
    # origin's permanently disabled push URL never needs to be unlocked.
    if remote_name not in ("origin", CANONICAL_URL) or remote_url != CANONICAL_URL:
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
    if any(not re.fullmatch(r"[0-9a-f]{40}", sha) or sha == ZERO
           for sha in (local_sha, remote_sha)):
        raise RuntimeError("creation, deletion, and invalid object IDs are rejected")
    approved = APPROVED_ANCHOR if anchor is None else anchor
    if not re.fullmatch(r"[0-9a-f]{40}", approved) or approved == ZERO:
        raise RuntimeError("approved anchor invalid")
    reject_alternate_history(repo)
    require_linear_history(repo, approved, remote_sha)
    require_linear_history(repo, approved, local_sha)
    if not is_ancestor(repo, remote_sha, local_sha):
        raise RuntimeError("non-fast-forward rejected")
    return local_ref, local_sha, remote_sha


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("remote_name")
    parser.add_argument("remote_url")
    args = parser.parse_args()
    try:
        local_ref, local_sha, remote_sha = validate(args.repo.resolve(), args.remote_name,
                                        args.remote_url, sys.stdin.buffer.read())
        scan = subprocess.run([sys.executable, str(SCRIPT_DIR / "check-publication-privacy.py"),
                               "--repo", str(args.repo.resolve()), "--pre-push"],
                              input=f"{local_ref} {local_sha} {BRANCH} {remote_sha}\n".encode(), check=False)
        return scan.returncode
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError, UnicodeError):
        print("safe push validation failed closed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
