# Verification record

The portable suite uses the Python standard library:

```bash
python3 -m unittest -v test_kit.py
```

Coverage includes fixture classification, image validation, mock-browser CDP
lifecycle, signing-plan policy, frozen-file checks, and bundle symlink handling.
The persistent-cookie runner test verifies that one bounded navigation timeout
is passed to both synthetic launch phases and recorded in context and phase
results; out-of-range values are rejected before host or app inspection and
before output creation. Its loopback fixture regression also verifies that only
the first seed response issues the synthetic cookie, so a restored seed page
cannot reseed a later check that arrives without the cookie.
The symlink regression verifies that internal links remain valid when the bundle
root is reached through an aliased parent, while external and broken links are
rejected. `sign_once.py` canonicalizes the bundle root before checking resolved
link targets.

`python3 -m unittest -v test_webgl1_runner.py` checks synthetic WebGL-state
acceptance and failure cases, the nonce-bound loopback fixture without a browser,
and bounds rejection before GUI-context inspection or output creation. These
tests do not launch Chromium, validate a GPU, or establish Metal library loading.

`python3 -m unittest -v test_webgl1_diagnostic_runner.py` checks the new
diagnostic page's nine fixed stages, raw pre-finish RGB160 readback, WebGL-only
source constraints, context-loss and bounded-state handling, exact nonce/document
validation, diagnostic-only classification, fixture routing, and fresh-output/
timeout guards. It compiles the embedded fixed JavaScript with
`node --check` when Node.js is available. Tests use no browser, app bundle,
profile, or GPU, and do not treat synthetic stage states as acceptance evidence.

The mock browser exercises the probe lifecycle; it is not evidence of Chromium
rendering. GUI confirmation, ordinary-Keychain behavior, and product acceptance
are separate from these portable unit checks. Do not use the diagnostic
`--use-mock-keychain` result as product acceptance.

Reference files and their SHA-256 digests are recorded in
`reference/provenance.json`. The mock browser is tracked executable; tests do
not chmod source files.

## Post-observation samples

When `--observe-seconds` is enabled, the probe retains its pre-wait document
and runtime values in the legacy `result.json` and writes a timestamped second
sample under `post-observation/`. The legacy server-receipt field covers the
whole run, so its classification is not an acceptance result for the post-wait
state. The second sample includes document/runtime values, a separate
screenshot and visual patch when available, network response/failure evidence,
and per-step capture errors. `network_events_snapshot_at` records when the
client snapshots the network-event array; it is not an individual event's
receive time. Queued CDP events may have arrived during the wait, so this is
not a precise human-response timestamp. `network_events` contains only the
delta newly appended to the CDP event list after the wait began, and
`http_document_200_event_during_wait` is true only for a document HTTP 200 in
that delta. An empty delta or false value does not imply the full run lacked a
pre-wait HTTP 200. Post-wait samples remain diagnostic data and do not replace
the document/runtime values used by the legacy classification.

The focused unit tests use a fake CDP client to check separate output,
timestamped evidence, the network-event delta, and continued capture after a
CDP error.
They do not simulate GUI input or establish that an approval prompt was
answered. GUI confirmation, ordinary-Keychain behavior, and product acceptance
remain separate acceptance conditions.

## Replan verification (2026-10-12)

- The revised plan separates current-copy cause identification, ordinary-Keychain
  stock recovery, and subsequent ANGLE/KOOV validation.
- Checked 32 local Markdown links and 11 shell blocks in the six updated
  entry-point/plan documents; staged whitespace checks also passed.
- No executable code changed in this documentation update. The two focused
  post-observation tests at `383310b` passed the previous independent cloud review.
- Normal-Keychain recovery and account/access-policy proposals are planned work,
  not new device findings or authorization to modify existing Keychain items.

## Public-source review (2026-10-12)

- Mapped Apple API, ACL, code-identity, and Keychain-implementation documentation
  to the pinned Chromium source. The source note distinguishes documented
  behavior, code-derived expectations, and device evidence still required.
- Added the item-location/search-list check because another login user does not
  isolate a shared System keychain item.
- Checked 18 local Markdown links and 2 shell blocks in four updated entry-point
  and evidence documents. This update changes documentation only.

## Restart handoff review (2026-10-12)

- Distinguished loopback preparation failure, prelaunch approval-review denial,
  unanswered Keychain prompts, and an actual owner denial response.
- Kept the existing GPU-disabled condition constant for Keychain comparisons;
  normal GPU operation requires a separate comparison.
- Checked 17 local Markdown links and 1 bash block in the three updated handoff,
  plan, and status documents; whitespace checks passed.
- Documentation only: no new device results, permission grants, or code changes.

## Persistent cookie runner (2026-10-12)

- Added a dedicated two-launch runner for one new profile, an HTTP-only synthetic
  persistent cookie, clean browser shutdown/restart, read-only encrypted-value
  metadata, and cookie receipt after restart. It records no cookie values.
- Added focused offline tests for fixture cookie handling and encrypted-storage
  metadata. These tests do not launch Chromium or bind a loopback socket.
- The three focused persistence tests passed; Python syntax compilation and
  `git diff --check` passed. The full suite was not run locally.
- The target Mac run still requires explicit owner authorization and real GUI
  confirmation; unit coverage is not normal-Keychain acceptance.

## Family 1 runner argument boundary (2026-10-13)

- Preserved the stock runner's exact default browser argv and normal GPU path.
- Added an explicit Family 1 experiment option with a fixed four-switch allowlist;
  both launches reuse one recorded argv/environment configuration.
- Rejected unknown or partial browser switches and unexpected opt-in environment
  values before output/profile creation or process launch.
- Focused checks exercise the default command, shared restart configuration, and
  unsafe-argument rejection with a synthetic output path. The two-launch case
  mocks app metadata, server, cookie metadata, and launch phases; it creates no
  real profile and starts no browser.
- Documented the exact fixed-snapshot Chromium switch definitions and dynamic
  library location/order. This does not establish device acceptance.

## Stock preflight follow-up review (2026-10-12)

- Fast-forwarded to `2e70227` and independently passed its three focused
  persistence tests and Python syntax checks in the cloud.
- Updated the handoff to distinguish owner-reported Allow, unobserved API return,
  and a separate unanswered trial. Allow Once does not grant later-process trust.
- Added read-only signature/certificate/search-scope diagnosis before acceptance;
  trust errors do not establish file tampering or a re-signing cause.
- Checked 19 local Markdown links in the three updated plan/status documents;
  whitespace checks passed. No new device trials, Keychain approvals, or trust
  configuration changes were performed by this documentation update.

## Complete device handoff review (2026-10-12)

- Added a single delegation covering stock recovery, DEPS-matched Family 1 ANGLE
  assembly and first signing, WebGL validation, and KOOV software acceptance.
  Explicit stage prerequisites preserve the normal-Keychain acceptance criteria.
- Verified that the existing runtime workflow pins a different input and references
  absent files; located its patch/verifier/static check at fixed history
  `cc781c1063261ffbe227939ff607ecefb51f6b2b` for a future reviewed port.
- Checked 31 local Markdown links and 1 shell block in five updated entry-point
  and handoff documents; whitespace checks passed.
- Documentation only: no workflow dispatch, signing, Keychain changes, new device
  trials, or claims of ANGLE/KOOV acceptance.

## Bundled investigation handoff review (2026-10-12)

- Added an investigation-wide delegation boundary, operation conditions,
  result-dependent next steps, bundled owner-input requests, and stopping rules.
- Preserved the existing cause-identification criteria and one-time-response
  consent boundary; this document does not grant new Keychain permissions.
- Checked 11 local Markdown links and 1 bash block in the two updated handoff
  and plan documents; whitespace checks passed. Documentation only.

## Cause-report intake and stock recovery handoff (2026-10-12)

- Fast-forwarded to device commit `71d5bb1`; independently passed its focused
  startup-wait regression and Python syntax checks in the cloud.
- Recorded the device agent's scoped cause-completion report, distinguishing
  post-denial requests from resumption of an existing request. Device logs and
  owner observations were not independently re-audited from the cloud.
- Added a bundled normal-Keychain stock recovery handoff covering successful key
  access, normal GPU, three fresh profiles with owner observations, and encrypted
  test-cookie persistence after restart. These are future acceptance conditions.
- Checked 33 local Markdown links and 2 shell blocks in five entry-point/plan
  documents; whitespace checks passed. No additional device measurements or
  new owner permission grants were made by this documentation update.
