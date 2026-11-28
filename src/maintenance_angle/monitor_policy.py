"""Durable policy state and effective-input fingerprints for Stable monitoring."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
from typing import Any

from .stable import version_key

STATE_SCHEMA_V1 = "angle-stable-monitor-state-v1"
STATE_SCHEMA_V2 = "angle-stable-monitor-state-v2"
SUCCESS_STATUS = "CI_BUILD_SUCCEEDED"
PENDING_SUCCESS_STATUS = "CI_BUILD_SUCCEEDED_PENDING_STATE"
FAILED_STATUSES = {
    "CI_BUILD_FAILED", "CI_BUILD_INTERRUPTED", "ARTIFACT_MISSING_OR_EXPIRED",
    "ARTIFACT_METADATA_MISMATCH", "SOURCE_PIN_MISMATCH",
}
ACTIVE_STATUSES = {"STABLE_RELEASE_DETECTED", "RETRY_REQUESTED", "REACQUIRE_REQUESTED"}

_CODE_MODULES = {
    "artifact.py", "chromium.py", "github_artifacts.py", "inputs.py",
    "monitor_policy.py", "stable.py", "versionhistory.py",
}
_CODE_SCRIPTS = {
    "angle-monitor.py", "check-publication-privacy.py", "resolve-build-inputs.py",
    "resolve-chromium-source.py", "write-angle-manifest.py", "verify-angle-artifact.py",
}


class MonitorStateError(ValueError):
    pass


class FingerprintError(MonitorStateError):
    pass


def _valid_version(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        version_key(value)
        return True
    except ValueError:
        return False


def _tracked_paths(root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"], check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise FingerprintError("cannot inspect tracked effective build inputs") from exc
    try:
        paths = [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]
    except UnicodeDecodeError as exc:
        raise FingerprintError("tracked input path is not UTF-8") from exc
    return sorted(paths)


def _is_effective_input(path: str) -> bool:
    if path in {".gitattributes", ".github/workflows/watch-chrome-stable.yml", "LICENSE"}:
        return True
    if path.startswith(("catalog/chrome/", "catalog/angle-revisions/",
                        "catalog/patchsets/", "catalog/recipes/")):
        return Path(path).suffix.lower() == ".json"
    if path.startswith(("patches/", "licenses/", "tests/angle-policy/")):
        return True
    if path.startswith("scripts/"):
        name = Path(path).name
        return path.endswith(".sh") or name in _CODE_SCRIPTS or name.startswith("verify-")
    if path.startswith("src/maintenance_angle/"):
        return Path(path).name in _CODE_MODULES
    return False


def effective_input_fingerprint(root: Path, chrome_version: str) -> str:
    """Hash the exact Stable build/verification inputs, excluding commit IDs and docs.

    The Chrome four-part tag is itself a source identity. Its resolved Chromium and
    ANGLE pins are separately recorded and checked; a changed pin for the same tag
    is rejected before any build. Tracked JSON catalog data, patch/recipe bytes,
    licenses, and monitor/build/verification inputs are inspected; catalog prose
    and other documentation are excluded.
    """
    if not _valid_version(chrome_version):
        raise FingerprintError("candidate version is malformed")
    root = root.resolve(strict=True)
    paths = [path for path in _tracked_paths(root) if _is_effective_input(path)]
    required = {
        ".github/workflows/watch-chrome-stable.yml", "scripts/angle-monitor.py",
        "scripts/build-and-verify-angle.sh", "scripts/build-angle-candidate.sh",
        "scripts/bootstrap-depot-tools.sh", "scripts/resolve-build-inputs.py",
        "scripts/resolve-chromium-source.py", "scripts/verify-artifact.sh",
        "scripts/verify-angle-binaries.sh", "scripts/verify-angle-artifact.py",
        "scripts/write-angle-manifest.py", "src/maintenance_angle/monitor_policy.py",
    }
    missing = required.difference(paths)
    if missing:
        raise FingerprintError("required effective build inputs are not tracked")
    digest = hashlib.sha256()
    digest.update(b"angle-stable-effective-inputs-v1\0")
    digest.update(chrome_version.encode("ascii") + b"\0")
    for relative in paths:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise FingerprintError("effective build input is missing or not a regular file")
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise FingerprintError("effective build input could not be inspected") from exc
        encoded = relative.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


def _summary(record: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "chrome_version", "platform", "architecture", "run_id", "status", "artifact_id",
        "artifact_name", "created_at",
        "expires_at", "chromium_revision", "angle_revision", "patchset_id", "patch_sha256",
        "recipe_id", "recipe_sha256", "selection_mode", "build_key", "workflow_revision",
        "effective_fingerprint", "device_compatibility", "adoption_status",
    )
    return {key: record[key] for key in fields if key in record}


def _fingerprint_history(*values: Any) -> list[str]:
    history: list[str] = []
    for value in values:
        if isinstance(value, list):
            for item in value:
                if item not in history:
                    history.append(item)
        elif isinstance(value, str) and value not in history:
            history.append(value)
    return history


def _attempt_history(outcome: dict[str, Any]) -> list[str]:
    # Accept the pre-release v2 spelling during local development of this schema.
    return outcome.get("attempted_fingerprints", outcome.get("automatic_attempt_fingerprints", []))


def normalize_state(state: dict[str, Any], *, final_state_artifact: bool = False) -> dict[str, Any]:
    """Validate and migrate v1 state without rolling back or dropping its records."""
    if not isinstance(state, dict) or state.get("schema") not in {STATE_SCHEMA_V1, STATE_SCHEMA_V2}:
        raise MonitorStateError("unsupported monitor state schema")
    records = state.get("records")
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise MonitorStateError("monitor state records are malformed")
    detected = state.get("last_detected_version")
    if not _valid_version(detected):
        raise MonitorStateError("monitor state has no valid last detected version")
    start = state.get("monitor_start_version", state.get("baseline"))
    if not _valid_version(start):
        raise MonitorStateError("monitor state has no valid start baseline")
    legacy_baseline = state.get("baseline", start)
    if not _valid_version(legacy_baseline):
        raise MonitorStateError("monitor state baseline is malformed")
    watermark = state.get("last_successful_version")
    if watermark is not None and not _valid_version(watermark):
        raise MonitorStateError("monitor state successful version is malformed")

    state["monitor_start_version"] = start
    state["baseline"] = state.get("baseline", start)
    state["schema"] = STATE_SCHEMA_V2

    successes = state.get("success_index", {})
    if not isinstance(successes, dict) or any(
        not _valid_version(version) or not isinstance(summary, dict)
        for version, summary in successes.items()
    ):
        raise MonitorStateError("monitor state success index is malformed")
    for version, summary in successes.items():
        if summary.get("status") != SUCCESS_STATUS:
            raise MonitorStateError("monitor state success index contains a non-success record")
        fingerprint = summary.get("effective_fingerprint")
        if fingerprint is not None and (not isinstance(fingerprint, str) or len(fingerprint) != 64 or
                                        any(char not in "0123456789abcdef" for char in fingerprint)):
            raise MonitorStateError("monitor state success index has a malformed effective-input fingerprint")
        if watermark is None or version_key(version) > version_key(watermark):
            watermark = version
    outcomes = state.get("candidate_outcomes", {})
    if not isinstance(outcomes, dict) or any(
        not _valid_version(version) or not isinstance(outcome, dict)
        for version, outcome in outcomes.items()
    ):
        raise MonitorStateError("monitor state candidate ledger is malformed")
    for outcome in outcomes.values():
        attempts = _attempt_history(outcome)
        if (not isinstance(attempts, list) or any(
            not isinstance(item, str) or len(item) != 64 or
            any(char not in "0123456789abcdef" for char in item) for item in attempts
        )):
            raise MonitorStateError("monitor state attempt fingerprint history is malformed")

    attempt_histories = {
        version: _fingerprint_history(_attempt_history(outcome))
        for version, outcome in outcomes.items()
    }
    for version, summary in successes.items():
        fingerprint = summary.get("effective_fingerprint")
        if isinstance(fingerprint, str):
            attempt_histories[version] = _fingerprint_history(attempt_histories.get(version, []), fingerprint)

    for record in records:
        version = record.get("chrome_version")
        if version is not None and not _valid_version(version):
            raise MonitorStateError("monitor state contains an invalid recorded Chrome version")
        fingerprint = record.get("effective_fingerprint")
        if fingerprint is not None and (not isinstance(fingerprint, str) or len(fingerprint) != 64 or
                                        any(char not in "0123456789abcdef" for char in fingerprint)):
            raise MonitorStateError("monitor state contains a malformed effective-input fingerprint")
        record_attempts = record.get("attempted_fingerprints", [])
        if (not isinstance(record_attempts, list) or any(
            not isinstance(item, str) or len(item) != 64 or
            any(char not in "0123456789abcdef" for char in item) for item in record_attempts
        )):
            raise MonitorStateError("monitor state record attempt fingerprint history is malformed")
        if not _valid_version(version):
            continue
        status = record.get("status")
        history = _fingerprint_history(attempt_histories.get(version, []), record_attempts)
        if status in ACTIVE_STATUSES | FAILED_STATUSES | {SUCCESS_STATUS, PENDING_SUCCESS_STATUS}:
            history = _fingerprint_history(history, fingerprint)
        attempt_histories[version] = history
        if status == PENDING_SUCCESS_STATUS and final_state_artifact:
            run_id = str(record.get("run_id", ""))
            expected_name = f"angle-macos-x86_64-chrome-{version}-run-{run_id}"
            if (not run_id or isinstance(record.get("artifact_id"), bool) or
                    not isinstance(record.get("artifact_id"), int) or record["artifact_id"] <= 0 or
                    record.get("artifact_name") != expected_name or
                    not isinstance(record.get("created_at"), str) or
                    not isinstance(record.get("expires_at"), str)):
                raise MonitorStateError("pending success lacks confirmed Stable artifact metadata")
            record["status"] = SUCCESS_STATUS
            status = SUCCESS_STATUS
        elif status == PENDING_SUCCESS_STATUS:
            previous = outcomes.get(version, {})
            outcomes[version] = {
                "status": "IN_PROGRESS", "run_id": str(record.get("run_id", "")),
                "effective_fingerprint": record.get("effective_fingerprint"),
                "source_pins": _source_pins(record, previous.get("source_pins")),
                "source_pin_run_id": _source_pin_run_id(record, previous.get("source_pin_run_id")),
                "attempted_fingerprints": history,
            }
        if status == SUCCESS_STATUS:
            if watermark is None or version_key(version) > version_key(watermark):
                watermark = version
            old = successes.get(version)
            if old is None or str(record.get("created_at", "")) >= str(old.get("created_at", "")):
                successes[version] = _summary(record)
            outcomes[version] = {
                "status": SUCCESS_STATUS, "run_id": str(record.get("run_id", "")),
                "effective_fingerprint": record.get("effective_fingerprint"),
                "source_pins": _source_pins(record, outcomes.get(version, {}).get("source_pins")),
                "source_pin_run_id": _source_pin_run_id(
                    record, outcomes.get(version, {}).get("source_pin_run_id")),
                "attempted_fingerprints": history,
            }
        elif status in FAILED_STATUSES:
            previous = outcomes.get(version, {})
            outcome = {
                "status": status, "run_id": str(record.get("run_id", "")),
                "effective_fingerprint": record.get("effective_fingerprint"),
                "failure_stage": record.get("failure_stage") or record.get("reason"),
                "source_pins": _source_pins(record, previous.get("source_pins")),
                "source_pin_run_id": _source_pin_run_id(record, previous.get("source_pin_run_id")),
                "attempted_fingerprints": history,
            }
            for key in ("patchset_id", "patch_sha256", "recipe_id", "recipe_sha256",
                        "selection_mode", "workflow_revision", "build_key"):
                if key in record:
                    outcome[key] = record[key]
            for key in ("requires_action", "auto_retry_suppressed", "auto_retry_suppression_reason"):
                if key in record:
                    outcome[key] = record[key]
            if not isinstance(outcome["effective_fingerprint"], str):
                outcome.update({"auto_retry_blocked": True,
                                "auto_retry_block_reason": "legacy-failure-fingerprint-unavailable"})
                record.setdefault("auto_retry_suppressed", True)
                record.setdefault("auto_retry_suppression_reason", outcome["auto_retry_block_reason"])
            outcomes[version] = outcome
        elif status in ACTIVE_STATUSES:
            previous = outcomes.get(version, {})
            outcomes[version] = {
                "status": "IN_PROGRESS", "run_id": str(record.get("run_id", "")),
                "effective_fingerprint": record.get("effective_fingerprint"),
                "source_pins": _source_pins(record, previous.get("source_pins")),
                "source_pin_run_id": _source_pin_run_id(record, previous.get("source_pin_run_id")),
                "attempted_fingerprints": history,
            }

    if final_state_artifact:
        for version, outcome in list(outcomes.items()):
            if outcome.get("status") == PENDING_SUCCESS_STATUS:
                outcome["status"] = "IN_PROGRESS"
    if watermark is not None and watermark not in successes:
        raise MonitorStateError("successful version watermark has no formal success record")
    state["last_successful_version"] = watermark
    state["success_index"] = successes
    state["candidate_outcomes"] = outcomes
    return state


def _source_pins(record: dict[str, Any], fallback: Any = None) -> dict[str, str] | None:
    chromium = record.get("chromium_revision")
    angle = record.get("angle_revision")
    if isinstance(chromium, str) and isinstance(angle, str):
        return {"chromium_revision": chromium, "angle_revision": angle}
    expected = record.get("expected_source_pins")
    if isinstance(expected, dict):
        chromium = expected.get("chromium_revision")
        angle = expected.get("angle_revision")
        if isinstance(chromium, str) and isinstance(angle, str):
            return {"chromium_revision": chromium, "angle_revision": angle}
    if isinstance(fallback, dict):
        chromium = fallback.get("chromium_revision")
        angle = fallback.get("angle_revision")
        if isinstance(chromium, str) and isinstance(angle, str):
            return {"chromium_revision": chromium, "angle_revision": angle}
    return None


def _source_pin_run_id(record: dict[str, Any], fallback: Any = None) -> str | None:
    for key in ("source_resolution_run_id", "retry_source_pin_run_id",
                "expected_source_pin_run_id", "reacquire_of_run_id"):
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    if record.get("chromium_revision") and record.get("angle_revision"):
        value = record.get("run_id")
        if isinstance(value, str) and value:
            return value
    return fallback if isinstance(fallback, str) and fallback else None


def update_outcome(state: dict[str, Any], record: dict[str, Any]) -> None:
    """Mirror non-success decisions outside the bounded per-run records array."""
    version = record.get("chrome_version")
    if not _valid_version(version):
        raise MonitorStateError("version record has no exact Chrome version")
    if record.get("status") == SUCCESS_STATUS:
        raise MonitorStateError("formal success can only be promoted from a validated final-state artifact")
    state = normalize_state(state)
    status = record.get("status")
    previous_outcome = state["candidate_outcomes"].get(version, {})
    history = _fingerprint_history(
        _attempt_history(previous_outcome) if isinstance(previous_outcome, dict) else [],
        record.get("attempted_fingerprints", []),
    )
    if status in ACTIVE_STATUSES | FAILED_STATUSES | {SUCCESS_STATUS, PENDING_SUCCESS_STATUS}:
        history = _fingerprint_history(history, record.get("effective_fingerprint"))
    record["attempted_fingerprints"] = history
    if status == PENDING_SUCCESS_STATUS:
        state["candidate_outcomes"][version] = {
            "status": PENDING_SUCCESS_STATUS, "run_id": str(record.get("run_id", "")),
            "effective_fingerprint": record.get("effective_fingerprint"),
            "source_pins": _source_pins(record, previous_outcome.get("source_pins")),
            "source_pin_run_id": _source_pin_run_id(record, previous_outcome.get("source_pin_run_id")),
            "attempted_fingerprints": history,
        }
    elif status in FAILED_STATUSES:
        outcome = {
            "status": status, "run_id": str(record.get("run_id", "")),
            "effective_fingerprint": record.get("effective_fingerprint"),
            "failure_stage": record.get("failure_stage") or record.get("reason"),
            "source_pins": _source_pins(record, previous_outcome.get("source_pins")),
            "source_pin_run_id": _source_pin_run_id(record, previous_outcome.get("source_pin_run_id")),
            "attempted_fingerprints": history,
        }
        for key in ("patchset_id", "patch_sha256", "recipe_id", "recipe_sha256",
                    "selection_mode", "workflow_revision", "build_key"):
            if key in record:
                outcome[key] = record[key]
        if not outcome["effective_fingerprint"]:
            outcome.update({"auto_retry_blocked": True,
                            "auto_retry_block_reason": "legacy-failure-fingerprint-unavailable"})
        state["candidate_outcomes"][version] = outcome
    elif status in ACTIVE_STATUSES:
        state["candidate_outcomes"][version] = {
            "status": "IN_PROGRESS", "run_id": str(record.get("run_id", "")),
            "effective_fingerprint": record.get("effective_fingerprint"),
            "source_pins": _source_pins(record, previous_outcome.get("source_pins")),
            "source_pin_run_id": _source_pin_run_id(record, previous_outcome.get("source_pin_run_id")),
            "attempted_fingerprints": history,
        }


def confirm_final_state(state: dict[str, Any]) -> dict[str, Any]:
    """A final state artifact proves the pending success index was persisted."""
    return normalize_state(state, final_state_artifact=True)


def comparison_baseline(state: dict[str, Any]) -> str:
    """Use the later of the explicit start boundary and formal success watermark."""
    start = state["monitor_start_version"]
    successful = state.get("last_successful_version")
    if successful is None or version_key(successful) < version_key(start):
        return start
    return successful
