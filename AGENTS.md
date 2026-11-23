# Repository working rules

This repository maintains exact-version macOS ANGLE build candidates for Chrome Stable.

- Keep source pins, catalog files, patches, manifests, licenses, and tests aligned. Never relax patch, binary, privacy, or license checks to make a candidate pass.
- Treat CI build success as a candidate only. Do not infer Chrome runtime compatibility, device support, or owner adoption from a build or synthetic test.
- Keep local Chrome bundles, profiles, downloaded artifacts, signing identity data, logs, receipts, and device evidence outside tracked source. Do not send them to CI.
- Use synthetic fixtures for automated tests. A task that requires a real browser, device, account, Keychain, signature, Bluetooth, or USB operation belongs to the owner.
- Do not run GitHub Actions manually unless the owner approves that specific run. A new schedule in the default branch starts on publication and must be described before push approval.
- Before work, verify the latest GitHub `main` tip instead of assuming a cached `origin/main` is current. Use a dedicated local repair branch/worktree and preserve other checkouts and their changes. Do not reuse completed migration branches or merged PRs.
- Do not commit without explicit owner approval. A separate approval is required to push the exact reviewed branch, create or edit a PR, or integrate into `main`. Never commit or push directly to `main`.
- Do not use `--no-verify`, force push, direct-URL push, push-URL override, or other guard bypasses. If the existing external guard does not allow the new work branch, stop and request separate review of the exact guard change.
- Preserve `.gitignore`, publication privacy checks, hooks, and safe-push behavior. Ask for separate review before changing an installed external guard or GitHub repository settings.
- Run focused syntax, static, and synthetic checks appropriate to changed code. Do not claim an Actions build or real-device acceptance unless it was actually run by the owner.
