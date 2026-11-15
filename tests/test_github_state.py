from datetime import datetime, timezone, timedelta
import io
import json
import unittest
from unittest.mock import patch
import zipfile

from src.maintenance_angle.github_artifacts import GitHubActionsArtifacts, GitHubError

INTERRUPTED_VERSION = ".".join(("158", "0", "1", "2"))


class GitHubStateTests(unittest.TestCase):
    def setUp(self):
        self.client = GitHubActionsArtifacts("owner/repo")
        self.future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()

    def artifact(self, name, run_id, artifact_id=44, *, expires=None):
        return {"name": name, "id": artifact_id, "expired": False,
                "expires_at": expires or self.future, "created_at": "2026-11-15T00:00:00Z",
                "workflow_run": {"id": run_id, "head_branch": "main"}}

    def run(self, run_id, created_at="2026-11-15T00:00:00Z"):
        return {"id": run_id, "status": "completed", "created_at": created_at}

    def test_first_run_bootstraps_without_a_commit_age_deadline(self):
        with patch.object(self.client, "artifacts", return_value=[]), \
                patch.object(self.client, "workflow_runs", return_value=[]):
            self.assertIsNone(self.client.load_latest_state("watch-chrome-stable.yml"))

    def test_reader_uses_the_exact_upload_artifact_member_name(self):
        state = {"schema": "angle-stable-monitor-state-v1", "last_detected_version": "157.0.300.2", "records": []}
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("stable-monitor-state.json", json.dumps(state))
        artifact = self.artifact("stable-monitor-state", 17)
        with patch.object(self.client, "download_artifact", return_value=archive.getvalue()):
            self.assertEqual(self.client.read_json_artifact(artifact, "stable-monitor-state.json"), state)
            with self.assertRaises(GitHubError):
                self.client.read_json_artifact(artifact, "state.json")

    def test_latest_completed_run_final_state_is_returned(self):
        artifact = self.artifact("stable-monitor-state", 17)
        state = {"schema": "angle-stable-monitor-state-v1", "records": []}
        with patch.object(self.client, "artifacts", return_value=[artifact]), \
                patch.object(self.client, "workflow_runs", return_value=[self.run(17)]), \
                patch.object(self.client, "read_json_artifact", return_value=state) as read:
            self.assertEqual(self.client.load_latest_state("watch-chrome-stable.yml"), state)
        read.assert_called_once_with(artifact, "stable-monitor-state.json")

    def test_checkpoint_recovery_marks_pending_build_interrupted_without_success(self):
        artifact = self.artifact("stable-monitor-checkpoint-18", 18)
        state = {"schema": "angle-stable-monitor-state-v1", "last_detected_version": INTERRUPTED_VERSION,
                 "records": [{"run_id": "18", "chrome_version": INTERRUPTED_VERSION,
                              "status": "STABLE_RELEASE_DETECTED"}]}
        with patch.object(self.client, "artifacts", return_value=[artifact]), \
                patch.object(self.client, "workflow_runs", return_value=[self.run(18)]), \
                patch.object(self.client, "read_json_artifact", return_value=state):
            recovered = self.client.load_latest_state("watch-chrome-stable.yml")
        self.assertEqual(recovered["last_detected_version"], INTERRUPTED_VERSION)
        self.assertEqual(recovered["records"][0]["status"], "CI_BUILD_INTERRUPTED")
        self.assertNotIn("artifact_id", recovered["records"][0])

    def test_resolved_input_checkpoint_preserves_retry_pins_for_explicit_next_attempt(self):
        artifact = self.artifact("stable-monitor-resolved-checkpoint-18", 18)
        state = {"schema": "angle-stable-monitor-state-v1", "last_detected_version": INTERRUPTED_VERSION,
                 "records": [{"run_id": "18", "chrome_version": INTERRUPTED_VERSION,
                              "status": "RETRY_REQUESTED", "retry_of_run_id": "17",
                              "chromium_revision": "a" * 40, "angle_revision": "b" * 40,
                              "patchset_id": "fixture-v2", "patch_sha256": "c" * 64,
                              "recipe_id": "recipe-v2", "recipe_sha256": "d" * 64,
                              "build_key": "e" * 64}]}
        with patch.object(self.client, "artifacts", return_value=[artifact]), \
                patch.object(self.client, "workflow_runs", return_value=[self.run(18)]), \
                patch.object(self.client, "read_json_artifact", return_value=state):
            recovered = self.client.load_latest_state("watch-chrome-stable.yml")
        record = recovered["records"][0]
        self.assertEqual(record["status"], "CI_BUILD_INTERRUPTED")
        self.assertEqual(record["retry_of_run_id"], "17")
        self.assertEqual(record["chromium_revision"], "a" * 40)
        self.assertEqual(record["patchset_id"], "fixture-v2")
        self.assertEqual(record["build_key"], "e" * 64)

    def test_run_without_checkpoint_safely_falls_back_to_prior_valid_state(self):
        artifact = self.artifact("stable-monitor-state", 16)
        state = {"schema": "angle-stable-monitor-state-v1", "last_detected_version": "157.0.300.2", "records": []}
        with patch.object(self.client, "artifacts", return_value=[artifact]), \
                patch.object(self.client, "workflow_runs", return_value=[self.run(17, "2026-11-15T00:01:00Z"),
                                                                            self.run(16)]), \
                patch.object(self.client, "read_json_artifact", return_value=state):
            self.assertEqual(self.client.load_latest_state("watch-chrome-stable.yml"), state)

    def test_expired_checkpoint_fails_closed_instead_of_rebuilding_from_older_state(self):
        old = self.artifact("stable-monitor-state", 16)
        expired = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        checkpoint = self.artifact("stable-monitor-checkpoint-17", 17, expires=expired)
        with patch.object(self.client, "artifacts", return_value=[old, checkpoint]), \
                patch.object(self.client, "workflow_runs", return_value=[self.run(17), self.run(16)]):
            with self.assertRaisesRegex(GitHubError, "expired"):
                self.client.load_latest_state("watch-chrome-stable.yml")

    def test_completed_runs_with_all_state_missing_require_explicit_recovery(self):
        with patch.object(self.client, "artifacts", return_value=[]), \
                patch.object(self.client, "workflow_runs", return_value=[self.run(18)]):
            with self.assertRaisesRegex(GitHubError, "state-lost"):
                self.client.load_latest_state("watch-chrome-stable.yml")


if __name__ == "__main__":
    unittest.main()
