# Phase 3D: macOS VM observability boundary

更新日: 2026-09-26

Phase 3D is a GitHub-hosted macOS Intel observation stage.  It is deliberately
separate from the user-owned-device Phase 3C and Case B/C procedures.  It does
not authorize a local Chrome launch, modify `/Applications`, use a signing
identity, or test Bluetooth, USB, KOOV, or a normal browsing profile.

## Primary record

The parent-verified public GitHub Actions metadata records a successful Phase 3D
dynamic ANGLE VM observation run. This is a run-status record only; it does not
silently add claims about release-manifest contents, artifact contents, or the
ANGLE revision.

| 項目 | 記録 |
| --- | --- |
| run | `36071196477` / success |
| commit | `e9002f5ba7f70ec6b23f6b82453c9580a33a399b` |
| artifact | `phase3d-dynamic-angle-36065655290-36071196477`（未期限） |
| 一次記録 | [GitHub Actions run](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36071196477) |

同じ確認で、Phase 3B synthetic fixture run `36241793357` とPhase 3C
synthetic preflight fixture run `36241795968` も成功として記録されている。
それぞれのdiagnostics artifactは
`phase3b-synthetic-fixture-diagnostics-36241793357` と
`phase3c-preflight-synthetic-diagnostics-36241795968` であり、Phase 3D
artifactと同一物とは扱わない。release-manifest SHA-256、artifact内容、
artifactのANGLE revisionはこのmetadata確認では未検証である。

この成功runは実機作業、署名、ローカルChrome起動、artifact取得・置換を
承認するものではない。Phase 5 implementationは、Phase 5 planに定めた
3B/3C/3D run、manifest SHA-256、artifact名、ANGLE revision等の詳細な
admission recordを満たすまで開始しない。

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
