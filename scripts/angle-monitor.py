#!/usr/bin/env python3
"""Manage the monitor's bounded state and version-index artifact records."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.maintenance_angle.github_artifacts import GitHubActionsArtifacts, GitHubError, usable_artifact  # noqa: E402
from src.maintenance_angle.stable import ReleaseError, select_candidate  # noqa: E402
from src.maintenance_angle.versionhistory import fetch_releases  # noqa: E402

BASELINE = "156.0.8078.48"
WORKFLOW = "watch-chrome-stable.yml"
EXACT_VERSION = re.compile(r"\d+(?:\.\d+){3}")
SHA1 = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
RETRYABLE_FAILURES = {"CI_BUILD_FAILED", "CI_BUILD_INTERRUPTED"}


def _valid_version(value: str) -> bool:
    return bool(EXACT_VERSION.fullmatch(value))


def _run_record(state: dict, run_id: str, version: str) -> dict:
    matches = [record for record in state["records"]
               if isinstance(record, dict) and str(record.get("run_id", "")) == str(run_id)
               and record.get("chrome_version") == version]
    if len(matches) != 1:
        raise ValueError("the current run must have exactly one version record")
    return matches[0]


def read_candidate(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("candidate record is unavailable") from exc
    if not isinstance(data, dict):
        raise ValueError("candidate record is malformed")
    return data


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def begin(args: argparse.Namespace) -> int:
    client = GitHubActionsArtifacts(args.repository)
    state = client.load_latest_state(WORKFLOW) or {
        "schema": "angle-stable-monitor-state-v1",
        "baseline": BASELINE,
        "last_detected_version": BASELINE,
        "records": [],
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "state_backend": "GitHub Actions artifacts",
        "state_retention_days": 90,
    }
    if not isinstance(state.get("records"), list) or not isinstance(state.get("last_detected_version"), str):
        raise ValueError("monitor state is malformed")
    if any(not isinstance(record, dict) for record in state["records"]):
        raise ValueError("monitor state contains a malformed version record")
    reacquire_version = args.reacquire_version
    retry_version = getattr(args, "retry_failed_version", "")
    operation = getattr(args, "operation", "")
    if operation == "reacquire_expired_artifact" and not reacquire_version:
        raise ValueError("the expired-artifact operation requires an exact version")
    if operation == "retry_failed_version" and not retry_version:
        raise ValueError("the failed-version retry operation requires an exact version")
    if operation == "monitor" and (reacquire_version or retry_version):
        raise ValueError("version retry inputs require their matching explicit operation")
    if reacquire_version and retry_version:
        raise ValueError("expired-artifact re-acquire and failed-version retry are separate operations")
    if retry_version:
        version = retry_version
        if not _valid_version(version):
            raise ValueError("retry target must be an exact four-part version")
        same_version = [record for record in state["records"] if isinstance(record, dict)
                        and record.get("chrome_version") == version]
        if any(str(record.get("run_id", "")) == str(args.run_id) for record in same_version):
            raise ValueError("this workflow run already has an attempt record for the requested version")
        if not same_version or same_version[-1].get("status") not in RETRYABLE_FAILURES:
            raise ValueError("the latest indexed attempt for this version is not failed or interrupted; use artifact re-acquire only for an expired success")
        previous = same_version[-1]
        previous_source = next((record for record in reversed(same_version)
                                if record.get("chromium_revision") or record.get("angle_revision")), None)
        expected_pins = None
        if previous_source is not None:
            chromium_revision = previous_source.get("chromium_revision")
            angle_revision = previous_source.get("angle_revision")
            if not isinstance(chromium_revision, str) or not SHA1.fullmatch(chromium_revision) or \
                    not isinstance(angle_revision, str) or not SHA1.fullmatch(angle_revision):
                raise ValueError("prior source pins are incomplete or malformed; refusing to substitute new pins")
            expected_pins = {"chromium_revision": chromium_revision, "angle_revision": angle_revision}
            source_mode = "compare-with-last-recorded-source-pins"
        else:
            if not getattr(args, "confirm_unpinned_retry", False):
                raise ValueError("no source pins were recorded; explicitly confirm a fresh resolution of this exact Chrome tag")
            source_mode = "fresh-exact-tag-after-prior-attempt-had-no-recorded-pins"
        previous_inputs = next(({
            key: record.get(key) for key in ("patchset_id", "patch_sha256", "recipe_id", "recipe_sha256",
                                              "selection_mode", "workflow_revision") if record.get(key) is not None
        } for record in reversed(same_version) if any(record.get(key) is not None for key in (
            "patchset_id", "patch_sha256", "recipe_id", "recipe_sha256", "selection_mode", "workflow_revision"))), {})
        failure_stage = previous.get("failure_stage") or previous.get("reason") or "unknown"
        retry_record = {
            "chrome_version": version, "platform": "macOS", "architecture": "x86_64",
            "status": "RETRY_REQUESTED", "run_id": str(args.run_id),
            "retry_of_run_id": str(previous.get("run_id", "")),
            "retry_of_status": previous.get("status"), "retry_of_failure_stage": failure_stage,
            "retry_source_mode": source_mode,
            "retry_source_pin_run_id": str(previous_source.get("run_id", "")) if previous_source else None,
            "expected_source_pins": expected_pins,
            "retry_previous_inputs": previous_inputs,
            "retry_unpinned_source_acknowledged": expected_pins is None,
            "detected_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        state["records"].append(retry_record)
        output = {
            "status": "BUILD_CANDIDATE", "chrome_version": version,
            "retry_failed_version": True, "retry_of_run_id": retry_record["retry_of_run_id"],
            "retry_of_status": retry_record["retry_of_status"],
            "retry_of_failure_stage": failure_stage, "retry_source_mode": source_mode,
            "expected_source_pins": expected_pins, "retry_previous_inputs": previous_inputs,
            "unpinned_source_retry_acknowledged": expected_pins is None,
        }
    elif reacquire_version:
        version = reacquire_version
        if not _valid_version(version):
            raise ValueError("re-acquire target must be an exact four-part version")
        prior = [record for record in state["records"] if record.get("chrome_version") == version
                 and record.get("status") == "CI_BUILD_SUCCEEDED"]
        prior.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        if not prior:
            raise ValueError("no successful indexed record exists for the requested version")
        old = prior[0]
        if any(str(record.get("run_id", "")) == str(args.run_id) for record in state["records"]
               if isinstance(record, dict) and record.get("chrome_version") == version):
            raise ValueError("this workflow run already has an attempt record for the requested version")
        old_artifact = next((item for item in client.artifacts()
                             if item.get("id") == old.get("artifact_id")), None)
        if usable_artifact(old_artifact):
            output = {"status": "EXISTING_ARTIFACT_AVAILABLE", "chrome_version": version,
                      "artifact_id": old.get("artifact_id"), "expires_at": old.get("expires_at")}
        else:
            for field in ("chromium_revision", "angle_revision"):
                if not isinstance(old.get(field), str):
                    raise ValueError("indexed source pins are missing; cannot re-acquire safely")
            state["records"].append({
                "chrome_version": version, "platform": "macOS", "architecture": "x86_64",
                "status": "REACQUIRE_REQUESTED", "reacquire_of_run_id": old.get("run_id"),
                "reacquire_of_artifact_id": old.get("artifact_id"), "reacquire_requested_run_id": args.run_id,
                "chromium_revision": old["chromium_revision"], "angle_revision": old["angle_revision"],
                "run_id": args.run_id,
                "detected_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            })
            output = {"status": "BUILD_CANDIDATE", "chrome_version": version,
                      "chromium_revision": old["chromium_revision"], "angle_revision": old["angle_revision"],
                      "reacquire": True, "reacquire_of_run_id": old.get("run_id"),
                      "reacquire_of_artifact_id": old.get("artifact_id")}
    elif args.fixture:
        payload = json.loads(args.fixture.read_text(encoding="utf-8"))
        candidate = select_candidate(payload, state.get("last_detected_version", BASELINE))
        output = candidate or {"status": "NO_NEW_FULLY_ROLLED_OUT_STABLE"}
    else:
        payload = fetch_releases()
        candidate = select_candidate(payload, state.get("last_detected_version", BASELINE))
        output = candidate or {"status": "NO_NEW_FULLY_ROLLED_OUT_STABLE"}
    if output.get("status") == "stable-fully-rolled-out" and "chrome_version" in output:
        output = {**output, "status": "BUILD_CANDIDATE"}
    if output.get("status") == "BUILD_CANDIDATE" and not output.get("reacquire") and not output.get("retry_failed_version"):
        candidate = output
        state["last_detected_version"] = candidate["chrome_version"]
        release = {**candidate, "status": "stable-fully-rolled-out"}
        state["records"].append({
            "chrome_version": candidate["chrome_version"],
            "platform": "macOS",
            "architecture": "x86_64",
            "status": "STABLE_RELEASE_DETECTED",
            "release": release,
            "detected_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "run_id": args.run_id,
        })
        output = {"status": "BUILD_CANDIDATE", **candidate}
    if len(state["records"]) > 1000:
        state["records"] = state["records"][-1000:]
    state["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    write(args.state, state)
    write(args.output, output)
    print(f"{output['status']}")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write(f"status={output['status']}\n")
            if output.get("chrome_version"):
                stream.write(f"chrome_version={output['chrome_version']}\n")
    return 0


def record_source(args: argparse.Namespace) -> int:
    state = json.loads(args.state.read_text(encoding="utf-8"))
    candidate = read_candidate(args.candidate)
    try:
        source = json.loads(args.source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("resolved source pins are unavailable") from exc
    version = candidate.get("chrome_version")
    if not isinstance(version, str) or source.get("chrome_version") != version:
        raise ValueError("resolved source version differs from the exact candidate")
    chromium_revision = source.get("chromium_revision")
    angle_revision = source.get("angle_revision")
    if not isinstance(chromium_revision, str) or not SHA1.fullmatch(chromium_revision) or \
            not isinstance(angle_revision, str) or not SHA1.fullmatch(angle_revision):
        raise ValueError("resolved Chromium and ANGLE pins must be full 40-character revisions")
    record = _run_record(state, str(args.run_id), version)
    expected = candidate.get("expected_source_pins")
    if candidate.get("reacquire"):
        expected = {"chromium_revision": candidate.get("chromium_revision"),
                    "angle_revision": candidate.get("angle_revision")}
    if expected is not None and (expected.get("chromium_revision") != chromium_revision or
                                 expected.get("angle_revision") != angle_revision):
        record.update({"source_resolution_status": "pin-mismatch",
                       "observed_chromium_revision": chromium_revision,
                       "observed_angle_revision": angle_revision,
                       "source_pin_mismatch": True})
        write(args.state, state)
        raise ValueError("exact Chrome tag resolved to different pins; observed pins were recorded and no build was started")
    if candidate.get("retry_failed_version") and expected is None and not candidate.get("unpinned_source_retry_acknowledged"):
        raise ValueError("retry with no prior source pins lacks an explicit exact-tag resolution acknowledgment")
    record.update({
        "source_resolution_status": "resolved", "source_resolution_run_id": str(args.run_id),
        "source_resolution_mode": candidate.get("retry_source_mode", "exact-chromium-version-tag"),
        "chromium_revision": chromium_revision, "angle_revision": angle_revision,
    })
    record.pop("observed_chromium_revision", None)
    record.pop("observed_angle_revision", None)
    record.pop("source_pin_mismatch", None)
    state["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    write(args.state, state)
    print("exact Chrome tag source pins recorded")
    return 0


def record_inputs(args: argparse.Namespace) -> int:
    state = json.loads(args.state.read_text(encoding="utf-8"))
    candidate = read_candidate(args.candidate)
    try:
        inputs = json.loads(args.inputs.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("resolved patch and recipe inputs are unavailable") from exc
    version = candidate.get("chrome_version")
    if not isinstance(version, str) or inputs.get("chrome_version") != version:
        raise ValueError("resolved build inputs differ from the exact candidate")
    record = _run_record(state, str(args.run_id), version)
    if (record.get("source_resolution_status") != "resolved" or
            inputs.get("chromium_revision") != record.get("chromium_revision") or
            inputs.get("angle_revision") != record.get("angle_revision")):
        raise ValueError("build inputs do not match the source pins already recorded for this run")
    values = {
        "patchset_id": inputs.get("patchset_id"), "patch_sha256": inputs.get("patch_sha256"),
        "recipe_id": inputs.get("recipe_id"), "recipe_sha256": inputs.get("recipe_sha256"),
        "selection_mode": inputs.get("selection_mode"),
        "workflow_revision": inputs.get("workflow_revision"), "build_key": inputs.get("build_key"),
    }
    if (not all(isinstance(values[key], str) and values[key] for key in ("patchset_id", "recipe_id")) or
            values["selection_mode"] not in {
                "catalog-baseline", "new-revision-candidate",
                "explicit-known-version-trial", "explicit-unlisted-revision-trial"} or
            not all(isinstance(values[key], str) and SHA256.fullmatch(values[key])
                    for key in ("patch_sha256", "recipe_sha256", "build_key")) or
            not isinstance(values["workflow_revision"], str) or not SHA1.fullmatch(values["workflow_revision"])):
        raise ValueError("resolved patch/recipe/build key metadata is incomplete")
    previous_inputs = record.get("retry_previous_inputs", {})
    if not isinstance(previous_inputs, dict):
        raise ValueError("prior retry input record is malformed")
    changes = sorted(key for key, value in values.items()
                     if previous_inputs.get(key) is not None and previous_inputs.get(key) != value)
    record.update(values)
    record["input_resolution_status"] = "resolved"
    if candidate.get("retry_failed_version"):
        record["retry_input_changes"] = changes
    state["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    write(args.state, state)
    print("exact patch, recipe, selection mode, workflow revision, and build key recorded")
    return 0


def finish(args: argparse.Namespace) -> int:
    client = GitHubActionsArtifacts(args.repository)
    state = json.loads(args.state.read_text(encoding="utf-8"))
    candidate = read_candidate(args.candidate)
    if candidate.get("status") == "BUILD_CANDIDATE":
        records = [r for r in state["records"] if isinstance(r, dict)
                   and str(r.get("run_id", "")) == str(args.run_id)]
        if not records:
            raise ValueError("detected release record is missing from state")
        record = records[-1]
        if args.job_status == "success":
            artifact = client.find_artifact(args.artifact_name)
            try:
                manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                manifest = None
            workflow_run = artifact.get("workflow_run", {}) if artifact else {}
            artifact_belongs_to_run = str(workflow_run.get("id", "")) == str(args.run_id)
            if not usable_artifact(artifact) or not artifact_belongs_to_run or not isinstance(manifest, dict):
                record.update({"status": "ARTIFACT_MISSING_OR_EXPIRED", "reason": "artifact-upload-not-confirmed",
                               "failure_stage": "artifact-publication"})
            else:
                expected = {
                    "run_id": str(args.run_id), "artifact_name": args.artifact_name,
                    "build_key": args.build_key, "chrome_version": str(record.get("chrome_version", "")),
                }
                for field in ("chromium_revision", "angle_revision", "patchset_id", "patch_sha256",
                              "recipe_id", "recipe_sha256", "selection_mode", "workflow_revision"):
                    if record.get(field) is not None:
                        expected[field] = str(record[field])
                if any(str(manifest.get(key, "")) != value for key, value in expected.items()):
                    record.update({"status": "ARTIFACT_METADATA_MISMATCH", "reason": "manifest-index-disagreement",
                                   "failure_stage": "artifact-metadata-validation"})
                else:
                    record.update({
                        "status": "CI_BUILD_SUCCEEDED", "artifact_id": artifact["id"],
                        "artifact_name": artifact["name"], "run_id": str(args.run_id),
                        "created_at": artifact.get("created_at"), "expires_at": artifact.get("expires_at"),
                        "platform": manifest.get("platform"), "architecture": manifest.get("architecture"),
                        "chromium_revision": manifest.get("chromium_revision"),
                        "angle_revision": manifest.get("angle_revision"),
                        "patchset_id": manifest.get("patchset_id"), "patch_sha256": manifest.get("patch_sha256"),
                        "recipe_id": manifest.get("recipe_id"), "recipe_sha256": manifest.get("recipe_sha256"),
                        "selection_mode": manifest.get("selection_mode"),
                        "depot_tools_revision": manifest.get("depot_tools_revision"),
                        "runner": manifest.get("runner"), "xcode_version": manifest.get("xcode_version"),
                        "macos_sdk_version": manifest.get("macos_sdk_version"),
                        "clang_version": manifest.get("clang_version"), "ninja_version": manifest.get("ninja_version"),
                        "gn_args_sha256": manifest.get("gn_args_sha256"), "libraries": manifest.get("libraries"),
                        "license_sha256": manifest.get("license_sha256"),
                        "workflow_revision": manifest.get("workflow_revision"),
                        "reacquire_of_run_id": record.get("reacquire_of_run_id"),
                        "reacquire_of_artifact_id": record.get("reacquire_of_artifact_id"),
                        "device_compatibility": "not-assessed", "adoption_status": "not-assessed",
                    })
        else:
            stage = args.failure_stage or "candidate-build"
            status = "CI_BUILD_INTERRUPTED" if args.job_status == "cancelled" else "CI_BUILD_FAILED"
            record.update({"status": status, "reason": stage, "failure_stage": stage})
            if stage == "official-tag-resolution" and record.get("source_resolution_status") != "resolved":
                record["source_resolution_status"] = "failed"
    state["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    write(args.state, state)
    print("monitor state finalized")
    return 0


def recover(args: argparse.Namespace) -> int:
    client = GitHubActionsArtifacts(args.repository)
    version = args.last_processed_version.strip()
    reason = args.reason.strip()
    state = None
    recovery_source = "explicit-owner-baseline"
    try:
        state = client.load_latest_state(WORKFLOW)
    except GitHubError:
        state = None
    if state is None:
        if len(version.split(".")) != 4 or not all(part.isdigit() for part in version.split(".")):
            raise ValueError("state is unavailable; provide an exact four-part last processed version")
        if tuple(int(part) for part in version.split(".")) < tuple(int(part) for part in BASELINE.split(".")):
            raise ValueError("recovery version cannot be older than the catalog baseline")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+){1,8}", reason) or len(reason) < 12:
            raise ValueError("state is unavailable; provide a generic lowercase recovery reason slug")
        state = {
            "schema": "angle-stable-monitor-state-v1", "baseline": BASELINE,
            "last_detected_version": version, "records": [],
            "state_backend": "GitHub Actions artifacts",
            "state_retention_days": 90,
        }
    else:
        retained_version = state.get("last_detected_version")
        if not isinstance(retained_version, str):
            raise ValueError("retained monitor state has no last processed version")
        if version and version != retained_version:
            raise ValueError("provided recovery version differs from the retained state")
        version = retained_version
        if not reason:
            reason = "retained-state-recovered"
        elif not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+){1,8}", reason):
            raise ValueError("recovery reason must be a generic lowercase slug")
        recovery_source = "retained-state-or-checkpoint"
    records = state.get("records")
    if not isinstance(records, list):
        raise ValueError("monitor state records are malformed")
    records.append({
        "chrome_version": version, "platform": "macOS", "architecture": "x86_64",
        "status": "STATE_RECOVERY_AUDIT", "reason": reason,
        "recovery_source": recovery_source, "run_id": str(args.run_id),
        "detected_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    })
    if len(records) > 1000:
        state["records"] = records[-1000:]
    state["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    write(args.state, state)
    print("monitor state recovered; no build was started")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("begin")
    p.add_argument("--operation", choices=("monitor", "retry_failed_version", "reacquire_expired_artifact"),
                   default="monitor")
    p.add_argument("--repository", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--fixture", type=Path)
    p.add_argument("--github-output", type=Path)
    p.add_argument("--reacquire-version", default="")
    p.add_argument("--retry-failed-version", default="")
    p.add_argument("--confirm-unpinned-retry", action="store_true")
    p.set_defaults(func=begin)
    p = sub.add_parser("record-source")
    p.add_argument("--run-id", required=True)
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.set_defaults(func=record_source)
    p = sub.add_parser("record-inputs")
    p.add_argument("--run-id", required=True)
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--inputs", type=Path, required=True)
    p.set_defaults(func=record_inputs)
    p = sub.add_parser("finish")
    p.add_argument("--repository", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--artifact-name", required=True)
    p.add_argument("--job-status", choices=("success", "failure", "cancelled"), required=True)
    p.add_argument("--failure-stage", default="")
    p.add_argument("--build-key", default="")
    p.add_argument("--manifest", type=Path, default=Path("/nonexistent"))
    p.set_defaults(func=finish)
    p = sub.add_parser("recover")
    p.add_argument("--repository", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--last-processed-version", default="")
    p.add_argument("--reason", default="")
    p.set_defaults(func=recover)
    args = parser.parse_args()
    try:
        return args.func(args)
    except (OSError, json.JSONDecodeError, ValueError, KeyError, TypeError, GitHubError, ReleaseError) as exc:
        print(f"monitor operation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
