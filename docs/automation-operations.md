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

## PR validation and activation

`validate-pr.yml` runs read-only catalog, unit, synthetic, privacy, and safe-push fixture checks for a PR targeting `main`. It does not trigger this monitor, fetch an ANGLE checkout, or run the full ANGLE build. The dedicated migration branch and its Draft PR do not activate the scheduled monitor.

The schedule becomes active only after separately approved integration into the default branch. A squash merge is the proposed linear-history method. Publishing to `main` can later start a macOS build when a new fully rolled out Stable version appears, so this side effect must be stated in the Draft PR and integration approval. The `reproduce-156.yml` workflow and all manual dispatches remain owner-approved actions.

Repository administration settings, workflow retention settings, old workflow cleanup, and the external publication guard are not changed here. See the [publication plan](main-publication-plan.md) and [build retention](build-and-artifacts.md).
