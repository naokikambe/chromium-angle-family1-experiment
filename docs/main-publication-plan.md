# Main publication plan

## Branch and review route

The migration candidate is based on the reviewed `main` base `0eb2fcc6323c0ed3c938077bb772e57bc5b880a3` and is prepared on the dedicated branch `migration/angle-maintenance`. The source worktree on `phase5-page-recovery` remains separate. The candidate does not merge or import that experiment history.

Publication is limited to this route:

1. Review the complete local diff, run the documented local checks, and request separate approval before creating a commit on `migration/angle-maintenance`.
2. After commit, report its ID, exact publication checks, and the CI events that the branch push and Draft PR will start. Ask for a second approval covering both the branch push and creation of a **Draft PR targeting `main`**.
3. Review the Draft PR and its PR-only synthetic validation results. Do not auto-merge.
4. Ask separately before integrating into `main`. A squash merge is the proposed option because it keeps the integration linear and makes the reviewed PR the unit of history.

There is no direct commit or push to `main`. The commit and branch publication approvals do not include main integration, old-branch cleanup, legacy workflow shutdown, repository settings, or external guard changes.

## Publication guard boundary

The installed owner-controlled guard is bound to the older `phase5-page-recovery` branch and its fixed anchor. The candidate remote push URL remains `disabled://phase5-safety-repair-required`; checked-in privacy checks, hooks, and safe-push scripts remain unchanged. This existing setup does not authorize publication of the new branch.

A separate review and approval is required for this narrowly scoped external guard update before any branch push. The proposed guard behavior is:

- Keep the canonical fetch URL, owner-only guard directory, hook integrity checks, prohibited-path rules, history privacy scan, and staged-content privacy scan.
- Allow only `refs/heads/migration/angle-maintenance`; reject `refs/heads/main`, all other branches, tags, deletions, multiple refs, force options, and direct-URL publication.
- For the first remote ref creation, require the local branch to descend from the exact base `0eb2fcc6323c0ed3c938077bb772e57bc5b880a3`. Require single-parent commits from that base and scan the complete added history for privacy violations. Do not auto-advance or infer a replacement base.
- For later updates, require the current remote work-branch tip to be an ancestor of the candidate tip. Keep the same ancestry, parent-count, privacy, and ref-name checks.
- Explicitly refuse a direct `main` push even if the work-branch checks pass. A reviewed Draft PR is the only proposed integration route.
- Keep the disabled push URL until the owner separately approves the exact external guard and local Git-config change. Do not install or modify that guard in this migration.

Do not use `--no-verify`, force push, an alternate URL, or ordinary push-URL reconfiguration to bypass the existing guard. If a local hook blocks an operation, stop and report it.

## PR validation and workflow effects

The PR validation workflow runs catalog, unit, static, privacy, and safe-push fixture checks on a PR targeting `main`, with read-only repository permissions and pinned Actions. It does not run the scheduled monitor, dispatch the reproduction workflow, fetch a full ANGLE checkout, or start the costly ANGLE build.

The Stable monitor schedule is guarded to `refs/heads/main`. It will not run from the dedicated branch or its PR. A separately approved squash integration into the default branch activates the six-hour schedule, which may later start a macOS ANGLE build when an eligible Stable release appears. The PR title/body and every push approval must state this effect.

The manual state-recovery operation only restores retained state or writes an owner-audited exact-version baseline. It does not build. Actions must not be manually dispatched during this migration.

## Candidate scope and verification limits

No project-wide `LICENSE` is added. Existing third-party license and notice files, privacy protections, and publication hook files remain unchanged. No Chrome app, profile, local receipt, signing identity, real-device information, credentials, build log, or generated binary belongs in Git, CI, or the PR body.

Before requesting commit approval, the handoff must list the branch, base, exact diff scope, regression results, privacy/license/guard checks, unrun ANGLE build and Actions work, residual risks, proposed commit message, and Draft PR title/body. Test count alone is not evidence that a real Chrome, KOOV, Metal, Bluetooth, USB, or device workflow has been accepted.
