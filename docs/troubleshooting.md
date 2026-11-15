# Troubleshooting

| Status or failure | Meaning | Next step |
| --- | --- | --- |
| `NO_NEW_FULLY_ROLLED_OUT_STABLE` | No Mac Stable release above the saved baseline has explicit 100% rollout | Keep the state artifact; the next scheduled scan checks again. |
| VersionHistory payload has no fraction | Full rollout cannot be established safely | Check the official API response and update the selector only after review. |
| Chromium tag missing or `chrome/VERSION` differs | Release metadata and source tag do not agree | Record the failure; do not build from `main` or another tag. |
| Known Chrome mapping differs from fetched source | Catalog and upstream source disagree | Stop and review the mapping; automation does not rewrite catalog. |
| Patch does not apply, paths differ, source blobs differ, or policy test fails | Candidate source is not covered by the reviewed patch | Preserve the failure record; prepare a reviewed patch update. Do not reduce checks. |
| Xcode/SDK differs | Hosted runner no longer matches the fixed recipe | Review and update the recipe explicitly. |
| `CI_BUILD_FAILED` | The recorded stage failed before artifact publication | Inspect the public workflow result; synthetic tests and CI build are distinct from device acceptance. |
| `CI_BUILD_INTERRUPTED` | A run ended after its checkpoint without writing final state | Review the recorded run/stage; use `operation=retry_failed_version` with the exact version to start one explicit new attempt after fixing the cause. |
| Failed exact version is skipped by monitor | `last_detected_version` already advanced when that version was first detected | Do not reset state. Select the latest failed/interrupted version in an explicit retry dispatch; if that attempt has no source pins, explicitly confirm resolving the same Chrome tag afresh. |
| Retry stops on changed source pins | The exact Chrome version tag resolves to a different Chromium or ANGLE revision than the prior recorded attempt | The observed pins are recorded separately and no build starts. Do not substitute them silently; review the source/tag history and decide on a separately reviewed recovery path. |
| `state-lost` | A completed monitor run has no matching readable state artifact | Stop automation and restore/review state; do not silently reset baseline. |
| Local exact match is missing | No indexed successful artifact exists for the exact version/architecture | Stop; do not use a close or latest version. |
| Artifact expired or missing | Actions retention ended or artifact was removed | For a prior successful indexed build, use `operation=reacquire_expired_artifact` with its exact version; this remains separate from a failed-build retry. |
| ZIP path, symlink, hash, source, or license check fails | Download is unsafe or metadata disagrees | Partial extraction is removed; do not prepare a copy. |
| Bluetooth string missing | Launcher template or copied app plist is incomplete | Repair the reviewed template/generator and regenerate a fresh copy before signing. |
| Code signing fails | Identity, nested code, or local policy did not accept the signing plan | Keep the copy for owner inspection; do not alter Keychain or security policy automatically. |
| Strict signature/hash check fails after launcher or prepare | The copy changed after signing or files do not match | Rebuild a fresh copy from the verified artifact and follow launcher-before-sign order. |
| Runtime library or device behavior fails | CI compatibility does not imply runtime support | Keep adoption pending; owner investigates the selected Chrome/OS/device and retains private evidence locally. |
