# Chrome 156 baseline

This versioned baseline preserves the five source inputs used by the Family 1 patch candidate:

| Input | Value |
| --- | --- |
| Chrome Stable | `156.0.8078.48` |
| Chromium source tag | `156.0.8078.48` |
| Chromium commit | `d0c02bfad08ec92a6ffcf989e53cd995e6381a4c` |
| ANGLE commit from Chromium `DEPS` | `3b89d84e9d59f75675ac4e2bef58fc068a9f0577` |
| Bound patchset | `metal-family1-v1` |
| Patch | `patches/metal-family1-v1/runtime.patch` |
| Patch SHA-256 | `dedac2c57daa69b72fe78bbde443f45d5a6cdfe128d4022049a35c0dbbf501b0` |
| Bound recipe | `macos-x64-metal-v1` |
| Build-recipe SHA-256 | `bea88d9ec894cb1ab875755be52c93b85ed9029d2f00a9f31363123e4d43d7ba` |
| depot_tools | `0306e4682b4ac35287c726fa35a983157a625902` |
| Runner / architecture | `macos-15-intel` / x86_64 |
| Xcode / SDK | 16.4 / 15.5 |
| Deployment target | macOS 13.0 |
| Ninja targets | `libEGL`, `libGLESv2` |

GN settings and blob IDs are in [`catalog/recipes/macos-x64-metal-v1.json`](../catalog/recipes/macos-x64-metal-v1.json) and [`catalog/patchsets/metal-family1-v1.json`](../catalog/patchsets/metal-family1-v1.json). The Chrome catalog entry binds these IDs and hashes to the exact source pins. The recipe digest covers its canonical JSON after removing only `candidate_default`; changing that new-version selection flag does not change the baseline build recipe digest. The [baseline reproduction workflow](../.github/workflows/reproduce-baseline.yml) asserts the exact patchset, patch hash, recipe, recipe hash, and `catalog-baseline` selection mode before building.

Unregistered Chrome/ANGLE versions still use the uniquely designated candidate patchset and default recipe. Passing explicit patchset and recipe IDs for Chrome 156 creates an `explicit-known-version-trial`; it is not recorded as reproduction of this baseline.

The original maintenance migration added the reproduction entrypoint but did not run it. This document does not establish whether a later run completed; check the exact Actions run and revision for build evidence. CI completion does not establish runtime or device acceptance.
