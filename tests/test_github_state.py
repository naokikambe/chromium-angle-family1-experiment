from datetime import datetime, timezone, timedelta
from email.message import Message
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import BaseHandler, HTTPDefaultErrorHandler, HTTPErrorProcessor, OpenerDirector
from urllib.response import addinfourl
import zipfile

from src.maintenance_angle import github_artifacts
from src.maintenance_angle.github_artifacts import GitHubActionsArtifacts, GitHubError

INTERRUPTED_VERSION = ".".join(("158", "0", "1", "2"))
MONITOR_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/angle-monitor.py"
MONITOR_SPEC = importlib.util.spec_from_file_location("angle_monitor_for_github_state_tests", MONITOR_SCRIPT)
monitor = importlib.util.module_from_spec(MONITOR_SPEC)
MONITOR_SPEC.loader.exec_module(monitor)


class _FixtureHTTPSHandler(BaseHandler):
    def __init__(self, requests, responder):
        self.requests = requests
        self.responder = responder

    def https_open(self, request):
        self.requests.append(request)
        status, body, headers = self.responder(request)
        response_headers = Message()
        for name, value in headers.items():
            response_headers[name] = value
        response = addinfourl(io.BytesIO(body), response_headers, request.full_url, code=status)
        response.msg = {200: "OK", 302: "Found", 401: "Unauthorized", 403: "Forbidden"}.get(status, "Error")
        return response


def _fixture_opener_builder(requests, responder):
    def build(*handlers):
        opener = OpenerDirector()
        opener.add_handler(_FixtureHTTPSHandler(requests, responder))
        for handler in handlers:
            opener.add_handler(handler)
        opener.add_handler(HTTPDefaultErrorHandler())
        opener.add_handler(HTTPErrorProcessor())
        return opener
    return build


def _state_zip(state):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("stable-monitor-state.json", json.dumps(state))
    return archive.getvalue()


class GitHubStateTests(unittest.TestCase):
    def setUp(self):
        self.client = GitHubActionsArtifacts("owner/repo")
        self.future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()

    def artifact(self, name, run_id, artifact_id=44, *, expires=None):
        return {"name": name, "id": artifact_id, "expired": False,
                "expires_at": expires or self.future, "created_at": "2026-11-15T00:00:00Z",
                "workflow_run": {"id": run_id, "head_branch": "main"}}

    def workflow_run(self, run_id, created_at="2026-11-15T00:00:00Z"):
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
        state = {"schema": "angle-stable-monitor-state-v1", "baseline": "156.0.8078.48",
                 "last_detected_version": "157.0.300.2", "records": []}
        with patch.object(self.client, "artifacts", return_value=[artifact]), \
                patch.object(self.client, "workflow_runs", return_value=[self.workflow_run(17)]), \
                patch.object(self.client, "read_json_artifact", return_value=state) as read:
            loaded = self.client.load_latest_state("watch-chrome-stable.yml")
        self.assertEqual(loaded["schema"], "angle-stable-monitor-state-v2")
        self.assertEqual(loaded["last_detected_version"], "157.0.300.2")
        self.assertIsNone(loaded["last_successful_version"])
        read.assert_called_once_with(artifact, "stable-monitor-state.json")

    def test_checkpoint_recovery_marks_pending_build_interrupted_without_success(self):
        artifact = self.artifact("stable-monitor-checkpoint-18", 18)
        state = {"schema": "angle-stable-monitor-state-v1", "baseline": "156.0.8078.48",
                 "last_detected_version": INTERRUPTED_VERSION,
                 "records": [{"run_id": "18", "chrome_version": INTERRUPTED_VERSION,
                              "status": "STABLE_RELEASE_DETECTED"}]}
        with patch.object(self.client, "artifacts", return_value=[artifact]), \
                patch.object(self.client, "workflow_runs", return_value=[self.workflow_run(18)]), \
                patch.object(self.client, "read_json_artifact", return_value=state):
            recovered = self.client.load_latest_state("watch-chrome-stable.yml")
        self.assertEqual(recovered["last_detected_version"], INTERRUPTED_VERSION)
        self.assertEqual(recovered["records"][0]["status"], "CI_BUILD_INTERRUPTED")
        self.assertNotIn("artifact_id", recovered["records"][0])

    def test_resolved_input_checkpoint_preserves_retry_pins_for_explicit_next_attempt(self):
        artifact = self.artifact("stable-monitor-resolved-checkpoint-18", 18)
        state = {"schema": "angle-stable-monitor-state-v1", "baseline": "156.0.8078.48",
                 "last_detected_version": INTERRUPTED_VERSION,
                 "records": [{"run_id": "18", "chrome_version": INTERRUPTED_VERSION,
                              "status": "RETRY_REQUESTED", "retry_of_run_id": "17",
                              "chromium_revision": "a" * 40, "angle_revision": "b" * 40,
                              "patchset_id": "fixture-v2", "patch_sha256": "c" * 64,
                              "recipe_id": "recipe-v2", "recipe_sha256": "d" * 64,
                              "build_key": "e" * 64}]}
        with patch.object(self.client, "artifacts", return_value=[artifact]), \
                patch.object(self.client, "workflow_runs", return_value=[self.workflow_run(18)]), \
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
        state = {"schema": "angle-stable-monitor-state-v1", "baseline": "156.0.8078.48",
                 "last_detected_version": "157.0.300.2", "records": []}
        with patch.object(self.client, "artifacts", return_value=[artifact]), \
                patch.object(self.client, "workflow_runs", return_value=[self.workflow_run(17, "2026-11-15T00:01:00Z"),
                                                                            self.workflow_run(16)]), \
                patch.object(self.client, "read_json_artifact", return_value=state):
            loaded = self.client.load_latest_state("watch-chrome-stable.yml")
        self.assertEqual(loaded["last_detected_version"], "157.0.300.2")
        self.assertEqual(loaded["schema"], "angle-stable-monitor-state-v2")

    def test_expired_checkpoint_fails_closed_instead_of_rebuilding_from_older_state(self):
        old = self.artifact("stable-monitor-state", 16)
        expired = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        checkpoint = self.artifact("stable-monitor-checkpoint-17", 17, expires=expired)
        with patch.object(self.client, "artifacts", return_value=[old, checkpoint]), \
                patch.object(self.client, "workflow_runs", return_value=[self.workflow_run(17), self.workflow_run(16)]):
            with self.assertRaisesRegex(GitHubError, "expired"):
                self.client.load_latest_state("watch-chrome-stable.yml")

    def test_completed_runs_with_all_state_missing_require_explicit_recovery(self):
        with patch.object(self.client, "artifacts", return_value=[]), \
                patch.object(self.client, "workflow_runs", return_value=[self.workflow_run(18)]):
            with self.assertRaisesRegex(GitHubError, "state-lost"):
                self.client.load_latest_state("watch-chrome-stable.yml")

    def test_artifact_download_follows_one_https_storage_redirect_without_github_headers(self):
        storage_url = "https://productionresultssa4.blob.core.windows.net/fixture/state.zip?proof=synthetic-only"
        requests = []

        def respond(request):
            if request.full_url.startswith("https://api.github.com/"):
                return 302, b"", {"Location": storage_url}
            return 200, b"synthetic zip bytes", {}

        client = GitHubActionsArtifacts("owner/repo", token="fixture-token")
        builder = _fixture_opener_builder(requests, respond)
        with patch.object(github_artifacts, "build_opener", side_effect=builder):
            self.assertEqual(client.download_artifact(44), b"synthetic zip bytes")

        self.assertEqual(len(requests), 2)
        self.assertTrue(requests[0].full_url.startswith("https://api.github.com/"))
        self.assertEqual(requests[0].get_header("Authorization"), "Bearer fixture-token")
        self.assertEqual(requests[0].get_header("X-github-api-version"), "2022-11-28")
        storage_headers = {name.lower() for name in requests[1].headers}
        self.assertNotIn("authorization", storage_headers)
        self.assertNotIn("proxy-authorization", storage_headers)
        self.assertNotIn("cookie", storage_headers)
        self.assertNotIn("x-github-api-version", storage_headers)
        self.assertEqual(requests[1].get_header("Accept"), "application/zip")

    def test_artifact_storage_401_and_403_are_reported_without_url_or_token(self):
        for status in (401, 403):
            with self.subTest(status=status):
                requests = []

                def respond(request):
                    if request.full_url.startswith("https://api.github.com/"):
                        return 302, b"", {"Location":
                            "https://productionresultssa4.blob.core.windows.net/fixture/state.zip?proof=synthetic-only"}
                    return status, b"", {}

                client = GitHubActionsArtifacts("owner/repo", token="fixture-token")
                builder = _fixture_opener_builder(requests, respond)
                with patch.object(github_artifacts, "build_opener", side_effect=builder):
                    with self.assertRaises(GitHubError) as raised:
                        client.download_artifact(44)

                message = str(raised.exception)
                self.assertIn(f"HTTP {status}", message)
                self.assertNotIn("fixture-token", message)
                self.assertNotIn("proof=synthetic-only", message)
                self.assertEqual(len(requests), 2)

    def test_artifact_download_rejects_downgrade_untrusted_and_nonstandard_port_redirects(self):
        locations = (
            "http://productionresultssa4.blob.core.windows.net/fixture/state.zip?proof=synthetic-only",
            "https://downloads.example.invalid/fixture/state.zip?proof=synthetic-only",
            "https://attacker.blob.core.windows.net/fixture/state.zip?proof=synthetic-only",
            "https://productionresultssa4.blob.core.windows.net:444/fixture/state.zip?proof=synthetic-only",
            "https://fixture@example.invalid@productionresultssa4.blob.core.windows.net/fixture/state.zip?proof=synthetic-only",
        )
        for location in locations:
            with self.subTest(target="redirect-target"):
                requests = []
                builder = _fixture_opener_builder(requests, lambda _request: (302, b"", {"Location": location}))
                client = GitHubActionsArtifacts("owner/repo", token="fixture-token")
                with patch.object(github_artifacts, "build_opener", side_effect=builder):
                    with self.assertRaisesRegex(GitHubError, "redirect rejected") as raised:
                        client.download_artifact(44)
                self.assertNotIn("fixture-token", str(raised.exception))
                self.assertNotIn("proof=synthetic-only", str(raised.exception))
                self.assertEqual(len(requests), 1)

    def test_artifact_download_rejects_a_second_redirect(self):
        requests = []

        def respond(request):
            if request.full_url.startswith("https://api.github.com/"):
                return 302, b"", {"Location":
                    "https://productionresultssa4.blob.core.windows.net/fixture/state.zip?proof=synthetic-only"}
            return 302, b"", {"Location":
                "https://productionresultssa5.blob.core.windows.net/fixture/other.zip?proof=synthetic-only"}

        builder = _fixture_opener_builder(requests, respond)
        client = GitHubActionsArtifacts("owner/repo", token="fixture-token")
        with patch.object(github_artifacts, "build_opener", side_effect=builder):
            with self.assertRaisesRegex(GitHubError, "redirect rejected"):
                client.download_artifact(44)
        self.assertEqual(len(requests), 2)
        self.assertNotIn("Authorization", requests[1].headers)

    def test_authenticated_api_request_does_not_follow_a_redirect(self):
        requests = []
        builder = _fixture_opener_builder(requests, lambda _request: (302, b"", {
            "Location": "https://productionresultssa4.blob.core.windows.net/fixture/state.zip?proof=synthetic-only"}))
        client = GitHubActionsArtifacts("owner/repo", token="fixture-token")
        with patch.object(github_artifacts, "build_opener", side_effect=builder):
            with self.assertRaisesRegex(GitHubError, "HTTP 302") as raised:
                client._request("actions/artifacts")
        self.assertNotIn("fixture-token", str(raised.exception))
        self.assertNotIn("proof=synthetic-only", str(raised.exception))
        self.assertEqual(len(requests), 1)

    def test_state_reader_uses_safe_redirect_before_preparing_explicit_retry(self):
        version = "158.0.8127.37"
        prior_state = {
            "schema": "angle-stable-monitor-state-v1", "baseline": "156.0.8078.48",
            "last_detected_version": version,
            "records": [{"chrome_version": version, "platform": "macOS", "architecture": "x86_64",
                         "status": "CI_BUILD_FAILED", "run_id": "44480771895",
                         "failure_stage": "patch-and-function-checks",
                         "chromium_revision": "b8c2be851f62f6a394ec57955d7f31335d7cb6d4",
                         "angle_revision": "1f6526a566c27c7c33aa73a78517450a4a2a1714",
                         "patchset_id": "metal-family1-v1", "patch_sha256": "c" * 64,
                         "recipe_id": "macos-x64-metal-v1", "recipe_sha256": "d" * 64,
                         "selection_mode": "new-revision-candidate",
                         "workflow_revision": "84594c238ae9e55285caf153f5af9772a1067a26"}],
        }
        archive_bytes = _state_zip(prior_state)
        artifact = self.artifact("stable-monitor-state", "44480771895", 14508194597,
                                 expires="2027-02-17T07:35:18Z")
        runs = [self.workflow_run("44611811768", "2026-11-19T20:44:55Z"),
                self.workflow_run("44480771895", "2026-11-19T07:35:18Z")]
        requests = []

        def respond(request):
            if request.full_url.startswith("https://api.github.com/"):
                return 302, b"", {"Location":
                    "https://productionresultssa4.blob.core.windows.net/fixture/state.zip?proof=synthetic-only"}
            return 200, archive_bytes, {}

        builder = _fixture_opener_builder(requests, respond)
        client = GitHubActionsArtifacts("owner/repo", token="fixture-token")
        with tempfile.TemporaryDirectory(prefix="retry-state-fixture-") as folder, \
                patch.object(client, "artifacts", return_value=[artifact]), \
                patch.object(client, "workflow_runs", return_value=runs), \
                patch.object(github_artifacts, "build_opener", side_effect=builder), \
                patch.object(monitor, "GitHubActionsArtifacts", return_value=client):
            root = Path(folder)
            args = type("Args", (), {
                "repository": "owner/repo", "run_id": "44700000000",
                "state": root / "state.json", "output": root / "candidate.json",
                "fixture": None, "github_output": None, "reacquire_version": "",
                "retry_failed_version": version, "confirm_unpinned_retry": False,
                "operation": "retry_failed_version", "last_processed_version": "", "reason": "",
            })()
            self.assertEqual(monitor.begin(args), 0)
            state = json.loads(args.state.read_text(encoding="utf-8"))
            candidate = json.loads(args.output.read_text(encoding="utf-8"))

        self.assertEqual(candidate["status"], "BUILD_CANDIDATE")
        self.assertEqual(candidate["retry_of_run_id"], "44480771895")
        self.assertEqual(candidate["expected_source_pins"], {
            "chromium_revision": "b8c2be851f62f6a394ec57955d7f31335d7cb6d4",
            "angle_revision": "1f6526a566c27c7c33aa73a78517450a4a2a1714",
        })
        self.assertEqual(state["last_detected_version"], version)
        self.assertEqual(state["records"][-1]["status"], "RETRY_REQUESTED")
        self.assertEqual(state["records"][-1]["retry_of_run_id"], "44480771895")
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0].get_header("Authorization"), "Bearer fixture-token")
        self.assertNotIn("Authorization", requests[1].headers)


if __name__ == "__main__":
    unittest.main()
