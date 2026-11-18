from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import unittest
import zipfile

from src.maintenance_angle.local import fetch_artifact, find_index_record
from tests.test_artifact_handling import make_artifact


class SharedIndexContractTests(unittest.TestCase):
    def test_local_match_and_fetch_share_the_latest_state_reader_and_exact_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            artifact_dir = root / "artifact"
            manifest = make_artifact(artifact_dir)
            expiry = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
            artifact_name = manifest["artifact_name"]
            record = {"chrome_version": manifest["chrome_version"], "platform": "macOS",
                      "architecture": manifest["architecture"], "status": "CI_BUILD_SUCCEEDED",
                      "artifact_id": 73, "artifact_name": artifact_name, "expires_at": expiry,
                      "run_id": manifest["run_id"], "build_key": manifest["build_key"],
                      "chromium_revision": manifest["chromium_revision"],
                      "angle_revision": manifest["angle_revision"]}
            state = {"schema": "angle-stable-monitor-state-v1", "records": [record]}
            archive = root / "artifact.zip"
            with zipfile.ZipFile(archive, "w") as output:
                for path in artifact_dir.rglob("*"):
                    if path.is_file():
                        output.write(path, arcname=path.relative_to(artifact_dir).as_posix())

            class Client:
                state_reads = 0

                def load_latest_state(self, workflow_file):
                    self.state_reads += 1
                    return state

                def artifacts(self):
                    return [{"id": 73, "name": artifact_name, "expired": False,
                             "expires_at": expiry}]

                def download_artifact(self, artifact_id):
                    self.downloaded_id = artifact_id
                    return archive.read_bytes()

            client = Client()
            matched, _artifact = find_index_record("owner/repo", manifest["chrome_version"],
                                                   manifest["architecture"], client)
            self.assertEqual(matched, record)
            destination = root / "fetched"
            result = fetch_artifact("owner/repo", manifest["chrome_version"], manifest["architecture"],
                                    destination, client)
            self.assertEqual(client.state_reads, 2)
            self.assertEqual(client.downloaded_id, 73)
            self.assertEqual(result["manifest"]["build_key"], manifest["build_key"])
            self.assertEqual(result["manifest"]["libraries"], manifest["libraries"])


if __name__ == "__main__":
    unittest.main()
