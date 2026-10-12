# Phase 5 ANGLE snapshot build

The runtime workflow is pinned to Chromium snapshot 1689422. Chromium source revision `82303c21a18acdc256c6264cd2ed0e1588df99d4` reports version `154.0.8037.0`, and its `DEPS` file pins ANGLE revision `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`. The workflow fetches that Chromium commit directly, checks its version and `DEPS` pin, and then checks out the matching ANGLE commit. The release tag is not used as the source identity.

The runtime patch adds diagnostic markers around renderer availability, Metal initialization, EGL config and context creation, and library loading. It also adds a narrowly scoped Family 1 runtime opt-in in `src/common/apple_platform_utils.mm`. The normal Mac GPU Family 2 check remains the default. Setting `ANGLE_PHASE5_ENABLE_METAL_FAMILY1=1` permits the Mac Family 1 capability check for this experiment; any other value fails closed. Family 2 devices continue through the existing Family 2 path when the variable is set.

The pinned source has a separate `requireGpuFamily2` feature gate in `DisplayMtl::initializeImpl()`. The documented experiment launch option is:

```text
ANGLE_PHASE5_ENABLE_METAL_FAMILY1=1 --disable-angle-features=requireGpuFamily2
```

That feature name exists in this ANGLE revision. `requireMsl21` does not, so the workflow does not pass it. The patch does not force a Metal shading language version; ANGLE retains its existing device and OS selection. This workflow does not establish which language version the target device selects. Other Metal feature checks remain tied to their actual family capability.

The workflow retains its macOS 13.0 deployment target. The new opt-in checks `MTLGPUFamilyMac1` directly and requires Mac Family 1 without Mac Family 2. For a machine rejected by the existing model gate, this is the only condition that permits the experiment to continue; it does not bypass the gate for other unsupported machines. `getMaxSupportedESVersion()` applies the same Family 1 without Family 2 check and returns ES 2.0 for that device. A Mac Family 2 device retains the existing maximum version path. This source boundary does not establish that a device successfully creates a context or renders.

The workflow builds only `libEGL.dylib` and `libGLESv2.dylib` on `macos-15-intel`. It records the Chromium, ANGLE, and depot_tools revisions; the patch and GN argument hashes; the x86_64 target and deployment target; toolchain metadata; and both library hashes. `verify-artifact.sh` checks Mach-O architecture, dependencies, install names, and signature validity. `verify-phase5-runtime-artifact.sh` additionally requires unsigned dylibs and matching source, patch, GN, and library hashes. The manifest records `RUNTIME_DEVICE_READY=false` because this artifact workflow does not validate loading, Metal startup, WebGL, or device rendering.

The snapshot's Chromium GL switches are defined in [`ui/gl/gl_switches.cc`](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/ui/gl/gl_switches.cc): `--use-gl=angle`, `--use-angle=metal`, `--use-dynamic-angle`, and `--disable-angle-features=requireGpuFamily2` are real switches in this source. [`ui/gl/gl_initializer_mac.cc`](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/ui/gl/gl_initializer_mac.cc) resolves dynamic ANGLE libraries under `FrameworkBundlePath()/Libraries`, loading `libGLESv2` before `libEGL`. The cookie runner's explicitly selected Family 1 experiment supplies all four reviewed switches to both launches and sets only `ANGLE_PHASE5_ENABLE_METAL_FAMILY1=1` in each child environment. Its default remains the stock GPU configuration with no ANGLE overrides. This is experiment preparation only; it does not establish runtime acceptance, and it does not select SwiftShader or the null backend.

Source references:

- [Chromium snapshot `chrome/VERSION`](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/chrome/VERSION)
- [Chromium snapshot `DEPS`](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/DEPS)
- [ANGLE `apple_platform_utils.mm`](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/src/common/apple_platform_utils.mm)
- [ANGLE `DisplayMtl.mm`](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/src/libANGLE/renderer/metal/DisplayMtl.mm)
- [ANGLE `mtl_utils.mm`](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/src/libANGLE/renderer/metal/mtl_utils.mm)
