#!/usr/bin/env python3
"""Resolve a catalog version against its real Chromium tag for PR build validation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.maintenance_angle.inputs import InputError, resolve_inputs
from src.maintenance_angle.stable import VERSION_RE


def checked_inputs(catalog: Path, version: str, source: dict, revision: str) -> dict:
    if not VERSION_RE.fullmatch(version):
        raise InputError("malformed requested Chrome version")
    entry = json.loads((catalog / "chrome" / f"{version}.json").read_text(encoding="utf-8"))
    for key in ("chrome_version", "chromium_revision", "angle_revision"):
        if source.get(key) != entry.get(key):
            raise InputError("Chromium tag differs from the reviewed catalog: " + key)
    value = resolve_inputs(catalog, version, source["chromium_revision"],
                           source["angle_revision"], revision)
    if (value["recipe"]["chrome_source"] != version or
            value["patch_source_revision"] != source["angle_revision"]):
        raise InputError("PR validation requires a patch and recipe mapped to this exact source")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chrome-version", required=True)
    parser.add_argument("--workflow-revision", required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not VERSION_RE.fullmatch(args.chrome_version):
        parser.error("malformed requested Chrome version")
    try:
        args.source_dir.mkdir(parents=True, exist_ok=False)
        prefix = ["git", "-C", str(args.source_dir)]
        subprocess.run(prefix + ["init", "-q"], check=True)
        subprocess.run(prefix + ["remote", "add", "origin",
                                 "https://chromium.googlesource.com/chromium/src.git"], check=True)
        tag = f"refs/tags/{args.chrome_version}"
        subprocess.run(prefix + ["fetch", "--depth=1", "origin", f"{tag}:{tag}"], check=True)
        subprocess.run(prefix + ["checkout", "--detach", tag], check=True)
        source = json.loads(subprocess.run(
            [sys.executable, str(ROOT / "scripts/resolve-chromium-source.py"),
             "--repo", str(args.source_dir), "--expected-version", args.chrome_version],
            capture_output=True, text=True, check=True).stdout)
        value = checked_inputs(ROOT / "catalog", args.chrome_version, source, args.workflow_revision)
        args.output.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, InputError, subprocess.CalledProcessError) as exc:
        print(f"PR build input preparation failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
