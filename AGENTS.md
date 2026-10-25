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
  retry6 is the next planned user-owned path after approval.

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
modification of saved test outputs or other pre-existing user data; xattr,
codesign, app launches, profiles,
Applications writes, tool installation, authentication, new permissions,
discarding changes, safety-requirement changes, and ambiguous process
termination.

- Preserve the dirty working tree, user changes, and retained retry outputs.
  Never use `git reset --hard`, `git checkout --`, or `git clean`.
- Do not modify or delete retained retry directories or saved test outputs
  unless the task explicitly authorizes that change.
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

## Publication privacy guard

Never commit or publish personal or actual-device data: usernames, home paths,
hostnames, non-loopback IP or MAC addresses, email addresses, serials, UDIDs,
signing team or certificate identities, Keychain ACL or item results, raw
device logs, profiles, cookies, authentication material, passwords or
passphrases, access/refresh/session tokens, API keys or client secrets, private
keys, recovery codes, screenshots, recordings, or device receipts. Apply this
rule to code, configuration, documentation, fixtures, commit messages, and CI
artifacts, logs, and summaries. Do not publish details specific to the owner's
environment, including the target device model. Public upstream
revision pins may be used as technical inputs. Exclude personal and
actual-device data from Git and CI.
Use clearly synthetic placeholders in fixtures; never use real local values in
tests.

Public technical claims should be reproducible from tracked procedures, public
source pins, and synthetic inputs wherever feasible. Include public inputs,
commands or procedure, and expected outcomes. If an end-to-end public
reproduction path is missing, describe the technical gap neutrally and identify
the smallest public input, procedure, or artifact needed to close it, without
pointing to non-public materials. Public documentation must not state or imply
that non-public information exists, or disclose or imply where it is kept.

## Copyright and licensing guard

Before adding a file to a public candidate, identify who created it or where it
came from. This applies to source code and patches (including copied upstream
context), documentation and quotations or translations, images, fonts, audio,
video, fixtures, generated outputs, binaries, and bundled dependencies. Public
availability, a synthetic label, missing metadata, or running a generator does
not establish redistribution rights. Do not treat the repository's lack of a
selected project-wide license as permission to reuse project material, and do
not add or change a project-wide license without owner approval.

For third-party or derived material, record the source URL and immutable
revision or version, a content hash where practical, copyright holder, license
or other permission, modifications, required attribution, and any required
LICENSE or NOTICE files. Confirm the terms cover the intended public
redistribution and modifications. For generated assets, record the source
inputs and generator/tool version and options, and verify rights for both the
inputs and outputs. Track relevant patent, codec, and trademark conditions
separately from copyright permission.
Do not include video files in a push unless their copyright and redistribution
license are confirmed; exclude files with unknown or incomplete rights.

Open-source material is acceptable when its applicable license permits the
intended use and redistribution and all license obligations are met. Include
required copyright notices, attribution, license texts, source code or source
offers, and other conditions for the distribution form. A license for one
component does not license unrelated files or the project as a whole.

If authorship, provenance, or redistribution rights are unknown or incomplete,
hold the file out of the public candidate until verified. Preserve required
notices; do not remove them to make publication appear clear.

Before commit or publication, inspect the staged diff and artifact paths,
confirm Git author and committer names use the public account alias and emails
use GitHub noreply addresses, and run `python3 scripts/check-publication-privacy.py`
after staging. The checker reads the
index by default and supports committed snapshots with `--tree REF`. The
commit-message hook checks proposed messages. The pre-push hook scans all
commits introduced by a ref update, not only its tip tree. Do not merge or
repush pre-cleanup history even if the tip is clean.
For a new remote branch it scans the full reachable local history. If history
must be replaced, prepare and review a fresh clean checkout while preserving
any prior user data through an owner-approved process; never rewrite history
or discard user data without explicit owner approval.
Review findings without
echoing matched values. Do not add broad exclusions or allowlists to bypass
the guard. The focused scanner recognizes selected token and private-key
formats and owner-supplied deny values; it cannot guarantee detection of
arbitrary passwords, tokens, or other secrets. Manual staged-content review is
still required. Audit maintained documentation links and repository SHA
references against public source pins and run records; use current source-tree
counterparts where appropriate, and distinguish them from refs actually
executed by old runs. Do not publish owner-specific metadata. The parent
independently reviews staged content before publication.

## Authorized branch publication policy

On 2026-10-20 the Owner approved the following public-anchor policy. Pin the
approved public anchor to `49b69c78861750b34ec533dfaa1fdbe3469fe9f2`; both the
remote tip and candidate must descend from it, and every reachable commit
after it must have exactly one parent. Reject every post-anchor merge. Permit
only a fast-forward update
of the existing `phase5-page-recovery` branch in the designated repository.
Do not create branches/tags, delete refs, force push, or import Git data
outside the checked public ancestry. These checks are limited to ancestry from
the fixed approved anchor and do not make broader claims about history.

Keep ordinary origin pushes disabled permanently. Publish only through the
reviewed, integrity-checked launcher and reviewed hook wrappers installed in a
durable owner-only directory outside public Git, as described in
`docs/safe-push-and-gc-procedure.md`. Missing or corrupt guard files must
prevent invoking push. Existing staged, message, and introduced-
commit privacy checks and parent review remain required. Limit changes to the
designated branch; do not alter unrelated Git configuration, delete refs, or
run GC in this scope.
