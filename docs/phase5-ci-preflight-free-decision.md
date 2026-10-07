# Phase 5 Free preflight decision

## Decision

As of 2026-10-07 UTC, the formal preflight path available on GitHub Free is
the graph-only path with `run_small_target=false`. It validates the exact
source/dependency input, patches, GN configuration, and generated target graph
without starting a compile. It is a preflight result, not evidence of a
successful Chromium compile and not a formal U0/U1 or same-revision runtime
comparison.

The exploratory small-target compile remains a separate path. It is not
enabled by default and is rejected when its bounded dry-run exceeds the
12,000-task limit. The previously observed `services_unittests` dry-run had
34,810 tasks, so increasing the limit on the Free runner is not an accepted
countermeasure.

## Evidence

Run [37698685164](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/37698685164)
completed successfully on workflow commit `0aafa411070892750e8214bb46c373b1af70fda5`.
The target experiment ref recorded by the run was
`a3bb53b3e0f9e58aff547b26811643a967cdf5fa`.

| Measurement | Result |
| --- | --- |
| `run_small_target` | `false` |
| source/deps duration | 1,750 seconds |
| GN generation duration | 37 seconds |
| generated graph targets | 301,111 |
| graph inspection | `not-run` (bounded graph-only path) |
| small target | `not-run` |
| compile step | skipped |
| `PREFLIGHT_SOURCE_OUTCOME` | `success` |
| `PREFLIGHT_GRAPH_OUTCOME` | `success` |
| `PREFLIGHT_SMALL_TARGET_OUTCOME` | `skipped` |
| final classification | `success` |
| cache | miss; restore-only, no source/out save |

The runner facts were macOS 15.7.9 on Intel `x86_64`, 4 CPUs, approximately
14 GiB reported memory, Xcode 16.4 (16F6), and macOS SDK 15.5. The run
recorded `remote_execution_configured=false` and
`remote_cache_configured=false`. Because this was graph-only, compile-time
Siso execution was intentionally not measured: Siso mode, fastlocal state,
and localexec parallelism are recorded as unknown/not-run rather than inferred
from the earlier full-build attempt. The Siso version probe also reported
that the project `.sisoenv` was unavailable before the source sync.

The cache key included the runner OS/architecture, Chromium revision, resolved
ANGLE revision and DEPS digest, normalized GN args digest, and both patch
digests. The depot_tools revision and Xcode/SDK facts were recorded separately
but were not components of this run's cache key. The run therefore does not
establish a cache hit or a reusable Chromium `source`/`out` cache.

## Relationship to the cancelled full build

Run [37464208418](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/37464208418)
remains classified as a budget/timeout cancellation caused by execution speed,
not a compiler failure. Run 37698685164 does not retry or invalidate that
classification; it supplies the bounded Free preflight result that was
missing before the decision.

## Safety boundary and next approval

No full Chromium build, artifact upload/download, codesign, xattr change,
Chrome launch, device operation, or KOOV operation was performed by Run
37698685164. `RUNTIME_DEVICE_READY=false` remains unchanged. Existing signed
bundles, retry/evidence/artifact/profile records, and source Chrome were not
modified.

Compile evidence requires a separate approved design. Acceptable candidates
to evaluate are a genuinely small executable GN target, an approved
self-hosted Intel Mac, an approved larger runner, or approved RBE/remote
cache. Each requires explicit review of runner isolation, toolchain parity,
credentials, cache namespace and retention, cost/quota, and reproducibility.
None of those alternatives is enabled by this record.
