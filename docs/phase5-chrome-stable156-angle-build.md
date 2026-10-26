# Chrome Stable 156 + Family 1 ANGLE build candidate

This candidate prepares only the ANGLE dynamic libraries. It does not download, modify, sign, or bundle Chrome. Chrome Stable 156.0.8078.48 is the versioned compatibility target identified for this build design; recheck the current Mac Stable release before running it because Stable rolls forward.

The Chrome source tag `156.0.8078.48` resolves to Chromium commit `d0c02bfad08ec92a6ffcf989e53cd995e6381a4c`. Its [`DEPS`](https://chromium.googlesource.com/chromium/src/+/d0c02bfad08ec92a6ffcf989e53cd995e6381a4c/DEPS) pins ANGLE revision `3b89d84e9d59f75675ac4e2bef58fc068a9f0577`. The runtime workflow fetches these immutable commits and checks the Chrome version and ANGLE `DEPS` entry before applying the patch.

The patch is limited to five ANGLE source files. It adds a fail-closed native Mac Family 1 opt-in, retains the default and Family 2 path, adds a compatibility fallback for older Metal math-option selectors on opted-in Family 1, and uses scalar GLSL-compatible `unpackSnorm4x8` emission for vertex shaders on that same path. It does not claim support for other GPU families or establish full ES3 conformance. Source URLs, blob IDs, patch hash, and license handling are recorded in [patch provenance](phase5-metal-family1-runtime-provenance.md).

The workflow is designed for the x86_64 `macos-15-intel` runner with Xcode 16.4, macOS SDK 15.5, macOS 13.0 deployment target, Metal enabled, GL/Vulkan/SwiftShader disabled, and `libEGL` / `libGLESv2` as the only Ninja targets. Xcode 16.4 and SDK 15.5 match the previously validated hosted build toolchain; the workflow fails early if that exact Xcode and Metal compiler are unavailable. The pinned depot_tools revision is `0306e4682b4ac35287c726fa35a983157a625902`.

The artifact is unsigned and must remain marked `RUNTIME_DEVICE_READY=false`. The manifest records Chrome and ANGLE source pins, patch and GN hashes, actual toolchain versions, and library hashes. The repository includes the upstream ANGLE license at [`licenses/ANGLE-LICENSE.txt`](../licenses/ANGLE-LICENSE.txt), and the workflow copies it plus applicable source `LICENSE` / `NOTICE` files into the artifact. It uses read-only repository permission and retains artifacts for 14 days.

Local source-application checks, three focused synthetic Family 1 policy tests, the offline MSL helper compile, the workflow static audit, YAML parsing, and syntax checks for embedded shell blocks pass. The full ANGLE build has not run. No Chrome bundle, Metal runtime loading, WebGL rendering, video playback, KOOV operation, or hardware acceptance is implied by these static checks.

If a later approved Chrome experiment uses this build, its ANGLE-specific runtime inputs are `ANGLE_PHASE5_ENABLE_METAL_FAMILY1=1` and `--disable-angle-features=requireGpuFamily2`. The ANGLE build alone does not verify that the selected Stable bundle loads these libraries or that its video and 3D behavior passes acceptance.
