import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone, timedelta

from src.maintenance_angle.artifact import ArtifactError, is_unexpired, safe_extract_zip, sha256, verify_manifest

ROOT = Path(__file__).resolve().parents[1]


def make_artifact(directory: Path, *, chrome_version: str = "156.0.8078.48", run_id: str = "123",
                  patchset_id: str = "metal-family1-v1", recipe_id: str = "macos-x64-metal-v1",
                  recipe_sha256: str = "d" * 64, workflow_revision: str = "1" * 40,
                  chromium_revision: str = "a" * 40, angle_revision: str = "b" * 40,
                  build_key: str = "e" * 64, selection_mode: str = "catalog-baseline",
                  patch_candidate_status: str = "catalog-match"):
    directory.mkdir()
    (directory / "libEGL.dylib").write_bytes(b"synthetic egl")
    (directory / "libGLESv2.dylib").write_bytes(b"synthetic gles")
    (directory / "LICENSE").write_text("synthetic license\n")
    (directory / "runtime-patch.diff").write_text("synthetic reviewed patch\n")
    (directory / "args.gn").write_text("is_debug = false\n")
    (directory / "ANGLE_REVISION").write_text("b" * 40 + "\n")
    (directory / "build-environment.txt").write_text("synthetic build environment\n")
    for name in ("file-results.txt", "lipo-results.txt", "otool-results.txt", "codesign-results.txt", "checksums.sha256"):
        (directory / name).write_text("synthetic inspection result\n")
    (directory / "licenses").mkdir()
    (directory / "licenses/NOTICE.txt").write_text("synthetic notice\n")
    manifest = {
        "schema": "angle-artifact-v1", "status": "CI_BUILD_SUCCEEDED",
        "chrome_version": chrome_version, "platform": "macOS", "architecture": "x86_64",
        "chromium_revision": chromium_revision, "angle_revision": angle_revision,
        "patchset_id": patchset_id, "patch_sha256": "c" * 64,
        "patch_candidate_status": patch_candidate_status,
        "selection_mode": selection_mode,
        "recipe_id": recipe_id, "recipe_sha256": recipe_sha256,
        "build_key": build_key, "depot_tools_revision": "f" * 40,
        "run_id": run_id, "artifact_name": f"angle-macos-x86_64-chrome-{chrome_version}-run-{run_id}",
        "workflow_revision": workflow_revision,
        "created_at": "2026-11-15T00:00:00Z", "deployment_target": "13.0",
        "runner": "macos-15-intel", "xcode_version": "Xcode 16.4;Build 16F6",
        "macos_sdk_version": "15.5", "clang_version": "Apple clang 17",
        "ninja_version": "1.12.1",
        "libraries": {"libEGL.dylib": sha256(directory / "libEGL.dylib"),
                       "libGLESv2.dylib": sha256(directory / "libGLESv2.dylib")},
        "gn_args_sha256": sha256(directory / "args.gn"),
        "binary_inspection_sha256": {
            name: sha256(directory / name) for name in (
                "file-results.txt", "lipo-results.txt", "otool-results.txt",
                "codesign-results.txt", "checksums.sha256")
        },
        "license_sha256": sha256(directory / "LICENSE"),
        "license_notices": {"licenses/NOTICE.txt": sha256(directory / "licenses/NOTICE.txt")},
        "device_compatibility": "not-assessed", "adoption_status": "not-assessed",
    }
    manifest_path = directory / "ANGLE_ARTIFACT_MANIFEST.json"
    manifest["patch_sha256"] = sha256(directory / "runtime-patch.diff")
    manifest_path.write_text(json.dumps(manifest, sort_keys=True))
    (directory / "ANGLE_ARTIFACT_MANIFEST.sha256").write_text(
        sha256(manifest_path) + "  ANGLE_ARTIFACT_MANIFEST.json\n")
    return manifest


class ArtifactHandlingTests(unittest.TestCase):

    def test_manifest_checks_exact_version_hashes_and_licenses(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "artifact"
            make_artifact(directory)
            result = verify_manifest(directory, expected_version="156.0.8078.48", expected_architecture="x86_64")
            self.assertEqual(result["status"], "CI_BUILD_SUCCEEDED")
            (directory / "LICENSE").write_text("changed\n")
            with self.assertRaises(ArtifactError):
                verify_manifest(directory)

    def test_safe_extract_rejects_traversal_and_removes_partial_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as source:
                source.writestr("../outside.txt", "no")
            destination = Path(temp) / "out"
            with self.assertRaises(ArtifactError):
                safe_extract_zip(archive, destination)
            self.assertFalse(destination.exists())

    def test_safe_extract_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "symlink.zip"
            info = zipfile.ZipInfo("link")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(archive, "w") as source:
                source.writestr(info, "outside")
            with self.assertRaises(ArtifactError):
                safe_extract_zip(archive, Path(temp) / "out")

    def test_expiry_requires_timezone_and_future_time(self):
        now = datetime.now(timezone.utc)
        self.assertTrue(is_unexpired((now + timedelta(hours=1)).isoformat(), now=now))
        self.assertFalse(is_unexpired((now - timedelta(hours=1)).isoformat(), now=now))
        self.assertFalse(is_unexpired("2026-11-15T00:00:00"))

    def test_manifest_requires_complete_toolchain_and_zoned_creation_time(self):
        for field, value in (("xcode_version", ""), ("macos_sdk_version", None),
                             ("clang_version", ""), ("ninja_version", ""),
                             ("runner", ""), ("created_at", "2026-11-15T00:00:00")):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp) / "artifact"
                manifest = make_artifact(directory)
                manifest[field] = value
                manifest_path = directory / "ANGLE_ARTIFACT_MANIFEST.json"
                manifest_path.write_text(json.dumps(manifest, sort_keys=True))
                (directory / "ANGLE_ARTIFACT_MANIFEST.sha256").write_text(
                    sha256(manifest_path) + "  ANGLE_ARTIFACT_MANIFEST.json\n")
                with self.assertRaises(ArtifactError):
                    verify_manifest(directory)

    def test_manifest_requires_a_known_input_selection_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "artifact"
            manifest = make_artifact(directory, selection_mode="explicit-known-version-trial")
            self.assertEqual(verify_manifest(directory)["selection_mode"], "explicit-known-version-trial")
            manifest["selection_mode"] = "catalog-default-fallback"
            manifest_path = directory / "ANGLE_ARTIFACT_MANIFEST.json"
            manifest_path.write_text(json.dumps(manifest, sort_keys=True))
            (directory / "ANGLE_ARTIFACT_MANIFEST.sha256").write_text(
                sha256(manifest_path) + "  ANGLE_ARTIFACT_MANIFEST.json\n")
            with self.assertRaisesRegex(ArtifactError, "selection mode"):
                verify_manifest(directory)

    def test_manifest_selection_mode_must_match_known_or_unlisted_source_state(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "artifact"
            manifest = make_artifact(directory, selection_mode="new-revision-candidate")
            manifest_path = directory / "ANGLE_ARTIFACT_MANIFEST.json"
            manifest_path.write_text(json.dumps(manifest, sort_keys=True))
            (directory / "ANGLE_ARTIFACT_MANIFEST.sha256").write_text(
                sha256(manifest_path) + "  ANGLE_ARTIFACT_MANIFEST.json\n")
            with self.assertRaisesRegex(ArtifactError, "source mapping state"):
                verify_manifest(directory)

    def test_manifest_writer_records_the_selected_source_patch_recipe_and_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            artifact = base / "artifact"
            artifact.mkdir()
            for name, content in {
                "libEGL.dylib": b"synthetic egl", "libGLESv2.dylib": b"synthetic gles",
                "runtime-patch.diff": b"synthetic candidate patch\n", "args.gn": b"symbol_level = 1\n",
                "ANGLE_REVISION": b"b" * 40 + b"\n", "build-environment.txt": b"synthetic\n",
                "LICENSE": b"synthetic license\n", "file-results.txt": b"file report\n",
                "lipo-results.txt": b"lipo report\n", "otool-results.txt": b"otool report\n",
                "codesign-results.txt": b"codesign report\n", "checksums.sha256": b"checksum report\n",
            }.items():
                (artifact / name).write_bytes(content)
            patch_hash = sha256(artifact / "runtime-patch.diff")
            inputs = {
                "chrome_version": "157.0.300.2", "chromium_revision": "a" * 40,
                "angle_revision": "b" * 40, "patchset_id": "fixture-patch-v2",
                "patch_sha256": patch_hash, "patch_candidate_status": "unlisted-revision-candidate",
                "selection_mode": "new-revision-candidate", "recipe_id": "fixture-recipe-v2",
                "recipe_sha256": "c" * 64, "build_key": "d" * 64, "workflow_revision": "e" * 40,
                "recipe": {"architecture": "x86_64", "depot_tools_revision": "f" * 40,
                           "runner": "synthetic-runner", "macos_deployment_target": "13.0"},
            }
            input_path = base / "inputs.json"
            input_path.write_text(json.dumps(inputs), encoding="utf-8")
            subprocess.run([
                sys.executable, str(ROOT / "scripts/write-angle-manifest.py"),
                "--artifact-dir", str(artifact), "--inputs", str(input_path),
                "--run-id", "321", "--artifact-name", "angle-macos-x86_64-chrome-157.0.300.2-run-321",
                "--xcode-version", "synthetic Xcode", "--sdk-version", "15.5",
                "--clang-version", "synthetic clang", "--ninja-version", "1.12.1",
            ], check=True, cwd=ROOT, capture_output=True, text=True)
            manifest = verify_manifest(artifact, expected_version="157.0.300.2")
            self.assertEqual(manifest["chromium_revision"], "a" * 40)
            self.assertEqual(manifest["patchset_id"], "fixture-patch-v2")
            self.assertEqual(manifest["patch_sha256"], patch_hash)
            self.assertEqual(manifest["recipe_id"], "fixture-recipe-v2")
            self.assertEqual(manifest["recipe_sha256"], "c" * 64)
            self.assertEqual(manifest["selection_mode"], "new-revision-candidate")
            self.assertEqual(manifest["build_key"], "d" * 64)


if __name__ == "__main__":
    unittest.main()
