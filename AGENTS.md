# Repository working rules

This repository maintains exact-version macOS ANGLE build candidates for Chrome Stable.

- Keep source pins, catalog files, patches, manifests, licenses, and tests aligned. Never relax patch, binary, privacy, or license checks to make a candidate pass.
- Treat CI build success as a candidate only. Do not infer Chrome runtime compatibility, device support, or owner adoption from a build or synthetic test.
- Keep local Chrome bundles, profiles, downloaded artifacts, signing identity data, logs, receipts, and device evidence outside tracked source. Do not send them to CI.
- Use synthetic fixtures for automated tests. A task that requires a real browser, device, account, Keychain, signature, Bluetooth, or USB operation belongs to the owner.
- Do not run GitHub Actions manually unless the owner approves that specific run. A new schedule in the default branch starts on publication and must be described before push approval.
- Work on the dedicated `migration/angle-maintenance` branch based on the reviewed `main` tip. Do not commit or push directly to `main`; main integration is through a reviewed PR and separate approval.
- Do not commit without explicit owner approval. After a commit, request a separate approval before pushing the exact work branch. This migration branch already has Draft PR #2 targeting `main`; update that PR rather than creating a duplicate. A PR status or metadata change still needs separate approval.
- Do not use `--no-verify`, force push, direct-URL push, push-URL override, or other guard bypasses. If the existing external guard does not allow the new work branch, stop and request separate review of the exact guard change.
- Preserve `.gitignore`, publication privacy checks, hooks, and safe-push behavior. Ask for separate review before changing an installed external guard or GitHub repository settings.
- Run focused syntax, static, and synthetic checks for changed code. Do not claim an Actions build or real-device acceptance unless it was actually run by the owner.
