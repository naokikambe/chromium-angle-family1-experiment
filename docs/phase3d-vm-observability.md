# Phase 3D: macOS VM observability boundary

更新日: 2026-10-02

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

## Phase 5 context属性検証trace（CI検証済み、実機確認待ち）

固定ANGLE revisionへ適用するruntime patchに、`validationEGL.cpp`のcontext
属性検証と属性値検証の結果をstderrへ記録する計装を追加した。各記録は属性キー、
属性値（値検証時）、`result=true/false`を含む。さらに`entry_points_egl_autogen.cpp`で
release runtimeの`IsEGLValidationEnabled()`状態を記録し、`Context::initialize()`の
version拒否時には`EGL_BAD_ATTRIBUTE`と属性`0x3098`（`EGL_CONTEXT_CLIENT_VERSION`）の
対応を直接記録する。既存の`Context.cpp`のES version checkおよび`libEGL` wrapperの
生属性列・config選択・`eglGetError`記録とは別のvalidation境界であり、
`EGL_BAD_ATTRIBUTE`の発生がversion拒否か属性検証拒否かをCI/VM上で分類できる。

解析器は`CONTEXT_ATTRIBUTE_VALIDATION_FAILURE_KEYS`と
`CONTEXT_ATTRIBUTE_VALUE_VALIDATION_FAILURE_KEYS`を出力し、失敗キーがある場合は
`egl-bad-attribute-from-context-attribute-validation`と分類する。次回の実機結果収集も
同じ解析器を自動実行し、`context-trace-analysis.txt`を新しい結果ディレクトリへ保存する。
`CONTEXT_VALIDATION_ENABLED_VALUES`、`CONTEXT_ERROR_ATTRIBUTE_KEYS`、
`CONTEXT_ERROR_ATTRIBUTE_VALUES`も出力し、直接のcontext error markerがある場合は
`egl-bad-attribute-from-context-error-attribute`と分類する。
さらに`Display::createContext()`の`Context::initialize()`返却境界を
`CONTEXT_INITIALIZE_ERROR_CODES`、`CONTEXT_INITIALIZE_ERROR_IDS`、
`CONTEXT_INITIALIZE_SUCCESS_COUNT`として記録する。`EGL_BAD_ATTRIBUTE`の直接属性キーが
得られないままcontext初期化エラーだけが返った場合は、
`egl-bad-attribute-from-context-initialize-error-needs-key`として実機の追加確認対象にする。
この変更のruntime patch SHA-256は
`6abc915e79513ceae887ef4e2a91ae65d40878edc87b0bf77c053adfd5a13e5f`である。固定revision
上のpatch適用・build・VM観測CIは成功したが、VMはIntel HD Graphics 5000ではないため、
実機属性原因の判定はまだ更新しない。

## Chrome 154.0.8037.58 rebuild observation record

The Phase 5 runtime artifact was rebuilt for the Chrome version currently
installed on the target Mac. The previous `.57` records remain historical;
this section is the current `.58` input and observation record.

| 項目 | 記録 |
| --- | --- |
| runtime build run | [`36545744638`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36545744638) / success / 33m30s |
| build commit | `7c034047a585986a52141b208f8b34bcda07ab84` |
| runtime artifact | `angle-macos-x86_64-chrome-154.0.8037.58-angle-1ff8799c-36545744638` / GitHub digest `sha256:76a4a04c342edfb263cf4d65157e9a5d5ebfc5c5331d9c896a4614115e89b379` |
| Chrome / Chromium | `154.0.8037.58` / `a654841425914cbb703a2931e07b70a83aedbafd` |
| ANGLE / depot_tools | `1ff8799c596d4fc9acea28343610b1f33650a6fa` / `0306e4682b4ac35287c726fa35a983157a625902` |
| runtime patch SHA-256 | `07d7e80d8ce1099cb3d9d3ad5654eabd39b3d33776932ad28e3d76deaf6d4070` |
| manifest SHA-256 | `c929c2fc2dcae41007599bbb2b86dd8daf7b923a868b85c1e7a2d5d2df12b64e` |
| dylib SHA-256 | `libEGL.dylib=f4a8a7575183a41373404f7c25b4f56e1a1540c5b1578d11437c180b1f698db8`; `libGLESv2.dylib=d0dedeeddb3b727e645648ee2b90462be43300c07914c3cc8ca7fc3de3b95e5c` |
| build validation | `libEGL=0`, `libGLESv2=0`; `verify-artifact.sh` and `verify-phase5-runtime-artifact.sh` passed; `TEST_ONLY_STUB=absent` |
| device boundary | `RUNTIME_DEVICE_READY=false`; x86_64 Mach-O、未署名 |
| CfT archive | official deterministic version URL / SHA-256 `84dfd08a56c5c5bdb5f74687b3fb1f6b7eeaf62ed0b700f91e283fb3ccee3beb` / bundle `154.0.8037.58` |
| observation run | [`36549980089`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36549980089) / success / 3m20s |
| observation commit | `063c9c47905c87653ed5cc40ee3504e85b14519e` |
| diagnostics artifact | `phase3d-dynamic-angle-36545744638-36549980089` / GitHub digest `sha256:bd41e2e171a9b9337ad5139d63c617f29c2fba2bab0845f0375fa3abeb4c17fd` |
| dynamic result | browser/GPU ANGLE flags `true`; each replacement library had GPU-correlated dyld evidence, but same-PID attribution was not established by the old classifier; EGL initialization failure `true`; GPU disabled fallback `true`; historical outcome label `both-replacement-libraries-gpu-loaded`; probe exit `0` |
| stock control | EGL initialization failure `false`; GPU disabled fallback `true`; comparison `dynamic-angle-differs-from-stock-control` |
| WebGL result | dynamic/stockともページ到達 `true`、WebGL2/WebGL1 context `false`、draw `false`、`context-null` |
| evidence limits | process-map observation `false`; dynamic collector failure count `0`; stock collector failure count `1`; VMはApple Paravirtualized Graphics Deviceで実機結果ではない |

The CfT known-good JSON did not list a unique mac-x64 entry for `.58` at the
time of the run. The probe therefore used the official version-fixed archive
URL, recorded its archive SHA-256, and still required the extracted bundle
version to equal `154.0.8037.58`. Distinct metadata URLs remain fatal.

The `.58` VM run recorded GPU-correlated dyld evidence for each library, but its
then-current classifier combined those signals independently and did not prove
both paths belonged to the same GPU PID. The recorded EGL failure, fallback,
and missing WebGL contexts remain valid observations. Same-PID loading requires
raw per-PID artifact review or a rerun with the corrected classifier. The VM
does not establish real-device rendering, Intel HD Graphics 5000 compatibility,
signing success, or KOOV behavior.

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
| dynamic result | each replacement library had GPU-correlated dyld evidence; same-PID attribution was not established by the old classifier; EGL initialization failure `true`; GPU disabled fallback `true`; probe exit `0` |
| stock control | EGL initialization failure `false`; GPU disabled fallback `true`; comparison `dynamic-angle-differs-from-stock-control` |
| evidence limits | process-map observation `false`; dynamic collector failure count `1`; post-run replacement hashes unchanged |

Interpretation: the historical probe recorded per-library GPU-correlated dyld
signals, but the old aggregation did not prove that both paths were loaded by
one GPU PID. EGL initialization did not reach a usable state in the Apple
Paravirtualized Graphics Device VM. This is a useful failure-boundary result,
not a rendering pass or evidence of Intel HD Graphics 5000 compatibility. The
fixed WebGL smoke is recorded below; user-owned-device/KOOV testing remains
separate.

## WebGL smoke observation

The fixed input `tests/fixtures/phase3d-webgl-smoke.html` was added to the
dynamic and stock-control probes. Each probe used only its disposable Chrome
for Testing bundle and temporary profile. The page creates independent WebGL2
and WebGL1 canvases, attempts a minimal clear operation, and records the
context/draw result, renderer metadata when available, and the exact null/error
boundary. The probe reads the result through Chrome's loopback-only DevTools
`/json` endpoint; no auxiliary server, installed Chrome, or user profile is
used.

| 項目 | 記録 |
| --- | --- |
| workflow / run | [`36514821653`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36514821653) / success / 3分52秒 |
| commit | `e42e51f` |
| input artifact | `angle-macos-x86_64-chrome-154.0.8037.57-angle-1ff8799c-36501314503` / ANGLE `1ff8799c596d4fc9acea28343610b1f33650a6fa` |
| diagnostics artifact | `phase3d-dynamic-angle-36501314503-36514821653` / GitHub digest `sha256:bf931a2be9b2060ba1366de67dea36c5231c59c225c9c4b387dd037be079be53` |
| dynamic result | page loaded `true`; WebGL2/WebGL1 context `false`; draw `false`; `webgl2_error=context-null`, `webgl1_error=context-null` |
| stock result | page loaded `true`; WebGL2/WebGL1 context `false`; draw `false`; `webgl2_error=context-null`, `webgl1_error=context-null` |
| interpretation | `dynamic-webgl-blocked-by-egl-initialization`; dynamic EGL failure `true`, stock EGL failure `false` |

The WebGL smoke workflow pass means the page was reached and its result was
captured with no probe infrastructure failure. It does not mean a WebGL
context or rendering succeeded. In this VM, both controls stopped at
`context-null`, consistent with the observed GPU/EGL boundary.

The first two WebGL attempts are retained as failure diagnostics: run
`36513869419` stopped before Chrome launch because an auxiliary result server
did not publish a port; run `36514367145` reached Chrome and DevTools but the
`/json` endpoint HTML-escaped the title JSON. The final implementation removed
the auxiliary server and decodes the DevTools title before JSON validation.

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
version. It downloads the matching official mac-x64 Chrome for Testing archive
from the known-good metadata when a unique entry exists, or from the official
version-fixed archive URL when metadata has not listed that exact version yet.
It records the archive SHA-256 and requires the extracted bundle version to
match exactly.

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

The outcome `both-replacement-libraries-gpu-loaded` requires both replacement
paths from the same observed GPU PID. Separate PIDs may still set the
per-library evidence booleans, but cannot satisfy the same-process outcome.
EGL failure detection accepts the observed display-count form and the
`GLDisplayEGL::Initialize failed` form while preserving the raw stderr.

For the dynamic workflow, `dynamic-angle-placement.txt` binds the placement to
the release manifest and concrete Framework version.
`replacement-library-inspection.txt` records the installed files' hashes,
Mach-O architecture, dependencies, and read-only signature state.
`replacement-library-post-run.sha256` confirms that Chrome execution did not
mutate either replacement.  `dynamic-angle-evidence.txt` and
`authoritative-result.txt` contain the boundary booleans and summarized
outcome.

`context-trace-analysis.txt` is generated for dynamic observations and groups
the raw `eglCreateContext` markers by call. It records config selection,
ES-version counts, the non-version attribute comparison, and a conclusion only
when the raw trace supports the context-version rejection path.

The optional `loader_trace` workflow input enables `DYLD_PRINT_LIBRARIES=1` for
the isolated Chrome for Testing launch.  Its output is preserved in
`browser-stderr.txt`; the relevant framework and replacement-library lines are
also copied to `dyld-library-loads.txt`.  Missing loader lines mean only that
this mechanism did not observe a load; they are not proof that a library was
never considered.

## Phase 5 context-creation boundary

The Phase 5 Family 1 experiment was re-observed with the approved runtime
opt-in applied by the VM probe.  This is a CI-only use of the manifest value;
the real-device Case C command remains unchanged until separately approved.

| item | record |
| --- | --- |
| runtime build run | [`36957895411`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36957895411) / success (source-fetch 503のfailed attempt後、同runの許可済みrerun) |
| runtime artifact | `angle-macos-x86_64-chrome-154.0.8037.59-angle-1ff8799c-family1-experiment-36957895411` / GitHub digest `sha256:3e737b0ef4c9c0b0ab20549978ef12cc2911c430b8c59b845b105f2f11c02d1b` |
| VM run | [`36961446419`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36961446419) / success |
| observation commit | `0978e64f2fefa3acfc4c1418f12bab58623a18f0` |
| input runtime artifact | `angle-macos-x86_64-chrome-154.0.8037.59-angle-1ff8799c-family1-experiment-36957895411` |
| diagnostics artifact | `phase3d-dynamic-angle-36957895411-36961446419` / GitHub digest `sha256:1e9d509171105c72c77360f72e7cfbfef2749b2d187407cb351cffe2d33dee65` |
| runtime opt-in | `--disable-angle-features=requireGpuFamily2,requireMsl21` / applied `true` |
| Chrome / Chromium / ANGLE | `154.0.8037.59` / `b5a24985a2f5ed35909845221b7203c5d8995c8f` / `1ff8799c596d4fc9acea28343610b1f33650a6fa` |
| manifest SHA-256 | `056d14e79bc5aa33dd791af35f877b462e9319e77544d26a2116db23f243b7ba` |
| runtime patch SHA-256 | `6abc915e79513ceae887ef4e2a91ae65d40878edc87b0bf77c053adfd5a13e5f` |
| dylib SHA-256 | `libEGL.dylib=44116767b6d4d02362b2dd117cf16af2e719ef143b573f9a52b4837c1415b470`; `libGLESv2.dylib=7a3a9317e392cd7651d048df86e21658c0e735f3bdf663e3ff8767b9e1fcb6ea` |
| device boundary | `RUNTIME_DEVICE_READY=false`; x86_64 Mach-O、未署名 |

With the opt-in, the VM reached Metal device selection, command queue,
format table, shader library, render utilities, and successful EGL display
initialization.  All six context calls used `config=no_config`; four ES 3.0
attempts used `0x3098=3` and two ES 2.0 attempts used `0x3098=2`.  The
release runtime reported `CONTEXT_VALIDATION_ENABLED_VALUES=false`.  The ES
3.0 attempts were rejected by `context_version_check requested=3.0
max_supported=2.0`, followed by the direct marker
`context_error code=EGL_BAD_ATTRIBUTE attribute=0x3098 value=3`; the otherwise
identical ES 2.0 attempts returned a context.  The trace reported
`eglGetError_return=0x3004`, and Chrome labelled the failure
`EGL_BAD_ATTRIBUTE`.  The analyzer therefore classified this run as
`CONCLUSION=egl-bad-attribute-from-context-error-attribute`: the failing
attribute observed in this VM run is `EGL_CONTEXT_CLIENT_VERSION (0x3098)`
with value `3`, not an independently rejected remaining attribute.
The new `context_initialize_error`/`context_initialize_success` boundary is
also present in the artifact, so a future `EGL_BAD_ATTRIBUTE` returned by
context initialization without a direct key will remain explicitly
unclassified rather than being mistaken for the version path.

The dynamic probe observed both replacement dylibs loading in the GPU process,
successful EGL display initialization, and GPU-disabled fallback.  The stock
control also reached the fallback boundary.  Dynamic and stock WebGL smoke
both reached the page, but WebGL1/WebGL2 contexts were null and no draw
completed.  These are CI/VM observations, not Intel HD Graphics 5000 or
KOOV results.

This does not identify the behavior of Intel HD Graphics 5000.  The VM
reported an Apple Paravirtualized Graphics Device, and the artifact remains
`RUNTIME_DEVICE_READY=false`; real-device evidence is still required to
confirm whether the same max-version boundary and error mapping occur there,
or whether the real device produces a different EGL error before context
creation.  The next device-only question is therefore whether Intel HD 5000
also reports `EGL_CONTEXT_CLIENT_VERSION (0x3098)` or identifies another
attribute/backend boundary.

## Chrome `.97` artifact and Chrome for Testing availability boundary

The current target Mac had advanced to Chrome `154.0.8037.97`.  The exact
`.97` runtime artifact was therefore rebuilt from the matching Chromium DEPS
ANGLE revision before any device preparation.

| item | record |
| --- | --- |
| runtime build | [`36964161986`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36964161986) / success |
| runtime artifact | `angle-macos-x86_64-chrome-154.0.8037.97-angle-e12217f3-family1-experiment-36964161986` / GitHub digest `sha256:cf4e9c149e387f94c9f5b9401802f6255c8bc0426d353d73b0d6981c390782ef` |
| manifest | SHA-256 `99f3b38400814b1c7919008a26b62ba1a6328171e1dcedd5540d1de165628603`; Chrome `.97`; ANGLE `e12217f3e133cb1029b050d893b1806d141483be`; `RUNTIME_DEVICE_READY=false` |
| dylibs | `libEGL.dylib=44116767b6d4d02362b2dd117cf16af2e719ef143b573f9a52b4837c1415b470`; `libGLESv2.dylib=d909e2dfbcda92ccae5842740d87f0108cb55cda99f3d3ebfe538ff9c476e2e0` |
| first VM observation | [`36966677898`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36966677898) / failure before browser start |
| VM diagnostics | `phase3d-dynamic-angle-36964161986-36966677898` / GitHub digest `sha256:61f2bd1be93e9d5ea93734380ed4ee8123c61dd9533d4dcb4253cdbc41822a6b` |
| failure boundary | Chrome for Testing `.97` archive download returned HTTP 404; `BROWSER_STARTED=false`, `ANGLE_ARTIFACT_VALIDATED=false`, and no GPU/EGL/WebGL observation occurred |

The CfT known-good index contains `154.0.8037.92` but not
`154.0.8037.97`.  The runtime workflow now permits the explicit pair
`Chrome .92` / ANGLE `802a8704ca940b633b731493ee192e0661eb8cdd` only when the
`cft_compatibility=true` input is selected.  Both runtime patches apply cleanly
to that ANGLE revision.  This compatibility artifact is VM-only diagnostic
material; it is recorded in its manifest and is rejected by the real-device
test-copy preparation path.  It must not be substituted for the exact `.97`
artifact or used to authorize signing, artifact placement, Chrome launch, or
KOOV.

## Explicit limits

Phase 3D cannot establish correct real-device rendering, graphics performance,
Bluetooth/USB access, KOOV behavior, or the exact taskgated outcome of a
locally Apple-signed test copy.  Those remain separately approved device-test
questions.  It also cannot guarantee a post-mortem `lsof` or `vmmap` capture
for a process that exits before collection starts; stderr and unified log
records are retained for that case.
