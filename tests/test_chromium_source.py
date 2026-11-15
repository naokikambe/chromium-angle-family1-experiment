import unittest

from src.maintenance_angle.chromium import SourceError, parse_angle_revision, parse_chrome_version


class ChromiumSourceTests(unittest.TestCase):
    def test_exact_version_and_angle_pin(self):
        version = "MAJOR=156\nMINOR=0\nBUILD=8078\nPATCH=48\n"
        self.assertEqual(parse_chrome_version(version), "156.0.8078.48")
        revision = "a" * 40
        self.assertEqual(parse_angle_revision("vars = {'angle_revision': '" + revision + "'}"), revision)

    def test_duplicate_or_missing_version_fields_rejected(self):
        with self.assertRaises(SourceError):
            parse_chrome_version("MAJOR=1\nMAJOR=2\nMINOR=0\nBUILD=1\nPATCH=0\n")
        with self.assertRaises(SourceError):
            parse_chrome_version("MAJOR=1\nMINOR=0\nBUILD=1\n")

    def test_multiple_or_malformed_angle_pins_rejected(self):
        with self.assertRaises(SourceError):
            parse_angle_revision("angle_revision='" + "a" * 40 + "' angle_revision='" + "b" * 40 + "'")
        with self.assertRaises(SourceError):
            parse_angle_revision("angle_revision='not-a-pin'")


if __name__ == "__main__":
    unittest.main()
