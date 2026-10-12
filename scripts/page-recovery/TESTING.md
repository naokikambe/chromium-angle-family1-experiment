# Verification record

- Platform: Linux cloud environment.
- Command from repository root: `python3 -m unittest discover -s scripts/page-recovery -p 'test_kit.py' -v`
- Result: 10 tests passed.
- Compilation: probe.py, sign_once.py, cdp_transport.py passed py_compile.
- CDP lifecycle was tested against mock_browser.py; this is not a Chromium rendering result.
- macOS codesign, a real Chromium executable, and GUI display remain untested.
- Downloaded entitlement sources and license are pinned in reference/provenance.json.
- Repository integration: local Markdown links and pinned reference SHA-256 digests verified.
- The mock browser is tracked executable; verification does not chmod source files.
- Physical-Mac handoff update: checked 12 local Markdown links and shell-block
  syntax in the four updated entry-point documents. No executable code changed;
  the existing portable test result above remains the latest code verification.
- Root-cause completion update: checked 13 local Markdown links and 4 shell
  blocks in the four updated entry-point documents. Reviewed the completion
  criteria, required new evidence for re-signing, and separation of cause
  identification from subsequent ANGLE/KOOV work. Documentation changes only;
  no new device experiment or root-cause finding is claimed.
