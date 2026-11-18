#!/usr/bin/env python3
"""Create the public manifest for a verified unsigned ANGLE build."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.maintenance_angle.artifact import LIBRARIES, sha256

INSPECTION_FILES = (
    "file-results.txt", "lipo-results.txt", "otool-results.txt",
    "codesign-results.txt", "checksums.sha256",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-name", required=True)
    parser.add_argument("--xcode-version", required=True)
    parser.add_argument("--sdk-version", required=True)
    parser.add_argument("--clang-version", required=True)
    parser.add_argument("--ninja-version", required=True)
    args = parser.parse_args()
    if not args.run_id.isdigit() or not re.fullmatch(r"angle-macos-x86_64-chrome-[0-9.]+-run-[0-9]+", args.artifact_name):
        parser.error("invalid run ID or artifact name")
    artifact_dir = args.artifact_dir.resolve(strict=True)
    inputs = json.loads(args.inputs.read_text(encoding="utf-8"))
    recipe = inputs["recipe"]
    libs = {name: sha256(artifact_dir / name) for name in LIBRARIES}
    manifest = {
        "schema": "angle-artifact-v1",
        "status": "CI_BUILD_SUCCEEDED",
        "chrome_version": inputs["chrome_version"],
        "platform": "macOS",
        "architecture": recipe["architecture"],
        "chromium_revision": inputs["chromium_revision"],
        "angle_revision": inputs["angle_revision"],
        "patchset_id": inputs["patchset_id"],
        "patch_sha256": inputs["patch_sha256"],
        "patch_candidate_status": inputs["patch_candidate_status"],
        "selection_mode": inputs["selection_mode"],
        "recipe_id": inputs["recipe_id"],
        "recipe_sha256": inputs["recipe_sha256"],
        "build_key": inputs["build_key"],
        "workflow_revision": inputs["workflow_revision"],
        "depot_tools_revision": recipe["depot_tools_revision"],
        "runner": recipe["runner"],
        "xcode_version": args.xcode_version,
        "macos_sdk_version": args.sdk_version,
        "clang_version": args.clang_version,
        "ninja_version": args.ninja_version,
        "gn_args_sha256": sha256(artifact_dir / "args.gn"),
        "deployment_target": recipe["macos_deployment_target"],
        "libraries": libs,
        "binary_inspection_sha256": {
            name: sha256(artifact_dir / name) for name in INSPECTION_FILES
        },
        "license_sha256": sha256(artifact_dir / "LICENSE"),
        "license_notices": {
            str(path.relative_to(artifact_dir).as_posix()): sha256(path)
            for path in sorted(artifact_dir.rglob("*"))
            if path.is_file() and not path.is_symlink()
            and (path.name.lower().startswith("license") or path.name.lower().startswith("notice"))
            and path.relative_to(artifact_dir).as_posix() != "LICENSE"
        },
        "run_id": args.run_id,
        "artifact_name": args.artifact_name,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "device_compatibility": "not-assessed",
        "adoption_status": "not-assessed",
    }
    manifest_path = artifact_dir / "ANGLE_ARTIFACT_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (artifact_dir / "ANGLE_ARTIFACT_MANIFEST.sha256").write_text(
        f"{sha256(manifest_path)}  ANGLE_ARTIFACT_MANIFEST.json\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
