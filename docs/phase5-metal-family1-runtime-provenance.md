# Chrome Stable 156 Family 1 runtime patch provenance

This patch targets the ANGLE revision pinned by Chrome Stable 156.0.8078.48:

- Chromium source tag: `156.0.8078.48`
- Chromium source commit: `d0c02bfad08ec92a6ffcf989e53cd995e6381a4c`
- ANGLE revision from that tag's `DEPS`: `3b89d84e9d59f75675ac4e2bef58fc068a9f0577`
- Runtime patch SHA-256: `dedac2c57daa69b72fe78bbde443f45d5a6cdfe128d4022049a35c0dbbf501b0`

The patch is derived from the public [ANGLE repository](https://github.com/google/angle) at the immutable ANGLE revision above. The source-file Git blob IDs at that revision are:

| Source file | Blob ID |
| --- | --- |
| `src/common/apple_platform_utils.mm` | `635abb6f2f9040e6efa8488beac7ebf0822a6906` |
| `src/libANGLE/renderer/metal/mtl_utils.mm` | `6912d1cf0d70fc483a49815be223b7c8f5f7a7b3` |
| `src/libANGLE/renderer/metal/ShaderMtl.mm` | `5fb6ca47c0979ebfd58f4bb6c206f3e683aeaffb` |
| `src/compiler/translator/msl/EmitMetal.cpp` | `b7aa310e48414e89d912d7c1c886549947a5983b` |
| `include/GLSLANG/ShaderLang.h` | `e59c7e773209f35d4422b9d7051b1df595a2750b` |

The changes add an explicit opt-in path for native Mac GPU Family 1, retain the normal Family 2 and default behavior, select a legacy Metal math-options fallback only for the opted-in Family 1 path, and emit a scalar vertex-stage `unpackSnorm4x8` compatibility helper. The original copyright and license notices in all changed ANGLE source files are preserved.

ANGLE's upstream [`LICENSE` at the pinned revision](https://github.com/google/angle/blob/3b89d84e9d59f75675ac4e2bef58fc068a9f0577/LICENSE) is included in this repository as [`licenses/ANGLE-LICENSE.txt`](../licenses/ANGLE-LICENSE.txt). Its Git blob ID is `0f65fd60fd68d465a2283378849f16532f5ee4f1`; SHA-256: `bf4da21bd20bcfb5b60b7ecc67fa864a79be049e21d6178076887f178dd6c71a`. The runtime build artifact must also include that license and all applicable upstream `LICENSE`/`NOTICE` files, as well as the patch and its source revision. This provenance record does not grant rights to Chrome binaries or unrelated project material.
