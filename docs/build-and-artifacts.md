# Build and artifacts

## Pinned recipe

The initial recipe targets macOS x86_64 on `macos-15-intel`, Xcode 16.4, macOS SDK 15.5, and deployment target 13.0. It checks out the exact Chromium `DEPS` ANGLE commit and the pinned `depot_tools` commit. The GN file comes from the catalog; Ninja builds only `libEGL` and `libGLESv2`. A runner image or Xcode/SDK drift stops the job instead of silently changing the recipe.

Before GN generation and Ninja compilation, the job resolves the exact patchset/recipe binding for a known Chrome version or the unique candidate defaults for an unregistered version. It applies the selected patch, verifies source blobs when the input is the patchset's exact mapped ANGLE revision, checks patch paths/order, and runs three focused source-policy harnesses against the patched sources. They compile extracted policy logic and include an offline MSL helper check; they do not compile ANGLE, launch a Metal device, or claim device support.

After checking out the recipe's exact `depot_tools` revision, the common build path runs that checkout's `ensure_bootstrap` with `DEPOT_TOOLS_DIR`, `DEPOT_TOOLS_BOOTSTRAP_PYTHON3=1`, and `DEPOT_TOOLS_UPDATE=0`. It checks the Git revision before and after bootstrap, requires the generated `python3_bin_reldir.txt` and its in-checkout Python binary, and validates only the dedicated Python before starting ANGLE setup. After `gclient sync`, while inside the pinned ANGLE checkout, it requires the ANGLE DEPS tools at `buildtools/mac/gn` and `third_party/ninja/ninja`, rejects non-Mach-O or non-x86_64 executables, and runs those exact files directly. This avoids depot_tools wrapper fallbacks. The artifact records their relative paths and versions, and its manifest uses the ANGLE Ninja version from that record. Bootstrap, dependency-tool validation, GN generation, and Ninja compilation have distinct failure stages. Bootstrap initializes local packages; it does not move the pinned Git checkout.

## Pre-merge build validation

`validate-pr.yml` checks the GitHub-generated merge commit for the PR and its current `main` base. After synthetic/privacy checks pass, same-repository PRs build both catalog versions `156.0.8078.48` and `158.0.8127.37` on `macos-15-intel`, at most two jobs in parallel, each with a 240-minute timeout. Fork PRs run the synthetic job only; a skipped build is not full-build acceptance.

`prepare-pr-angle-inputs.py` fetches the real Chromium version tag, verifies its VERSION/DEPS and catalog pins, and requires a patch/recipe mapped to that exact source. The PR, Stable monitor, and manual 156 reproduction all call `build-and-verify-angle.sh` for the same dependency checkout, patch/policy checks, GN/Ninja targets, binary inspection, license assembly, manifest, and hash validation. PR jobs never invoke monitor state operations.

Successful PR outputs use the existing manifest-compatible artifact name and include `PR_VALIDATION.json` recording role, PR number, base/head/merge commits, and merge tree. They are retained for seven days and are not added to the Stable state/index; normal local match/fetch cannot select them. The manifest workflow revision is the tested merge SHA, not the eventual squash commit. These outputs do not become formal Stable artifacts by merging. If `main` changes, validate the new merge result before integration. A successful build does not prove Chrome/GPU/device compatibility or actual scheduled execution.

## Artifact contents

A successful artifact contains the two top-level dylibs, the unchanged `runtime-patch.diff`, `LICENSE`, collected upstream `LICENSE*`/`NOTICE*` files, `args.gn`, `ANGLE_REVISION`, build environment data, `file`/`lipo`/`otool`/`codesign` verification reports, library checksums, `ANGLE_ARTIFACT_MANIFEST.json`, and its SHA-256 file. The manifest binds Chrome, Chromium, ANGLE, patch ID/hash, recipe ID/hash, the `selection_mode`, workflow revision, depot_tools, actual toolchain, GN args, library hashes, license hashes, inspection-report hashes, run ID, artifact name, and the not-assessed compatibility/adoption state. The `angle-build-key-v2` fingerprint includes the selected source, patch, recipe, selection mode, and workflow commit.

The binary verifier requires thin x86_64 Mach-O files, the catalog deployment target, no test-only symbols, and unsigned libraries. A separate manifest verifier checks exact version, architecture, build key, source pins, file hashes, and license presence. No generated library or archive is added to Git.

## Retention and search

The candidate ZIP and `stable-monitor-state` index are GitHub Actions artifacts retained for 90 days. The index is refreshed after each scheduled run and includes exact Chrome version, platform, architecture, source/patch/recipe/toolchain/library hashes, run ID, artifact ID, status, creation time, and expiry. Cache is not the index. The read-only monitor API needs `actions:read`; it also needs repository `contents:read`. Upload uses the workflow’s artifact mechanism and does not grant source write permission.

After expiry, the local tool refuses the artifact. The owner can manually request a rebuild for the exact indexed version; that is a new candidate with a new ID and hashes. For long-term preservation, the owner downloads and retains a verified artifact outside GitHub Actions and outside the repository. There is no automatic Release or long-term cloud store in this initial design.

The repository's [BSD 3-Clause project license](../LICENSE) applies to repository-authored workflow files, scripts, and documentation as scoped in the [README](../README.md). ANGLE remains under its upstream license; each artifact carries the applicable source license and discovered notices. Neither license statement assigns a blanket license to every file in the repository or expands ANGLE's terms to unrelated material.
