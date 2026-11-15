import unittest

from src.maintenance_angle.stable import ReleaseError, select_candidate


class StableSelectionTests(unittest.TestCase):
    def release(self, version, fraction=1.0, end=None):
        serving = {"startTime": "2026-11-01T00:00:00Z"}
        if end is not None:
            serving["endTime"] = end
        return {"version": version, "fraction": fraction, "serving": serving}

    def test_selects_newest_fully_rolled_out_mac_candidate(self):
        data = {"releases": [self.release("157.0.300.1", 0.5), self.release("156.0.301.8"),
                             self.release("157.0.301.1"), self.release("157.0.300.9", 1.0, "2026-11-10") ]}
        self.assertEqual(select_candidate(data, "156.0.300.0")["chrome_version"], "157.0.301.1")

    def test_does_not_accept_partial_or_missing_rollout_fraction(self):
        self.assertIsNone(select_candidate({"releases": [self.release("157.0.300.1", 0.9)]}, "156.0.300.0"))
        with self.assertRaises(ReleaseError):
            select_candidate({"releases": [{"version": "157.0.300.1", "serving": {"startTime": "now"}}]}, "156.0.300.0")

    def test_malformed_payload_and_baseline_fail_closed(self):
        with self.assertRaises(ReleaseError):
            select_candidate({}, "156.0.0")
        with self.assertRaises(ReleaseError):
            select_candidate({"releases": []}, "156.0.0")


if __name__ == "__main__":
    unittest.main()
