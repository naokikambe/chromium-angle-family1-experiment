# Phase 3D: macOS VM observability boundary

Phase 3D is a GitHub-hosted macOS Intel observation stage.  It is deliberately
separate from the user-owned-device Phase 3C and Case B/C procedures.  It does
not authorize a local Chrome launch, modify `/Applications`, use a signing
identity, or test Bluetooth, USB, KOOV, or a normal browsing profile.

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
