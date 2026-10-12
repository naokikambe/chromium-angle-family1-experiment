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
