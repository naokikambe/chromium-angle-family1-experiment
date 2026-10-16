# Vertex input diagnosis at the pinned ANGLE revision

Use the 22-stage diagnostic runner on an unchanged, hash-verified candidate. This
is a decision guide, not device acceptance. Match pixels, GL errors, actual context
attributes, owner GUI observations, and custom-library/Metal samples to the same
trial and GPU process. Keep all device evidence private.

The source input is ANGLE `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`.
[`VertexArrayMtl::setupDraw` and attribute synchronization](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/src/libANGLE/renderer/metal/VertexArrayMtl.mm)
select different descriptors for disabled constant attributes and enabled buffer
attributes. Enabled attributes bind the current Metal buffer with its offset,
format, stride, and per-vertex step function. Attribute synchronization can choose
conversion when the intended and actual format differ or offset/stride alignment
requires it. A constant point therefore does not verify VBO fetch.

[`BufferMtl`](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/src/libANGLE/renderer/metal/BufferMtl.mm)
allocates storage and handles uploads, shadow data, and synchronization.
`bufferData(size)` plus `bufferSubData` is an API comparison; it does not guarantee
a distinct Metal storage mode. Do not infer an internal path from the API name.

| Diagnostic result | Next boundary to inspect |
| --- | --- |
| Clear/readback fails | Framebuffer, render pass, synchronization, or readback; do not infer vertex failure |
| Single-sample constant point succeeds but both VBO points fail | Enabled attribute descriptor, buffer upload/binding, format conversion, or vertex fetch |
| Packed and interleaved VBO points differ | Recorded stride/offset and source conversion conditions; confirm buffer bounds before changing code |
| A single VBO point succeeds but a three-point draw using the same in-clip vec2 buffer fails | Compare `POINTS` draws with `first=0`, `1`, and `2`, each with `count=1`; read both each intended vertex center and the corresponding x position on the NDC `y=0` centerline. An index-specific failure narrows the boundary to that selected vertex or position; centerline-only pixels suggest a vertical fetch/transform discrepancy; individual successes with a failing multi-point draw leave count-dependent submission/state as a candidate. |
| VBO points succeed but triangles fail | Primitive assembly, translated position, clipping, culling, rasterization, or triangle pipeline state |
| vec4/stride16 succeeds while vec2 fails | Format/component expansion and descriptor differences; shader translation remains a hypothesis |
| In-clip triangle succeeds while oversized triangle fails | Clip-space transformation and triangle clipping; verify winding and reset state |
| Subdata path differs | Upload/storage/synchronization differences; inspect actual native path before assigning cause |
| Only antialias-disabled context succeeds | Sample/render-pass/resolve paths are candidates; normal-context acceptance remains required |

Multiple failures can coexist. Missing observations, context loss, skipped stages,
or a timeout do not select a cause. Nonzero color is not an exact readback pass;
compare expected RGBA and coverage. Verify shader compile/link, active attribute
location, enabled/size/type/normalized/stride/buffer-match/offset, upload size,
draw issuance, and bounded errors before interpreting a pixel difference.

If device results justify native instrumentation, scope it to the first failing
boundary in the pinned source, retain default and Family 2 behavior, and validate
the patch and fixed build inputs. Any changed dylib requires a new completely
unsigned official app copy, assembly, and first signing. Preserve the prior
candidate. Do not dispatch an old workflow or rebuild solely because a diagnostic
kit has been prepared. KOOV starts only after the normal-context draw/readback and
page/Keychain/cookie acceptance conditions have passed.
