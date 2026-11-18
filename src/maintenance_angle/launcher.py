"""Bluetooth-aware launcher template and Info.plist validation."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shlex
import sys
from typing import Any
from urllib.parse import urlsplit


class LauncherError(ValueError):
    pass


ARCH_COMMAND = "/usr/bin/arch"
PYTHON_COMMAND = sys.executable


def load_usage_template(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LauncherError("launcher usage template is unavailable or invalid") from exc
    expected = {"bluetooth": {"info_plist_key": "NSBluetoothAlwaysUsageDescription",
                              "default_text": "Bluetooth is used to communicate with the selected robotics controller."}}
    if data != {"schema": "angle-launcher-usage-v1", "required_features": expected}:
        raise LauncherError("launcher template must define the Bluetooth purpose string")
    return data


def with_usage_descriptions(info: dict[str, Any], template: dict[str, Any],
                            requested: set[str], overrides: dict[str, str] | None = None) -> dict[str, Any]:
    if not isinstance(info, dict) or not isinstance(requested, set) or not requested:
        raise LauncherError("at least one explicit launcher feature is required")
    available = template.get("required_features", {})
    overrides = overrides or {}
    result = dict(info)
    for feature in requested:
        spec = available.get(feature)
        if not isinstance(spec, dict):
            raise LauncherError(f"no reviewed usage description exists for feature: {feature}")
        key = spec.get("info_plist_key")
        value = overrides.get(feature, spec.get("default_text"))
        if not isinstance(key, str) or not key or not isinstance(value, str) or not value.strip():
            raise LauncherError(f"usage description is missing for feature: {feature}")
        result[key] = value.strip()
    return result


def validate_koov_app_id(value: str) -> str:
    if not re.fullmatch(r"[a-p]{32}", value):
        raise LauncherError("KOOV Chrome app ID must be 32 characters from a through p")
    return value


def validate_registration_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise LauncherError("KOOV registration URL must be an absolute HTTPS URL without credentials")
    return value


def launcher_script(app_path: Path, profile_path: Path, executable_path: Path,
                    runtime_architecture: str, *, koov_app_id: str | None = None,
                    registration_url: str | None = None) -> str:
    if runtime_architecture not in {"x86_64", "arm64"}:
        raise LauncherError("runtime architecture must be x86_64 or arm64")
    if (koov_app_id is None) == (registration_url is None):
        raise LauncherError("choose exactly one KOOV daily app ID or registration URL")
    entrypoint = ("--app-id=" + validate_koov_app_id(koov_app_id) if koov_app_id is not None
                  else "--app=" + validate_registration_url(registration_url or ""))
    app_path = app_path.expanduser().resolve(strict=True)
    profile_path = profile_path.expanduser().resolve(strict=False)
    executable_path = executable_path.expanduser().absolute()
    app = shlex.quote(str(app_path))
    executable = shlex.quote(str(executable_path))
    profile = shlex.quote(str(profile_path))
    python = shlex.quote(PYTHON_COMMAND)
    arch_command = shlex.quote(ARCH_COMMAND)
    version = shlex.quote(str(_read_binding_value(app_path, "chrome_version")))
    architecture = shlex.quote(runtime_architecture)
    installation_id = shlex.quote(str(_read_binding_value(app_path, "installation_id")))
    build_key = shlex.quote(str(_read_binding_value(app_path, "artifact_build_key")))
    launch_entry = shlex.quote(entrypoint)
    return f'''#!/bin/bash
set -euo pipefail
APP_PATH={app}
PROFILE_PATH={profile}
CHROME_EXECUTABLE={executable}
EXPECTED_VERSION={version}
EXPECTED_ARCHITECTURE={architecture}
INSTALLATION_ID={installation_id}
EXPECTED_BUILD_KEY={build_key}
BINDING_FILE="$PROFILE_PATH/.angle-profile-binding.json"
if [[ ! -d "$APP_PATH" || ! -d "$PROFILE_PATH" || -L "$PROFILE_PATH" || ! -x "$CHROME_EXECUTABLE" ]]; then
  printf 'Chrome copy is missing\\n' >&2
  exit 66
fi
{python} - "$BINDING_FILE" "$APP_PATH" "$EXPECTED_VERSION" "$EXPECTED_ARCHITECTURE" "$INSTALLATION_ID" "$EXPECTED_BUILD_KEY" "$PROFILE_PATH" <<'PY'
import json, os, plistlib, sys
binding_path, app_path, version, architecture, installation_id, build_key, profile_path = sys.argv[1:]
try:
    if os.path.islink(binding_path) or os.path.islink(os.path.join(app_path, "Contents", "Resources", "ANGLE_LOCAL_BINDING.json")):
        raise SystemExit("symbolic installation binding is refused")
    binding = json.load(open(binding_path, encoding="utf-8"))
    app = os.path.realpath(app_path)
    profile = os.path.realpath(profile_path)
    info = plistlib.load(open(os.path.join(app, "Contents", "Info.plist"), "rb"))
    local = json.load(open(os.path.join(app, "Contents", "Resources", "ANGLE_LOCAL_BINDING.json"), encoding="utf-8"))
except (OSError, ValueError, TypeError):
    raise SystemExit("Chrome profile or installation binding is unavailable")
expected = {{"schema": "angle-profile-binding-v1", "installation_id": installation_id,
            "chrome_app_path": app, "chrome_version": version,
            "runtime_architecture": architecture, "artifact_build_key": build_key,
            "profile_path": profile}}
if any(binding.get(key) != value for key, value in expected.items()):
    raise SystemExit("dedicated Chrome profile is bound to a different installation")
if (info.get("CFBundleShortVersionString") != version or
        local.get("schema") != "angle-local-binding-v1" or
        local.get("installation_id") != installation_id or
        local.get("chrome_version") != version or
        local.get("runtime_architecture") != architecture or
        local.get("artifact_build_key") != build_key):
    raise SystemExit("Chrome copy does not match the dedicated profile binding")
PY
export ANGLE_PHASE5_ENABLE_METAL_FAMILY1=1
exec {arch_command} "-$EXPECTED_ARCHITECTURE" "$CHROME_EXECUTABLE" \\
  --use-dynamic-angle \\
  --use-gl=angle \\
  --use-angle=metal \\
  --disable-angle-features=requireGpuFamily2 \\
  --user-data-dir="$PROFILE_PATH" \\
  {launch_entry}
'''


def _read_binding_value(app_path: Path, key: str) -> Any:
    try:
        value = json.loads((app_path / "Contents/Resources/ANGLE_LOCAL_BINDING.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LauncherError("Chrome copy has no usable local installation binding") from exc
    if value.get("schema") != "angle-local-binding-v1" or not value.get(key):
        raise LauncherError("Chrome copy has no usable local installation binding")
    return value[key]
