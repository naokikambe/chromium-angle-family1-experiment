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
- Baseline commit before the current uncommitted Phase 3B Libraries work:
  `9bd2b7c74868ae3acbec543205026baddea60c23`.
- Chrome target: `154.0.8037.45`; Chromium revision:
  `731082f0a26ce4b3976c3d82943092f5d13daf13`.
- ANGLE revision: `72b8f72a7587ec776d7d2a57d275a6e9b1781b1d`.
- depot_tools revision: `0306e4682b4ac35287c726fa35a983157a625902`.
- Successful artifact: `angle-macos-x86_64-chrome-154.0.8037.45-angle-72b8f72a-35515036255`.
- Current uncommitted work changes Phase 3B Libraries validation from an
  ANGLE-only directory assumption to a verified Chrome baseline plus exactly
  the two ANGLE dylibs.

## Outstanding Work

1. Parent reviews the current Libraries inventory implementation and fixture
   coverage.
2. After code review approval, the implementer updates Phase 3 documentation
   for manifest schema v3 and the baseline-plus-ANGLE inventory model.
3. Parent reviews the documentation and requests explicit human approval
   before any commit, push, signing, or real-device retry.

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
