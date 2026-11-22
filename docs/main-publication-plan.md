# Main publication and integration plan

## Current protections

Start maintenance work from the verified current GitHub `main` tip on a dedicated local branch/worktree. A cached `origin/main` is not proof of the latest remote state. Preserve existing checkouts, branches, workflow runs, artifacts, and evidence.

The existing safe-push document and installed guard define the publication route and restrictions. This plan does not change or extend them. If a reviewed branch is outside the allowed route, stop and request a separate review of a concrete guard change; do not bypass or modify the guard as part of routine work.

The approval boundaries are separate:

1. Explicit owner approval is required before creating a commit.
2. A separate approval is required before pushing the exact reviewed branch, subject to the existing guard.
3. PR creation or editing requires its own approval.
4. Integration into `main` requires a separate approval after the current PR head, base, and required checks have been reviewed.

No direct commit or push to `main` is allowed. Commit approval does not authorize push, PR operations, Actions dispatch/rerun/cancel, main integration, branch cleanup, artifact deletion, repository setting changes, or external guard changes.

## Current workflow effects

`.github/workflows/validate-pr.yml` runs on pull requests targeting `main`. Its read-only synthetic job validates the catalog, unit suite, safe-push fixtures, and privacy scan. For same-repository PRs, that job gates full ANGLE builds for the catalog versions 156 and 158 on `macos-15-intel`, with up to two jobs in parallel and a 240-minute timeout. Fork PRs receive the synthetic job only. Review current results for the exact PR head and base; a stale or skipped build is not full-build acceptance.

The `watch-chrome-stable.yml` schedule runs every six hours only on `main`. Integrating changes can therefore affect future Stable candidate builds. Its manual operations and `reproduce-baseline.yml` dispatch remain owner-approved actions. Do not run, rerun, or cancel Actions without approval for that specific operation.

PR validation artifacts are temporary validation outputs with merge provenance. They are not indexed Stable artifacts and do not establish runtime, device, KOOV, Bluetooth, USB, or owner acceptance. A full CI build is separate from those acceptance decisions.

## Scope and verification

Preserve the existing project license scope, ANGLE and Chromium notices, privacy checks, hooks, safe-push behavior, and prohibited publication targets. Do not add Chrome or KOOV binaries, local profiles, receipts, signing identity data, device evidence, credentials, build logs, or generated test videos to Git, CI, or a PR body.

Before integration, review the exact diff and current workflow effects, including possible schedule activation. Keep synthetic checks, CI builds, owner-run local operations, and real-device acceptance as separate evidence types. See [publication privacy](publication-privacy.md), [safe-push procedure](safe-push-and-gc-procedure.md), and [workflow operations](automation-operations.md).
