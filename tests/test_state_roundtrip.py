import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from src.maintenance_angle.github_artifacts import GitHubActionsArtifacts

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/angle-monitor.py"
SPEC = importlib.util.spec_from_file_location("angle_monitor_roundtrip", SCRIPT)
monitor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(monitor)
INTERRUPTED_VERSION = ".".join(("158", "0", "1", "2"))


class FirstRunClient:
    def __init__(self, repository):
        pass

    def load_latest_state(self, workflow_file):
        return None


class StateArtifactRoundTripTests(unittest.TestCase):
    def test_writer_archive_reader_and_next_begin_share_one_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            releases = root / "releases.json"
            releases.write_text(json.dumps({"releases": [{"version": "157.0.300.2", "fraction": 1.0,
                                                          "serving": {"startTime": "now"}}]}))
            state_path = root / "stable-monitor-state.json"
            candidate_path = root / "candidate.json"
            first_args = type("Args", (), {"repository": "owner/repo", "run_id": "10",
                "state": state_path, "output": candidate_path, "fixture": releases,
                "github_output": None, "reacquire_version": ""})()
            with patch.object(monitor, "GitHubActionsArtifacts", FirstRunClient):
                monitor.begin(first_args)
            written = json.loads(state_path.read_text())
            self.assertEqual(written["last_detected_version"], "157.0.300.2")

            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w") as output:
                output.write(state_path, arcname="stable-monitor-state.json")
            artifact = {"id": 91, "name": "stable-monitor-state", "expired": False,
                        "expires_at": "2999-01-01T00:00:00Z", "created_at": "2026-11-15T00:00:00Z",
                        "workflow_run": {"id": "10", "head_branch": "main"}}
            remote = GitHubActionsArtifacts("owner/repo")
            with patch.object(remote, "artifacts", return_value=[artifact]), \
                    patch.object(remote, "workflow_runs", return_value=[{"id": "10", "status": "completed",
                                                                            "created_at": "2026-11-15T00:00:00Z"}]), \
                    patch.object(remote, "download_artifact", return_value=archive.getvalue()):
                loaded = remote.load_latest_state("watch-chrome-stable.yml")
            self.assertEqual(loaded, written)

            class NextRunClient:
                def __init__(self, repository):
                    pass

                def load_latest_state(self, workflow_file):
                    return loaded

            second_args = type("Args", (), {"repository": "owner/repo", "run_id": "11",
                "state": root / "next-state.json", "output": root / "next-candidate.json",
                "fixture": releases, "github_output": None, "reacquire_version": ""})()
            with patch.object(monitor, "GitHubActionsArtifacts", NextRunClient):
                monitor.begin(second_args)
            next_state = json.loads(second_args.state.read_text())
            next_candidate = json.loads(second_args.output.read_text())
            self.assertEqual(next_state["last_detected_version"], "157.0.300.2")
            self.assertEqual(next_candidate["status"], "NO_NEW_FULLY_ROLLED_OUT_STABLE")
            self.assertEqual(len(next_state["records"]), 1)

    def test_interrupted_checkpoint_is_not_rebuilt_or_marked_success_on_next_begin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = {"schema": "angle-stable-monitor-state-v1", "baseline": monitor.BASELINE,
                     "last_detected_version": INTERRUPTED_VERSION, "records": [
                         {"run_id": "20", "chrome_version": INTERRUPTED_VERSION,
                          "status": "STABLE_RELEASE_DETECTED"}]}
            state_path = root / "stable-monitor-state.json"
            state_path.write_text(json.dumps(state))
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w") as output:
                output.write(state_path, arcname="stable-monitor-state.json")
            checkpoint = {"id": 92, "name": "stable-monitor-checkpoint-20", "expired": False,
                          "expires_at": "2999-01-01T00:00:00Z", "created_at": "2026-11-15T00:00:00Z",
                          "workflow_run": {"id": "20", "head_branch": "main"}}
            remote = GitHubActionsArtifacts("owner/repo")
            with patch.object(remote, "artifacts", return_value=[checkpoint]), \
                    patch.object(remote, "workflow_runs", return_value=[{"id": "20", "status": "completed",
                                                                            "created_at": "2026-11-15T00:00:00Z"}]), \
                    patch.object(remote, "download_artifact", return_value=archive.getvalue()):
                recovered = remote.load_latest_state("watch-chrome-stable.yml")
            self.assertEqual(recovered["records"][0]["status"], "CI_BUILD_INTERRUPTED")

            release_fixture = root / "releases.json"
            release_fixture.write_text(json.dumps({"releases": [{"version": INTERRUPTED_VERSION, "fraction": 1.0,
                                                                  "serving": {"startTime": "now"}}]}))

            class NextRunClient:
                def __init__(self, repository):
                    pass

                def load_latest_state(self, workflow_file):
                    return recovered

            args = type("Args", (), {"repository": "owner/repo", "run_id": "21",
                "state": root / "next-state.json", "output": root / "candidate.json",
                "fixture": release_fixture, "github_output": None, "reacquire_version": ""})()
            with patch.object(monitor, "GitHubActionsArtifacts", NextRunClient):
                monitor.begin(args)
            next_state = json.loads(args.state.read_text())
            candidate = json.loads(args.output.read_text())
            self.assertEqual(candidate["status"], "NO_NEW_FULLY_ROLLED_OUT_STABLE")
            self.assertEqual(next_state["records"][0]["status"], "CI_BUILD_INTERRUPTED")
            self.assertFalse(any(r.get("status") == "CI_BUILD_SUCCEEDED" for r in next_state["records"]))


if __name__ == "__main__":
    unittest.main()
