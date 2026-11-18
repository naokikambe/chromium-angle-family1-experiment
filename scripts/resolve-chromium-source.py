#!/usr/bin/env python3
"""Read a fetched Chromium version tag and its exact DEPS ANGLE revision."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.maintenance_angle.chromium import SourceError, parse_angle_revision, parse_chrome_version  # noqa: E402


def git_show(repo: Path, path: str) -> str:
    return subprocess.run(["git", "-C", str(repo), "show", f"HEAD:{path}"],
                          check=True, capture_output=True, text=True).stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--repo", type=Path, help="fetched Chromium tag checkout")
    source.add_argument("--fixture-dir", type=Path, help="synthetic dir with chrome/VERSION and DEPS")
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--revision", help="required with --fixture-dir")
    args = parser.parse_args()
    try:
        if args.repo:
            repo = args.repo.resolve(strict=True)
            version_data = git_show(repo, "chrome/VERSION")
            deps_data = git_show(repo, "DEPS")
            revision = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD^{commit}"],
                                      check=True, capture_output=True, text=True).stdout.strip()
        else:
            if not args.revision:
                raise SourceError("fixture mode requires --revision")
            fixture = args.fixture_dir.resolve(strict=True)
            version_data = (fixture / "chrome/VERSION").read_text(encoding="utf-8")
            deps_data = (fixture / "DEPS").read_text(encoding="utf-8")
            revision = args.revision
        version = parse_chrome_version(version_data)
        angle_revision = parse_angle_revision(deps_data)
        if version != args.expected_version:
            raise SourceError("tag version does not match the Stable release version")
        if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
            raise SourceError("Chromium commit is not a full SHA-1")
    except (OSError, subprocess.CalledProcessError, SourceError) as exc:
        print(f"Chromium source resolution failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"chrome_version": version, "chromium_revision": revision,
                      "angle_revision": angle_revision}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
