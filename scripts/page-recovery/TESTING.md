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

## Continuation handoff verification (2026-10-12)

- The `cc49dd9` portable suite was independently checked in the cloud: 11 tests
  passed. This is a script verification result, not device rendering evidence.
- The continuation update changes documentation only. Checked 23 local Markdown
  links and 14 shell blocks in six documents, and reviewed the authorization
  response observations and root-cause completion criteria.
- The handoff notes that `probe.py` captures document/image evidence before its
  GUI observation delay; response-after-delay experiments need fresh observations.
- Device-specific measurements remain in the local investigation report.
