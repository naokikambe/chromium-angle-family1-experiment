# Stable update policy

## Release detection

The scheduled monitor queries Chrome VersionHistory for `platforms/mac/channels/stable`, requests currently serving releases, and accepts only a four-component numeric version with a serving start time, no end time, and an explicit rollout fraction of `1.0`. Missing or partial rollout information fails closed. It does not treat a Chromium `main` update or a tag appearance alone as a Stable release.

For the selected version the workflow fetches the exact same-named Chromium tag from `https://chromium.googlesource.com/chromium/src.git`. It checks that `chrome/VERSION` matches the Stable version, records the fetched commit, and reads the single full `angle_revision` in that commit’s `DEPS`. A known catalog mapping must match exactly and uses the patchset/recipe IDs and hashes bound in its Chrome source record. A new Chrome/ANGLE mapping is a candidate and does not write to the catalog; it uses exactly one designated candidate patchset and default recipe. Missing or ambiguous choices stop the run instead of falling back to file order or another version’s binding.

## Patch and unknown ANGLE behavior

The reviewed patch remains byte-for-byte fixed for a given patchset. The 156 reproduction workflow also locks its expected patchset/hash and recipe/hash and asserts `catalog-baseline`, so changes to new-version defaults cannot alter it. For the known 156 source, the workflow checks its five source blob IDs. For an unlisted ANGLE revision it checks the selected patch hash, ordered paths, clean application, and the focused native-family, math-option, and vertex-unpack synthetic tests against the patched source. Only a candidate passing all checks proceeds to build. Explicit alternate inputs for a known Chrome version are recorded as a trial. Any incompatibility is recorded as failure; there is no automatic patch edit, check weakening, or repeated retry.

A patch/test/build failure advances the detected-version state and stops that candidate. An owner can inspect the indexed failure and decide whether to prepare a reviewed patch/catalog change. A manual re-acquire run is available only for an exact previously successful version whose artifact is expired or missing; it verifies the public release tag and original source pins before rebuilding. It creates a new run, artifact ID, and hashes; it does not claim to restore the same expired bytes.

## Candidate and adoption states

CI success means only that the candidate libraries were built, licensed, hashed, and passed the defined binary checks. It does not certify Metal runtime behavior, any device family, Chrome loading, WebGL or video behavior, KOOV operation, or owner adoption. Those are owner-controlled acceptance steps.
