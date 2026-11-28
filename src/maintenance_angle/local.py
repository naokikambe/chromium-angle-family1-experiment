"""Safe, explicit local app operations for manually selected Chrome copies."""
from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import re
import shutil
import shlex
import stat
import subprocess
import tempfile
import uuid
from typing import Any

from .artifact import LIBRARIES, sha256, verify_manifest
from .github_artifacts import GitHubActionsArtifacts, GitHubError, usable_artifact
from .launcher import LauncherError, launcher_script, load_usage_template, with_usage_descriptions

WORKFLOW_FILE = "watch-chrome-stable.yml"


class LocalError(ValueError):
    pass


def inspect_app(app_path: Path, runtime_architecture: str | None = None) -> dict[str, Any]:
    app = app_path.expanduser().resolve(strict=True)
    if not app.is_dir() or app.suffix != ".app":
        raise LocalError("selected Chrome path must be an existing .app bundle")
    info_path = app / "Contents/Info.plist"
    if info_path.is_symlink() or not info_path.is_file():
        raise LocalError("selected app has no regular Info.plist")
    try:
        info = plistlib.loads(info_path.read_bytes())
    except Exception as exc:
        raise LocalError("selected app Info.plist is invalid") from exc
    name = info.get("CFBundleExecutable")
    version = info.get("CFBundleShortVersionString")
    if not isinstance(name, str) or Path(name).name != name:
        raise LocalError("selected app executable name is invalid")
    if not isinstance(version, str) or len(version.split(".")) != 4 or not all(p.isdigit() for p in version.split(".")):
        raise LocalError("selected app version is not an exact four-part numeric version")
    executable = app / "Contents/MacOS" / name
    if executable.is_symlink() or not executable.is_file() or not os.access(executable, os.X_OK):
        raise LocalError("selected app executable is unavailable")
    try:
        architectures = subprocess.run(["/usr/bin/lipo", "-archs", str(executable)], check=True,
                                       capture_output=True, text=True, timeout=20).stdout.split()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise LocalError("selected app architecture could not be inspected") from exc
    if not architectures or any(a not in {"x86_64", "arm64"} for a in architectures):
        raise LocalError("selected app architecture output is malformed")
    if runtime_architecture is not None and runtime_architecture not in architectures:
        raise LocalError("selected runtime architecture is not present in the Chrome executable")
    return {"app_path": str(app), "version": version, "architectures": architectures,
            "runtime_architecture": runtime_architecture,
            "bundle_identifier": info.get("CFBundleIdentifier"), "executable": str(executable)}


def find_loader_library_dir(app: Path, version: str | None = None) -> Path:
    if version is None:
        try:
            info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
            version = info.get("CFBundleShortVersionString")
        except (OSError, plistlib.InvalidFileException) as exc:
            raise LocalError("selected Chrome version is unavailable") from exc
    if not isinstance(version, str) or not re.fullmatch(r"\d+(?:\.\d+){3}", version):
        raise LocalError("selected Chrome version is not exact")
    frameworks = app / "Contents/Frameworks"
    matches: list[Path] = []
    diagnostics: list[str] = []
    for framework in frameworks.glob("*.framework"):
        if framework.is_symlink() or not framework.is_dir():
            continue
        versions = framework / "Versions"
        if versions.is_symlink() or not versions.is_dir():
            continue
        numeric = [p for p in versions.iterdir()
                   if re.fullmatch(r"\d+(?:\.\d+){3}", p.name) and p.is_dir() and not p.is_symlink()]
        if numeric:
            selected = [p for p in numeric if p.name == version]
            if len(selected) != 1:
                diagnostics.append(f"{framework.name} has no unique Framework version {version}")
                continue
            current = versions / "Current"
            if not current.is_symlink():
                diagnostics.append(f"{framework.name} has no Current symlink")
                continue
            try:
                current_real = current.resolve(strict=True)
                selected_real = selected[0].resolve(strict=True)
            except OSError:
                diagnostics.append(f"{framework.name} Current target is unavailable")
                continue
            if current_real != selected_real:
                diagnostics.append(f"{framework.name} Current does not select Chrome version {version}")
                continue
            libraries = selected[0] / "Libraries"
            try:
                current_libraries = (current / "Libraries").resolve(strict=True)
                selected_libraries = libraries.resolve(strict=True)
            except OSError:
                diagnostics.append(f"{framework.name} Libraries path is unavailable")
                continue
            if libraries.is_dir() and not libraries.is_symlink() and current_libraries == selected_libraries:
                matches.append(libraries)
            continue
        # Older Chrome bundles use the single-version A layout. Do not fall
        # back to it when any numeric version directory is present.
        legacy = versions / "A"
        current = versions / "Current"
        if legacy.is_dir() and not legacy.is_symlink() and current.is_symlink():
            try:
                if current.resolve(strict=True) == legacy.resolve(strict=True):
                    libraries = legacy / "Libraries"
                    if libraries.is_dir() and not libraries.is_symlink():
                        matches.append(libraries)
            except OSError:
                diagnostics.append(f"{framework.name} Current target is unavailable")
    if len(matches) != 1:
        detail = "; ".join(diagnostics)
        raise LocalError("cannot identify one Chrome Framework Libraries directory for the selected version" +
                         (f": {detail}" if detail else ""))
    return matches[0]


def find_index_record(repository: str, version: str, architecture: str,
                      client: GitHubActionsArtifacts | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    if len(version.split(".")) != 4 or not all(x.isdigit() for x in version.split(".")):
        raise LocalError("requested version must have four numeric components")
    if architecture not in {"x86_64", "arm64"}:
        raise LocalError("unsupported architecture")
    client = client or GitHubActionsArtifacts(repository)
    state = client.load_latest_state(WORKFLOW_FILE)
    if not state:
        raise LocalError("no monitor index is available")
    records = state.get("records", [])
    success_index = state.get("success_index", {})
    if not isinstance(records, list) or not isinstance(success_index, dict):
        raise LocalError("monitor success index is malformed")
    matches = [r for r in records
               if r.get("chrome_version") == version and r.get("platform") == "macOS"
               and r.get("architecture") == architecture and r.get("status") == "CI_BUILD_SUCCEEDED"]
    indexed_success = success_index.get(version)
    if (isinstance(indexed_success, dict) and indexed_success.get("chrome_version") == version
            and indexed_success.get("platform") == "macOS"
            and indexed_success.get("architecture") == architecture
            and indexed_success.get("status") == "CI_BUILD_SUCCEEDED"
            and not any(r.get("run_id") == indexed_success.get("run_id")
                        and r.get("artifact_id") == indexed_success.get("artifact_id") for r in matches)):
        matches.append(indexed_success)
    matches.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
    for record in matches:
        try:
            artifact_id = int(record["artifact_id"])
        except (KeyError, TypeError, ValueError):
            continue
        artifact = next((a for a in client.artifacts() if a.get("id") == artifact_id), None)
        if usable_artifact(artifact) and artifact.get("name") == record.get("artifact_name"):
            if artifact.get("expires_at") != record.get("expires_at"):
                continue
            return record, artifact
    raise LocalError("no unexpired, indexed success artifact exactly matches this version and architecture")


def fetch_artifact(repository: str, version: str, architecture: str,
                   destination: Path, client: GitHubActionsArtifacts | None = None) -> dict[str, Any]:
    if destination.exists() or destination.is_symlink():
        raise LocalError("artifact destination must be new and unused")
    client = client or GitHubActionsArtifacts(repository)
    record, artifact = find_index_record(repository, version, architecture, client)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="angle-artifact-", suffix=".zip", delete=False) as stream:
        archive_path = Path(stream.name)
        stream.write(client.download_artifact(int(artifact["id"])))
    try:
        from .artifact import safe_extract_zip
        safe_extract_zip(archive_path, destination)
        manifest = verify_manifest(destination, expected_version=version,
                                   expected_architecture=architecture, expected_build_key=record.get("build_key"))
        if manifest.get("run_id") not in (str(record.get("run_id")), record.get("run_id")):
            raise LocalError("artifact run ID differs from the version index")
        if manifest.get("artifact_name") != record.get("artifact_name"):
            raise LocalError("artifact name differs from the version index")
        if manifest.get("chromium_revision") != record.get("chromium_revision"):
            raise LocalError("artifact source metadata differs from the version index")
        if manifest.get("angle_revision") != record.get("angle_revision"):
            raise LocalError("artifact ANGLE metadata differs from the version index")
        return {"record": record, "artifact": artifact, "manifest": manifest,
                "artifact_dir": str(destination)}
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    finally:
        archive_path.unlink(missing_ok=True)


def plan_install(app_path: Path, artifact_dir: Path, target_copy: Path, profile_dir: Path,
                 runtime_architecture: str) -> dict[str, Any]:
    if runtime_architecture not in {"x86_64", "arm64"}:
        raise LocalError("runtime architecture must be x86_64 or arm64")
    selected = inspect_app(app_path, runtime_architecture)
    artifact = verify_manifest(artifact_dir.resolve(strict=True), expected_version=selected["version"],
                               expected_architecture=runtime_architecture)
    if target_copy.exists() or target_copy.is_symlink():
        raise LocalError("target copy path already exists")
    if profile_dir.exists() or profile_dir.is_symlink():
        raise LocalError("dedicated profile path already exists")
    library_dir = find_loader_library_dir(Path(selected["app_path"]), selected["version"])
    relative = library_dir.relative_to(Path(selected["app_path"]))
    return {"schema": "angle-local-plan-v1", "chrome_version": selected["version"],
            "architecture": runtime_architecture, "source_app": selected["app_path"],
            "target_copy": str(target_copy), "profile_path": str(profile_dir),
            "library_directory_relative": relative.as_posix(), "artifact_build_key": artifact["build_key"],
            "chromium_revision": artifact["chromium_revision"], "angle_revision": artifact["angle_revision"],
            "patchset_id": artifact["patchset_id"], "recipe_id": artifact["recipe_id"],
            "library_hashes": artifact["libraries"], "steps": ["copy to new path", "place two libraries",
            "generate Bluetooth-aware launcher", "sign copied framework and app", "strictly verify", "freeze after review"]}


def _copy_tree_without_flags(source: Path, destination: Path) -> tuple[int, int]:
    source = source.expanduser().resolve(strict=True)
    destination = destination.expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise LocalError("target copy path already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    identity: tuple[int, int] | None = None
    try:
        destination.mkdir(mode=0o700)
        root_stat = destination.lstat()
        identity = (root_stat.st_dev, root_stat.st_ino)
        os.chmod(destination, 0o700)
        stack = [(source, destination)]
        while stack:
            src_dir, dst_dir = stack.pop()
            with os.scandir(src_dir) as entries:
                for entry in entries:
                    src = Path(entry.path)
                    dst = dst_dir / entry.name
                    metadata = entry.stat(follow_symlinks=False)
                    if stat.S_ISLNK(metadata.st_mode):
                        link_target = os.readlink(src)
                        if os.path.isabs(link_target):
                            raise LocalError("source app contains an absolute symlink")
                        try:
                            resolved_target = (src.parent / link_target).resolve(strict=True)
                            resolved_target.relative_to(source)
                        except (OSError, ValueError) as exc:
                            raise LocalError("source app symlink escapes its bundle") from exc
                        os.symlink(link_target, dst)
                    elif stat.S_ISDIR(metadata.st_mode):
                        dst.mkdir(mode=0o700)
                        os.chmod(dst, 0o700)
                        stack.append((src, dst))
                    elif stat.S_ISREG(metadata.st_mode):
                        shutil.copyfile(src, dst, follow_symlinks=False)
                        source_mode = stat.S_IMODE(metadata.st_mode) & 0o777
                        os.chmod(dst, source_mode | stat.S_IWUSR)
                    else:
                        raise LocalError("source app contains a special file")
        for directory, _dirs, _files in os.walk(destination, topdown=False, followlinks=False):
            source_directory = source / Path(directory).relative_to(destination)
            source_mode = stat.S_IMODE(source_directory.stat(follow_symlinks=False).st_mode) & 0o777
            os.chmod(directory, source_mode | 0o700)
        return identity
    except Exception:
        if identity is not None:
            _remove_created_copy(destination, identity)
        raise


def _tree_fingerprint(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for directory, dirs, files in os.walk(root, topdown=True, followlinks=False):
        base = Path(directory)
        names = list(dirs) + list(files)
        dirs[:] = [name for name in dirs if not (base / name).is_symlink()]
        for name in names:
            path = base / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                result[relative] = "symlink:" + os.readlink(path)
            elif path.is_file():
                executable_bits = stat.S_IMODE(path.stat(follow_symlinks=False).st_mode) & 0o111
                result[relative] = f"file:{executable_bits:o}:{sha256(path)}"
            elif not path.is_dir():
                raise LocalError("app tree contains an unsupported special file")
    return result


def _remove_created_copy(destination: Path, identity: tuple[int, int]) -> bool:
    """Remove only the new copy created by this call, even after a partial failure."""
    try:
        current = destination.lstat()
    except FileNotFoundError:
        return True
    if stat.S_ISLNK(current.st_mode) or (current.st_dev, current.st_ino) != identity:
        return False
    for directory, dirs, _files in os.walk(destination, topdown=True, followlinks=False):
        base = Path(directory)
        for name in dirs:
            child = base / name
            if not child.is_symlink():
                try:
                    os.chmod(child, stat.S_IMODE(child.stat(follow_symlinks=False).st_mode) | 0o700)
                except OSError:
                    pass
        os.chmod(base, stat.S_IMODE(base.stat(follow_symlinks=False).st_mode) | 0o700)
    shutil.rmtree(destination)
    return True


def prepare_copy(app_path: Path, artifact_dir: Path, target_copy: Path,
                 profile_dir: Path, runtime_architecture: str) -> dict[str, Any]:
    plan = plan_install(app_path, artifact_dir, target_copy, profile_dir, runtime_architecture)
    source = Path(plan["source_app"])
    source_fingerprint = _tree_fingerprint(source)
    copy_identity = _copy_tree_without_flags(source, target_copy)
    try:
        if _tree_fingerprint(target_copy) != source_fingerprint:
            raise LocalError("new Chrome copy content differs from its source")
        library_dir = target_copy / PurePosixPath(plan["library_directory_relative"])
        for name in LIBRARIES:
            shutil.copyfile(artifact_dir / name, library_dir / name)
            os.chmod(library_dir / name, 0o755)
            if sha256(library_dir / name) != plan["library_hashes"][name]:
                raise LocalError(f"copied library hash mismatch: {name}")
        copied_info = target_copy / "Contents/Info.plist"
        if sha256(source / "Contents/Info.plist") != sha256(copied_info):
            raise LocalError("copied Info.plist content differs from source")
        resources = target_copy / "Contents/Resources"
        if resources.is_symlink():
            raise LocalError("Chrome Resources directory cannot be a symlink")
        resources.mkdir(parents=True, exist_ok=True)
        binding_path = resources / "ANGLE_LOCAL_BINDING.json"
        if binding_path.exists() or binding_path.is_symlink():
            raise LocalError("Chrome copy already contains a local ANGLE binding")
        binding = {
            "schema": "angle-local-binding-v1",
            "installation_id": str(uuid.uuid4()),
            "artifact_manifest_sha256": sha256(artifact_dir / "ANGLE_ARTIFACT_MANIFEST.json"),
            "artifact_build_key": plan["artifact_build_key"],
            "chrome_version": plan["chrome_version"],
            "runtime_architecture": plan["architecture"],
            "framework_libraries_relative": plan["library_directory_relative"],
            "ci_unsigned_library_hashes": plan["library_hashes"],
        }
        binding_path.write_text(json.dumps(binding, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        os.chmod(binding_path, 0o600)
        plan["installation_id"] = binding["installation_id"]
        plan["status"] = "PREPARED_UNSIGNED"
        plan["target_library_directory"] = str(library_dir)
        return plan
    except Exception:
        _remove_created_copy(target_copy, copy_identity)
        raise


def _read_local_binding(app: Path) -> dict[str, Any]:
    path = app / "Contents/Resources/ANGLE_LOCAL_BINDING.json"
    if path.is_symlink() or not path.is_file():
        raise LocalError("Chrome copy has no regular local ANGLE binding")
    try:
        binding = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LocalError("Chrome local ANGLE binding is malformed") from exc
    if not isinstance(binding, dict) or binding.get("schema") != "angle-local-binding-v1":
        raise LocalError("Chrome local ANGLE binding has an unsupported schema")
    required = ("installation_id", "artifact_manifest_sha256", "artifact_build_key", "chrome_version",
                "runtime_architecture", "framework_libraries_relative", "ci_unsigned_library_hashes")
    if any(key not in binding for key in required):
        raise LocalError("Chrome local ANGLE binding is incomplete")
    if (not isinstance(binding["installation_id"], str) or not re.fullmatch(r"[A-Za-z0-9-]{1,80}", binding["installation_id"])
            or not isinstance(binding["chrome_version"], str)
            or not re.fullmatch(r"\d+(?:\.\d+){3}", binding["chrome_version"])
            or binding["runtime_architecture"] not in {"x86_64", "arm64"}
            or not isinstance(binding["artifact_build_key"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", binding["artifact_build_key"])
            or not isinstance(binding["artifact_manifest_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", binding["artifact_manifest_sha256"])):
        raise LocalError("Chrome local ANGLE binding has invalid installation metadata")
    hashes = binding["ci_unsigned_library_hashes"]
    if (not isinstance(hashes, dict) or set(hashes) != set(LIBRARIES)
            or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                   for value in hashes.values())):
        raise LocalError("Chrome local ANGLE binding has invalid CI library hashes")
    relative = PurePosixPath(binding["framework_libraries_relative"])
    if relative.is_absolute() or ".." in relative.parts:
        raise LocalError("Chrome local ANGLE binding has an unsafe Framework path")
    return binding


def _profile_binding(app: Path, profile: Path, binding: dict[str, Any]) -> dict[str, str]:
    return {"schema": "angle-profile-binding-v1", "installation_id": binding["installation_id"],
            "chrome_app_path": str(app), "chrome_version": binding["chrome_version"],
            "runtime_architecture": binding["runtime_architecture"],
            "artifact_build_key": binding["artifact_build_key"], "profile_path": str(profile)}


def _ensure_profile_binding(app: Path, profile: Path, binding: dict[str, Any]) -> bool:
    profile = profile.resolve(strict=False)
    expected = _profile_binding(app, profile, binding)
    marker = profile / ".angle-profile-binding.json"
    created = False
    if profile.is_symlink():
        raise LocalError("dedicated profile path cannot be a symlink")
    if not profile.exists():
        profile.parent.mkdir(parents=True, exist_ok=True)
        profile.mkdir(mode=0o700)
        created = True
    elif not profile.is_dir():
        raise LocalError("dedicated profile path is not a directory")
    if marker.is_symlink():
        raise LocalError("dedicated profile binding cannot be a symlink")
    if marker.exists():
        try:
            existing = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LocalError("dedicated profile binding is unreadable") from exc
        if existing != expected:
            raise LocalError("dedicated profile is bound to a different Chrome installation")
    else:
        if any(profile.iterdir()):
            raise LocalError("existing profile contents have no ANGLE installation binding")
        marker.write_text(json.dumps(expected, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        os.chmod(marker, 0o600)
    return created


def _chrome_info_with_bluetooth(app: Path, template_path: Path,
                                bluetooth_purpose: str | None) -> tuple[Path, dict[str, Any]]:
    info_path = app / "Contents/Info.plist"
    if info_path.is_symlink() or not info_path.is_file():
        raise LocalError("copied app Info.plist is unavailable")
    info = plistlib.loads(info_path.read_bytes())
    template = load_usage_template(template_path)
    updates = with_usage_descriptions(info, template, {"bluetooth"},
                                       {"bluetooth": bluetooth_purpose} if bluetooth_purpose else None)
    executable_name = updates.get("CFBundleExecutable")
    if not isinstance(executable_name, str) or Path(executable_name).name != executable_name:
        raise LocalError("copied app executable name is invalid")
    executable = app / "Contents/MacOS" / executable_name
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise LocalError("copied app executable is unavailable")
    temporary = info_path.with_name(info_path.name + ".angle-tmp")
    if temporary.exists() or temporary.is_symlink():
        raise LocalError("temporary Info.plist path already exists")
    temporary.write_bytes(plistlib.dumps(updates, fmt=plistlib.FMT_XML, sort_keys=True))
    os.chmod(temporary, stat.S_IMODE(info_path.stat().st_mode) & 0o777)
    os.replace(temporary, info_path)
    return executable, updates


def create_launcher(app_path: Path, profile_dir: Path, output: Path, template_path: Path,
                    bluetooth_purpose: str | None = None, *, koov_app_id: str) -> dict[str, Any]:
    app = app_path.expanduser().resolve(strict=True)
    profile = profile_dir.expanduser().resolve(strict=False)
    output = output.expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise LocalError("launcher output already exists")
    binding = _read_local_binding(app)
    _ensure_profile_binding(app, profile, binding)
    executable, updates = _chrome_info_with_bluetooth(app, template_path, bluetooth_purpose)
    from .launcher import validate_koov_app_id
    validate_koov_app_id(koov_app_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".angle-tmp")
    if temporary.exists() or temporary.is_symlink():
        raise LocalError("temporary launcher path already exists")
    temporary.write_text(launcher_script(app, profile, executable, binding["runtime_architecture"],
                                         koov_app_id=koov_app_id), encoding="utf-8")
    temporary.chmod(0o700)
    os.replace(temporary, output)
    return {"launcher": str(output), "profile_path": str(profile),
            "bluetooth_usage_description": updates["NSBluetoothAlwaysUsageDescription"],
            "status": "OPTIONAL_COMMAND_READY_BEFORE_SIGNING"}


def create_finder_launchers(app_path: Path, profile_dir: Path, output_dir: Path,
                            template_path: Path, *, koov_app_id: str, registration_url: str,
                            bundle_id_prefix: str, bluetooth_purpose: str | None = None) -> dict[str, Any]:
    from .launcher import validate_koov_app_id, validate_registration_url
    try:
        validate_koov_app_id(koov_app_id)
        validate_registration_url(registration_url)
    except LauncherError as exc:
        raise LocalError(str(exc)) from exc
    if (not re.fullmatch(r"[A-Za-z0-9.-]+", bundle_id_prefix) or "." not in bundle_id_prefix
            or bundle_id_prefix.startswith(".") or bundle_id_prefix.endswith(".") or ".." in bundle_id_prefix):
        raise LocalError("launcher bundle ID prefix must be a reverse-DNS identifier")
    app = app_path.expanduser().resolve(strict=True)
    profile = profile_dir.expanduser().resolve(strict=False)
    output = output_dir.expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise LocalError("Finder launcher output directory must be new and unused")
    binding = _read_local_binding(app)
    profile_created = _ensure_profile_binding(app, profile, binding)
    try:
        executable, updates = _chrome_info_with_bluetooth(app, template_path, bluetooth_purpose)
        output.mkdir(parents=True)
        apps = (
            ("KOOV Registration.app", "KOOV Registration", "registration", registration_url,
             bundle_id_prefix + ".registration"),
            ("KOOV ANGLE Family1.app", "KOOV ANGLE Family1", "daily", koov_app_id,
             bundle_id_prefix + ".daily"),
        )
        generated: list[dict[str, str]] = []
        for filename, name, mode, value, bundle_id in apps:
            launcher_app = output / filename
            macos = launcher_app / "Contents/MacOS"
            macos.mkdir(parents=True)
            script_kwargs = {"registration_url": value} if mode == "registration" else {"koov_app_id": value}
            launcher = macos / "Launcher"
            launcher.write_text(launcher_script(app, profile, executable, binding["runtime_architecture"],
                                                **script_kwargs), encoding="utf-8")
            launcher.chmod(0o700)
            launcher_info = {
                "CFBundleName": name,
                "CFBundleDisplayName": name,
                "CFBundleIdentifier": bundle_id,
                "CFBundleExecutable": "Launcher",
                "CFBundlePackageType": "APPL",
                "CFBundleVersion": "1",
                "CFBundleShortVersionString": "1.0",
                "NSBluetoothAlwaysUsageDescription": updates["NSBluetoothAlwaysUsageDescription"],
            }
            (launcher_app / "Contents/Info.plist").write_bytes(
                plistlib.dumps(launcher_info, fmt=plistlib.FMT_XML, sort_keys=True))
            generated.append({"name": filename, "entrypoint": mode, "bundle_id": bundle_id})
        return {"launchers": generated, "profile_binding_created": profile_created,
                "status": "FINDER_LAUNCHERS_READY_BEFORE_SIGNING"}
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        if profile_created:
            shutil.rmtree(profile, ignore_errors=True)
        raise


def _signature_details(target: Path) -> dict[str, Any]:
    result = subprocess.run(["/usr/bin/codesign", "--display", "--verbose=4", str(target)],
                            capture_output=True, text=True, check=False, timeout=60)
    if result.returncode:
        raise LocalError("code-signature metadata could not be read")
    output = result.stdout + "\n" + result.stderr
    cdhash = re.search(r"(?m)^CDHash=([0-9a-fA-F]+)\s*$", output)
    if not cdhash:
        raise LocalError("code-signature metadata has no CDHash")
    authorities = re.findall(r"(?m)^Authority=(.+)$", output)
    team = re.search(r"(?m)^TeamIdentifier=(.+)$", output)
    signature = re.search(r"(?m)^Signature=(.+)$", output)
    return {"cdhash": cdhash.group(1).lower(), "authorities": authorities,
            "team_identifier": team.group(1) if team else None,
            "signature": signature.group(1) if signature else None}


def _validate_external_receipt_path(app: Path, receipt_path: Path) -> Path:
    raw = receipt_path.expanduser()
    if not raw.is_absolute():
        raise LocalError("signed receipt path must be absolute")
    receipt = raw.absolute()
    if receipt.exists() or receipt.is_symlink():
        raise LocalError("signed receipt path must be new and unused")
    try:
        receipt.resolve(strict=False).relative_to(app)
    except ValueError:
        pass
    else:
        raise LocalError("signed receipt must be outside the Chrome app bundle")
    repository = Path(__file__).resolve().parents[2]
    try:
        receipt.resolve(strict=False).relative_to(repository)
    except ValueError:
        pass
    else:
        raise LocalError("signed receipt must stay outside the repository")
    return receipt


def sign_copy(app_path: Path, artifact_dir: Path, identity: str, receipt_path: Path,
              *, execute: bool = False) -> list[list[str]]:
    if not identity or "\n" in identity or "\x00" in identity:
        raise LocalError("signing identity must be a non-empty one-line value")
    app = app_path.expanduser().resolve(strict=True)
    receipt = _validate_external_receipt_path(app, receipt_path)
    if execute:
        verify_prepared_app(app, artifact_dir, require_signature=False)
    binding = _read_local_binding(app)
    library_dir = app / PurePosixPath(binding["framework_libraries_relative"])
    if library_dir.resolve(strict=True) != find_loader_library_dir(app, binding["chrome_version"]).resolve(strict=True):
        raise LocalError("local binding Framework path no longer matches Chrome")
    framework = library_dir.parents[2]
    resources = app / "Contents/Resources"
    signed_receipt_path = resources / "ANGLE_LOCAL_SIGNED_RECEIPT.json"
    if signed_receipt_path.exists() or signed_receipt_path.is_symlink():
        raise LocalError("Chrome copy already contains a signed receipt")
    library_targets = [library_dir / name for name in LIBRARIES]
    commands = [["/usr/bin/codesign", "--force", "--sign", identity, "--timestamp=none", str(target)]
                for target in library_targets]
    commands.extend([["/usr/bin/codesign", "--force", "--sign", identity, "--timestamp=none", str(framework)],
                     ["/usr/bin/codesign", "--force", "--sign", identity, "--timestamp=none", str(app)]])
    if not execute:
        return commands
    for target in library_targets + [framework]:
        subprocess.run(["/usr/bin/codesign", "--force", "--sign", identity, "--timestamp=none", str(target)],
                       check=True, timeout=120)
    signed_hashes = {name: sha256(library_dir / name) for name in LIBRARIES}
    signature_details = {name: _signature_details(library_dir / name) for name in LIBRARIES}
    framework_signature = _signature_details(framework)
    inner_receipt = {
        "schema": "angle-local-signed-receipt-v1",
        "binding_sha256": sha256(resources / "ANGLE_LOCAL_BINDING.json"),
        "installation_id": binding["installation_id"],
        "artifact_manifest_sha256": binding["artifact_manifest_sha256"],
        "artifact_build_key": binding["artifact_build_key"],
        "chrome_version": binding["chrome_version"],
        "runtime_architecture": binding["runtime_architecture"],
        "framework_libraries_relative": binding["framework_libraries_relative"],
        "ci_unsigned_library_hashes": binding["ci_unsigned_library_hashes"],
        "signed_library_hashes": signed_hashes,
        "library_signatures": signature_details,
        "framework_signature": framework_signature,
    }
    signed_receipt_path.write_text(json.dumps(inner_receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.chmod(signed_receipt_path, 0o644)
    subprocess.run(commands[-1], check=True, timeout=120)
    for target in library_targets + [framework, app]:
        subprocess.run(["/usr/bin/codesign", "--verify", "--strict", str(target)], check=True, timeout=120)
    external = {**inner_receipt, "requested_signing_identity": identity,
                "app_signature": _signature_details(app)}
    receipt.parent.mkdir(parents=True, exist_ok=True)
    try:
        with receipt.open("x", encoding="utf-8") as stream:
            json.dump(external, stream, sort_keys=True, indent=2)
            stream.write("\n")
        os.chmod(receipt, 0o600)
    except Exception:
        receipt.unlink(missing_ok=True)
        raise
    return commands


def _verify_signed_state(app: Path, library_dir: Path, framework: Path, binding: dict[str, Any],
                         hashes: dict[str, str], receipt_path: Path | None) -> tuple[str, dict[str, Any]]:
    if receipt_path is None:
        raise LocalError("signed verification requires the external local receipt path")
    inside_path = app / "Contents/Resources/ANGLE_LOCAL_SIGNED_RECEIPT.json"
    if inside_path.is_symlink() or not inside_path.is_file():
        raise LocalError("signed Chrome copy has no regular in-app receipt")
    receipt = receipt_path.expanduser().absolute()
    if receipt.is_symlink() or not receipt.is_file():
        raise LocalError("external local signing receipt is unavailable")
    try:
        inner = json.loads(inside_path.read_text(encoding="utf-8"))
        external = json.loads(receipt.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LocalError("local signing receipt is malformed") from exc
    if not isinstance(inner, dict) or not isinstance(external, dict) or any(external.get(k) != v for k, v in inner.items()):
        raise LocalError("in-app and external signing receipts do not match")
    required = {
        "schema": "angle-local-signed-receipt-v1",
        "binding_sha256": sha256(app / "Contents/Resources/ANGLE_LOCAL_BINDING.json"),
        "installation_id": binding["installation_id"],
        "artifact_manifest_sha256": binding["artifact_manifest_sha256"],
        "artifact_build_key": binding["artifact_build_key"],
        "chrome_version": binding["chrome_version"],
        "runtime_architecture": binding["runtime_architecture"],
        "framework_libraries_relative": binding["framework_libraries_relative"],
        "ci_unsigned_library_hashes": binding["ci_unsigned_library_hashes"],
        "signed_library_hashes": hashes,
    }
    if any(inner.get(key) != value for key, value in required.items()):
        raise LocalError("signed receipt does not bind the verified CI artifact and Chrome copy")
    if not isinstance(external.get("requested_signing_identity"), str) or not external.get("requested_signing_identity"):
        raise LocalError("external receipt has no signing identity record")
    for target in [app, framework] + [library_dir / name for name in LIBRARIES]:
        result = subprocess.run(["/usr/bin/codesign", "--verify", "--strict", str(target)],
                                capture_output=True, text=True, check=False, timeout=180)
        if result.returncode:
            raise LocalError("strict code-signature verification failed")
    current_library_signatures = {name: _signature_details(library_dir / name) for name in LIBRARIES}
    if inner.get("library_signatures") != current_library_signatures:
        raise LocalError("signed library CDHash or signer metadata differs from the receipt")
    if inner.get("framework_signature") != _signature_details(framework):
        raise LocalError("signed Framework CDHash or signer metadata differs from the receipt")
    if external.get("app_signature") != _signature_details(app):
        raise LocalError("Chrome app signature metadata differs from the external receipt")
    return "strict-verified-with-local-receipt", external


def verify_prepared_app(app_path: Path, artifact_dir: Path, *, require_signature: bool = False,
                        launcher_path: Path | None = None, profile_path: Path | None = None,
                        receipt_path: Path | None = None) -> dict[str, Any]:
    app = app_path.expanduser().resolve(strict=True)
    binding = _read_local_binding(app)
    architecture = binding.get("runtime_architecture")
    if architecture not in {"x86_64", "arm64"}:
        raise LocalError("local binding has an unsupported runtime architecture")
    selected = inspect_app(app, architecture)
    manifest_root = artifact_dir.resolve(strict=True)
    manifest = verify_manifest(manifest_root, expected_version=selected["version"],
                               expected_architecture=architecture,
                               expected_build_key=binding.get("artifact_build_key"))
    if sha256(manifest_root / "ANGLE_ARTIFACT_MANIFEST.json") != binding.get("artifact_manifest_sha256"):
        raise LocalError("local binding does not match the exact CI artifact manifest")
    if binding.get("chrome_version") != selected["version"] or binding.get("ci_unsigned_library_hashes") != manifest["libraries"]:
        raise LocalError("local binding does not match the selected Chrome and CI library hashes")
    relative = PurePosixPath(str(binding.get("framework_libraries_relative", "")))
    if relative.is_absolute() or ".." in relative.parts:
        raise LocalError("local binding Framework path is unsafe")
    library_dir = app / relative
    expected_dir = find_loader_library_dir(app, selected["version"])
    if library_dir.resolve(strict=True) != expected_dir.resolve(strict=True):
        raise LocalError("local binding Framework path differs from the selected Chrome version")
    framework = library_dir.parents[2]
    hashes = {name: sha256(library_dir / name) for name in LIBRARIES}
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    bt = info.get("NSBluetoothAlwaysUsageDescription")
    if not isinstance(bt, str) or not bt.strip():
        raise LocalError("Bluetooth purpose string is missing from the copied Chrome app")
    signed = require_signature or (receipt_path is not None and (app / "Contents/Resources/ANGLE_LOCAL_SIGNED_RECEIPT.json").exists())
    if signed:
        signature, verified_receipt = _verify_signed_state(app, library_dir, framework, binding, hashes, receipt_path)
    else:
        if hashes != manifest["libraries"]:
            raise LocalError("unsigned installed libraries do not match the verified CI artifact")
        signature, verified_receipt = "not-signed", None
    result: dict[str, Any] = {"chrome_version": selected["version"], "architecture": architecture,
            "artifact_build_key": manifest["build_key"], "ci_unsigned_library_hashes": manifest["libraries"],
            "installed_library_hashes": hashes, "bluetooth_usage_description": bt,
            "signature": signature, "status": "VERIFIED"}
    if verified_receipt is not None:
        result["signed_receipt"] = "verified"
    if launcher_path is not None:
        if profile_path is None:
            raise LocalError("launcher verification also requires its bound profile path")
        result["launcher"] = verify_launcher_script(launcher_path, app, profile_path)["status"]
    return result


def verify_launcher_script(path: Path, app_path: Path, profile_path: Path) -> dict[str, str]:
    raw_script = path.expanduser().absolute()
    if raw_script.is_symlink():
        raise LocalError("launcher script is missing or symlinked")
    script = raw_script.resolve(strict=True)
    app = app_path.expanduser().resolve(strict=True)
    profile = profile_path.expanduser().resolve(strict=False)
    if not script.is_file() or not os.access(script, os.X_OK):
        raise LocalError("launcher script is missing or not executable")
    text = script.read_text(encoding="utf-8")
    binding = _read_local_binding(app)
    expected = (shlex.quote(str(app)), shlex.quote(str(profile)),
                shlex.quote(str(app / "Contents/MacOS" / plistlib.loads((app / "Contents/Info.plist").read_bytes())["CFBundleExecutable"])),
                shlex.quote(str(binding["runtime_architecture"])),
                "ANGLE_PHASE5_ENABLE_METAL_FAMILY1=1", "--use-dynamic-angle", "--use-gl=angle",
                "--use-angle=metal", "--disable-angle-features=requireGpuFamily2",
                "--user-data-dir=\"$PROFILE_PATH\"", ".angle-profile-binding.json")
    if any(value not in text for value in expected):
        raise LocalError("launcher script does not match the reviewed app, architecture, and bound profile")
    if not (profile / ".angle-profile-binding.json").is_file():
        raise LocalError("launcher has no dedicated profile binding")
    try:
        marker = json.loads((profile / ".angle-profile-binding.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LocalError("launcher profile binding is unreadable") from exc
    if marker != _profile_binding(app, profile, binding):
        raise LocalError("launcher profile binding does not match the selected Chrome copy")
    result = subprocess.run(["/bin/bash", "-n", str(script)], capture_output=True, text=True, check=False)
    if result.returncode:
        raise LocalError("launcher shell syntax is invalid")
    return {"launcher": str(script), "status": "VALID"}
