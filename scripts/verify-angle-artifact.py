#!/usr/bin/env python3
"""Validate ANGLE artifact metadata and library hashes without executing it."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.maintenance_angle.artifact import ArtifactError, verify_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument("--version")
    parser.add_argument("--architecture", default="x86_64")
    parser.add_argument("--build-key")
    args = parser.parse_args()
    try:
        manifest = verify_manifest(args.artifact_dir.resolve(strict=True), expected_version=args.version,
                                   expected_architecture=args.architecture, expected_build_key=args.build_key)
    except (OSError, ArtifactError) as exc:
        print(f"ANGLE artifact verification failed: {exc}", file=sys.stderr)
        return 1
    print(f"ANGLE artifact metadata verified: {manifest['chrome_version']} {manifest['architecture']} {manifest['build_key']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
