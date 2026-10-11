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

## Probe-only revalidation (2026-10-09)

Run [37872947759](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/37872947759)
completed on workflow commit `a6522316b16fbf27daadb66ebe26b4e05c270216`.
Its source/deps step took 1,361 seconds and GN generation took 33 seconds.
Both requested fuzzer targets produced a Ninja dry-run count of zero and
`ninja: no work to do`; their `gn desc` type queries timed out. The workflow
classification was `success`, but those target measurements were not useful
for estimating build actions.

Run [37883694891](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/37883694891)
completed on workflow commit `8b58ce4ea6df234f92e210deb267adadde63b860`.
`run_small_target=false`; the compile step was skipped. Source/deps took 2,529
seconds, the job took 1 hour 6 minutes 6 seconds, GN generation took 60 seconds,
and the graph contained 301,111 targets. Cache was missed. All three GN type
queries timed out at 15 seconds. The added post-sync probe found
`build/config/siso/.sisoenv` and recorded Siso `v1.5.30`. Siso execution mode,
fastlocal, and localexec parallelism remained `not-run`, because this run did
not invoke a build.

| Probe target | Dry-run actions | Result | Additional observation |
| --- | ---: | --- | --- |
| `network_content_security_policy_fuzzer` | 0 | `no-work` | `ninja -t query` timed out at 20 seconds |
| `content_sms_parser_fuzzer` | 0 | `no-work` | `ninja -t query` timed out at 20 seconds |
| `url_unittests` | 4,631 | `within-cap` | Under the 12,000-action exploratory cap |

The target-query timeout did not explain why the two fuzzer targets had no
work; their dry-run output confirmed only `ninja: no work to do`. The
`url_unittests` dry-run supplied an actionable task estimate, and the overall
probe metric was `mixed`. The final workflow classification was `success`,
which records successful source/deps and graph inspection; it is not compile
evidence. No exploratory target was compiled.

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

Run 38060390806 adds successful exploratory compile evidence for one small
executable target; it does not establish that a full Chromium build fits the
GitHub Free job budget. A full build, self-hosted Intel Mac, larger runner, or
RBE/remote cache still requires a separate design and approval, including
review of runner isolation, toolchain parity, credentials, cache namespace
and retention, cost/quota, and reproducibility. None of those alternatives
was enabled by this record.

## Exploratory executable follow-ups (2026-10-10)

The following runs used workflow commit
`e09be281ea0028ca1fce4fb3b26d0dd3c01ea969`, target ref
`a3bb53b3e0f9e58aff547b26811643a967cdf5fa`, Chromium revision
`b510e9d7cd3a2fbd78d0ddc42234103206c5f78d`, ANGLE revision
`e12217f3e133cb1029b050d893b1806d141483be`, and URLLoader diagnostic patch
SHA-256 `1be36abf18ac58b94ff1421607be18152c0373a9f92b0aeeb14ad8e352a250c1`.
The later executable probes used `run_small_target=false`,
`probe_small_target=true`, and the 2,000-action cap.

Run [38031399216](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/38031399216)
used the invalid Ninja name `zlib`. Resolution returned `not-found`, the
compile step was skipped, and the workflow rejected the input. This was a
target-name typo, not a compiler or source failure.

Run [38040639732](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/38040639732)
corrected the input by selecting `//third_party/zlib:zlib` with
`small_target_ninja=auto`. Its dry-run contained 22 actions, and the bounded
library compile succeeded with exit code 0. The job took 22 minutes 57 seconds.
Siso was offline, fastlocal was disabled for non-interactive execution, and
remote execution was not configured. This proves the bounded library compile
path works; it is not executable-target evidence.

Run [38043853147](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/38043853147)
was a probe-only run; the job took 48 minutes 15 seconds and compilation was
skipped.

| Executable candidate | GN label | Dry-run actions | Result against 2,000 cap |
| --- | --- | ---: | --- |
| `gpu_unittests` | `//gpu:gpu_unittests` | 20,677 | `too-large` |
| `gl_unittests` | `//ui/gl:gl_unittests` | 10,717 | `too-large` |
| `base_unittests` | `//base:base_unittests` | 4,826 | `too-large` |

Run [38049201882](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/38049201882)
was another probe-only run; the job took 32 minutes 36 seconds. All labels
resolved to exact Ninja target names. GN target type queries timed out.

| Executable candidate | GN label | Dry-run actions | Probe result |
| --- | --- | ---: | --- |
| `url_formatter_fixer_fuzzer` | `//components/url_formatter:url_formatter_fixer_fuzzer` | 6,689 | `too-large` |
| `brotli_fuzzer` | `//third_party/brotli:brotli_fuzzer` | 0 | `no-work` |
| `base64_decode_fuzzer` | `//base:base64_decode_fuzzer` | 0 | `no-work` |

Run [38055127274](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/38055127274)
probed three ordinary executables declared in the pinned
`third_party/zlib/BUILD.gn`. The job took 28 minutes 35 seconds. All resolved
to exact Ninja target names; GN type queries timed out, while the BUILD file
declares each target as `executable`.

| Executable candidate | GN label | Dry-run actions | Breakdown | Probe result |
| --- | --- | ---: | --- | --- |
| `zlib_bench` | `//third_party/zlib:zlib_bench` | 89 | 85 compile, 4 link | `within-cap` |
| `minigzip` | `//third_party/zlib:minigzip` | 89 | 85 compile, 4 link | `within-cap` |
| `zpipe` | `//third_party/zlib:zpipe` | 89 | 85 compile, 4 link | `within-cap` |

For runs 38043853147, 38049201882, and 38055127274, source/deps and graph
outcomes succeeded, final classification was `success`, and the compile step
was skipped. These classifications record successful preflight and
measurement only. The 89-action results made each zlib executable eligible
for a bounded exploratory compile, but did not predict compile success. The
separately approved `zlib_bench`, `minigzip`, and `zpipe` compile results are
documented below. These exploratory compiles remain distinct from a full
Chromium build, U0/U1, and same-revision runtime evidence.

Run [38060390806](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/38060390806)
used the same pinned inputs and selected `//third_party/zlib:zlib_bench`
with `small_target_ninja=auto`, `run_small_target=true`, and
`probe_small_target=false`. Its exact-source/dependency fetch succeeded in
22m32s. The macOS Intel job completed successfully in 32m47s. The runner was
macOS 15.7.9 on `x86_64`, with 4 CPUs, 14 GiB memory, Xcode 16.4, and SDK
15.5. The Actions cache missed. After sync, Siso was version 1.5.30; the
build log reported 89 local steps, 0 remote steps, 0 cache hits, and 8
skipped steps. Fastlocal and localexec parallelism were not measured, and
remote execution/cache were not configured.

The graph-stage Ninja dry run counted 90 actions, one more than the 89
actions in the preceding probe. The bounded compile completed successfully:
Siso reported `Build Succeeded: 89 steps` in 1m20.82s; the compile step took
1m24s and returned exit code 0. Classification was `success`, and the overall
run concluded successfully at 15:11 UTC. This is exploratory executable
evidence only, not a full Chromium build or same-revision runtime evidence.

Run [38093906182](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/38093906182)
used the same pinned inputs and selected `//third_party/zlib:minigzip` with
`small_target_ninja=auto`, `run_small_target=true`, and
`probe_small_target=false`. The exact-source/dependency fetch took 24m22s,
and the macOS Intel job completed successfully in 35m16s. Runner facts
matched the preceding bounded compile: macOS 15.7.9 on `x86_64`, 4 CPUs,
14 GiB memory, Xcode 16.4, SDK 15.5. The Actions cache missed. Siso v1.5.30
reported 89 local steps, 0 remote steps, 0 cache hits, and 8 skipped steps;
fastlocal and localexec parallelism were not measured, and remote execution
and cache were not configured.

The graph-stage Ninja dry-run metric was 90, while Siso completed 89 steps.
The bounded compile succeeded with exit code 0; Siso reported
`Build Succeeded: 89 steps` in 1m22.74s, and the compile step took 1m26s.
Classification and the overall run both concluded `success` at 23:42 UTC.
This is exploratory executable evidence only, not a full Chromium build or
same-revision runtime evidence.

Run [38104419774](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/38104419774)
used the same pinned inputs and selected `//third_party/zlib:zpipe` with
`small_target_ninja=auto`, `run_small_target=true`, and
`probe_small_target=false`. The exact-source/dependency fetch took 21m31s,
and the macOS Intel job completed successfully in 30m23s. Runner facts
matched the preceding bounded compiles: macOS 15.7.9 on `x86_64`, 4 CPUs,
14 GiB memory, Xcode 16.4, and SDK 15.5. The Actions cache missed. Siso v1.5.30
reported 89 local steps, 0 remote steps, 0 cache hits, and 8 skipped steps;
fastlocal and localexec parallelism were not measured, and remote execution
and cache were not configured.

The graph-stage Ninja dry run counted 90 actions, while Siso completed 89
steps. The bounded compile succeeded with exit code 0; Siso reported
`Build Succeeded: 89 steps` in 1m06.96s, and the compile step took about
1m09s. Classification and the overall run both concluded `success` at
02:43 UTC on 2026-10-11. This is exploratory executable evidence only, not a
full Chromium build or same-revision runtime evidence.

## Probe-only follow-up (2026-10-11)

Run [38106809472](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/38106809472)
used workflow commit `e09be281ea0028ca1fce4fb3b26d0dd3c01ea969` and the same
pinned target, Chromium, ANGLE, and diagnostic-patch inputs above. It requested
probe-only measurements for three new executable candidates:
`//third_party/brotli:brotli`, `//third_party/opus:opus_compare`, and
`//third_party/opus:opus_demo`, with the 2,000-action cap,
`run_small_target=false`, and `probe_small_target=true`.

The run failed with `environment_failure` before source/deps sync or target
measurement. The resolve job and all preflight unit tests passed, but the
macOS Intel job could not fetch pinned depot_tools: Git exited 128 with
`Could not resolve host: chromium.googlesource.com` at 02:58 UTC. The source,
graph, and candidate-probe steps were skipped; no candidate was measured and
no compile ran. This is a runner DNS/network failure, not a compiler or target
failure.

Recommended retry safeguard: add a small bounded retry with backoff around
the pinned depot_tools `git fetch`, then retain the exact revision check and
fail with the original network error after the retry budget. Re-dispatch only
after that workflow change is reviewed; keep probe-only mode and the same
2,000-action cap. No Chromium full build, artifact operation, or repository
push was part of this run.

Run [38116285147](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/38116285147)
repeated the probe-only measurement after the bounded depot_tools fetch retry
was added in workflow commit `9965e3cd7706bb4a63a095caca185b62eb7c6762`.
It used the same target ref, Chromium and ANGLE revisions, and URLLoader
diagnostic patch SHA-256 listed above. The run concluded `success`; the
resolver job took 4 seconds and the macOS Intel job took 44m14s, from
05:54:15 to 06:38:29 UTC on 2026-10-11. The compile step was skipped.

The runner was macOS 15.7.9 on X64 with 4 CPUs and 14 GiB of memory, using
Xcode 16.4 (build 16F6) and macOS SDK 15.5. The Actions cache missed, and
source and DEPS were absent before sync. The cache key included the Chromium
revision, DEPS SHA-256, ANGLE revision, GN args SHA-256, and the URLLoader and
Xcode compatibility patch hashes. Exact source/dependency sync measured
1,586 seconds (26m26s).
After sync, Siso v1.5.30 and the project environment were present. Siso mode
and fastlocal were `not-run`; remote execution and remote cache were not
configured. No compile throughput or localexec parallelism was measured.

GN generation measured 48 seconds and produced a graph of 301,111 targets.
Each candidate resolved to the exact Ninja name and its dry-run plan was
counted without executing compiler or linker commands:

| Executable candidate | GN label | Dry-run actions | Compile | Link | GN type lookup | Probe result |
| --- | --- | ---: | ---: | ---: | --- | --- |
| `brotli` | `//third_party/brotli:brotli` | 106 | 100 | 6 | 15-second timeout | `within-cap` |
| `opus_compare` | `//third_party/opus:opus_compare` | 221 | 217 | 4 | 15-second timeout | `within-cap` |
| `opus_demo` | `//third_party/opus:opus_demo` | 221 | 217 | 4 | 15-second timeout | `within-cap` |

All candidates were below the 2,000-action cap. The supplemental GN type
lookups timed out and returned `unknown`; this did not affect Ninja task
counting. The workflow recorded `small_target_status=probe-success` and
`classification=success`. The pinned depot_tools step succeeded, and the logs
show no transient DNS error or retry event, so this run does not exercise the
new retry branch. These results are exploratory measurements only; they do
not establish a successful compile, full Chromium build, or same-revision
runtime evidence.

Suggested next approval: compile only `brotli`, the smallest measured target
(106 dry-run actions), in the bounded small-target mode with the same pinned
inputs, 2,000-action limit, and 1,200-second compile budget. This would be a
separate workflow dispatch; no executable was compiled in run 38116285147.
