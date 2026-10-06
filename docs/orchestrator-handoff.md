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

- Track the active branch, HEAD, and dirty state from the current checkout;
  this handoff does not pin a release version or artifact.
- New ANGLE artifacts use `ANGLE_RELEASE_MANIFEST` schema `angle-release-v1`
  with a SHA-256 sidecar. It binds the requested Chrome release to resolved
  Chromium/ANGLE revisions, pinned depot_tools, dylib hashes, artifact identity,
  build run ID, UTC time, and GN-args hash.
- The Chrome `154.0.8037.45` artifact (run `35515036255`) is a legacy record
  without this manifest schema. It must not be implicitly accepted by new
  scripts.
- Libraries validation preserves the verified source baseline and allows only
  the two release-manifest-hash-verified ANGLE dylibs as additions. The active
  Framework version is discovered via `Versions/Current`, not pinned to `.17`
  or `.45`.

### Phase 5 source URLLoader diagnostic latest record (2026-10-06)

- Branch `phase3-dynamic-angle-prep`, HEAD
  `f444054a141b808043b69c6e0bf0ebfb57008dd4`, clean worktree.
- Same-revision source diagnostic run
  [`37464208418`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/37464208418)
  used Chromium `b510e9d7cd3a2fbd78d0ddc42234103206c5f78d`, ANGLE
  `e12217f3e133cb1029b050d893b1806d141483be`, and ANGLE build run
  `37009376538`.
- Static audit, ANGLE preparation, source/dependency checkout, Xcode 16
  compatibility patch, and URLLoader diagnostic patch all succeeded.
- The unbranded `chrome` full build was cancelled by the parent job's
  360-minute limit. No unsigned Chromium bundle was produced and U0/U1
  diagnostics did not run; the build diagnostics artifact was uploaded.
- The log shows `offline mode`, `fastlocal=1->0`, and prolonged
  `localexec/4` waits while compiling roughly 84,000 tasks from an empty
  output directory. This is an execution-throughput/timeout mismatch, not a
  confirmed compiler error.
- Do not repeat the same clean workflow blindly. Candidate remediation is a
  persistent high-performance Intel macOS runner with Siso fast-local or
  remote cache/execution and a revision/GN-args/patch-keyed build cache.
  Smaller diagnostic targets remain exploratory and are not formal Chromium
  comparisons.
- Signing, xattr changes, real-device work, KOOV, and
  `RUNTIME_DEVICE_READY=false` changes remain prohibited/unchanged.

## Outstanding Work

1. Review release-manifest generation/validation, dynamic attempt-root safety,
   Framework current-version policy, and all fixture cases.
2. The complete synthetic fixture suites are accepted only from pinned Phase
   3B/3C GitHub Actions on `macos-15-intel`; local full-suite execution is
   prohibited.
3. CI success is required before asking for human approval of device work, but
   is not itself authorization. Main/other branches, force/rebase/merge/tag/
   release, PR/issue, and real-device/retry operations remain approval gates.

CI retains runner/environment information, repository state, fixture
stdout/stderr, exit status, and the diagnostics index. Formal acceptance
requires CI job success, fixture exit `0`, passing static checks and
`git diff --check`, no skipped required fixtures, and no unexpected
diagnostics. A CI failure is handled by parent log/artifact review and
classification, bounded Luna correction, parent review/static checks,
checkpoint commit/push, and a new run; only one clearly transient
runner/service failure may justify a rerun. Main and real-device operations
remain approval boundaries. Retry3 is a saved failure/no-operation record.

Phase 3C accepts an explicitly selected artifact only when its verified release
manifest exactly matches source Chrome's version. Output and results are direct
children of an unused `attempt-YYYYMMDD-HHMMSS` root; legacy retry0–12 evidence
remains immutable. Preflight records read-only evidence, prepares once, validates
the test-copy manifest/inventories, and calls signing only as `--dry-run`. Real
signing, Chrome, and KOOV require separate human approval.

Step 0 uses `ensure-angle-release-artifact.sh` to read source Chrome's version,
reuse exactly one matching verified cache artifact, or dispatch and wait for the
pinned build workflow before downloading and verifying a new artifact. It never
modifies source Chrome. Dispatch and download are side effects and remain within
an explicit Human-approved Step 0 invocation. Phase 3B CI uses only stubbed GitHub
commands for this path.

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
