import contextlib
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.probes import media_webgl  # noqa: E402


class MediaWebGLCliTests(unittest.TestCase):
    def test_expected_architecture_is_required_and_supported_values_parse(self):
        arguments = [
            "--app", "/Applications/Chrome.app",
            "--expected-version", "156.0.8078.48",
            "--mode", "family1",
            "--h264-fixture", "/tmp/h264.mp4",
            "--h264-sha256", "a" * 64,
            "--vp8-fixture", "/tmp/vp8.webm",
            "--vp8-sha256", "b" * 64,
            "--confirm-rights-cleared-synthetic-inputs",
            "--out-dir", "/tmp/media-webgl-result",
        ]
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            media_webgl.build_parser().parse_args(arguments)
        self.assertEqual(raised.exception.code, 2)
        self.assertIn('"failure_stage": "arguments"', output.getvalue())

        for architecture in ("x86_64", "arm64"):
            parsed = media_webgl.build_parser().parse_args(
                arguments[:4] + ["--expected-architecture", architecture] + arguments[4:]
            )
            self.assertEqual(parsed.expected_architecture, architecture)

    def test_browser_command_selects_architecture_and_family1_flags(self):
        command = media_webgl.browser_command(
            Path("/Applications/Chrome.app/Contents/MacOS/Chrome"),
            Path("/tmp/chrome-profile"),
            "x86_64",
            "family1",
        )
        self.assertEqual(command[:3], [
            "/usr/bin/arch",
            "-x86_64",
            "/Applications/Chrome.app/Contents/MacOS/Chrome",
        ])
        self.assertIn("--use-angle=metal", command)
        self.assertIn("--disable-angle-features=requireGpuFamily2", command)
        self.assertEqual(command[-1], "about:blank")

        arm_command = media_webgl.browser_command(
            Path("/Applications/Chrome.app/Contents/MacOS/Chrome"),
            Path("/tmp/chrome-profile"),
            "arm64",
            "default",
        )
        self.assertEqual(arm_command[:2], ["/usr/bin/arch", "-arm64"])
        self.assertNotIn("--use-angle=metal", arm_command)

    def test_browser_command_rejects_unknown_architecture(self):
        with self.assertRaisesRegex(ValueError, "unsupported-browser-architecture"):
            media_webgl.browser_command(Path("Chrome"), Path("profile"), "i386", "default")


if __name__ == "__main__":
    unittest.main()
