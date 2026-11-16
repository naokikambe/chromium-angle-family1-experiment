from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def runner_contexts_in_job_env(text):
    """Return runner-context references from job-level env blocks only."""
    in_jobs = False
    in_job_env = False
    matches = []
    for number, line in enumerate(text.splitlines(), start=1):
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if indent == 0 and stripped == "jobs:":
            in_jobs = True
            continue
        if not in_jobs or not stripped or stripped.startswith("#"):
            continue
        if indent == 4 and stripped == "env:":
            in_job_env = True
            continue
        if in_job_env and indent <= 4:
            in_job_env = False
        if in_job_env and re.search(r"\brunner\.", line):
            matches.append((number, line.strip()))
    return matches


class WorkflowContractTests(unittest.TestCase):
    def test_workflows_are_read_only_and_actions_are_immutable_pins(self):
        for relative in (".github/workflows/watch-chrome-stable.yml", ".github/workflows/reproduce-156.yml",
                         ".github/workflows/validate-pr.yml"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("contents: read", text)
            self.assertRegex(text, r"(?m)^\s+uses: [^\n]+@[0-9a-f]{40}(?:\s+#.*)?$")
            for line in text.splitlines():
                if "uses:" in line:
                    self.assertRegex(line, r"@[0-9a-f]{40}(?:\s+#.*)?$")
            self.assertNotRegex(text, r"(?m)^  push:")
            self.assertNotIn("contents: write", text)
            self.assertEqual(runner_contexts_in_job_env(text), [])

        invalid = "jobs:\n  build:\n    env:\n      VALUE: ${{ runner.temp }}\n    steps:\n      - env:\n          VALUE: ${{ runner.temp }}\n"
        self.assertEqual(runner_contexts_in_job_env(invalid), [(4, "VALUE: ${{ runner.temp }}")])

    def test_runner_temp_paths_are_initialized_on_the_runner_before_use(self):
        watch = (ROOT / ".github/workflows/watch-chrome-stable.yml").read_text(encoding="utf-8")
        monitor_init = watch.index("name: Initialize runner-local monitor paths")
        self.assertLess(monitor_init, watch.index("name: Detect a new fully rolled out Mac Stable release"))
        for variable, path in (
            ("CANDIDATE_FILE", "stable-candidate.json"),
            ("STATE_FILE", "stable-monitor-state.json"),
            ("INPUTS_FILE", "build-inputs.json"),
            ("ARTIFACT_DIR", "angle-candidate"),
            ("FAILURE_STAGE_FILE", "angle-failure-stage"),
        ):
            self.assertIn(f"printf '{variable}=%s/{path}\\n' \"$RUNNER_TEMP\"", watch)
        recovery_init = watch.index("name: Initialize runner-local recovery path")
        self.assertLess(recovery_init, watch.index("name: Restore retained state or write an owner-audited baseline"))

        reproduce = (ROOT / ".github/workflows/reproduce-156.yml").read_text(encoding="utf-8")
        initialize = reproduce.index("name: Initialize runner-local reproduction paths")
        self.assertLess(initialize, reproduce.index("name: Resolve the pinned Chromium 156 release inputs"))
        self.assertIn("printf 'INPUTS_FILE=%s/build-inputs.json\\n' \"$RUNNER_TEMP\"", reproduce)
        self.assertIn("printf 'ARTIFACT_DIR=%s/angle-baseline-156\\n' \"$RUNNER_TEMP\"", reproduce)

    def test_monitor_is_scheduled_and_serialized_with_bounded_artifacts(self):
        text = (ROOT / ".github/workflows/watch-chrome-stable.yml").read_text(encoding="utf-8")
        self.assertIn("cron: '17 */6 * * *'", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("actions: read", text)
        self.assertIn("if: github.ref == 'refs/heads/main'", text)
        self.assertEqual(text.count("retention-days: 90"), 5)
        self.assertIn("--run-id \"$GITHUB_RUN_ID\"", text)
        self.assertIn("scripts/resolve-chromium-source.py", text)
        self.assertIn("scripts/build-angle-candidate.sh", text)
        self.assertIn("scripts/verify-artifact.sh", text)
        self.assertIn("scripts/verify-angle-binaries.sh", text)
        self.assertIn("scripts/write-angle-manifest.py", text)
        self.assertIn("stable-monitor-checkpoint-${{ github.run_id }}", text)
        self.assertIn("steps.checkpoint.outcome == 'success'", text)
        self.assertIn("stable-monitor-state.json", text)
        self.assertIn("operation == 'recover_state'", text)
        self.assertIn("retry_failed_version", text)
        self.assertIn("reacquire_expired_artifact", text)
        self.assertIn("confirm_unpinned_retry", text)
        self.assertIn("scripts/angle-monitor.py recover", text)
        self.assertIn("scripts/angle-monitor.py record-source", text)
        self.assertIn("scripts/angle-monitor.py record-inputs", text)
        self.assertIn("stable-monitor-resolved-checkpoint-${{ github.run_id }}", text)
        self.assertNotIn("scripts/build-angle-candidate.sh", text[text.index("  recover-monitor-state:"):])
        self.assertNotRegex(text, r"(?i)gh\s+(pr|issue|release|repo)\s+(create|edit)")
        self.assertNotRegex(text, r"(?i)git\s+(commit|tag|push)")

    def test_pr_validation_is_synthetic_read_only_and_does_not_trigger_monitor_build(self):
        text = (ROOT / ".github/workflows/validate-pr.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:", text)
        self.assertIn("- main", text)
        self.assertIn("contents: read", text)
        self.assertIn("python3 -m unittest discover -s tests -v", text)
        self.assertIn("scripts/test_safe_push.py", text)
        self.assertIn("scripts/test_safe_push_launcher.py", text)
        self.assertIn("scripts/check-publication-privacy.py --tree", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("workflow_dispatch:", text)
        self.assertNotIn("scripts/build-angle-candidate.sh", text)
        self.assertNotIn("ninja", text)

    def test_exact_156_reproduction_entry_is_manual_only(self):
        text = (ROOT / ".github/workflows/reproduce-156.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("schedule:", text)
        self.assertIn("156.0.8078.48", text)
        self.assertIn("d0c02bfad08ec92a6ffcf989e53cd995e6381a4c", text)
        self.assertIn("3b89d84e9d59f75675ac4e2bef58fc068a9f0577", text)
        self.assertIn("--expect-patchset-id metal-family1-v1", text)
        self.assertIn("--expect-patch-sha256 dedac2c57daa69b72fe78bbde443f45d5a6cdfe128d4022049a35c0dbbf501b0", text)
        self.assertIn("--expect-recipe-id macos-x64-metal-v1", text)
        self.assertIn("--expect-recipe-sha256 bea88d9ec894cb1ab875755be52c93b85ed9029d2f00a9f31363123e4d43d7ba", text)
        self.assertIn('inputs["selection_mode"] == "catalog-baseline"', text)

    def test_build_script_gates_unknown_angle_on_fixed_patch_and_policy_tests(self):
        text = (ROOT / "scripts/build-angle-candidate.sh").read_text(encoding="utf-8")
        self.assertIn('"apply","--check"', text)
        self.assertIn('inputs["patch_candidate_status"] == "catalog-match"', text)
        self.assertIn("phase5-metal-family1-native-query-policy.py", text)
        self.assertIn("phase5-metal-family1-math-options-policy.py", text)
        self.assertEqual(text.count('--mtl-utils "$angle_root/src/libANGLE/renderer/metal/mtl_utils.mm"'), 2)
        self.assertIn("phase5-metal-family1-vertex-unpack-policy.py", text)
        self.assertIn('test "$actual_sdk" = "$expected_sdk"', text)


if __name__ == "__main__":
    unittest.main()
