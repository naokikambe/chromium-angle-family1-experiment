# Chrome 158 candidate and explicit retry plan

## Current monitor behavior

The historical records below predate the success-watermark and effective-fingerprint state. On the first scheduled run after that change reaches `main`, a schema-v1 failure for 158 has no fingerprint and is therefore kept as `ACTION_REQUIRED`; migration alone does not trigger a retry. The monitor first chooses the newest fully rolled-out Mac Stable above the last formally successful version. If 158 is still the newest eligible release, it is suppressed pending review. If a newer release exists, that newer version can be attempted without being blocked by 158. A normal scheduled attempt after a relevant-input change is limited to once for that new fingerprint. The explicit retry and expired-artifact re-acquire operations remain separate.

## State retrieval prerequisite found before the redirect fix

The latest scheduled run is `44611811768` (run number 3, workflow revision `84594c238ae9e55285caf153f5af9772a1067a26`). It failed in `Detect a new fully rolled out Mac Stable release`; source resolution, checkpoint, build, and upload steps were skipped, and the run has no artifacts. Its log reports a generic `GitHub Actions API request failed` and does not identify the failing endpoint.

The most recent saved state is still artifact `14508194597` from run `44480771895`, with the two checkpoints listed below. It remains unexpired. Since run `44611811768` saved no state or checkpoint, the reader skips it and falls back to the state from run `44480771895`. That state records `CI_BUILD_FAILED`, `last_detected_version=158.0.8127.37`, and the pinned Chromium/ANGLE revisions below.

An independent read-only reproduction found that the current artifact client sends its GitHub API Bearer header on the cross-origin redirect to the signed artifact-storage URL: downloading the state ZIP through that path returns HTTP 401. A test request to the same redirect without GitHub credentials returned HTTP 200 with a 976-byte ZIP. The saved state was not changed. The generic run log alone cannot attribute its API failure to this redirect, but the next explicit retry needs this saved state and will encounter the defect unless the reader is fixed.

At that time, retry approval depended on the redirect regression and a read-only state-load preflight. PR #3 later merged the artifact redirect fix into `main` at `5ba61b9f043905cf0f67ef0449a4781f1bf22055`. This historical finding does not establish that the old artifact IDs are still available or that the failed attempt remains the latest eligible retry. Before any future retry, read the current state with the merged code and verify the latest failed 158 record, source pins, checkpoints, and artifact availability. Do not recover/reset state or rewrite `last_detected_version` as part of that check.

## Recorded failure (historical)

The Stable monitor run `44480771895` completed as a failure on workflow revision `84594c238ae9e55285caf153f5af9772a1067a26`. The live run and job records show that the build step stopped at `patch-and-function-checks` during `git apply --check`; the candidate upload was skipped. The retained `stable-monitor-state` artifact records `CI_BUILD_FAILED`, `last_detected_version=158.0.8127.37`, and the resolved source pins below. Its artifact ID is `14508194597`, with pre-build and resolved checkpoints `14507983612` and `14507964810`. No successful ANGLE build artifact exists for this run.

The exact source is Chrome `158.0.8127.37`, Chromium `b8c2be851f62f6a394ec57955d7f31335d7cb6d4`, and ANGLE `1f6526a566c27c7c33aa73a78517450a4a2a1714`. The patch selection was `metal-family1-v1` and recipe `macos-x64-metal-v1`, with mode `new-revision-candidate`. The corrected candidate defaults are `metal-family1-158-v1` and `macos-x64-metal-158-v1`; the resolver must still report `new-revision-candidate`, never `catalog-baseline`, for Chrome 158.

## Explicit retry on current `main` (owner approval required)

PR #3 was merged at `5ba61b9f043905cf0f67ef0449a4781f1bf22055`. The current `validate-pr.yml` runs synthetic/privacy checks and then exact 156/158 builds for same-repository PRs. Those jobs do not retry a historical failed monitor attempt or update its state. Their seven-day artifacts include PR-only merge provenance and are not formal Stable candidates.

GitHub dispatches a workflow file from the default branch, and the monitor build job runs only on `refs/heads/main`. A dispatch is not authorized by this plan. First confirm the current failed-state record and exact pins; only after separate owner approval for one run, use these inputs on the then-current reviewed `main`:

| Field | Value |
| --- | --- |
| Workflow | `.github/workflows/watch-chrome-stable.yml` (`Watch Chrome Stable ANGLE candidates`) |
| Ref | `main` (`refs/heads/main`) at the reviewed fix commit |
| `operation` | `retry_failed_version` |
| `retry_failed_version` | `158.0.8127.37` |
| `confirm_unpinned_retry` | `false` |
| Other inputs | Empty/default |
| Runner | `macos-15-intel`, x86_64 |
| Recipe toolchain | Xcode 16.4, macOS SDK 15.5, deployment target 13.0 |
| Targets | `libEGL`, `libGLESv2` |
| Workflow timeout | 240 minutes |

Before build, the retry must resolve the same Chromium and ANGLE pins recorded above. The monitor compares them with the failed attempt and stops if either changes. It must record the new workflow revision, patch/recipe IDs and hashes, selection mode, build key, failed run ID, and failure stage. The expected inputs are patchset `metal-family1-158-v1`, patch SHA-256 `5a3956dbc6428cc6afe610b09a99d4eeaadedb6b8ac396e8e6ccd670a2983def`, recipe `macos-x64-metal-158-v1`, recipe digest `99966e8b1bdc647db9be1bf356716ecb0719aa03e151658ffd98e67aea67339a`, and `new-revision-candidate` mode.

The failed run spent about 6½ minutes resolving source and about 4½ minutes fetching dependencies and reaching the patch check; it never reached GN or Ninja. There is no successful 158 build duration to measure. Planning estimate for the corrected full run is 45–150 minutes, with the full 240-minute timeout reserved because dependency and compilation time remain unmeasured.

## Expected retained artifacts

If all checks and both library builds pass, the run should save:

- `stable-monitor-checkpoint-<new-run-id>` and `stable-monitor-resolved-checkpoint-<new-run-id>` for recovery, each with the `stable-monitor-state.json` member.
- `angle-macos-x86_64-chrome-158.0.8127.37-run-<new-run-id>` for 90 days. It contains unsigned `libEGL.dylib` and `libGLESv2.dylib`, the selected runtime patch, upstream ANGLE license/notices, GN arguments, and the verified manifest.
- `stable-monitor-state` for 90 days, with the new retry record and final outcome.

The artifact is only a build candidate. It does not establish Chrome or device compatibility.

## Failure and state handling

This is one new, explicit workflow run. Do not rerun run `44480771895`, delete the recorded state/checkpoints, lower `last_detected_version`, or replace the pins. On failure, retain the new run's checkpoints and final state, inspect the failed job and exact `failure_stage`, and leave the version marked failed/interrupted for diagnosis. Normal monitoring suppresses the same failed fingerprint, allows one attempt for changed relevant inputs, and suppresses that new fingerprint after failure. An expired success uses `reacquire_expired_artifact`, not this retry operation.

This plan does not authorize dispatch, rerun, commit, push, PR creation/editing, or main integration.
