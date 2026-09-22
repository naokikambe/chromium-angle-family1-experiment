# Orchestrator Handoff

## Governance Contract

- The Human is Owner/Approver; the parent is Orchestrator/Reviewer; Luna is
  Implementer. The Human communicates only with the parent. The parent manages
  Luna directly through bounded subagent tasks, and Luna reports only to the
  parent.
- The parent plans, assigns, tracks, independently reviews actual diffs and
  verification, gives corrections, and decides commit/device readiness. Only
  one Luna runs at a time; a healthy Luna is reused, while an interrupted,
  ended, unresponsive, or unrecoverable Luna may be replaced without human
  approval.
- A brief must identify repository, branch, HEAD, dirty and preserved state,
  reading list, allowed files, purpose, requirements, completion criteria,
  fixtures, validation, forbidden operations, commit/push and device
  prohibitions, and report format.
- Luna stays within the brief, never self-approves, starts subagents, commits,
  pushes, merges, opens GitHub Issues or pull requests, runs Actions, or uses
  real Chrome, artifacts, retries, xattrs, codesign, Chrome/GPU Helper, KOOV,
  or profiles. Ordinary fixes, fixture failures, documentation gaps, and
  diagnostics are IN PROGRESS or CHANGES REQUIRED, not BLOCKED.
- BLOCKED requires a human approval boundary, auth/permissions, unavailable
  external dependency, unsafe integration, required human design choice,
  exhausted safe diagnostics, or material state mismatch. Safe investigation,
  bounded diagnostics, edits, static checks, and verified fixture-child
  termination are autonomous. Human approval remains required for commits,
  publication/Actions, real-device or artifact/retry work, test-copy and
  evidence changes, xattr/codesign/app/profile operations, installation,
  authentication, new permissions, discarding changes, safety-rule changes,
  and ambiguous process termination.
- Precedence is system/runtime safety, current Human instruction, `AGENTS.md`,
  parent task, handoff/status documents, other docs, then inference. Preserve
  dirty worktrees and retained retry/evidence; public docs contain no local
  absolute paths, user names, machine output, credentials, or other secrets.

## Current State

- Working branch: `phase3-dynamic-angle-prep`.
- The Phase 3B Libraries implementation is committed on
  `phase3-dynamic-angle-prep`; track the active checkpoint from branch HEAD.
- Chrome target: `154.0.8037.45`; Chromium revision:
  `731082f0a26ce4b3976c3d82943092f5d13daf13`.
- ANGLE revision: `72b8f72a7587ec776d7d2a57d275a6e9b1781b1d`.
- depot_tools revision: `0306e4682b4ac35287c726fa35a983157a625902`.
- Successful artifact: `angle-macos-x86_64-chrome-154.0.8037.45-angle-72b8f72a-35515036255`.
- Phase 3B Libraries validation preserves the verified Chrome baseline and
  adds exactly the two top-level ANGLE dylibs. The manifest schema is v4 and
  recursively records directories, files, and symlinks without following them.

## Outstanding Work

1. Parent reviews the Libraries inventory implementation, workflow, and
   fixture coverage.
2. The complete synthetic fixture suite is accepted only from the pinned
   macos-15-intel GitHub Actions workflow; local full-suite execution is not
   evidence.
3. Parent may checkpoint/fix-commit and push this branch, then dispatch and
   monitor CI. Main/other branches, force/rebase/merge/tag/release, PR/issue,
   and real-device or retry operations remain prohibited.

CI retains runner/environment information, repository state, fixture
stdout/stderr, exit status, and the diagnostics index. Formal acceptance
requires CI job success, fixture exit `0`, passing static checks and
`git diff --check`, no skipped required fixtures, and no unexpected
diagnostics. A CI failure is handled by parent log/artifact review and
classification, bounded Luna correction, parent review/static checks,
checkpoint commit/push, and a new run; only one clearly transient
runner/service failure may justify a rerun. Main and real-device operations
remain approval boundaries. Retry3 is a saved failure/no-operation record.

Phase 3C adds a bounded preflight script and synthetic CI fixture. It gates a
clean expected branch, non-symlink user-owned inputs, Chrome version and
x86_64 source, source-process absence, pinned artifact revision and hashes,
new safe output/results paths, and collisions/retry paths. It records
read-only inspection/signature evidence, prepares once, validates manifest and
inventories, and invokes signing only as `--dry-run`. The one retry4 preflight
stopped during prepare because its directory entry could not be represented by
the then-current inventory schema; no ANGLE dylib or manifest was completed and
sign dry-run was not reached. Retry4 is retained and not reused; retry6 is the
next planned path. Real signing, Chrome, and KOOV were not performed. The
retained retry5 reporting discrepancy is labeled `inconsistent-reporting-preserved`;
its saved evidence records successful copy-before components, unsigned preparation,
manifest v4/inventories, and sign dry-run. It is evidence only, not a signing or
reuse authorization.
The initial Phase 3C CI failure was a synthetic fixture path-role mismatch:
read-only source validation incorrectly rejected an existing source under
`/Applications`. That rule is corrected while writable output/results remain
forbidden there; any real preflight requires renewed human review and approval.

## Safety Boundary

- Never alter source Chrome, retained retry directories, saved evidence, or
  downloaded artifacts.
- Do not run GitHub Actions, create a test app, modify xattrs, sign code,
  launch Chrome/GPU Helper/KOOV, or access a Chrome profile without explicit
  human approval.
- Keep local paths, user-specific data, and device evidence out of public
  documentation and commits.
- Use one `luna_implementer` task at a time. The parent must inspect every
  resulting diff and rerun proportionate verification before approval.
