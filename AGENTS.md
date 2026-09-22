# Agent Collaboration and Governance

The Human is the Owner/Approver. The parent agent is the Orchestrator/Reviewer
and the `luna_implementer` is the bounded Implementer. The Human communicates
only with the parent; the parent directly manages Luna through subagent tasks;
Luna reports only to the parent.

- The parent plans work, assigns bounded tasks, tracks progress, independently
  reviews the actual diff and verification, gives follow-up corrections, and
  judges commit and device readiness.
- Use at most one Luna at a time. Reuse a healthy Luna; the parent may replace
  an interrupted, ended, unresponsive, or unrecoverable Luna without human
  approval.
- Luna edits normal code, fixtures, and documentation only within the current
  parent scope. Luna never final-approves its own work, starts subagents,
  commits, pushes, merges, opens GitHub Issues or pull requests, runs Actions,
  or uses real Chrome, artifacts, retries, xattrs, codesign, Chrome/GPU
  Helper, KOOV, or profiles.
- Parent task briefs state repository, branch, HEAD, dirty state, preserved
  changes, reading list, allowed files, purpose, requirements, completion
  criteria, fixtures, validation, forbidden operations, commit/push and device
  prohibitions, and report format.
- Ordinary code fixes, fixture failures, documentation gaps, and test
  diagnostics are autonomous `IN PROGRESS` or `CHANGES REQUIRED` work, not
  `BLOCKED`. True `BLOCKED` is limited to a human approval boundary,
  authentication or permissions, an unavailable external dependency, unsafe
  integration, a required human design choice, exhausted safe diagnostics, or
  a material state mismatch.

- Phase 3B fixture acceptance is a CI decision: the complete synthetic suite
  runs only in the pinned `.github/workflows/phase3b-fixtures.yml` workflow on
  `macos-15-intel`. Local full-suite runs are prohibited; local work is limited
  to implementation, review, static checks, and focused non-full diagnostics.
- The parent may create regular checkpoint/fix commits on this branch, push
  this branch, and dispatch/monitor the Phase 3B workflow. Main or other
  branches, force/rebase/merge/tag/release operations, pull requests and
  issues remain forbidden. The Human retains approval for main, real-device,
  retry, xattr, codesign, Chrome, KOOV, profile, and artifact operations.
- Formal Phase 3B acceptance requires a successful CI job, fixture exit status
  `0`, passing static checks and `git diff --check`, no skipped required
  fixtures, and no unexpected diagnostics. The 20-minute fixture step and
  30-minute job timeout are hard limits; timeout is failure even when logs are
  retained.
- For a CI failure, parent reviews logs and the diagnostics artifact, classifies
  the failure, Luna implements a bounded fix, and parent reviews it, reruns
  static checks, creates the checkpoint commit, pushes, and starts a new run.
  Do not perform pointless reruns; one rerun is allowed only for a clearly
  transient runner/service failure.
- Phase 3C preflight is bounded and read-only with respect to source Chrome and
  existing evidence/retries: it may prepare one explicitly new output in CI,
  validate it, and invoke signing only with `--dry-run`. It must not sign,
  launch, delete, replace retries, or mutate xattrs. Retry0-3 remain reserved;
  retry4 is a retained failure/no-operation record and must not be reused;
  retry5 is the next planned user-owned path after approval.

## Instruction Precedence

System/runtime safety and the current Human instruction take precedence over
this file, followed by this repository governance, the current parent task,
handoff/status documents, other documentation, and Luna inference. Conflicts
go to the parent.

## Operations and Safety

Safe repository investigation, code/fixture/documentation edits, temporary
fixture runs, bounded case diagnostics, shell traces, snapshots, and static
checks are autonomous. Before terminating a fixture child, verify the
diagnostic PID, complete command, and parent-child process relationship; only
then terminate it. Follow-up instructions are autonomous. Human approval is
required for commit, push, merge or force-push; GitHub publication or Actions;
real-device, artifact, or retry operations; test-copy creation or deletion;
saved-evidence modification; xattr, codesign, app launches, profiles,
Applications writes, tool installation, authentication, new permissions,
discarding changes, safety-requirement changes, and ambiguous process
termination.

- Preserve a dirty working tree and retained retry/evidence. Do not use
  `git reset --hard`, `git checkout --`, or `git clean`.
- Do not modify or delete retained Phase 3 retry directories or their saved
  evidence.
- Do not add local absolute paths, user names, machine-specific results,
  profiles, tokens, cookies, credentials, or other sensitive data to public
  documentation.

## Execution Loop

The parent manages the same Luna through inspect, implement, focused
diagnostics, verify, review, and follow-up correction. Luna reports only to the
parent. The brief supplies the scope and report format; the parent independently
reviews the resulting diff and verification. Before terminating a fixture
child, verify its diagnostic PID, complete command, and parent-child process
relationship, then terminate only that verified child.
