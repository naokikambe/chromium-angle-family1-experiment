# Verification record

The portable suite uses the Python standard library:

```bash
python3 -m unittest -v test_kit.py
```

Coverage includes fixture classification, image validation, mock-browser CDP
lifecycle, signing-plan policy, frozen-file checks, and bundle symlink handling.
The symlink regression verifies that internal links remain valid when the bundle
root is reached through an aliased parent, while external and broken links are
rejected. `sign_once.py` canonicalizes the bundle root before checking resolved
link targets.

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

## Bundled investigation handoff review (2026-10-12)

- Added an investigation-wide delegation boundary, operation conditions,
  result-dependent next steps, bundled owner-input requests, and stopping rules.
- Preserved the existing cause-identification criteria and one-time-response
  consent boundary; this document does not grant new Keychain permissions.
- Checked 11 local Markdown links and 1 bash block in the two updated handoff
  and plan documents; whitespace checks passed. Documentation only.
