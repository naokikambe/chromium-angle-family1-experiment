# Phase 3D: macOS VM observability boundary

更新日: 2026-09-29

Phase 3D is a GitHub-hosted macOS Intel observation stage.  It is deliberately
separate from the user-owned-device Phase 3C and Case B/C procedures.  It does
not authorize a local Chrome launch, modify `/Applications`, use a signing
identity, or test Bluetooth, USB, KOOV, or a normal browsing profile.

## Primary record

The parent-verified public GitHub Actions metadata and read-only diagnostics
artifact review record a successful Phase 3D dynamic ANGLE VM observation run.
The review also verifies the selected release manifest, artifact identity, and
ANGLE revision listed below; it does not merge the separate 3B/3C diagnostics
artifacts into this record.

| 項目 | 記録 |
| --- | --- |
| run | `36071196477` / success |
| commit | `e9002f5ba7f70ec6b23f6b82453c9580a33a399b` |
| artifact | `phase3d-dynamic-angle-36065655290-36071196477`（未期限） / archive SHA-256 `8f142e7503555fe3d9a75f0716daf8777509b28089e17b1bb4a8cfef7aabe298` |
| 一次記録 | [GitHub Actions run](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36071196477) |
| release manifest | schema `angle-release-v1` / Chrome `154.0.8037.57` / SHA-256 `ed01fc7c8a1634193cebc7e016be2fddd4a1d0094e7a77abdc98798d6b078c4f` / sidecar validation success |
| 選択ANGLE artifact | `angle-macos-x86_64-chrome-154.0.8037.57-angle-1ff8799c-36065655290` / build run `36065655290` |
| ANGLE revision | `1ff8799c596d4fc9acea28343610b1f33650a6fa` |

同じ確認で、Phase 3B synthetic fixture run `36241793357` とPhase 3C
synthetic preflight fixture run `36241795968` も成功として記録されている。
それぞれのdiagnostics artifactは
`phase3b-synthetic-fixture-diagnostics-36241793357` と
`phase3c-preflight-synthetic-diagnostics-36241795968` であり、Phase 3D
artifactと同一物とは扱わない。3B diagnostics archiveのSHA-256は
`2299e7085280d7ef80bec61f4f4a0d3de26cef8a1e7680eb3f633b4e4646ccab`、3Cは
`d33c4e301f023ce9870e2a8faba139fb9415c5109aca9584d080ad661ac9ec03`であり、
それぞれのfixture exit statusは`0`である。

この成功runは、当時の実機作業、署名、ローカルChrome起動、artifact取得・置換を
承認するものではない。Phase 5 implementationと専用stub CIは、Phase 5
planに定めた3B/3C/3D run、manifest SHA-256、artifact名、ANGLE revision等の
詳細なadmission recordを前提に完了した。専用CI run `36432392861`は成功し、
`angle-metal-family1-test-stub-36432392861`（schema
`phase5-metal-family1-test-stub-v1`）でtargeted EGL test 4件がすべて成功した。
これはcompile-time test-only profileの検証であり、後続のruntime artifact/VM観測とは
別の記録である。後続のHuman承認によりruntime artifact `36501314503`を入力にした
Phase 3D run `36507728136`も成功したが、署名・実機起動・KOOV操作は行っていない。
VM観測の成功もIntel HD Graphics 5000での実機成功を意味しない。

## Phase 5 runtime artifact observation record

The following record uses the runtime artifact produced by Phase 5 CI rather than the
historical release artifact above.

| 項目 | 記録 |
| --- | --- |
| observation run | [`36507728136`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36507728136) / success / 3m04s |
| observation commit | `73e04a42b0375e06a41b096fa45bd216d0f5abc7` |
| input build run | `36501314503` / runtime artifact `angle-macos-x86_64-chrome-154.0.8037.57-angle-1ff8799c-36501314503` |
| diagnostics artifact | `phase3d-dynamic-angle-36501314503-36507728136` / GitHub digest `sha256:0e313e79fc1d16f76aa4c7cad6b1e65ad349031195e57cfc8f7695060c4f36ea` |
| release manifest | SHA-256 `fc0c39145695fa5501039b7aa1093326aadf7af71022e6b30294f464604dbdc2` / ANGLE `1ff8799c596d4fc9acea28343610b1f33650a6fa` |
| dynamic result | both replacement libraries GPU-correlated dyld-loaded; EGL initialization failure `true`; GPU disabled fallback `true`; probe exit `0` |
| stock control | EGL initialization failure `false`; GPU disabled fallback `true`; comparison `dynamic-angle-differs-from-stock-control` |
| evidence limits | process-map observation `false`; dynamic collector failure count `1`; post-run replacement hashes unchanged |

Interpretation: the runtime artifact reached the observed GPU process through dyld,
but initialization did not reach a usable EGL state in the Apple Paravirtualized
Graphics Device VM. This is a useful load/stop-boundary result, not a rendering
pass and not evidence of Intel HD Graphics 5000 compatibility. WebGL smoke and
user-owned-device/KOOV testing remain separate stages.

## Purpose

The stage answers software-boundary questions that can be collected on a
hosted VM:

- whether Chrome starts and remains alive for the observation period;
- every GPU-process attempt observable through the process sampler or Chrome
  stderr, including short-lived failed attempts;
- child-process command lines, parent relationships, and fallback switches;
- best-effort `lsof` and `vmmap` evidence immediately after a GPU PID is
  detected;
- dyld loader records for the Chrome framework and, when present, replacement
  `libEGL.dylib` and `libGLESv2.dylib`;
- unified logging, code-signing/Gatekeeper state, GPU/display inventory, and
  new crash reports.

The workflow dispatch input is an exact four-component Chrome for Testing
version.  It downloads only the matching official mac-x64 Chrome for Testing
archive and records the archive SHA-256 and bundle version.

## Dynamic ANGLE observation

`.github/workflows/phase3d-dynamic-angle-vm.yml` is the formal replacement
library observation.  Its required input is a successful ANGLE build workflow
run ID.  The workflow downloads that run's artifact, validates
`ANGLE_RELEASE_MANIFEST` and its sidecar, runs the full artifact verifier, and
derives the exact Chrome version from the manifest.  It then downloads the
matching Chrome for Testing bundle; a missing CfT release or any version,
manifest, or dylib hash mismatch is fatal.

Only the extracted, disposable CfT bundle under the runner temporary directory
is modified.  The two verified dylibs are installed into the concrete
`Versions/Current` Framework version after checking that `Current` resolves to
the manifest Chrome version and that neither destination already exists.  No
`/Applications` app, xattr, signing identity, or codesign mutation is used.

The launch adds `--use-gl=angle`, `--use-angle=metal`, and
`--use-dynamic-angle`.  The result distinguishes several boundaries rather
than treating VM rendering as a pass requirement:

- browser command-line receipt of all three requested switches;
- GPU-process receipt of the GL and ANGLE switches;
- exact replacement paths observed by dyld, both globally and correlated to
  an observed GPU PID;
- exact replacement paths observed in best-effort `lsof` or `vmmap` evidence;
- EGL initialization failure and `--use-gl=disabled` fallback.

`DYNAMIC_ANGLE_OUTCOME` summarizes the strongest observed boundary.  In
descending order it reports both replacement libraries loaded by an observed
GPU process, both seen by dyld without GPU attribution, a partial replacement
load, GPU ANGLE flags without a replacement load, browser flags only, or no
observed ANGLE flags.  A negative load observation is not silently converted
into proof that dyld never considered the library.

## Baseline result and interpretation

The first baseline probe used Chrome for Testing 154.0.8037.57 on
`macos-15-intel`.  The runner reported an Apple Paravirtualized Graphics Device
with Metal 2 support, but Chrome's initial GPU processes failed EGL display
initialization and exited.  Chrome then remained alive with a later GPU process
using `--use-gl=disabled`.

This is a VM baseline, not evidence that a replacement ANGLE build is broken.
Consequently, Phase 3D treats successful hardware rendering as an additional
observation, not a required pass condition.  The required outcome is complete,
honestly-labelled evidence showing whether a replacement library was reached
and where initialization stopped.

## Evidence model

`authoritative-result.txt` records both the union of GPU PIDs and the source
counts:

- `GPU_PID_COUNT` is the union of observed GPU PIDs;
- `GPU_PID_COUNT_PROCESS_SAMPLER` comes from command-line process sampling;
- `GPU_PID_COUNT_STDERR` comes from GPU-specific Chrome stderr records.

`gpu-pid-events.tsv` preserves each event and its source.
`gpu-pid-all-sources.tsv` is the deduplicated PID table.  A PID visible only in
stderr is still valid evidence of a short-lived GPU attempt, but is not claimed
to have a captured command line, `lsof`, or `vmmap` record.
`gpu-collector-status.tsv` records each best-effort collector outcome;
`GPU_COLLECTOR_FAILURE_COUNT` reports its non-zero entries without converting a
complete browser/process observation into an infrastructure failure.

For the dynamic workflow, `dynamic-angle-placement.txt` binds the placement to
the release manifest and concrete Framework version.
`replacement-library-inspection.txt` records the installed files' hashes,
Mach-O architecture, dependencies, and read-only signature state.
`replacement-library-post-run.sha256` confirms that Chrome execution did not
mutate either replacement.  `dynamic-angle-evidence.txt` and
`authoritative-result.txt` contain the boundary booleans and summarized
outcome.

The optional `loader_trace` workflow input enables `DYLD_PRINT_LIBRARIES=1` for
the isolated Chrome for Testing launch.  Its output is preserved in
`browser-stderr.txt`; the relevant framework and replacement-library lines are
also copied to `dyld-library-loads.txt`.  Missing loader lines mean only that
this mechanism did not observe a load; they are not proof that a library was
never considered.

## Explicit limits

Phase 3D cannot establish correct real-device rendering, graphics performance,
Bluetooth/USB access, KOOV behavior, or the exact taskgated outcome of a
locally Apple-signed test copy.  Those remain separately approved device-test
questions.  It also cannot guarantee a post-mortem `lsof` or `vmmap` capture
for a process that exits before collection starts; stderr and unified log
records are retained for that case.
