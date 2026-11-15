from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BuildSourcePolicyCliTests(unittest.TestCase):
    def test_build_cli_path_runs_native_and_math_harnesses_on_synthetic_mtl_utils(self):
        with tempfile.TemporaryDirectory() as temp:
            angle_root = Path(temp) / "angle-source"
            mtl_utils = angle_root / "src/libANGLE/renderer/metal/mtl_utils.mm"
            mtl_utils.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / "tests/fixtures/angle-policy/mtl_utils.mm", mtl_utils)
            build_script = (ROOT / "scripts/build-angle-candidate.sh").read_text(encoding="utf-8")
            expected_contract = '--mtl-utils "$angle_root/src/libANGLE/renderer/metal/mtl_utils.mm"'
            self.assertGreaterEqual(build_script.count(expected_contract), 2)
            for helper in ("phase5-metal-family1-native-query-policy.py",
                           "phase5-metal-family1-math-options-policy.py"):
                with self.subTest(helper=helper):
                    result = subprocess.run(
                        [sys.executable, str(ROOT / "tests/angle-policy" / helper),
                         "--mtl-utils", str(mtl_utils)],
                        cwd=ROOT, capture_output=True, text=True, check=False, timeout=180)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
