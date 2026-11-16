# Main publication and integration plan

## Current review route

The migration is under review in Draft PR #2, from `migration/angle-maintenance` to `main`. It is based on the reviewed `main` commit `0eb2fcc6323c0ed3c938077bb772e57bc5b880a3`; it does not import the old experiment branch history. The PR already exists and must be updated in place.

The branch was published from an independent local checkout with a dedicated owner-controlled publication guard. The existing experiment checkout and its guard were left unchanged. Local guard paths and contents do not belong in this repository.

For any further branch update:

1. Review the complete local diff and run the documented focused checks.
2. Obtain the owner's explicit approval before creating a commit on `migration/angle-maintenance`.
3. After the commit is reviewable, obtain separate approval before pushing that exact branch update. A push starts the PR-only validation workflow. Do not create a second PR.
4. Keep the PR in draft unless the owner separately approves a ready-for-review change. Do not submit or resolve a GitHub review without approval.
5. Obtain separate approval before integrating into `main`. A squash merge is the proposed method because it keeps the integration linear and the reviewed PR is the unit of history.

No direct commit or push to `main` is allowed. Source removal of obsolete workflows is part of this branch cleanup. Branch-update approval does not authorize PR metadata changes, manual Actions runs, main integration, old-branch cleanup, GitHub-side workflow disablement, old run/artifact deletion, repository settings changes, or external guard changes.

## Publication protections

The published work branch uses the reviewed, dedicated publication route. Keep the canonical repository identity, exact branch restriction, fixed base ancestry, privacy checks, hook integrity, and single-parent history requirements. Do not weaken `.gitignore`, privacy scanners, hooks, or the safe-push launcher. Do not use `--no-verify`, force push, direct-URL push, push-URL overrides, or another guard bypass.

The publication route only authorizes updates to `migration/angle-maintenance`. It does not authorize a direct `main` update. Main integration remains through the Draft PR and requires its own approval.

## PR checks and workflow effects

`validate-pr.yml` runs catalog, unit, synthetic, privacy, and safe-push fixture checks for a PR targeting `main`. It has read-only repository permissions and pinned Actions. It does not run the scheduled monitor, dispatch the reproduction workflow, fetch a full ANGLE checkout, or start the full ANGLE build.

The Stable monitor schedule is guarded to `refs/heads/main`; it does not run from the work branch or its PR. Integration into the default branch activates the six-hour schedule. A later scheduled run can start a macOS ANGLE build if it finds a new fully rolled out Stable release. Include that effect in any PR description update and main-integration approval.

The `reproduce-baseline.yml` workflow is a manual, fixed-input Chrome 156 baseline build. GitHub only accepts `workflow_dispatch` for a workflow file present on the default branch, so this PR's renamed reproduction workflow is not a pre-main build route. If a full build is required before integration, agree on and approve a separate route such as an owner-run local build; do not add a main-branch validation workflow without approval. The state-recovery operation only restores retained state or writes an owner-audited exact-version baseline; it does not build. Do not dispatch, rerun, or cancel Actions without the owner's approval for that specific operation.

## Scope and verification limits

Do not add a project-wide `LICENSE`. Preserve third-party license and notice files, privacy protections, and publication hooks. Do not add a Chrome app, profile, local receipt, signing identity, real-device information, credentials, build logs, or generated binaries to Git, CI, or the PR body.

The PR validation is synthetic. It does not prove a full ANGLE build, Chrome launch, KOOV operation, signing/freeze, Bluetooth/USB behavior, or owner adoption. If a full build is needed before main integration, request approval for the exact workflow, ref, inputs, runner, expected duration, artifact retention, and failure handling. The main-integration decision must summarize the current PR head/base and checks, resolved findings, remaining limits, exact integration commit/method, and schedule activation effect.
