# Main publication and integration plan

## Current state

PR #2 was merged into `main` at `84594c238ae9e55285caf153f5af9772a1067a26`. The Chrome 158 patch work is prepared on the new local branch `migration/angle158-metal-family1`, based on that exact commit. The earlier `migration/angle-maintenance` branch and its history remain intact.

The publication route previously reviewed for `migration/angle-maintenance` does not authorize a new branch. Review the exact new branch against the current `main` and obtain a separate publication-guard decision before any push. Do not update PR #2, create another PR, or change the guard as part of this preparation. The work is currently staged for review; no commit, push, PR operation, or Actions dispatch has been performed.

For a later publication:

1. Review the full staged snapshot and its focused checks.
2. Obtain explicit approval before creating the commit.
3. Obtain a separate guard review and approval to push the exact new branch. If the installed guard rejects the branch, stop; do not bypass or modify it.
4. After a reviewable push, create or update a PR only with separate approval. State that merging the change to `main` changes the defaults for unregistered Chrome/ANGLE candidates while leaving the fixed Chrome 156 binding intact.
5. Obtain separate approval before integration into `main`. The monitor schedule runs only from `main`; integration can therefore activate a future Stable build.

No direct commit or push to `main` is allowed. Commit approval does not authorize push, PR creation or editing, Actions dispatch/rerun/cancel, main integration, branch cleanup, old run/artifact deletion, repository setting changes, or external guard changes.

## Publication protections

Preserve the canonical repository identity, approved branch restriction, fixed base ancestry, privacy checks, hook integrity, and single-parent history requirements. Do not weaken `.gitignore`, privacy scanners, hooks, or the safe-push launcher. Do not use `--no-verify`, force push, direct-URL push, push-URL overrides, or another guard bypass.

The earlier publication route authorized only `migration/angle-maintenance`. A new route for `migration/angle158-metal-family1` requires its own review. Main integration remains through a reviewed PR and its separate approval.

## Workflow effects

`validate-pr.yml` runs catalog, unit, synthetic, privacy, and safe-push fixture checks for a PR targeting `main`. It has read-only repository permissions and pinned Actions. It does not run the Stable monitor, dispatch the fixed 156 reproduction workflow, fetch a full ANGLE checkout, or start the full ANGLE build.

The Stable monitor schedule is guarded to `refs/heads/main`; it does not run from the work branch or its PR. Integrating this change updates the candidate defaults. A later scheduled run can start a macOS ANGLE build when it finds a newly detected fully rolled out Stable version.

The `reproduce-baseline.yml` workflow is a manual, fixed-input Chrome 156 baseline build. The retry for Chrome 158 is a separate `retry_failed_version` dispatch and requires the fixed update on `main`. Its exact approval inputs and failure handling are documented in [`158-candidate-retry-plan.md`](158-candidate-retry-plan.md). Do not rerun the historical failed run as a substitute. Do not dispatch, rerun, or cancel Actions without specific approval.

## Scope and verification limits

Preserve ANGLE's upstream license and notices, privacy protections, and publication hooks. Do not add a project-wide `LICENSE`, Chrome app, profile, local receipt, signing identity, device information, credentials, build logs, or generated binaries to Git, CI, or a PR body.

Catalog, patch application, source-policy harnesses, and synthetic tests do not prove a full ANGLE build, Chrome launch, KOOV operation, signing/freeze, Bluetooth/USB behavior, or owner adoption. The local machine has Xcode 16.4 and SDK 15.5 on x86_64, but about 20 GiB free; this request does not run a full local build. The retry plan uses the pinned `macos-15-intel` runner with the workflow's 240-minute timeout. The main-integration decision must summarize the then-current PR head/base and checks, resolved findings, remaining limits, exact integration commit/method, and schedule activation effect.
