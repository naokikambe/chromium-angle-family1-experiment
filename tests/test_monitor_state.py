import copy
import importlib.util
import io
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from src.maintenance_angle.local import LocalError, fetch_artifact, find_index_record
from src.maintenance_angle.artifact import sha256
from src.maintenance_angle.github_artifacts import GitHubActionsArtifacts
from src.maintenance_angle.monitor_policy import confirm_final_state, normalize_state, update_outcome
from tests.test_artifact_handling import make_artifact

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/angle-monitor.py"
SPEC = importlib.util.spec_from_file_location("angle_monitor", SCRIPT)
monitor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(monitor)
RECOVERED_VERSION = ".".join(("158", "0", "1", "2"))
OLDER_VERSION = ".".join(("155", "0", "1", "1"))


class FakeClient:
    state = None
    artifact_list = []
    uploaded = None
    artifact_list = []
    archive_bytes = b""

    def __init__(self, repository):
        self.repository = repository

    def load_latest_state(self, workflow_file):
        return copy.deepcopy(self.state)

    def artifacts(self):
        return copy.deepcopy(self.artifact_list)

    def find_artifact(self, name):
        return copy.deepcopy(self.uploaded)

    def download_artifact(self, artifact_id):
        self.downloaded_id = artifact_id
        return self.archive_bytes


class MonitorStateTests(unittest.TestCase):
    def setUp(self):
        FakeClient.state = None
        FakeClient.artifact_list = []
        FakeClient.uploaded = None
        FakeClient.artifact_list = []
        FakeClient.archive_bytes = b""
        self.client_patch = patch.object(monitor, "GitHubActionsArtifacts", FakeClient)
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def args(self, **values):
        defaults = {"repository": "owner/repo", "run_id": "100", "state": self.root / "state.json",
                    "output": self.root / "candidate.json", "fixture": None, "github_output": None,
                    "reacquire_version": "", "retry_failed_version": "", "confirm_unpinned_retry": False,
                    "operation": "monitor", "last_processed_version": "", "reason": ""}
        defaults.update(values)
        return type("Args", (), defaults)()

    def test_new_candidate_persists_detection_and_exact_version(self):
        fixture = self.root / "releases.json"
        fixture.write_text(json.dumps({"releases": [{"version": "157.0.300.2", "fraction": 1.0,
                                                     "serving": {"startTime": "now"}}]}))
        args = self.args(fixture=fixture)
        self.assertEqual(monitor.begin(args), 0)
        state = json.loads(args.state.read_text())
        candidate = json.loads(args.output.read_text())
        self.assertEqual(candidate["status"], "BUILD_CANDIDATE")
        self.assertEqual(state["last_detected_version"], "157.0.300.2")
        self.assertIsNone(state["last_successful_version"])
        self.assertRegex(candidate["effective_fingerprint"], r"^[0-9a-f]{64}$")
        self.assertEqual(state["records"][0]["status"], "STABLE_RELEASE_DETECTED")

    def test_fingerprint_inspection_failure_stops_and_recovers_when_inputs_are_inspectable(self):
        fixture = self.root / "releases.json"
        fixture.write_text(json.dumps({"releases": [{"version": "157.0.300.2", "fraction": 1.0,
                                                     "serving": {"startTime": "now"}}]}))
        unavailable = self.args(run_id="100", fixture=fixture)
        with patch.object(monitor, "effective_input_fingerprint",
                          side_effect=monitor.FingerprintError("synthetic unavailable input")):
            monitor.begin(unavailable)
        state = json.loads(unavailable.state.read_text())
        self.assertEqual(json.loads(unavailable.output.read_text())["status"], "ACTION_REQUIRED")
        self.assertEqual(state["candidate_outcomes"]["157.0.300.2"]["status"], "FINGERPRINT_UNAVAILABLE")

        FakeClient.state = state
        restored = self.args(run_id="101", fixture=fixture)
        with patch.object(monitor, "effective_input_fingerprint", return_value="f" * 64):
            monitor.begin(restored)
        self.assertEqual(json.loads(restored.output.read_text())["status"], "BUILD_CANDIDATE")

    def test_manual_retry_fingerprint_failure_does_not_leave_a_false_active_attempt(self):
        version = "157.0.300.2"
        FakeClient.state = {"schema": "angle-stable-monitor-state-v2", "baseline": monitor.BASELINE,
            "monitor_start_version": monitor.BASELINE, "last_detected_version": version,
            "last_successful_version": None, "success_index": {},
            "candidate_outcomes": {version: {"status": "CI_BUILD_FAILED", "run_id": "20",
                "effective_fingerprint": "a" * 64, "attempted_fingerprints": ["a" * 64],
                "source_pins": {"chromium_revision": "b" * 40, "angle_revision": "c" * 40},
                "source_pin_run_id": "20"}},
            "records": [{"chrome_version": version, "run_id": "20", "status": "CI_BUILD_FAILED",
                "effective_fingerprint": "a" * 64, "chromium_revision": "b" * 40,
                "angle_revision": "c" * 40}]}
        retry = self.args(run_id="21", operation="retry_failed_version", retry_failed_version=version)
        with patch.object(monitor, "effective_input_fingerprint",
                          side_effect=monitor.FingerprintError("synthetic unavailable input")):
            monitor.begin(retry)
        state = json.loads(retry.state.read_text())
        self.assertEqual(json.loads(retry.output.read_text())["status"], "ACTION_REQUIRED")
        self.assertEqual(state["records"][-1]["status"], "EFFECTIVE_INPUT_FINGERPRINT_FAILED")

        FakeClient.state = state
        fixture = self.root / "releases.json"
        fixture.write_text(json.dumps({"releases": [{"version": version, "fraction": 1.0,
                                                       "serving": {"startTime": "now"}}]}))
        changed = self.args(run_id="22", fixture=fixture)
        with patch.object(monitor, "effective_input_fingerprint", return_value="b" * 64):
            monitor.begin(changed)
        self.assertEqual(json.loads(changed.output.read_text())["status"], "BUILD_CANDIDATE")

    def test_expired_exact_success_can_be_reacquired_manually(self):
        FakeClient.state = {"schema": "angle-stable-monitor-state-v1", "baseline": "156.0.8078.48",
                            "last_detected_version": "157.0.300.2", "records": [{
                                "chrome_version": "157.0.300.2", "platform": "macOS", "architecture": "x86_64",
                                "status": "CI_BUILD_SUCCEEDED", "artifact_id": 10, "artifact_name": "old",
                                "run_id": "9", "created_at": "2026-11-14T00:00:00Z",
                                "chromium_revision": "a" * 40, "angle_revision": "b" * 40,
                            }]}
        FakeClient.artifact_list = [{"id": 10, "expired": True,
                                     "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}]
        args = self.args(operation="reacquire_expired_artifact", reacquire_version="157.0.300.2", run_id="101")
        monitor.begin(args)
        candidate = json.loads(args.output.read_text())
        state = json.loads(args.state.read_text())
        self.assertTrue(candidate["reacquire"])
        self.assertEqual(candidate["chromium_revision"], "a" * 40)
        self.assertEqual(state["records"][-1]["run_id"], "101")
        self.assertEqual(state["last_detected_version"], "157.0.300.2")

    def test_trimmed_success_index_survives_state_roundtrip_and_local_fetch(self):
        version = "156.0.8078.48"
        run_id = "9000"
        artifact_id = 73
        artifact_dir = self.root / "artifact"
        manifest = make_artifact(artifact_dir, chrome_version=version, run_id=run_id)
        expiry = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        artifact_name = manifest["artifact_name"]
        success = {
            "chrome_version": version, "platform": "macOS", "architecture": "x86_64",
            "status": "CI_BUILD_SUCCEEDED", "run_id": run_id, "artifact_id": artifact_id,
            "artifact_name": artifact_name, "created_at": manifest["created_at"], "expires_at": expiry,
            "build_key": manifest["build_key"], "chromium_revision": manifest["chromium_revision"],
            "angle_revision": manifest["angle_revision"],
        }
        audit_records = [{"chrome_version": version, "status": "STATE_RECOVERY_AUDIT",
                          "run_id": str(index), "detected_at": "2026-11-15T00:00:00Z"}
                         for index in range(1000)]
        FakeClient.state = {
            "schema": "angle-stable-monitor-state-v1", "baseline": version,
            "last_detected_version": version, "records": [success, *audit_records],
        }
        release_fixture = self.root / "releases.json"
        release_fixture.write_text(json.dumps({"releases": [{"version": version, "fraction": 1.0,
            "serving": {"startTime": "2026-11-15T00:00:00Z"}}]}))
        args = self.args(run_id="1001", fixture=release_fixture)
        monitor.begin(args)

        persisted = json.loads(args.state.read_text())
        self.assertEqual(len(persisted["records"]), 1000)
        self.assertFalse(any(record.get("run_id") == run_id for record in persisted["records"]))
        indexed = persisted["success_index"][version]
        self.assertEqual(indexed["platform"], "macOS")
        self.assertEqual(indexed["architecture"], "x86_64")

        state_archive = io.BytesIO()
        with zipfile.ZipFile(state_archive, "w") as output:
            output.writestr("stable-monitor-state.json", args.state.read_text())
        state_artifact_expiry = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        remote = GitHubActionsArtifacts("owner/repo")
        with patch.object(remote, "artifacts", return_value=[{
                "id": 88, "name": "stable-monitor-state", "expired": False,
                "expires_at": state_artifact_expiry, "created_at": "2026-11-23T00:00:00Z",
                "workflow_run": {"id": "1001", "head_branch": "main"}}]), \
                patch.object(remote, "workflow_runs", return_value=[{
                    "id": "1001", "status": "completed", "created_at": "2026-11-23T00:00:00Z"}]), \
                patch.object(remote, "download_artifact", return_value=state_archive.getvalue()):
            loaded_state = remote.load_latest_state("watch-chrome-stable.yml")
        self.assertIsNotNone(loaded_state)
        self.assertEqual(loaded_state["success_index"][version]["architecture"], "x86_64")

        artifact_archive = self.root / "artifact.zip"
        with zipfile.ZipFile(artifact_archive, "w") as output:
            for path in artifact_dir.rglob("*"):
                if path.is_file():
                    output.write(path, arcname=path.relative_to(artifact_dir).as_posix())

        class IndexedClient:
            def __init__(self):
                self.state_reads = 0
                self.downloaded_id = None

            def load_latest_state(self, workflow_file):
                self.state_reads += 1
                return copy.deepcopy(loaded_state)

            def artifacts(self):
                return [{"id": artifact_id, "name": artifact_name, "expired": False,
                         "expires_at": expiry}]

            def download_artifact(self, requested_id):
                self.downloaded_id = requested_id
                return artifact_archive.read_bytes()

        client = IndexedClient()
        matched, _artifact = find_index_record("owner/repo", version, "x86_64", client)
        self.assertEqual(matched["run_id"], run_id)
        with self.assertRaises(LocalError):
            find_index_record("owner/repo", version, "arm64", client)
        destination = self.root / "fetched"
        result = fetch_artifact("owner/repo", version, "x86_64", destination, client)
        self.assertEqual(client.downloaded_id, artifact_id)
        self.assertEqual(result["manifest"]["build_key"], manifest["build_key"])
        self.assertEqual(client.state_reads, 3)

    def test_later_failure_does_not_erase_success_or_block_expired_success_reacquire(self):
        version = "157.0.300.2"
        FakeClient.state = {"schema": "angle-stable-monitor-state-v1", "baseline": monitor.BASELINE,
            "last_detected_version": version, "records": [
                {"chrome_version": version, "status": "CI_BUILD_SUCCEEDED", "run_id": "9",
                 "artifact_id": 10, "artifact_name": "old-success", "created_at": "2026-11-14T00:00:00Z",
                 "chromium_revision": "a" * 40, "angle_revision": "b" * 40},
                {"chrome_version": version, "status": "CI_BUILD_FAILED", "run_id": "10",
                 "failure_stage": "later-retry", "effective_fingerprint": "c" * 64},
            ]}
        FakeClient.artifact_list = [{"id": 10, "expired": True,
            "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}]
        args = self.args(run_id="11", operation="reacquire_expired_artifact", reacquire_version=version)
        monitor.begin(args)
        state = json.loads(args.state.read_text())
        self.assertEqual(state["last_successful_version"], version)
        self.assertEqual(state["success_index"][version]["artifact_id"], 10)
        self.assertEqual(json.loads(args.output.read_text())["status"], "BUILD_CANDIDATE")
        self.assertTrue(json.loads(args.output.read_text())["reacquire"])

    def test_existing_unexpired_artifact_is_not_rebuilt(self):
        future = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        FakeClient.state = {"schema": "angle-stable-monitor-state-v1", "baseline": "156.0.8078.48",
                            "last_detected_version": "157.0.300.2", "records": [{
                                "chrome_version": "157.0.300.2", "status": "CI_BUILD_SUCCEEDED",
                                "artifact_id": 10, "run_id": "9", "expires_at": future,
                            }]}
        FakeClient.artifact_list = [{"id": 10, "name": "old", "expired": False, "expires_at": future}]
        args = self.args(operation="reacquire_expired_artifact", reacquire_version="157.0.300.2")
        monitor.begin(args)
        self.assertEqual(json.loads(args.output.read_text())["status"], "EXISTING_ARTIFACT_AVAILABLE")
        retry = self.args(operation="retry_failed_version", retry_failed_version="157.0.300.2")
        with self.assertRaisesRegex(ValueError, "not failed or interrupted"):
            monitor.begin(retry)

    def test_failed_attempt_requires_explicit_retry_and_can_reach_local_match_and_fetch(self):
        version = "157.0.300.2"
        failure = {"chrome_version": version, "platform": "macOS", "architecture": "x86_64",
                   "status": "CI_BUILD_FAILED", "run_id": "20", "reason": "source-fetch",
                   "failure_stage": "source-fetch", "chromium_revision": "a" * 40,
                   "angle_revision": "b" * 40, "patchset_id": "metal-family1-v1",
                   "patch_sha256": "c" * 64, "recipe_id": "macos-x64-metal-v1",
                   "recipe_sha256": "d" * 64, "selection_mode": "new-revision-candidate",
                   "workflow_revision": "1" * 40}
        FakeClient.state = {"schema": "angle-stable-monitor-state-v1", "baseline": monitor.BASELINE,
                            "last_detected_version": version, "records": [failure]}
        release_fixture = self.root / "releases.json"
        release_fixture.write_text(json.dumps({"releases": [{"version": version, "fraction": 1.0,
                                                               "serving": {"startTime": "now"}}]}))

        normal = self.args(run_id="20", fixture=release_fixture)
        monitor.begin(normal)
        blocked = json.loads(normal.output.read_text())
        self.assertEqual(blocked["status"], "ACTION_REQUIRED")
        self.assertEqual(blocked["reason"], "legacy-failure-fingerprint-unavailable")
        migrated = json.loads(normal.state.read_text())
        self.assertTrue(migrated["records"][0]["auto_retry_suppressed"])
        self.assertIsNone(migrated["last_successful_version"])

        retry = self.args(run_id="21", operation="retry_failed_version", retry_failed_version=version)
        monitor.begin(retry)
        candidate = json.loads(retry.output.read_text())
        state = json.loads(retry.state.read_text())
        attempt = state["records"][-1]
        self.assertTrue(candidate["retry_failed_version"])
        self.assertEqual(candidate["retry_of_run_id"], "20")
        self.assertEqual(candidate["retry_of_failure_stage"], "source-fetch")
        self.assertEqual(candidate["expected_source_pins"], {"chromium_revision": "a" * 40,
                                                              "angle_revision": "b" * 40})
        self.assertEqual(candidate["retry_previous_inputs"]["selection_mode"], "new-revision-candidate")
        self.assertEqual(state["last_detected_version"], version)

        duplicate = self.args(run_id="21", operation="retry_failed_version", retry_failed_version=version)
        FakeClient.state = state
        with self.assertRaisesRegex(ValueError, "already has an attempt"):
            monitor.begin(duplicate)

        source_path = self.root / "source.json"
        source_path.write_text(json.dumps({"chrome_version": version, "chromium_revision": "a" * 40,
                                           "angle_revision": "b" * 40}))
        monitor.record_source(type("Args", (), {"state": retry.state, "candidate": retry.output,
            "source": source_path, "run_id": "21"})())

        artifact_dir = self.root / "artifact"
        manifest = make_artifact(artifact_dir, chrome_version=version, run_id="21",
                                 patchset_id="metal-family1-v2", recipe_id="macos-x64-metal-v2",
                                 recipe_sha256="3" * 64, workflow_revision="2" * 40,
                                 selection_mode="new-revision-candidate",
                                 patch_candidate_status="unlisted-revision-candidate")
        (artifact_dir / "runtime-patch.diff").write_text("synthetic reviewed patch update\n")
        manifest["patch_sha256"] = sha256(artifact_dir / "runtime-patch.diff")
        manifest_path = artifact_dir / "ANGLE_ARTIFACT_MANIFEST.json"
        manifest_path.write_text(json.dumps(manifest, sort_keys=True))
        (artifact_dir / "ANGLE_ARTIFACT_MANIFEST.sha256").write_text(
            sha256(manifest_path) + "  ANGLE_ARTIFACT_MANIFEST.json\n")
        inputs_path = self.root / "inputs.json"
        inputs_path.write_text(json.dumps({"chrome_version": version, "chromium_revision": "a" * 40,
            "angle_revision": "b" * 40, "patchset_id": "metal-family1-v2",
            "patch_sha256": manifest["patch_sha256"], "recipe_id": "macos-x64-metal-v2",
            "recipe_sha256": "3" * 64, "selection_mode": "new-revision-candidate",
            "workflow_revision": "2" * 40, "build_key": "e" * 64}))
        monitor.record_inputs(type("Args", (), {"state": retry.state, "candidate": retry.output,
            "inputs": inputs_path, "run_id": "21"})())
        state_before_finish = json.loads(retry.state.read_text())
        self.assertEqual(state_before_finish["records"][-1]["retry_input_changes"],
                         ["patch_sha256", "patchset_id", "recipe_id", "recipe_sha256", "workflow_revision"])
        self.assertEqual(state_before_finish["records"][-1]["selection_mode"], "new-revision-candidate")

        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as output:
            for path in artifact_dir.rglob("*"):
                if path.is_file():
                    output.write(path, arcname=path.relative_to(artifact_dir).as_posix())
        expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        artifact_name = manifest["artifact_name"]
        FakeClient.uploaded = {"id": 77, "name": artifact_name, "expired": False,
            "expires_at": expires, "created_at": datetime.now(timezone.utc).isoformat(),
            "workflow_run": {"id": "21", "head_branch": "main"}}
        finish_args = self.args(run_id="21", state=retry.state, output=retry.output)
        finish_args.candidate = retry.output
        finish_args.artifact_name = artifact_name
        finish_args.job_status = "success"
        finish_args.failure_stage = ""
        finish_args.build_key = "e" * 64
        finish_args.manifest = manifest_path
        monitor.finish(finish_args)
        indexed_state = json.loads(retry.state.read_text())
        self.assertEqual(indexed_state["records"][-1]["status"], "CI_BUILD_SUCCEEDED_PENDING_STATE")
        self.assertIsNone(indexed_state["last_successful_version"])
        indexed_state = confirm_final_state(indexed_state)
        self.assertEqual(indexed_state["records"][-1]["status"], "CI_BUILD_SUCCEEDED")
        self.assertEqual(indexed_state["records"][-1]["retry_of_run_id"], "20")
        self.assertEqual(indexed_state["records"][-1]["patchset_id"], "metal-family1-v2")
        self.assertEqual(indexed_state["records"][-1]["selection_mode"], "new-revision-candidate")
        self.assertEqual(indexed_state["last_detected_version"], version)

        FakeClient.state = indexed_state
        FakeClient.artifact_list = [{"id": 77, "name": artifact_name, "expired": False,
                                     "expires_at": expires}]
        FakeClient.archive_bytes = archive.getvalue()
        client = FakeClient("owner/repo")
        matched, _artifact = find_index_record("owner/repo", version, "x86_64", client)
        self.assertEqual(matched["run_id"], "21")
        fetched = fetch_artifact("owner/repo", version, "x86_64", self.root / "fetched", client)
        self.assertEqual(fetched["manifest"]["patchset_id"], "metal-family1-v2")
        self.assertEqual(fetched["manifest"]["selection_mode"], "new-revision-candidate")
        self.assertEqual(fetched["manifest"]["run_id"], "21")
        self.assertEqual(client.downloaded_id, 77)

    def test_changed_effective_inputs_get_one_automatic_attempt_then_same_failure_is_blocked(self):
        version = "157.0.300.2"
        FakeClient.state = {"schema": "angle-stable-monitor-state-v1", "baseline": monitor.BASELINE,
            "last_detected_version": version, "records": [{"chrome_version": version, "run_id": "20",
                "status": "CI_BUILD_FAILED", "failure_stage": "patch-and-function-checks",
                "effective_fingerprint": "a" * 64, "chromium_revision": "b" * 40,
                "angle_revision": "c" * 40, "workflow_revision": "1" * 40}]}
        release_fixture = self.root / "releases.json"
        release_fixture.write_text(json.dumps({"releases": [{"version": version, "fraction": 1.0,
                                                               "serving": {"startTime": "now"}}]}))

        changed = self.args(run_id="21", fixture=release_fixture)
        with patch.object(monitor, "effective_input_fingerprint", return_value="d" * 64):
            monitor.begin(changed)
        candidate = json.loads(changed.output.read_text())
        self.assertEqual(candidate["status"], "BUILD_CANDIDATE")
        self.assertEqual(candidate["expected_source_pins"], {
            "chromium_revision": "b" * 40, "angle_revision": "c" * 40})
        self.assertEqual(candidate["effective_fingerprint"], "d" * 64)

        finish_args = self.args(run_id="21", state=changed.state, output=changed.output)
        finish_args.candidate = changed.output
        finish_args.artifact_name = "unused"
        finish_args.job_status = "failure"
        finish_args.failure_stage = "patch-and-function-checks"
        finish_args.build_key = ""
        finish_args.manifest = self.root / "missing-manifest.json"
        monitor.finish(finish_args)
        failed_state = json.loads(changed.state.read_text())
        self.assertEqual(failed_state["records"][-1]["status"], "CI_BUILD_FAILED")
        self.assertEqual(failed_state["records"][-1]["effective_fingerprint"], "d" * 64)

        # A workflow revision/documentation-only commit can change the build key,
        # but the exact same effective-input digest remains a blocker.
        same = self.args(run_id="22", fixture=release_fixture)
        FakeClient.state = failed_state
        with patch.object(monitor, "effective_input_fingerprint", return_value="d" * 64):
            monitor.begin(same)
        blocked = json.loads(same.output.read_text())
        self.assertEqual(blocked["status"], "ACTION_REQUIRED")
        self.assertEqual(blocked["reason"], "same-effective-inputs-already-failed")
        self.assertEqual(json.loads(same.state.read_text())["records"][-1]["run_id"], "21")

        # Reverting to an older failed fingerprint stays blocked even after the
        # bounded run history is gone; the candidate ledger keeps both attempts.
        trimmed = json.loads(same.state.read_text())
        trimmed["records"] = []
        FakeClient.state = trimmed
        reverted = self.args(run_id="23", fixture=release_fixture)
        with patch.object(monitor, "effective_input_fingerprint", return_value="a" * 64):
            monitor.begin(reverted)
        reverted_result = json.loads(reverted.output.read_text())
        self.assertEqual(reverted_result["status"], "ACTION_REQUIRED")
        self.assertEqual(reverted_result["reason"], "same-effective-inputs-already-attempted")
        persisted = json.loads(reverted.state.read_text())
        self.assertEqual(persisted["candidate_outcomes"][version]["attempted_fingerprints"],
                         ["a" * 64, "d" * 64])

    def test_newer_stable_is_selected_even_when_an_older_candidate_failed(self):
        FakeClient.state = {"schema": "angle-stable-monitor-state-v2", "baseline": monitor.BASELINE,
            "monitor_start_version": monitor.BASELINE, "last_detected_version": "158.0.1000.2",
            "last_successful_version": None, "success_index": {},
            "candidate_outcomes": {"158.0.1000.2": {"status": "CI_BUILD_FAILED",
                "run_id": "20", "effective_fingerprint": "a" * 64}},
            "records": [{"chrome_version": "158.0.1000.2", "run_id": "20",
                "status": "CI_BUILD_FAILED", "effective_fingerprint": "a" * 64}]}
        fixture = self.root / "releases.json"
        fixture.write_text(json.dumps({"releases": [
            {"version": "158.0.1000.2", "fraction": 1.0, "serving": {"startTime": "old"}},
            {"version": "159.0.1000.2", "fraction": 1.0, "serving": {"startTime": "new"}},
        ]}))
        args = self.args(run_id="21", fixture=fixture)
        with patch.object(monitor, "effective_input_fingerprint", return_value="b" * 64):
            monitor.begin(args)
        candidate = json.loads(args.output.read_text())
        self.assertEqual(candidate["status"], "BUILD_CANDIDATE")
        self.assertEqual(candidate["chrome_version"], "159.0.1000.2")

    def test_v1_migration_uses_formal_success_record_not_detected_watermark(self):
        FakeClient.state = {"schema": "angle-stable-monitor-state-v1", "baseline": monitor.BASELINE,
            "last_detected_version": "158.0.1000.2", "records": [
                {"chrome_version": "157.0.1000.2", "status": "CI_BUILD_SUCCEEDED", "run_id": "10",
                 "artifact_id": 11, "chromium_revision": "a" * 40, "angle_revision": "b" * 40},
                {"chrome_version": "158.0.1000.2", "status": "CI_BUILD_FAILED", "run_id": "20"},
            ]}
        fixture = self.root / "releases.json"
        fixture.write_text(json.dumps({"releases": [{"version": "158.0.1000.2", "fraction": 1.0,
                                                       "serving": {"startTime": "now"}}]}))
        args = self.args(run_id="21", fixture=fixture)
        with patch.object(monitor, "effective_input_fingerprint", return_value="a" * 64):
            monitor.begin(args)
        migrated = json.loads(args.state.read_text())
        candidate = json.loads(args.output.read_text())
        self.assertEqual(migrated["schema"], "angle-stable-monitor-state-v2")
        self.assertEqual(migrated["last_detected_version"], "158.0.1000.2")
        self.assertEqual(migrated["last_successful_version"], "157.0.1000.2")
        self.assertEqual(migrated["success_index"]["157.0.1000.2"]["artifact_id"], 11)
        self.assertEqual(candidate["status"], "ACTION_REQUIRED")

    def test_watermark_without_a_formal_success_record_is_rejected(self):
        malformed = {"schema": "angle-stable-monitor-state-v2", "baseline": monitor.BASELINE,
            "monitor_start_version": monitor.BASELINE, "last_detected_version": monitor.BASELINE,
            "last_successful_version": "157.0.300.2", "success_index": {},
            "candidate_outcomes": {}, "records": []}
        with self.assertRaisesRegex(ValueError, "no formal success record"):
            normalize_state(malformed)

    def test_success_cannot_be_promoted_through_a_partial_outcome_update(self):
        state = monitor._initial_state()
        with self.assertRaisesRegex(ValueError, "validated final-state artifact"):
            update_outcome(state, {"chrome_version": "157.0.300.2",
                                   "status": "CI_BUILD_SUCCEEDED", "run_id": "20"})
        self.assertIsNone(state["last_successful_version"])
        self.assertEqual(state["success_index"], {})

    def test_record_trimming_keeps_success_and_failure_ledgers(self):
        FakeClient.state = {"schema": "angle-stable-monitor-state-v2", "baseline": monitor.BASELINE,
            "monitor_start_version": monitor.BASELINE, "last_detected_version": "159.0.1000.2",
            "last_successful_version": "157.0.1000.2",
            "success_index": {"157.0.1000.2": {"status": "CI_BUILD_SUCCEEDED", "artifact_id": 99}},
            "candidate_outcomes": {"158.0.1000.2": {"status": "CI_BUILD_FAILED", "run_id": "20",
                "effective_fingerprint": "a" * 64}},
            "records": [{"chrome_version": "157.0.1000.2", "status": "STATE_RECOVERY_AUDIT",
                         "run_id": str(index)} for index in range(1000)]}
        fixture = self.root / "releases.json"
        fixture.write_text(json.dumps({"releases": [{"version": "159.0.1000.2", "fraction": 1.0,
                                                       "serving": {"startTime": "now"}}]}))
        args = self.args(run_id="1001", fixture=fixture)
        with patch.object(monitor, "effective_input_fingerprint", return_value="b" * 64):
            monitor.begin(args)
        state = json.loads(args.state.read_text())
        self.assertEqual(len(state["records"]), 1000)
        self.assertEqual(state["last_successful_version"], "157.0.1000.2")
        self.assertEqual(state["success_index"]["157.0.1000.2"]["artifact_id"], 99)
        self.assertEqual(state["candidate_outcomes"]["158.0.1000.2"]["effective_fingerprint"], "a" * 64)

    def test_non_main_pr_artifact_cannot_advance_success_watermark(self):
        version = "157.0.300.2"
        fixture = self.root / "releases.json"
        fixture.write_text(json.dumps({"releases": [{"version": version, "fraction": 1.0,
                                                       "serving": {"startTime": "now"}}]}))
        args = self.args(run_id="44", fixture=fixture)
        with patch.object(monitor, "effective_input_fingerprint", return_value="a" * 64):
            monitor.begin(args)
        artifact_name = f"angle-macos-x86_64-chrome-{version}-run-44"
        FakeClient.uploaded = {"id": 88, "name": artifact_name, "expired": False,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=20)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "workflow_run": {"id": "44", "head_branch": "feature/pr-validation"}}
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps({"run_id": "44", "artifact_name": artifact_name,
            "build_key": "b" * 64, "chrome_version": version}))
        finish_args = self.args(run_id="44", state=args.state, output=args.output)
        finish_args.candidate = args.output
        finish_args.artifact_name = artifact_name
        finish_args.job_status = "success"
        finish_args.failure_stage = ""
        finish_args.build_key = "b" * 64
        finish_args.manifest = manifest
        monitor.finish(finish_args)
        state = json.loads(args.state.read_text())
        self.assertEqual(state["records"][-1]["status"], "ARTIFACT_MISSING_OR_EXPIRED")
        self.assertIsNone(state["last_successful_version"])

    def test_source_pin_change_is_recorded_but_never_becomes_an_accepted_pin(self):
        version = "157.0.300.2"
        FakeClient.state = {"schema": "angle-stable-monitor-state-v1", "baseline": monitor.BASELINE,
            "last_detected_version": version, "records": [{"chrome_version": version, "run_id": "20",
                "status": "CI_BUILD_FAILED", "failure_stage": "source-fetch",
                "chromium_revision": "a" * 40, "angle_revision": "b" * 40}]}
        first = self.args(run_id="21", operation="retry_failed_version", retry_failed_version=version)
        monitor.begin(first)
        source_path = self.root / "changed-source.json"
        source_path.write_text(json.dumps({"chrome_version": version, "chromium_revision": "f" * 40,
                                           "angle_revision": "e" * 40}))
        with self.assertRaisesRegex(ValueError, "observed pins were recorded"):
            monitor.record_source(type("Args", (), {"state": first.state, "candidate": first.output,
                "source": source_path, "run_id": "21"})())
        observed = json.loads(first.state.read_text())["records"][-1]
        self.assertEqual(observed["source_resolution_status"], "pin-mismatch")
        self.assertTrue(observed["source_pin_mismatch"])
        self.assertEqual(observed["observed_chromium_revision"], "f" * 40)
        self.assertNotIn("chromium_revision", observed)

        finish_args = self.args(run_id="21", state=first.state, output=first.output)
        finish_args.candidate = first.output
        finish_args.artifact_name = "unused"
        finish_args.job_status = "failure"
        finish_args.failure_stage = "source-pin-comparison"
        finish_args.build_key = ""
        finish_args.manifest = self.root / "missing-manifest.json"
        monitor.finish(finish_args)
        FakeClient.state = json.loads(first.state.read_text())
        self.assertEqual(FakeClient.state["candidate_outcomes"][version]["source_pins"], {
            "chromium_revision": "a" * 40, "angle_revision": "b" * 40})
        retained = copy.deepcopy(FakeClient.state)
        retained["records"] = []

        # A changed local input may start once, but the changed source tag is
        # still checked against the durable pin after record history is trimmed.
        FakeClient.state = copy.deepcopy(retained)
        release_fixture = self.root / "releases.json"
        release_fixture.write_text(json.dumps({"releases": [{"version": version, "fraction": 1.0,
                                                               "serving": {"startTime": "now"}}]}))
        automatic = self.args(run_id="22", fixture=release_fixture)
        with patch.object(monitor, "effective_input_fingerprint", return_value="d" * 64):
            monitor.begin(automatic)
        automatic_candidate = json.loads(automatic.output.read_text())
        self.assertEqual(automatic_candidate["status"], "BUILD_CANDIDATE")
        self.assertEqual(automatic_candidate["expected_source_pins"], {
            "chromium_revision": "a" * 40, "angle_revision": "b" * 40})
        with self.assertRaisesRegex(ValueError, "observed pins were recorded"):
            monitor.record_source(type("Args", (), {"state": automatic.state,
                "candidate": automatic.output, "source": source_path, "run_id": "22"})())
        auto_record = json.loads(automatic.state.read_text())["records"][-1]
        self.assertTrue(auto_record["source_pin_mismatch"])
        self.assertNotIn("chromium_revision", auto_record)

        FakeClient.state = retained
        next_retry = self.args(run_id="22", operation="retry_failed_version", retry_failed_version=version)
        monitor.begin(next_retry)
        candidate = json.loads(next_retry.output.read_text())
        self.assertEqual(candidate["expected_source_pins"], {"chromium_revision": "a" * 40,
                                                              "angle_revision": "b" * 40})
        self.assertEqual(candidate["retry_source_mode"], "compare-with-last-recorded-source-pins")
        self.assertEqual(json.loads(next_retry.state.read_text())["records"][-1]["retry_source_pin_run_id"], "20")

    def test_retry_without_source_pins_requires_an_explicit_exact_tag_acknowledgment(self):
        version = "157.0.300.2"
        FakeClient.state = {"schema": "angle-stable-monitor-state-v1", "baseline": monitor.BASELINE,
            "last_detected_version": version, "records": [{"chrome_version": version, "run_id": "30",
                "status": "CI_BUILD_FAILED", "failure_stage": "official-tag-resolution"}]}
        args = self.args(run_id="31", operation="retry_failed_version", retry_failed_version=version)
        with self.assertRaisesRegex(ValueError, "no source pins were recorded"):
            monitor.begin(args)
        args.confirm_unpinned_retry = True
        monitor.begin(args)
        candidate = json.loads(args.output.read_text())
        self.assertEqual(candidate["retry_source_mode"],
                         "fresh-exact-tag-after-prior-attempt-had-no-recorded-pins")
        self.assertTrue(candidate["unpinned_source_retry_acknowledged"])

    def test_finish_indexes_artifact_only_after_manifest_and_run_match(self):
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        artifact_name = "angle-macos-x86_64-chrome-157.0.300.2-run-100"
        FakeClient.uploaded = {"id": 77, "name": artifact_name, "expired": False,
                               "expires_at": future, "created_at": datetime.now(timezone.utc).isoformat(),
                               "workflow_run": {"id": "100", "head_branch": "main"}}
        state_path, candidate_path, manifest_path = self.root / "state.json", self.root / "candidate.json", self.root / "manifest.json"
        state_path.write_text(json.dumps({"schema": "angle-stable-monitor-state-v2",
            "baseline": monitor.BASELINE, "monitor_start_version": monitor.BASELINE,
            "last_detected_version": monitor.BASELINE, "last_successful_version": None,
            "records": [{"run_id": "100", "chrome_version": "157.0.300.2",
                         "status": "STABLE_RELEASE_DETECTED", "effective_fingerprint": "f" * 64}]}))
        candidate_path.write_text(json.dumps({"status": "BUILD_CANDIDATE", "chrome_version": "157.0.300.2"}))
        manifest_path.write_text(json.dumps({"run_id": "100", "artifact_name": artifact_name,
                                             "build_key": "a" * 64, "chrome_version": "157.0.300.2",
                                             "platform": "macOS", "architecture": "x86_64",
                                             "chromium_revision": "b" * 40, "angle_revision": "c" * 40,
                                             "selection_mode": "new-revision-candidate",
                                             "libraries": {}}))
        args = self.args(state=state_path, output=candidate_path)
        args.candidate = candidate_path
        args.artifact_name = artifact_name
        args.job_status = "success"
        args.failure_stage = ""
        args.build_key = "a" * 64
        args.manifest = manifest_path
        monitor.finish(args)
        record = json.loads(state_path.read_text())["records"][0]
        self.assertEqual(record["status"], "CI_BUILD_SUCCEEDED_PENDING_STATE")
        self.assertIsNone(json.loads(state_path.read_text())["last_successful_version"])
        persisted = confirm_final_state(json.loads(state_path.read_text()))
        self.assertEqual(persisted["records"][0]["status"], "CI_BUILD_SUCCEEDED")
        self.assertEqual(persisted["last_successful_version"], "157.0.300.2")
        self.assertEqual(record["artifact_id"], 77)
        self.assertEqual(record["angle_revision"], "c" * 40)
        self.assertEqual(record["selection_mode"], "new-revision-candidate")

    def test_manual_recovery_from_total_state_loss_requires_audited_exact_version(self):
        args = self.args(run_id="102", last_processed_version=RECOVERED_VERSION,
                         reason="owner-confirmed-history-loss")
        self.assertEqual(monitor.recover(args), 0)
        state = json.loads(args.state.read_text())
        self.assertEqual(state["last_detected_version"], RECOVERED_VERSION)
        self.assertEqual(state["records"][0]["status"], "STATE_RECOVERY_AUDIT")
        self.assertEqual(state["records"][0]["recovery_source"], "explicit-owner-baseline")

    def test_manual_recovery_refuses_missing_or_old_version_and_reason(self):
        with self.assertRaisesRegex(ValueError, "exact four-part"):
            monitor.recover(self.args(run_id="103"))
        args = self.args(run_id="104", last_processed_version=OLDER_VERSION, reason="Too old baseline")
        with self.assertRaisesRegex(ValueError, "older than the catalog baseline"):
            monitor.recover(args)
        args = self.args(run_id="105", last_processed_version=RECOVERED_VERSION, reason="Needs review from owner")
        with self.assertRaisesRegex(ValueError, "lowercase recovery reason slug"):
            monitor.recover(args)


if __name__ == "__main__":
    unittest.main()
