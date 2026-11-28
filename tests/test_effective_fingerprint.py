import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.maintenance_angle import monitor_policy


REQUIRED = (
    ".github/workflows/watch-chrome-stable.yml", "scripts/angle-monitor.py",
    "scripts/build-and-verify-angle.sh", "scripts/build-angle-candidate.sh",
    "scripts/bootstrap-depot-tools.sh", "scripts/resolve-build-inputs.py",
    "scripts/resolve-chromium-source.py", "scripts/verify-artifact.sh",
    "scripts/verify-angle-binaries.sh", "scripts/verify-angle-artifact.py",
    "scripts/write-angle-manifest.py", "src/maintenance_angle/monitor_policy.py",
)


class EffectiveFingerprintTests(unittest.TestCase):
    def test_docs_and_revision_metadata_do_not_change_fingerprint_but_build_inputs_do(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = [*REQUIRED, ".gitattributes", "catalog/recipes/recipe.json",
                     "catalog/README.md", "patches/runtime.patch",
                     "tests/angle-policy/policy.py", "README.md"]
            for relative in paths:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture: " + relative)

            tracked = b"\0".join(path.encode() for path in paths) + b"\0"
            result = subprocess.CompletedProcess(args=[], returncode=0, stdout=tracked)
            with patch.object(monitor_policy.subprocess, "run", return_value=result):
                initial = monitor_policy.effective_input_fingerprint(root, "158.0.8127.37")
                (root / "README.md").write_text("documentation-only change")
                after_docs = monitor_policy.effective_input_fingerprint(root, "158.0.8127.37")
                (root / "catalog/README.md").write_text("catalog documentation-only change")
                after_catalog_docs = monitor_policy.effective_input_fingerprint(root, "158.0.8127.37")
                (root / "catalog/recipes/recipe.json").write_text("changed effective recipe")
                after_recipe = monitor_policy.effective_input_fingerprint(root, "158.0.8127.37")
                (root / "patches/runtime.patch").write_text("changed reviewed patch bytes")
                after_patch = monitor_policy.effective_input_fingerprint(root, "158.0.8127.37")
                (root / "scripts/build-angle-candidate.sh").write_text("changed build processing")
                after_build_script = monitor_policy.effective_input_fingerprint(root, "158.0.8127.37")
                another_version = monitor_policy.effective_input_fingerprint(root, "159.0.1000.2")

            self.assertEqual(initial, after_docs)
            self.assertEqual(initial, after_catalog_docs)
            self.assertNotEqual(initial, after_recipe)
            self.assertNotEqual(after_recipe, after_patch)
            self.assertNotEqual(after_patch, after_build_script)
            self.assertNotEqual(initial, another_version)

    def test_fingerprint_fails_closed_if_a_required_build_input_is_unavailable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "scripts").mkdir()
            tracked = b"scripts/angle-monitor.py\0"
            result = subprocess.CompletedProcess(args=[], returncode=0, stdout=tracked)
            with patch.object(monitor_policy.subprocess, "run", return_value=result):
                with self.assertRaises(monitor_policy.FingerprintError):
                    monitor_policy.effective_input_fingerprint(root, "158.0.8127.37")


if __name__ == "__main__":
    unittest.main()
