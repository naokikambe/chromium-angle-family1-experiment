from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

APPLE_GATE_SOURCE = '''
bool IsMetalRendererAvailable()
{
    const bool family1RuntimeOptIn =
        GetEnvironmentVar("ANGLE_PHASE5_ENABLE_METAL_FAMILY1") == "1";
#if defined(ANGLE_PLATFORM_MACOS)
    if (!machineModelSufficient && !family1RuntimeOptIn)
#else
    if (!machineModelSufficient)
#endif
    {
        return false;
    }
#if TARGET_OS_MACCATALYST && __IPHONE_OS_VERSION_MIN_REQUIRED < 160000
    return [device supportsFamily:MTLGPUFamilyMacCatalyst2];
#elif TARGET_OS_MACCATALYST || TARGET_OS_OSX
    const bool supportsFamily2 = [device supportsFamily:MTLGPUFamilyMac2];
#if TARGET_OS_OSX && !TARGET_OS_MACCATALYST
    if (supportsFamily2 || !family1RuntimeOptIn)
    {
        return supportsFamily2;
    }
    const bool supportsFamily1 = [device supportsFamily:MTLGPUFamilyMac1];
    return supportsFamily1;
#else
    return supportsFamily2;
#endif
#else
    return false;
#endif
}
'''


class BuildSourcePolicyCliTests(unittest.TestCase):
    def test_build_cli_path_runs_native_and_math_harnesses_on_synthetic_mtl_utils(self):
        with tempfile.TemporaryDirectory() as temp:
            angle_root = Path(temp) / "angle-source"
            mtl_utils = angle_root / "src/libANGLE/renderer/metal/mtl_utils.mm"
            apple_utils = angle_root / "src/common/apple_platform_utils.mm"
            mtl_utils.parent.mkdir(parents=True)
            apple_utils.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / "tests/fixtures/angle-policy/mtl_utils.mm", mtl_utils)
            apple_utils.write_text(APPLE_GATE_SOURCE, encoding="utf-8")
            build_script = (ROOT / "scripts/build-angle-candidate.sh").read_text(encoding="utf-8")
            expected_contract = '--mtl-utils "$angle_root/src/libANGLE/renderer/metal/mtl_utils.mm"'
            self.assertGreaterEqual(build_script.count(expected_contract), 2)
            self.assertIn('--apple-platform-utils "$angle_root/src/common/apple_platform_utils.mm"', build_script)
            for helper in ("native-query-policy.py",
                           "math-options-policy.py"):
                with self.subTest(helper=helper):
                    command = [sys.executable, str(ROOT / "tests/angle-policy" / helper),
                               "--mtl-utils", str(mtl_utils)]
                    if helper == "native-query-policy.py":
                        command.extend(("--apple-platform-utils", str(apple_utils)))
                    result = subprocess.run(
                        command,
                        cwd=ROOT, capture_output=True, text=True, check=False, timeout=180)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
