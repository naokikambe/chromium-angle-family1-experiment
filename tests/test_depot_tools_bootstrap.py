import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_SCRIPT = ROOT / "scripts/bootstrap-depot-tools.sh"


class DepotToolsBootstrapTests(unittest.TestCase):
    def fixture(self, directory):
        root = directory / "depot-tools"
        root.mkdir()
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Fixture"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "fixture@example.com"], check=True)
        marker = root / "tracked"
        marker.write_text("pinned checkout\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "tracked"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture pin"], check=True)
        revision = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        marker.write_text("second checkout\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "commit", "-qam", "fixture drift"], check=True)
        drift_revision = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        subprocess.run(["git", "-C", str(root), "checkout", "-q", "--detach", revision], check=True)

        trace = directory / "trace.txt"
        (root / "ensure_bootstrap").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "printf 'ensure_bootstrap\\n' >> \"$FIXTURE_TRACE\"\n"
            "[[ \"$DEPOT_TOOLS_DIR\" == \"$PWD\" || \"$DEPOT_TOOLS_DIR\" == \"$(cd \"$DEPOT_TOOLS_DIR\" && pwd -P)\" ]]\n"
            "[[ \"$DEPOT_TOOLS_UPDATE\" == 0 ]]\n"
            "[[ \"$DEPOT_TOOLS_BOOTSTRAP_PYTHON3\" == 1 ]]\n"
            "if [[ \"${FIXTURE_BOOTSTRAP_FAILURE:-0}\" == 1 ]]; then exit 17; fi\n"
            "if [[ \"${FIXTURE_DRIFT_REVISION:-}\" != \"\" ]]; then git -C \"$DEPOT_TOOLS_DIR\" update-ref HEAD \"$FIXTURE_DRIFT_REVISION\"; fi\n"
            "if [[ \"${FIXTURE_MISSING_PYTHON:-0}\" == 1 ]]; then exit 0; fi\n"
            "mkdir -p \"$DEPOT_TOOLS_DIR/python3_bin\" \"$DEPOT_TOOLS_DIR/python-bin\"\n"
            "printf 'python3_bin\\n' > \"$DEPOT_TOOLS_DIR/python3_bin_reldir.txt\"\n"
            "printf '#!/bin/sh\\nexit 0\\n' > \"$DEPOT_TOOLS_DIR/python3_bin/python3\"\n"
            "chmod +x \"$DEPOT_TOOLS_DIR/python3_bin/python3\"\n",
            encoding="utf-8",
        )
        (root / "ensure_bootstrap").chmod(0o755)

        python_dir = root / "python-bin"
        python_dir.mkdir()
        (python_dir / "python3").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "if [[ \"${1:-}\" == --version ]]; then\n"
            "  printf 'python3-version\\n' >> \"$FIXTURE_TRACE\"\n"
            "  printf 'Python fixture\\n'\n"
            "elif [[ \"${1:-}\" == -c ]]; then\n"
            "  printf 'python3-executable\\n' >> \"$FIXTURE_TRACE\"\n"
            "  printf '%s/python3_bin/python3\\n' \"$DEPOT_TOOLS_DIR\"\n"
            "else exit 19; fi\n",
            encoding="utf-8",
        )
        (python_dir / "python3").chmod(0o755)
        for name in ("gn", "ninja"):
            path = root / name
            path.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                f"printf '{name}-version\\n' >> \"$FIXTURE_TRACE\"\n"
                f"[[ \"${{1:-}}\" == --version ]]\n"
                f"printf '{name} fixture\\n'\n",
                encoding="utf-8",
            )
            path.chmod(0o755)

        wrong = directory / "wrong-tools"
        wrong.mkdir()
        for name in ("python3", "gn", "ninja"):
            path = wrong / name
            path.write_text(
                "#!/usr/bin/env bash\n"
                f"printf 'wrong-{name}\\n' >> \"$FIXTURE_TRACE\"\n"
                "exit 23\n",
                encoding="utf-8",
            )
            path.chmod(0o755)

        stage = directory / "failure-stage"
        env = dict(
            os.environ,
            PATH=str(wrong) + os.pathsep + os.environ.get("PATH", ""),
            FIXTURE_TRACE=str(trace),
            FIXTURE_DRIFT_REVISION="",
            DEPOT_TOOLS_UPDATE="inherited-value-must-be-overridden",
            DEPOT_TOOLS_BOOTSTRAP_PYTHON3="0",
            FAILURE_STAGE_FILE=str(stage),
        )
        return root, revision, drift_revision, trace, stage, env

    def run_helper(self, root, revision, env):
        return subprocess.run(
            ["bash", str(BOOTSTRAP_SCRIPT), str(root), revision],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

    def test_fresh_checkout_bootstraps_before_depot_tools_tools_and_rejects_path_decoys(self):
        with tempfile.TemporaryDirectory() as temp:
            root, revision, _, trace, stage, env = self.fixture(Path(temp))
            self.assertFalse((root / "python3_bin_reldir.txt").exists())

            result = self.run_helper(root, revision, env)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            calls = trace.read_text(encoding="utf-8").splitlines()
            self.assertEqual(
                calls,
                ["ensure_bootstrap", "python3-version", "python3-executable", "gn-version", "ninja-version"],
            )
            self.assertLess(calls.index("ensure_bootstrap"), calls.index("gn-version"))
            self.assertNotIn("wrong-python3", calls)
            self.assertNotIn("wrong-gn", calls)
            self.assertNotIn("wrong-ninja", calls)
            self.assertEqual(subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(), revision)
            self.assertEqual(stage.read_text(encoding="utf-8").strip(), "depot-tools-tool-validation")
            self.assertIn("depot_tools revision: " + revision, result.stdout)

    def test_bootstrap_failure_stops_before_patch_gn_and_ninja(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            root, revision, _, trace, _, env = self.fixture(directory)
            env["FIXTURE_BOOTSTRAP_FAILURE"] = "1"
            driver = directory / "driver.sh"
            driver.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                f"bash {BOOTSTRAP_SCRIPT!s} \"$DEPOT_TOOLS_DIR\" \"$FIXTURE_REVISION\"\n"
                "printf 'patch\\n' >> \"$FIXTURE_TRACE\"\n"
                "\"$DEPOT_TOOLS_DIR/gn\" gen out/Release\n"
                "\"$DEPOT_TOOLS_DIR/ninja\" -C out/Release\n",
                encoding="utf-8",
            )
            driver_env = dict(env, DEPOT_TOOLS_DIR=str(root), FIXTURE_REVISION=revision)

            result = subprocess.run(["bash", str(driver)], env=driver_env, capture_output=True, text=True, check=False)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ensure_bootstrap exited unsuccessfully", result.stderr)
            self.assertEqual(trace.read_text(encoding="utf-8").splitlines(), ["ensure_bootstrap"])
            self.assertEqual(stage_or_none(directory), "depot-tools-bootstrap")

    def test_missing_python_environment_stops_with_a_specific_error(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            root, revision, _, trace, _, env = self.fixture(directory)
            env["FIXTURE_MISSING_PYTHON"] = "1"

            result = self.run_helper(root, revision, env)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("python3_bin_reldir.txt is missing after ensure_bootstrap", result.stderr)
            self.assertEqual(trace.read_text(encoding="utf-8").splitlines(), ["ensure_bootstrap"])

    def test_revision_change_during_bootstrap_is_rejected_before_tools(self):
        with tempfile.TemporaryDirectory() as temp:
            root, revision, drift_revision, trace, _, env = self.fixture(Path(temp))
            env["FIXTURE_DRIFT_REVISION"] = drift_revision

            result = self.run_helper(root, revision, env)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("checkout revision after bootstrap", result.stderr)
            self.assertEqual(trace.read_text(encoding="utf-8").splitlines(), ["ensure_bootstrap"])
            self.assertEqual(subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(), drift_revision)

    def test_symlinked_gn_cannot_escape_the_pinned_checkout(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            root, revision, _, trace, _, env = self.fixture(directory)
            (root / "gn").unlink()
            (root / "gn").symlink_to(directory / "wrong-tools" / "gn")

            result = self.run_helper(root, revision, env)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("pinned tool entry is missing, non-executable, or a symlink: gn", result.stderr)
            self.assertEqual(trace.read_text(encoding="utf-8").splitlines(), ["ensure_bootstrap"])


def stage_or_none(directory):
    path = directory / "failure-stage"
    return path.read_text(encoding="utf-8").strip() if path.exists() else None


if __name__ == "__main__":
    unittest.main()
