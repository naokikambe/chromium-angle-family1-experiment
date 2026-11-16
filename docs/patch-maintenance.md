# Patch maintenance and provenance

The Family 1 runtime patch is [`patches/metal-family1-v1/runtime.patch`](../patches/metal-family1-v1/runtime.patch). Its exact SHA-256, five ordered source paths, and baseline source blob IDs are in [`catalog/patchsets/metal-family1-v1.json`](../catalog/patchsets/metal-family1-v1.json). The Chrome 156 source entry binds the baseline patchset ID and blob hash directly. `candidate_for_new_angle` selects a patchset for unregistered ANGLE candidates; it does not select the known 156 patchset. The patch remains one file and is not split during this migration.

Likewise, Chrome 156 is bound to recipe `macos-x64-metal-v1` and its build-recipe digest. That digest is the SHA-256 of canonical JSON with only the `candidate_default` selector removed, so changing which recipe is the default for unregistered versions does not invalidate or replace the baseline. The 156 reproduction workflow also checks the exact bound IDs and hashes. To test an alternate recipe or patchset for a known version, supply both IDs explicitly; the result is classified as a trial, not as baseline reproduction.

For Chrome Stable 156.0.8078.48, Chromium commit `d0c02bfad08ec92a6ffcf989e53cd995e6381a4c` pins ANGLE `3b89d84e9d59f75675ac4e2bef58fc068a9f0577`. The changes narrowly add an explicit native Mac Family 1 opt-in, preserve the ordinary and Family 2 path, use a legacy Metal math-option fallback only for the opted-in case, and emit a scalar vertex-stage `unpackSnorm4x8` helper for that path. Existing ANGLE source copyright and license notices remain in upstream source.

The patch’s origin is the public ANGLE repository at the pinned revision. The source blobs are recorded so the known baseline can be checked. For newer ANGLE, source blob differences are expected; the selected candidate patch must still apply cleanly and pass all focused policy tests. Changing the unregistered-version patch default does not change the 156 binding. A new incompatibility requires a separately reviewed patch update and new source/provenance mapping. Automation never edits the patch.

The upstream ANGLE license is kept at [`licenses/ANGLE-LICENSE.txt`](../licenses/ANGLE-LICENSE.txt). It covers the upstream ANGLE material under its terms and is not a license grant for the repository as a whole. The artifact includes upstream license and notice files from the checked-out source. No root `LICENSE` is added.

Useful immutable references:

- [ANGLE source at the 156 pin](https://github.com/google/angle/tree/3b89d84e9d59f75675ac4e2bef58fc068a9f0577)
- [ANGLE license at the 156 pin](https://github.com/google/angle/blob/3b89d84e9d59f75675ac4e2bef58fc068a9f0577/LICENSE)
- [Chromium 156 tag](https://chromium.googlesource.com/chromium/src/+/refs/tags/156.0.8078.48)
- [Chromium 156 DEPS](https://chromium.googlesource.com/chromium/src/+/d0c02bfad08ec92a6ffcf989e53cd995e6381a4c/DEPS)
