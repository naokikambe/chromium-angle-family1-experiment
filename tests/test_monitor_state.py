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

from src.maintenance_angle.local import fetch_artifact, find_index_record
from src.maintenance_angle.artifact import sha256
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
        self.assertEqual(state["records"][0]["status"], "STABLE_RELEASE_DETECTED")

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
        self.assertEqual(json.loads(normal.output.read_text())["status"], "NO_NEW_FULLY_ROLLED_OUT_STABLE")

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
            "workflow_run": {"id": "21"}}
        finish_args = self.args(run_id="21", state=retry.state, output=retry.output)
        finish_args.candidate = retry.output
        finish_args.artifact_name = artifact_name
        finish_args.job_status = "success"
        finish_args.failure_stage = ""
        finish_args.build_key = "e" * 64
        finish_args.manifest = manifest_path
        monitor.finish(finish_args)
        indexed_state = json.loads(retry.state.read_text())
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
                               "workflow_run": {"id": "100"}}
        state_path, candidate_path, manifest_path = self.root / "state.json", self.root / "candidate.json", self.root / "manifest.json"
        state_path.write_text(json.dumps({"records": [{"run_id": "100", "chrome_version": "157.0.300.2",
                                                        "status": "STABLE_RELEASE_DETECTED"}]}))
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
        self.assertEqual(record["status"], "CI_BUILD_SUCCEEDED")
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
