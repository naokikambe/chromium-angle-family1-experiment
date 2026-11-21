import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_SCRIPT = ROOT / "scripts/bootstrap-depot-tools.sh"
ANGLE_TOOLS_SCRIPT = ROOT / "scripts/validate-angle-build-tools.sh"


def init_git_checkout(root, filename, contents):
    root.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Fixture"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "fixture@example.com"], check=True)
    (root / filename).write_text(contents, encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", filename], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture pin"], check=True)
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


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
        # These pinned wrapper files deliberately exist but must not be started here.
        for name in ("gn", "ninja"):
            path = root / name
            path.write_text(
                "#!/usr/bin/env bash\n"
                f"printf 'premature-{name}\\n' >> \"$FIXTURE_TRACE\"\n"
                "exit 23\n",
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

    def test_fresh_checkout_initializes_python_before_any_gn_or_ninja(self):
        with tempfile.TemporaryDirectory() as temp:
            root, revision, _, trace, stage, env = self.fixture(Path(temp))
            self.assertFalse((root / "python3_bin_reldir.txt").exists())

            result = self.run_helper(root, revision, env)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            calls = trace.read_text(encoding="utf-8").splitlines()
            self.assertEqual(calls, ["ensure_bootstrap", "python3-version", "python3-executable"])
            self.assertFalse(any("gn" in call or "ninja" in call for call in calls))
            self.assertNotIn("wrong-python3", calls)
            self.assertEqual(subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(), revision)
            self.assertEqual(stage.read_text(encoding="utf-8").strip(), "depot-tools-python-validation")
            self.assertIn("depot_tools revision: " + revision, result.stdout)

    def test_bootstrap_failure_stops_before_patch_gn_and_ninja(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            root, revision, _, trace, stage, env = self.fixture(directory)
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
            self.assertEqual(stage.read_text(encoding="utf-8").strip(), "depot-tools-python-bootstrap")

    def test_missing_ensure_bootstrap_is_reported_as_bootstrap_stage(self):
        with tempfile.TemporaryDirectory() as temp:
            root, revision, _, trace, stage, env = self.fixture(Path(temp))
            (root / "ensure_bootstrap").unlink()

            result = self.run_helper(root, revision, env)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not contain executable ensure_bootstrap", result.stderr)
            self.assertFalse(trace.exists())
            self.assertEqual(stage.read_text(encoding="utf-8").strip(), "depot-tools-python-bootstrap")

    def test_missing_python_environment_stops_with_a_specific_error(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            root, revision, _, trace, stage, env = self.fixture(directory)
            env["FIXTURE_MISSING_PYTHON"] = "1"

            result = self.run_helper(root, revision, env)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("python3_bin_reldir.txt is missing after ensure_bootstrap", result.stderr)
            self.assertEqual(trace.read_text(encoding="utf-8").splitlines(), ["ensure_bootstrap"])
            self.assertEqual(stage.read_text(encoding="utf-8").strip(), "depot-tools-python-validation")

    def test_revision_change_during_bootstrap_is_rejected_before_python_or_build_tools(self):
        with tempfile.TemporaryDirectory() as temp:
            root, revision, drift_revision, trace, _, env = self.fixture(Path(temp))
            env["FIXTURE_DRIFT_REVISION"] = drift_revision

            result = self.run_helper(root, revision, env)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("checkout revision after bootstrap", result.stderr)
            self.assertEqual(trace.read_text(encoding="utf-8").splitlines(), ["ensure_bootstrap"])
            self.assertEqual(subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(), drift_revision)


class AngleBuildToolValidationTests(unittest.TestCase):
    def fixture(self, directory):
        angle_root = directory / "angle"
        angle_revision = init_git_checkout(angle_root, "pin", "ANGLE source pin\n")
        depot_tools_root = directory / "depot-tools"
        depot_revision = init_git_checkout(depot_tools_root, "pin", "depot_tools source pin\n")
        wrong_tools = directory / "wrong-tools"
        wrong_tools.mkdir()
        trace = directory / "trace.txt"
        for name in ("gn", "ninja"):
            executable = wrong_tools / name
            executable.write_text(
                "#!/bin/sh\n"
                f"printf 'external-{name}\\n' >> \"$FIXTURE_TRACE\"\n"
                "exit 29\n",
                encoding="utf-8",
            )
            executable.chmod(0o755)
        stage = directory / "failure-stage"
        env = dict(
            os.environ,
            PATH=str(wrong_tools) + os.pathsep + os.environ.get("PATH", ""),
            FIXTURE_TRACE=str(trace),
            FAILURE_STAGE_FILE=str(stage),
        )
        return angle_root, angle_revision, depot_tools_root, depot_revision, trace, stage, env

    def run_validation(self, fixture):
        angle_root, angle_revision, depot_root, depot_revision, _, _, env = fixture
        return subprocess.run(
            ["bash", str(ANGLE_TOOLS_SCRIPT), str(angle_root), angle_revision, str(depot_root), depot_revision],
            cwd=angle_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

    def install_native_tool_fixture(self, root, relative_path, trace_event):
        tool = root / relative_path
        tool.parent.mkdir(parents=True, exist_ok=True)
        source = tool.with_suffix(".c")
        source.write_text(
            "#include <stdio.h>\n"
            "#include <string.h>\n"
            "#include <stdlib.h>\n"
            "int main(int argc, char **argv) {\n"
            "  if (argc > 1 && strcmp(argv[1], \"--version\") == 0) {\n"
            "    const char *trace = getenv(\"FIXTURE_TRACE\");\n"
            "    if (trace) { FILE *f = fopen(trace, \"a\"); if (f) { fprintf(f, \"" + trace_event + "\\n\"); fclose(f); } }\n"
            "    puts(\"ANGLE dependency fixture 1.0\");\n"
            "    return 0;\n"
            "  }\n"
            "  return 0;\n"
            "}\n",
            encoding="utf-8",
        )
        subprocess.run(
            [shutil.which("clang") or "clang", "-arch", "x86_64", str(source), "-o", str(tool)],
            check=True,
            capture_output=True,
            text=True,
        )
        source.unlink()
        return tool

    def test_missing_synced_dependency_stops_without_path_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = self.fixture(Path(temp))
            result = self.run_validation(fixture)
            trace = fixture[4]
            stage = fixture[5]

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("pinned ANGLE dependency is missing", result.stderr)
            self.assertIn("buildtools/mac/gn", result.stderr)
            self.assertFalse(trace.exists())
            self.assertEqual(stage.read_text(encoding="utf-8").strip(), "angle-build-tool-validation")

    def test_shell_wrapper_that_falls_back_to_external_gn_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = self.fixture(Path(temp))
            angle_root = fixture[0]
            for relative_path, tool in (
                ("buildtools/mac/gn", "gn"),
                ("third_party/ninja/ninja", "ninja"),
            ):
                entry = angle_root / relative_path
                entry.parent.mkdir(parents=True, exist_ok=True)
                entry.write_text(
                    "#!/bin/sh\n"
                    f"printf 'wrapper-{tool}\\n' >> \"$FIXTURE_TRACE\"\n"
                    f"exec {tool} \"$@\"\n",
                    encoding="utf-8",
                )
                entry.chmod(0o755)

            result = self.run_validation(fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not a macOS x86_64 executable", result.stderr)
            self.assertFalse(fixture[4].exists(), "neither wrapper nor PATH fallback should run")

    @unittest.skipUnless(os.uname().sysname == "Darwin" and shutil.which("clang"), "needs macOS clang for x86_64 fixture binaries")
    def test_fresh_python_bootstrap_precedes_sync_and_uses_synced_native_tools(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            depot_fixture_dir = directory / "fresh-depot"
            depot_fixture_dir.mkdir()
            depot_root, depot_revision, _, trace, stage, env = DepotToolsBootstrapTests().fixture(depot_fixture_dir)
            angle_root = directory / "angle"
            angle_revision = init_git_checkout(angle_root, "pin", "ANGLE source pin\n")
            staging_root = directory / "synced-dependencies"
            self.install_native_tool_fixture(staging_root, "gn", "angle-dependency-gn")
            self.install_native_tool_fixture(staging_root, "ninja", "angle-dependency-ninja")

            driver = directory / "common-build-sequence.sh"
            driver.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "export DEPOT_TOOLS_DIR=\"$FIXTURE_DEPOT_ROOT\"\n"
                "export DEPOT_TOOLS_UPDATE=0\n"
                "export DEPOT_TOOLS_BOOTSTRAP_PYTHON3=1\n"
                "export PATH=\"$DEPOT_TOOLS_DIR/python-bin:$DEPOT_TOOLS_DIR:$PATH\"\n"
                f"bash {BOOTSTRAP_SCRIPT!s} \"$DEPOT_TOOLS_DIR\" \"$FIXTURE_DEPOT_REVISION\"\n"
                "cd \"$FIXTURE_ANGLE_ROOT\"\n"
                "printf 'angle-bootstrap\\n' >> \"$FIXTURE_TRACE\"\n"
                "printf 'gclient-sync\\n' >> \"$FIXTURE_TRACE\"\n"
                "mkdir -p buildtools/mac third_party/ninja\n"
                "cp \"$FIXTURE_GN\" buildtools/mac/gn\n"
                "cp \"$FIXTURE_NINJA\" third_party/ninja/ninja\n"
                f"bash {ANGLE_TOOLS_SCRIPT!s} \"$FIXTURE_ANGLE_ROOT\" \"$FIXTURE_ANGLE_REVISION\" "
                "\"$DEPOT_TOOLS_DIR\" \"$FIXTURE_DEPOT_REVISION\"\n",
                encoding="utf-8",
            )
            driver_env = dict(
                env,
                FIXTURE_DEPOT_ROOT=str(depot_root),
                FIXTURE_DEPOT_REVISION=depot_revision,
                FIXTURE_ANGLE_ROOT=str(angle_root),
                FIXTURE_ANGLE_REVISION=angle_revision,
                FIXTURE_GN=str(staging_root / "gn"),
                FIXTURE_NINJA=str(staging_root / "ninja"),
            )

            result = subprocess.run(
                ["bash", str(driver)], env=driver_env, capture_output=True, text=True, check=False, timeout=60
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("ANGLE GN path: buildtools/mac/gn", result.stdout)
            self.assertIn("ANGLE Ninja path: third_party/ninja/ninja", result.stdout)
            self.assertEqual(
                trace.read_text(encoding="utf-8").splitlines(),
                [
                    "ensure_bootstrap",
                    "python3-version",
                    "python3-executable",
                    "angle-bootstrap",
                    "gclient-sync",
                    "angle-dependency-gn",
                    "angle-dependency-ninja",
                ],
            )
            self.assertEqual(stage.read_text(encoding="utf-8").strip(), "angle-build-tool-validation")


if __name__ == "__main__":
    unittest.main()
