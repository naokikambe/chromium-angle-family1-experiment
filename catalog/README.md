# Catalog selection and hashes

The catalog stores exact source mappings and separately identifies defaults for unregistered Chrome/ANGLE revisions. The resolver does not use file order.

## Known Chrome versions

Each `chrome/*.json` entry records the exact Chromium and ANGLE pins plus a `baseline_inputs` object with the required `patchset_id`, `patch_sha256`, `recipe_id`, and `recipe_sha256`. The resolver uses these bindings for known versions and rejects missing, duplicate, inconsistent, or hash-mismatched records.

The patch hash is SHA-256 over the patch file bytes. The recipe hash is SHA-256 over canonical JSON (`sort_keys=True`, compact separators, UTF-8) after removing only `candidate_default`. That field selects a recipe for unregistered versions and does not change the build itself. The recipe ID and every other recipe field remain covered by the digest.

## Unregistered versions and explicit trials

For an unregistered version, exactly one patchset must have `candidate_for_new_angle: true` and exactly one recipe must have `candidate_default: true`. Those two entries must form a consistent source/patch/recipe pair. Zero or multiple choices stop resolution.

An operator may pass both a patchset ID and a recipe ID to run a separate input trial. The manifest and build key label that selection as `explicit-known-version-trial` or `explicit-unlisted-revision-trial`; an explicit trial is not a reproduction of a known baseline. Normal known-version reproduction uses `catalog-baseline`, while automatic new-version candidate builds use `new-revision-candidate`.
