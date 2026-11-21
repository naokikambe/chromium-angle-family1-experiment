import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pr_build_inputs", ROOT / "scripts/prepare-pr-angle-inputs.py")
prepare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare)


class PrBuildInputTests(unittest.TestCase):
    def test_both_versions_resolve_exact_source_and_preserve_selection(self):
        for version, mode in (("156.0.8078.48", "catalog-baseline"),
                              ("158.0.8127.37", "new-revision-candidate")):
            source = json.loads((ROOT / "catalog/chrome" / f"{version}.json").read_text())
            inputs = prepare.checked_inputs(ROOT / "catalog", version, source, "a" * 40)
            self.assertEqual(inputs["selection_mode"], mode)
            self.assertEqual(inputs["recipe"]["chrome_source"], version)
            self.assertEqual(inputs["workflow_revision"], "a" * 40)

    def test_source_drift_is_rejected_before_build(self):
        version = "158.0.8127.37"
        source = json.loads((ROOT / "catalog/chrome" / f"{version}.json").read_text())
        for field, value in (("chrome_version", "158.0.8127.99"),
                             ("chromium_revision", "b" * 40), ("angle_revision", "c" * 40)):
            with self.subTest(field=field), self.assertRaises(prepare.InputError):
                changed = dict(source, **{field: value})
                prepare.checked_inputs(ROOT / "catalog", version, changed, "a" * 40)

    def test_malformed_version_cannot_select_arbitrary_catalog_path(self):
        with self.assertRaises(prepare.InputError):
            prepare.checked_inputs(ROOT / "catalog", "../fixture", {}, "a" * 40)


class SharedBuildPathTests(unittest.TestCase):
    def fixture(self, directory, failure):
        repo = directory / "repository"
        scripts = repo / "scripts"
        scripts.mkdir(parents=True)
        trace = directory / "calls.jsonl"
        for name in ("build-angle-candidate.sh", "verify-artifact.sh", "verify-angle-binaries.sh"):
            build_environment = (
                'mkdir -p "$3"\n'
                f'printf "DEPOT_TOOLS_REVISION={"f" * 40}\\nDEPOT_TOOLS_NINJA=fixture depot Ninja 1.2\\n" '
                '> "$3/build-environment.txt"\n'
                if name == "build-angle-candidate.sh" else ""
            )
            (scripts / name).write_text(
                '#!/bin/sh\nset -eu\n'
                f'printf \'%s\\n\' \'{name}\' >> "$FIXTURE_TRACE"\n'
                f'if [ "$FIXTURE_FAILURE" = "{name}" ]; then exit 9; fi\n'
                + build_environment)
        for name in ("write-angle-manifest.py", "verify-angle-artifact.py"):
            (scripts / name).write_text(
                'import json, os, sys\n'
                'with open(os.environ["FIXTURE_TRACE"], "a") as stream:\n'
                f' stream.write(json.dumps(["{name}", *sys.argv[1:]]) + "\\n")\n')
        tools = directory / "tools"
        tools.mkdir()
        for name in ("xcodebuild", "xcrun", "ninja"):
            command = tools / name
            command.write_text('#!/bin/sh\nprintf "synthetic tool version\\n"\n')
            command.chmod(0o755)
        inputs = directory / "inputs.json"
        inputs.write_text(json.dumps({"chrome_version": "158.0.8127.37", "architecture": "x86_64",
                                      "recipe": {"macos_deployment_target": "13.0",
                                                 "depot_tools_revision": "f" * 40}, "build_key": "a" * 64}))
        env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"],
                   GITHUB_RUN_ID="123", FIXTURE_TRACE=str(trace), FIXTURE_FAILURE=failure)
        return repo, inputs, trace, env

    def test_shared_path_verifies_binary_manifest_and_exact_build_key(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            repo, inputs, trace, env = self.fixture(directory, "")
            result = subprocess.run(["bash", str(ROOT / "scripts/build-and-verify-angle.sh"),
                                     str(repo), str(inputs), str(directory / "output"),
                                     "angle-macos-x86_64-chrome-158.0.8127.37-run-123"],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = trace.read_text().splitlines()
            self.assertEqual(lines[:3], ["build-angle-candidate.sh", "verify-artifact.sh", "verify-angle-binaries.sh"])
            verify = json.loads(lines[-1])
            self.assertIn("--build-key", verify)
            self.assertEqual(verify[-1], "a" * 64)
            manifest = json.loads(next(line for line in lines if '"write-angle-manifest.py"' in line))
            self.assertEqual(manifest[manifest.index("--ninja-version") + 1], "fixture depot Ninja 1.2")

    def test_build_or_binary_failure_prevents_manifest_creation(self):
        for failure in ("build-angle-candidate.sh", "verify-angle-binaries.sh"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp)
                repo, inputs, trace, env = self.fixture(directory, failure)
                result = subprocess.run(["bash", str(ROOT / "scripts/build-and-verify-angle.sh"),
                                         str(repo), str(inputs), str(directory / "output"), "fixture"],
                                        env=env, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("write-angle-manifest.py", trace.read_text())
