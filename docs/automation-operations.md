# Automation operations

## Scheduled monitor

`.github/workflows/watch-chrome-stable.yml` checks every six hours on `main`. A newly published Stable version is fetched from its exact Chromium version tag and checked against `chrome/VERSION` and `DEPS`. The workflow resolves a known version's exact baseline binding or the unique defaults for an unregistered version, then applies the selected patch, runs focused tests, verifies the pinned Xcode/SDK recipe, builds ANGLE, and stores a verified candidate. Normal runs need no local machine, login, response, or device.

The workflow has `contents:read` and `actions:read`; source checkout credentials are not persisted. It creates no commit, catalog change, PR, issue, tag, release, notification, or device evidence. It serializes monitor runs. A detected candidate is attempted once; failures are recorded without automatic retry.

## State and recovery

The rolling state and version index are JSON in the `stable-monitor-state` Actions artifact. Its exact archive member is `stable-monitor-state.json`; it is refreshed at the end of each monitor run and retained for 90 days. The candidate package is a separate Actions artifact, also retained for 90 days.

Before source resolution or any candidate build, the monitor uploads `stable-monitor-checkpoint-<run-id>` with the same `stable-monitor-state.json` member. After the exact Chromium/ANGLE pins and current patch/recipe inputs are recorded, it uploads `stable-monitor-resolved-checkpoint-<run-id>` before building. Source resolution and build steps require the pre-build checkpoint; the build also requires the resolved-input checkpoint. Therefore a run without the first checkpoint could not have started source resolution or a build. If a completed run has no final state but has a valid checkpoint, the reader restores the newest available checkpoint and changes its pending attempt to `CI_BUILD_INTERRUPTED`. The checkpoint already advanced `last_detected_version` for a newly detected release, so it is not automatically rebuilt or marked successful. A checkpoint expiry, malformed archive, or invalid schema fails closed.

If the latest run has neither final state nor checkpoint, the reader can use the previous valid state because that run was gated from building. It continues across runs without either artifact until it finds a valid final state or checkpoint. If the recorded artifact is expired, unreadable, or all saved states are missing, normal monitoring stops with `state-lost`; it never silently returns to the 156 baseline.

The first run can initialize the 156 baseline when the workflow has no prior completed runs and no state artifacts. This does not depend on the workflow file’s commit date, so PR review delay cannot close an initial time window.

For explicit recovery, manually dispatch `watch-chrome-stable.yml` with `operation=recover_state`. The recovery job does not resolve source or build ANGLE. It restores the latest retained state/checkpoint and writes an audit record. If no state can be recovered, the owner must enter the exact last processed Chrome version and a generic lowercase reason slug such as `owner-confirmed-history-loss`; do not enter personal, device, or local details. The job writes a `STATE_RECOVERY_AUDIT` record and saves the state artifact without building. That explicit version prevents future candidate duplication below the recovered point. State-recovery dispatch requires separate owner approval.

Local `match` and `fetch` use the same final state artifact contract and require a successful, unexpired indexed record whose live artifact metadata, run ID, build key, exact Chrome version, architecture, manifest, and hashes agree.

Two manual operations handle different cases:

- `operation=reacquire_expired_artifact` with `reacquire_version` selects a prior successful exact-version record whose artifact is no longer available. It uses that success record's Chromium and ANGLE pins. It does not claim bit-for-bit restoration of expired bytes.
- `operation=retry_failed_version` with `retry_failed_version` selects only the latest `CI_BUILD_FAILED` or `CI_BUILD_INTERRUPTED` attempt for the exact version. It creates a new run record and never rolls back `last_detected_version` or rewrites prior state. The new run records the failed run ID and stage, exact source pins, patch and recipe identifiers/hashes, selection mode, workflow revision, and build key. When prior source pins exist, the exact Chromium tag must resolve to those same pins or the retry stops. If no source pins were recorded because source resolution did not finish, the dispatch also requires `confirm_unpinned_retry=true`; the new run then records that it resolved the exact version tag afresh. Patch or recipe changes are allowed only through the current reviewed repository inputs and are listed as retry input changes.

Neither operation runs automatically. A retry is one explicit new workflow run, not a retry loop. Re-dispatching the same run ID is rejected. A later failed retry may be retried only through another explicit dispatch, and an expired successful artifact stays on the separate re-acquire path.

For the recorded Chrome 158 failure (`44480771895`), use the separate approval plan in [`158-candidate-retry-plan.md`](158-candidate-retry-plan.md) after the fix is published and available on `main`. Dispatch `watch-chrome-stable.yml` on `main` with `operation=retry_failed_version`, `retry_failed_version=158.0.8127.37`, and `confirm_unpinned_retry=false`. The workflow must resolve Chromium `b8c2be851f62f6a394ec57955d7f31335d7cb6d4` and ANGLE `1f6526a566c27c7c33aa73a78517450a4a2a1714` or stop. Do not rerun the historical failed run; a rerun and a new audited retry are different operations.

## PR validation and activation

`validate-pr.yml` runs read-only catalog, unit, synthetic, privacy, and safe-push fixture checks against the proposed merge with `main`. For same-repository PRs, success gates a two-version matrix of full ANGLE builds (156 and 158), each with the same pinned toolchain and shared build/verification entrypoint as the monitor. Inspect the synthetic job and both matrix jobs. A skipped build or a pass on an older head/base is not current full-build acceptance. Fork PRs receive only the synthetic checks.

PR builds do not trigger the monitor, update state/index, or retry the recorded failed version. Their outputs are marked PR-only, retain merge provenance, and expire in seven days. The workflow has no push, schedule, or dispatch trigger. A PR update automatically starts these checks and can consume two macOS build jobs, each up to 240 minutes. The recorded 45–150-minute estimate per 158 build remains unmeasured. The branch's PR does not activate the scheduled monitor.

The schedule becomes active only after separately approved integration into the default branch. A squash merge is the proposed linear-history method. Publishing to `main` can later start a macOS build when a new fully rolled out Stable version appears, so this side effect must be stated in the Draft PR and integration approval. The `reproduce-baseline.yml` workflow and all manual dispatches remain owner-approved actions.

This branch removes obsolete workflow source files and their dedicated helpers. It does not disable workflows registered from `main` or delete old runs, artifacts, or other-branch copies. Repository administration, workflow retention settings, and the external publication guard are unchanged. See the [publication plan](main-publication-plan.md) and [build retention](build-and-artifacts.md).
