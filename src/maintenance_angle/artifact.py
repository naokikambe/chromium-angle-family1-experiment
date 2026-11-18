"""Manifest checks and safe extraction for CI ANGLE artifacts."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from .stable import VERSION_RE

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
LIBRARIES = ("libEGL.dylib", "libGLESv2.dylib")


class ArtifactError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest(directory: Path) -> dict[str, Any]:
    path = directory / "ANGLE_ARTIFACT_MANIFEST.json"
    if path.is_symlink() or not path.is_file():
        raise ArtifactError("artifact manifest is missing or symlinked")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactError("artifact manifest is invalid") from exc
    if not isinstance(value, dict):
        raise ArtifactError("artifact manifest must be an object")
    return value


def verify_manifest(directory: Path, *, expected_version: str | None = None,
                    expected_architecture: str = "x86_64",
                    expected_build_key: str | None = None) -> dict[str, Any]:
    manifest = load_manifest(directory)
    checksum_path = directory / "ANGLE_ARTIFACT_MANIFEST.sha256"
    if checksum_path.is_symlink() or not checksum_path.is_file():
        raise ArtifactError("artifact manifest checksum is missing or symlinked")
    checksum_tokens = checksum_path.read_text(encoding="utf-8").split()
    if len(checksum_tokens) != 2 or checksum_tokens[1] != "ANGLE_ARTIFACT_MANIFEST.json" or \
            checksum_tokens[0] != sha256(directory / "ANGLE_ARTIFACT_MANIFEST.json"):
        raise ArtifactError("artifact manifest checksum mismatch")
    if manifest.get("schema") != "angle-artifact-v1":
        raise ArtifactError("unsupported ANGLE artifact schema")
    if manifest.get("status") != "CI_BUILD_SUCCEEDED":
        raise ArtifactError("artifact is not marked as a successful CI build")
    if manifest.get("platform") != "macOS" or manifest.get("architecture") != expected_architecture:
        raise ArtifactError("artifact platform or architecture does not match")
    version = manifest.get("chrome_version")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        raise ArtifactError("artifact Chrome version is malformed")
    if expected_version is not None and version != expected_version:
        raise ArtifactError("artifact Chrome version does not match the requested version")
    if expected_build_key is not None and manifest.get("build_key") != expected_build_key:
        raise ArtifactError("artifact build key does not match the selected index record")
    for field in ("chromium_revision", "angle_revision", "depot_tools_revision"):
        if not isinstance(manifest.get(field), str) or not HEX40.fullmatch(manifest[field]):
            raise ArtifactError(f"artifact {field} is not a full source pin")
    for field in ("patch_sha256", "recipe_sha256", "build_key"):
        if not isinstance(manifest.get(field), str) or not HEX64.fullmatch(manifest[field]):
            raise ArtifactError(f"artifact {field} is malformed")
    patch_file = directory / "runtime-patch.diff"
    if patch_file.is_symlink() or not patch_file.is_file() or sha256(patch_file) != manifest["patch_sha256"]:
        raise ArtifactError("artifact runtime patch is missing or has a bad hash")
    if manifest.get("patch_candidate_status") not in {"catalog-match", "unlisted-revision-candidate"}:
        raise ArtifactError("artifact patch candidate state is malformed")
    if manifest.get("selection_mode") not in {
            "catalog-baseline", "new-revision-candidate",
            "explicit-known-version-trial", "explicit-unlisted-revision-trial"}:
        raise ArtifactError("artifact input selection mode is malformed")
    known_source_selection = manifest["selection_mode"] in {
        "catalog-baseline", "explicit-known-version-trial"}
    if known_source_selection != (manifest["patch_candidate_status"] == "catalog-match"):
        raise ArtifactError("artifact input selection mode disagrees with its source mapping state")
    if manifest.get("device_compatibility") != "not-assessed":
        raise ArtifactError("CI artifact must remain separate from device acceptance")
    if manifest.get("adoption_status") != "not-assessed":
        raise ArtifactError("CI artifact must remain separate from owner adoption")
    run_id = manifest.get("run_id")
    if not isinstance(run_id, (str, int)) or not str(run_id).isdigit():
        raise ArtifactError("artifact run ID is malformed")
    libraries = manifest.get("libraries")
    if not isinstance(libraries, dict) or set(libraries) != set(LIBRARIES):
        raise ArtifactError("artifact library list is incomplete")
    actual_dylibs = {p.name for p in directory.glob("*.dylib") if p.is_file()}
    if actual_dylibs != set(LIBRARIES):
        raise ArtifactError("artifact contains unexpected or missing top-level libraries")
    for name, expected in libraries.items():
        path = directory / name
        if path.is_symlink() or not path.is_file() or not HEX64.fullmatch(str(expected)):
            raise ArtifactError(f"artifact library is missing, symlinked, or has an invalid hash: {name}")
        if sha256(path) != expected:
            raise ArtifactError(f"artifact library hash mismatch: {name}")
    for field in ("patchset_id", "recipe_id", "artifact_name", "created_at",
                  "deployment_target", "workflow_revision", "runner", "xcode_version",
                  "macos_sdk_version", "clang_version", "ninja_version"):
        if not isinstance(manifest.get(field), str) or not manifest[field]:
            raise ArtifactError(f"artifact {field} is missing")
    if not HEX40.fullmatch(manifest["workflow_revision"]):
        raise ArtifactError("artifact workflow revision is malformed")
    try:
        created_at = datetime.fromisoformat(manifest["created_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ArtifactError("artifact creation time is malformed") from exc
    if created_at.tzinfo is None:
        raise ArtifactError("artifact creation time has no timezone")
    if not isinstance(manifest.get("gn_args_sha256"), str) or not HEX64.fullmatch(manifest["gn_args_sha256"]):
        raise ArtifactError("artifact GN args hash is malformed")
    args_path = directory / "args.gn"
    revision_path = directory / "ANGLE_REVISION"
    environment_path = directory / "build-environment.txt"
    for required in (args_path, revision_path, environment_path):
        if required.is_symlink() or not required.is_file():
            raise ArtifactError(f"artifact build input record is missing: {required.name}")
    if sha256(args_path) != manifest["gn_args_sha256"]:
        raise ArtifactError("artifact GN args hash does not match")
    inspection = manifest.get("binary_inspection_sha256")
    inspection_names = {"file-results.txt", "lipo-results.txt", "otool-results.txt",
                        "codesign-results.txt", "checksums.sha256"}
    if not isinstance(inspection, dict) or set(inspection) != inspection_names:
        raise ArtifactError("artifact binary inspection results are incomplete")
    for name, expected in inspection.items():
        report = directory / name
        if report.is_symlink() or not report.is_file() or not HEX64.fullmatch(str(expected)) or sha256(report) != expected:
            raise ArtifactError(f"artifact binary inspection result is missing or invalid: {name}")
    if revision_path.read_text(encoding="utf-8").strip() != manifest["angle_revision"]:
        raise ArtifactError("artifact ANGLE revision file does not match manifest")
    if not re.fullmatch(r"[0-9]+\.[0-9]+", manifest["deployment_target"]):
        raise ArtifactError("artifact deployment target is malformed")
    expected_name = f"angle-macos-x86_64-chrome-{version}-run-{run_id}"
    if manifest.get("artifact_name") != expected_name:
        raise ArtifactError("artifact name does not identify its version and run")
    license_path = directory / "LICENSE"
    if license_path.is_symlink() or not license_path.is_file():
        raise ArtifactError("required ANGLE license is missing or symlinked")
    if manifest.get("license_sha256") != sha256(license_path):
        raise ArtifactError("ANGLE license hash does not match manifest")
    notices = manifest.get("license_notices")
    if not isinstance(notices, dict):
        raise ArtifactError("artifact license notice list is malformed")
    for relative, expected in notices.items():
        path = PurePosixPath(str(relative))
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise ArtifactError("artifact license notice path is unsafe")
        notice = directory.joinpath(*path.parts)
        if notice.is_symlink() or not notice.is_file() or not HEX64.fullmatch(str(expected)) or sha256(notice) != expected:
            raise ArtifactError("artifact license notice is missing or has a bad hash")
    return manifest


def safe_extract_zip(archive: Path, destination: Path) -> None:
    """Extract a zip to a new directory, rejecting traversal and special files."""
    if destination.exists() or destination.is_symlink():
        raise ArtifactError("extraction destination must be new and unused")
    destination.mkdir(parents=True, mode=0o700)
    root = destination.resolve()
    try:
        with zipfile.ZipFile(archive) as source:
            entries = source.infolist()
            if len(entries) > 50000 or sum(item.file_size for item in entries) > 5 * 1024**3:
                raise ArtifactError("archive exceeds safe extraction limits")
            written_files: set[Path] = set()
            for info in entries:
                raw_name = info.filename.replace("\\", "/")
                member = PurePosixPath(raw_name)
                mode = info.external_attr >> 16
                if member.is_absolute() or not raw_name or not member.parts or ".." in member.parts or ":" in member.parts[0] or raw_name.startswith("/"):
                    raise ArtifactError("archive contains an unsafe path")
                kind = stat.S_IFMT(mode)
                if stat.S_ISLNK(mode) or (kind and kind not in (stat.S_IFREG, stat.S_IFDIR)):
                    raise ArtifactError("archive contains a symlink or special file")
                target = (destination / Path(*member.parts)).resolve()
                try:
                    target.relative_to(root)
                except ValueError as exc:
                    raise ArtifactError("archive path escapes its destination") from exc
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True, mode=0o700)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                if target in written_files or target.exists() or target.is_symlink():
                    raise ArtifactError("archive contains a duplicate path")
                with source.open(info) as src, target.open("xb") as dst:
                    while block := src.read(1024 * 1024):
                        dst.write(block)
                if mode:
                    target.chmod(mode & 0o777)
                written_files.add(target)
    except Exception as exc:
        shutil.rmtree(destination, ignore_errors=True)
        if isinstance(exc, ArtifactError):
            raise
        if isinstance(exc, (OSError, zipfile.BadZipFile, RuntimeError)):
            raise ArtifactError("artifact archive could not be extracted") from exc
        raise


def is_unexpired(value: str, *, now: datetime | None = None) -> bool:
    try:
        expiry = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return False
    if expiry.tzinfo is None:
        return False
    return expiry > (now or datetime.now(timezone.utc))
