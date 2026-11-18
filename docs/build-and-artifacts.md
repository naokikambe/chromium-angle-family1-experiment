# Build and artifacts

## Pinned recipe

The initial recipe targets macOS x86_64 on `macos-15-intel`, Xcode 16.4, macOS SDK 15.5, and deployment target 13.0. It checks out the exact Chromium `DEPS` ANGLE commit and the pinned `depot_tools` commit. The GN file comes from the catalog; Ninja builds only `libEGL` and `libGLESv2`. A runner image or Xcode/SDK drift stops the job instead of silently changing the recipe.

Before GN/Ninja, the job resolves the exact patchset/recipe binding for a known Chrome version or the unique candidate defaults for an unregistered version. It applies the selected patch, verifies the expected source blobs for the known baseline, checks patch paths/order, and runs three focused synthetic C++ policy tests on the actual patched sources. These tests do not launch Metal or claim device support.

## Artifact contents

A successful artifact contains the two top-level dylibs, the unchanged `runtime-patch.diff`, `LICENSE`, collected upstream `LICENSE*`/`NOTICE*` files, `args.gn`, `ANGLE_REVISION`, build environment data, `file`/`lipo`/`otool`/`codesign` verification reports, library checksums, `ANGLE_ARTIFACT_MANIFEST.json`, and its SHA-256 file. The manifest binds Chrome, Chromium, ANGLE, patch ID/hash, recipe ID/hash, the `selection_mode`, workflow revision, depot_tools, actual toolchain, GN args, library hashes, license hashes, inspection-report hashes, run ID, artifact name, and the not-assessed compatibility/adoption state. The `angle-build-key-v2` fingerprint includes the selected source, patch, recipe, selection mode, and workflow commit.

The binary verifier requires thin x86_64 Mach-O files, the catalog deployment target, no test-only symbols, and unsigned libraries. A separate manifest verifier checks exact version, architecture, build key, source pins, file hashes, and license presence. No generated library or archive is added to Git.

## Retention and search

The candidate ZIP and `stable-monitor-state` index are GitHub Actions artifacts retained for 90 days. The index is refreshed after each scheduled run and includes exact Chrome version, platform, architecture, source/patch/recipe/toolchain/library hashes, run ID, artifact ID, status, creation time, and expiry. Cache is not the index. The read-only monitor API needs `actions:read`; it also needs repository `contents:read`. Upload uses the workflow’s artifact mechanism and does not grant source write permission.

After expiry, the local tool refuses the artifact. The owner can manually request a rebuild for the exact indexed version; that is a new candidate with a new ID and hashes. For long-term preservation, the owner downloads and retains a verified artifact outside GitHub Actions and outside the repository. There is no automatic Release or long-term cloud store in this initial design.

The repository contains the upstream ANGLE license for the source used here. Each artifact carries the source license and discovered notices. This does not create a project-wide license or expand ANGLE’s terms to unrelated material.
