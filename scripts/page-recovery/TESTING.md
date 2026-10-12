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

When `--observe-seconds` is enabled, the probe keeps its original pre-wait
`result.json` and writes a timestamped second sample under
`post-observation/`. This includes document/runtime values, a separate
screenshot and visual patch when available, network response/failure evidence,
and per-step capture errors. `network_events_snapshot_at` records when the
client snapshots the network-event array; it is not an individual event's
receive time. Queued CDP events may have arrived during the wait, so this is
not a precise human-response timestamp. `network_events` contains only the
delta newly appended to the CDP event list after the wait began, and
`http_document_200_event_during_wait` is true only for a document HTTP 200 in
that delta. An empty delta or false value does not imply the full run lacked a
pre-wait HTTP 200. A post-wait capture failure remains diagnostic data and
does not alter the pre-wait classification.

The focused unit tests use a fake CDP client to check separate output,
timestamped evidence, the network-event delta, and continued capture after a
CDP error.
They do not simulate GUI input or establish that an approval prompt was
answered. GUI confirmation, ordinary-Keychain behavior, and product acceptance
remain separate acceptance conditions.
