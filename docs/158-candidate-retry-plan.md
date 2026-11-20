# Chrome 158 candidate and explicit retry plan

## State retrieval prerequisite added 2026-11-20

The latest scheduled run is `44611811768` (run number 3, workflow revision `84594c238ae9e55285caf153f5af9772a1067a26`). It failed in `Detect a new fully rolled out Mac Stable release`; source resolution, checkpoint, build, and upload steps were skipped, and the run has no artifacts. Its log reports a generic `GitHub Actions API request failed` and does not identify the failing endpoint.

The most recent saved state is still artifact `14508194597` from run `44480771895`, with the two checkpoints listed below. It remains unexpired. Since run `44611811768` saved no state or checkpoint, the reader skips it and falls back to the state from run `44480771895`. That state records `CI_BUILD_FAILED`, `last_detected_version=158.0.8127.37`, and the pinned Chromium/ANGLE revisions below.

An independent read-only reproduction found that the current artifact client sends its GitHub API Bearer header on the cross-origin redirect to the signed artifact-storage URL: downloading the state ZIP through that path returns HTTP 401. A test request to the same redirect without GitHub credentials returned HTTP 200 with a 976-byte ZIP. The saved state was not changed. The generic run log alone cannot attribute its API failure to this redirect, but the next explicit retry needs this saved state and will encounter the defect unless the reader is fixed.

Before authorizing the retry, the fixed reader must pass the redirect regression tests and a read-only state-load preflight against the retained artifact. Confirm the preflight returns the recorded failed 158 attempt and exact source pins; do not begin a retry, recover/reset state, or rewrite `last_detected_version` during this check. If the retained state cannot be read, stop and keep the state artifacts for diagnosis.

## Recorded failure

The Stable monitor run `44480771895` completed as a failure on workflow revision `84594c238ae9e55285caf153f5af9772a1067a26`. The live run and job records show that the build step stopped at `patch-and-function-checks` during `git apply --check`; the candidate upload was skipped. The retained `stable-monitor-state` artifact records `CI_BUILD_FAILED`, `last_detected_version=158.0.8127.37`, and the resolved source pins below. Its artifact ID is `14508194597`, with pre-build and resolved checkpoints `14507983612` and `14507964810`. No successful ANGLE build artifact exists for this run.

The exact source is Chrome `158.0.8127.37`, Chromium `b8c2be851f62f6a394ec57955d7f31335d7cb6d4`, and ANGLE `1f6526a566c27c7c33aa73a78517450a4a2a1714`. The patch selection was `metal-family1-v1` and recipe `macos-x64-metal-v1`, with mode `new-revision-candidate`. The corrected candidate defaults are `metal-family1-158-v1` and `macos-x64-metal-158-v1`; the resolver must still report `new-revision-candidate`, never `catalog-baseline`, for Chrome 158.

## Dispatch to approve after publication and main integration

The workflow only runs build jobs for `refs/heads/main`, and GitHub dispatches a workflow file from the default branch. After the fix is reviewed and integrated, record the exact `main` SHA that contains the new catalog and code, then use:

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

This is one new, explicit workflow run. Do not rerun run `44480771895`, delete the recorded state/checkpoints, lower `last_detected_version`, or replace the pins. On failure, retain the new run's checkpoints and final state, inspect the failed job and exact `failure_stage`, and leave the version marked failed/interrupted for diagnosis. The schedule will not automatically retry this version. Any further attempt requires a separate explicit approval and a new dispatch. An expired success uses `reacquire_expired_artifact`, not this retry operation.

This plan does not authorize dispatch, rerun, commit, push, PR creation/editing, or main integration.
