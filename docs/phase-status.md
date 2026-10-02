# Phase 状態

更新日: 2026-10-02

## Orchestration

人間がOwner/Approver、親エージェントがOrchestrator/Reviewer、Lunaが
Implementerである。人間は親とのみ通信し、親は一度に一体だけのLunaへ
範囲限定の指示を出し、実diffと検証を独立レビューする。親はこのbranchの
通常checkpoint/fix commit、push、Phase 3B CIのdispatch/monitorを行える。
main/他branch、force/rebase/merge/tag/release、PR/issue、署名、実機・artifact・retry操作は
引き続き人間の承認境界である。通常の修正・fixture
失敗・文書不足・診断は `IN PROGRESS` または `CHANGES REQUIRED` であり、
`BLOCKED` は承認境界、権限、利用不能な外部依存、安全でない統合、必須の人間
設計判断、診断枯渇、または重大な状態不一致に限る。dirty worktree、保存済み
retryディレクトリ、evidenceは消去・reset・cleanしない。

Phase 3Bの正式acceptanceは、CI job成功、fixture exit `0`、static checksと
`git diff --check`成功、required fixtureのskipなし、unexpected diagnosticsなしを
すべて満たすこととする。fixture stepは20分、jobは30分で、timeoutは失敗である。
CIはrunner/environment情報とfixture stdout/stderr、exit status、diagnostics indexを保持する。
失敗時は親がlogs/artifactをreview・分類し、Lunaがbounded fix、親がreview/static checksを行い、
checkpoint commit/push後に新runを開始する。明確なtransient runner/service failureの場合だけ
1回のrerunを許可し、無目的なrerunはしない。mainと実機は承認境界であり、retry3は保存済みfailure/no-opである。

Phase 3C preflight is being migrated to verified release manifests and dynamic
attempt roots. New artifacts use `angle-release-v1`; source Chrome's exact
version must match the selected artifact manifest. Existing retry0–12 and their
evidence remain immutable historical records. New attempts use a fresh
`attempt-YYYYMMDD-HHMMSS` root with output and results as direct children. The
current-only Framework policy discovers `Versions/Current` from the selected
Chrome release rather than pinning `.17` or `.45`. Formal acceptance is only
the pinned Phase 3B/3C synthetic Actions workflows; local full fixtures are
prohibited. CI success is required before requesting separate human approval
for new real-device work. Any separately approved historical device-test record remains historical and does not authorize a new signing, Chrome, or KOOV operation.

| Phase | 状態 | 記録 |
| --- | --- | --- |
| Phase 0 | 保留 | 基準資料の比較設計は完了。実機ログがワークスペースに未提供のため、ログ保全と比較表作成は保留。Phase 3 の実機試験前に完了させる。 |
| Phase 1 | 完了 | Chromium `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854`、ANGLE `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`、dynamic ANGLE の探索位置と主要 dylib を固定ソースで確認済み。Feature override が後続の条件付き既定値で上書きされない根拠を `docs/baseline.md` に追記した。 |
| Phase 2 | Phase 2B 完了 | 初回run `35495704110` と失敗follow-up run `35497602637` の記録は保持する。2回目のfollow-up run [`35501697418`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/35501697418) は固定ANGLE checkout、`gclient sync`、GN、Ninja、artifact検証、uploadに成功した。artifactはx86_64の`libEGL.dylib`と`libGLESv2.dylib`のみを含み、各自己install name以外に非system依存はなく、署名は未署名（Phase 2では許容）である。Phase 2B時点では未実行だった固定depot_tools `0306e4682b4ac35287c726fa35a983157a625902` のbootstrap付き構成は、Phase 3A run `35515036255`で初めて実行・検証された。 |
| Phase 3A | legacy artifact記録 | Chrome `154.0.8037.45`向けartifact `35515036255`は過去の固定SHA・形式・依存・署名検証結果として記録する。新形式のrelease manifestを持たず、新しい実機試験には使用しない。 |
| Phase 3B | synthetic fixture CI成功（記録時点） | `angle-release-v1`はChrome/Chromium/ANGLE/depot_tools識別子、dylib SHA、artifact/run metadataを束縛する。test-copy manifestはrelease manifest SHAを記録し、Libraries baselineを保持したままANGLE 2本だけ追加する。正式なsynthetic fixture判定は下記のrunの記録時点で成功した。ローカルfull fixtureは実行しない。retry0–12は保存済み履歴として不変保持し、新規attempt rootは別名で作成する。この行はCI記録の要約であり、後日の実機試行状態を表さない。 |
| Phase 3B 以降 | synthetic 3B/3C成功、Phase 3D VM観測成功（各記録時点） | Phase 3D文書に記録された、別途承認済みの過去のユーザー所有機器テスト・署名・Chrome起動記録は履歴として保持する。3B/3C/3D run metadataはCI/VMの記録であり、新規の実機作業を承認しない。Phase 5の詳細な入場記録と専用stub CIは完了しているが、この行自体は現在の実機試行結果を表さない。 |
| Phase 5 | fallback CI/VM成功、正確な`.97` fallback artifactで実機WebGL1 context/draw成功。WebGL2/KOOV未達 | `.97` fallback runtime CI [`36988193107`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36988193107) はsuccess。artifactは`angle-macos-x86_64-chrome-154.0.8037.97-angle-e12217f3-family1-experiment-36988193107`、ANGLE `e12217f3e133cb1029b050d893b1806d141483be`、GitHub digest `sha256:984225daa95e44dd621dee93e604cce9fea414015287ba1b3fa7eb2cb7ff7bc7`、manifest SHA-256 `73e94ae3b306086201401bfc31540296362aac5505d4af478537abed6391e961`、`RUNTIME_DEVICE_READY=false`。`.97` fallback実機ではIntel HD Graphics 5000を選択し、`require_gpu_family2 enabled=false has_override=true`、`eglInitialize_return_success`、`max_es_version=2.0`、非WebGLES3→ES2 fallbackを確認した。WebGL1 page/context/drawは成功し、rendererはIntel HD Graphics 5000。WebGL2は`context-null`、KOOVは未実施。WebGL実行中の同一GPU helper processでreplacement `libEGL.dylib`/`libGLESv2.dylib`を`lsof`/`vmmap`確認済み。fallback patch SHA-256は`7bd8a40eaa6311c4ca37ebd68c19ab3d9822b936000e38dbadea70b92667a014`。詳細は[`docs/phase5-real-device-observation.md`](phase5-real-device-observation.md)。 |

最新の再構築・再試行はruntime CI [`37009376538`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/37009376538)のartifact `angle-macos-x86_64-chrome-154.0.8037.97-angle-e12217f3-family1-experiment-37009376538`（GitHub digest `sha256:247f0ee4be552c8e4f8790db04c39753631abc62312b78318dcdd5a80808652d`、manifest SHA-256 `97b03d254b67b604173436bdf64a9c09c93f61d468b66880b36508c5e8d3bab2`）であり、同じ実機結果を再現した。WebGL2のES3要求だけが`EGL_CONTEXT_CLIENT_VERSION (0x3098)=3`で`EGL_BAD_ATTRIBUTE`となり、WebGL1 context/drawは成功した。`RUNTIME_DEVICE_READY=false`は維持し、KOOVは未実施である。

## Phase 3の一次記録（2026-09-26確認）

親エージェントが確認した公開GitHub Actionsのrun metadataと、読み取り専用で取得したdiagnostics artifactの検証結果を記録する。3B/3C/3Dのrunはそれぞれ別artifactであり、3B/3Cのdiagnostics成功と、3Dで選択されたrelease manifest/artifactの検証結果を混同しない。

| 対象 | run | commit | diagnostics / artifact | 一次記録 |
| --- | --- | --- | --- | --- |
| Phase 3B synthetic fixture | `36963092889` / success | `f2a14f9a2a09aa3559fb792521c68a613d8351ea` | `phase3b-synthetic-fixture-diagnostics-36963092889` / archive SHA-256 `0ce6b2e4e05e374fc5298dad50e5bdd6c765b701f09f2b370ea1ca401a905e3c` / fixture exit `0` / release-artifact exit `0` / no skipped or unexpected diagnostics | [Actions run](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36963092889) |
| Phase 3C synthetic preflight fixture | `36241795968` / success | `3b116228de6c2af80b14cdfb36ff6fec1af6db38` | `phase3c-preflight-synthetic-diagnostics-36241795968` / archive SHA-256 `d33c4e301f023ce9870e2a8faba139fb9415c5109aca9584d080ad661ac9ec03` / exit `0` | [Actions run](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36241795968) |
| Phase 3D dynamic ANGLE VM observation | `36071196477` / success | `e9002f5ba7f70ec6b23f6b82453c9580a33a399b` | `phase3d-dynamic-angle-36065655290-36071196477` / archive SHA-256 `8f142e7503555fe3d9a75f0716daf8777509b28089e17b1bb4a8cfef7aabe298` | [Actions run](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36071196477) |

Phase 3D diagnostics artifactの`ANGLE_RELEASE_MANIFEST`はsidecar検証に成功した。schemaは`angle-release-v1`、Chromeは`154.0.8037.57`、manifest SHA-256は`ed01fc7c8a1634193cebc7e016be2fddd4a1d0094e7a77abdc98798d6b078c4f`、選択artifactは`angle-macos-x86_64-chrome-154.0.8037.57-angle-1ff8799c-36065655290`、ANGLE revisionは`1ff8799c596d4fc9acea28343610b1f33650a6fa`、build runは`36065655290`である。これにより、Phase 5の詳細なadmission recordはソース実装開始に必要な範囲で完了した。さらにPhase 5専用stub CI run `36432392861`も成功し、targeted EGL testと専用artifactのmanifestを検証した。ただし、新規Actions dispatch、artifact download、署名、Chrome起動、実機操作を承認するものではない。

## Phase 5専用CI一次記録（2026-09-29確認）

| 項目 | 記録 |
| --- | --- |
| workflow / run | `phase5-metal-family1.yml` / [`36432392861`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36432392861) / success |
| commit | `0784dc1731e6709282260a9a8fda25df2fc0194f` |
| artifact / schema | `angle-metal-family1-test-stub-36432392861` / `phase5-metal-family1-test-stub-v1` |
| ANGLE revision | `1ff8799c596d4fc9acea28343610b1f33650a6fa` |
| patch SHA-256 | `00a11d2289b306de4642cde3711cba051667b38fd5d97f46a434ba7f24ac5258` |
| manifest SHA-256 | `c99b82bcd19cb564aa8f0aae7c2e0ecd8c18342de168c2d47e5a00b342f2b638` |
| artifact-files SHA-256 | `17b5ee8a79978f01255c13ffb3fb4f2ee01a89e1303d5faa5a681b5886916d0f` |
| test result | exit `0` / 4 tests passed |

## Phase 5 runtime artifact CI一次記録（2026-09-29確認）

| 項目 | 記録 |
| --- | --- |
| workflow / run | `phase5-metal-family1.yml` / [`36501314503`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36501314503) / success |
| commit | `b7cd00cb3383bf44eea7ce355f63de7e9ddaf524` |
| runtime artifact | `angle-macos-x86_64-chrome-154.0.8037.57-angle-1ff8799c-36501314503` / schema `phase5-metal-family1-runtime-v1` / GitHub digest `sha256:ea859f38e4e0f64a00975b5c6d0574b8238e1d82cb2667a96580c96d404df5b2` |
| diagnostics artifact | `phase5-metal-family1-runtime-diagnostics-36501314503` / GitHub digest `sha256:b11ee99fa11d66b78580cecfc7bd3874721a43e3aa6482b26944d51ba5cfc6b6` |
| Chrome / Chromium | `154.0.8037.57` / `73c14f6228d7cd537c855007e8f88678969cc0eb` |
| ANGLE / depot_tools | `1ff8799c596d4fc9acea28343610b1f33650a6fa` / `0306e4682b4ac35287c726fa35a983157a625902` |
| runtime patch SHA-256 | `07d7e80d8ce1099cb3d9d3ad5654eabd39b3d33776932ad28e3d76deaf6d4070` |
| manifest SHA-256 | `fc0c39145695fa5501039b7aa1093326aadf7af71022e6b30294f464604dbdc2` |
| artifact-files SHA-256 | `fc9e1ab16fded2c9d5b28e4978e8bf1f8c7c487e7a58ae894044497a5be351ab` |
| dylib SHA-256 | `libEGL.dylib=f4a8a7575183a41373404f7c25b4f56e1a1540c5b1578d11437c180b1f698db8`; `libGLESv2.dylib=d0dedeeddb3b727e645648ee2b90462be43300c07914c3cc8ca7fc3de3b95e5c` |
| build / validation | `libEGL=0`, `libGLESv2=0`; `verify-artifact.sh` and `verify-phase5-runtime-artifact.sh` passed; test-only stub marker absent |
| device boundary | `RUNTIME_DEVICE_READY=false`; x86_64 Mach-O、未署名。署名、配置、Chrome起動、実機操作は未実施 |

## Phase 5 Chrome 154.0.8037.58 rebuild一次記録（2026-09-29確認）

| 項目 | 記録 |
| --- | --- |
| runtime workflow / run | `phase5-metal-family1.yml` / [`36545744638`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36545744638) / success |
| commit | `7c034047a585986a52141b208f8b34bcda07ab84` |
| runtime artifact | `angle-macos-x86_64-chrome-154.0.8037.58-angle-1ff8799c-36545744638` / GitHub digest `sha256:76a4a04c342edfb263cf4d65157e9a5d5ebfc5c5331d9c896a4614115e89b379` |
| diagnostics artifact | `phase5-metal-family1-runtime-diagnostics-36545744638` / GitHub digest `sha256:cb7fa54575c6a59fab10da1c3d0c08852660552fadf76de27e3b2632b7e357e9` |
| Chrome / Chromium | `154.0.8037.58` / `a654841425914cbb703a2931e07b70a83aedbafd` |
| ANGLE / depot_tools | `1ff8799c596d4fc9acea28343610b1f33650a6fa` / `0306e4682b4ac35287c726fa35a983157a625902` |
| runtime patch / manifest | `07d7e80d8ce1099cb3d9d3ad5654eabd39b3d33776932ad28e3d76deaf6d4070` / `c929c2fc2dcae41007599bbb2b86dd8daf7b923a868b85c1e7a2d5d2df12b64e` |
| dylib SHA-256 | `libEGL.dylib=f4a8a7575183a41373404f7c25b4f56e1a1540c5b1578d11437c180b1f698db8`; `libGLESv2.dylib=d0dedeeddb3b727e645648ee2b90462be43300c07914c3cc8ca7fc3de3b95e5c` |
| device boundary | `RUNTIME_DEVICE_READY=false`; x86_64 Mach-O、未署名 |
| Phase 3D VM/WebGL | [`36549980089`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36549980089) / diagnostics `phase3d-dynamic-angle-36545744638-36549980089` / digest `sha256:bd41e2e171a9b9337ad5139d63c617f29c2fba2bab0845f0375fa3abeb4c17fd` |
| VM result | dynamic: the old probe recorded GPU-correlated dyld evidence per library but did not establish same-PID loading; EGL failure `true`, GPU fallback `true`; stock: EGL failure `false`, GPU fallback `true`; both WebGL contexts `false`, draw `false`, `context-null` |

## Phase 5次段階の実行方針（CI先行）

Phase 5専用stub CIの成功は、記録時点でtest-only profileと初期化停止段階の検証が完了したことを示す。続くruntime artifact CIとVM観測も完了し、現在は実機試行の結果を別記録として扱う。次の項目はCI/VM記録の順序を示すもので、現在の実機試行が未実施であることを示すものではない。

1. test-only stubと分離した、明示的opt-inの実機用runtime patchを固定ANGLE revisionへ適用する。
2. `libEGL.dylib`／`libGLESv2.dylib`、patch provenance、manifest、SHA-256を含む実機用artifactをCIで生成・検証する。
3. targeted test、static audit、artifact validationを実行する。
4. Phase 3D VMで動的ANGLEロード、GPU process引数、EGL初期化、fallbackを観測する。
5. 必要性と入力ページを別途固定したうえで、VM上のWebGL smoke観測を追加した。これはrun [`36514821653`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36514821653)で完了した。KOOV、USB、Bluetooth、既存profileはCIの対象外とする。

runtime artifact workflowは実装済みで、明示的runtime opt-inとしてCI dispatchを実施した。初回再run `36497660658`のtimeout、修正後のruntime build run `36501314503`、続くPhase 3D VM観測と固定WebGL smoke観測は、それぞれ当時のCI/VM記録として完了している。VM成功を実機成功とは扱わない。実機試行の署名・Chrome起動は別途実施済みであり、その結果は「Phase 5実機試行の結果」と実機観測文書に記録する。KOOV操作は未実施である。

Phase 3D VM観測run `36507728136`は、runtime artifact `36501314503`を固定入力として成功した。dynamic probeでは`BROWSER_STARTED=true`、`BROWSER_ALIVE_AT_DEADLINE=true`、各replacement dylibについてGPU process相関dyld signalが`true`、`EGL_INITIALIZATION_FAILURE_OBSERVED=true`、`GPU_DISABLED_FALLBACK_OBSERVED=true`、`PROBE_EXIT_STATUS=0`だった。旧probeはライブラリごとのsignalを独立集計していたため、両pathが同じGPU PIDに属するとは確認できない。従って記録済み`both-replacement-libraries-gpu-loaded`はsame-PID証明として扱わず、raw artifact再確認または修正後probeの再実行を要する。stock controlではEGL初期化失敗は観測されず、両ケースともGPU disabled fallbackが発生したため、comparisonは`dynamic-angle-differs-from-stock-control`となった。描画成功やIntel HD Graphics 5000実機互換性の証明ではない。

## Phase 5 実機試行の結果（2026-09-29）

`.58` runtime artifactを使った新規attempt `attempt-20260929-193416`では、Phase 3C preflightは`completed-dry-run`となり、その後に明示承認されたtest copyだけをApple Development署名した。署名receipt v3の生成、deep strict verification、Chrome起動、Intel HD Graphics 5000 / Metalのadapter選択を確認した。

live repeatのCase BとCase Cでは、いずれも`Initialization of all (1) EGL display types failed`、`GLDisplayEGL::Initialize failed`、GPU process終了、`--use-gl=disabled` fallbackを確認した。Case Cの`--disable-angle-features=requireGpuFamily2`はGPU processへ到達したが、初期化成功やANGLE feature overrideの認識までは証明しない。`lsof`、`vmmap`、collector結果は両replacement dylibの直接ロードを証明しなかったため、ロード済みとも未ロードとも断定しない。停止条件によりWebGLとKOOVは実施していない。source Chromeは`.58`のままで、既存retry/evidenceは変更していない。

runtime manifestの`RUNTIME_DEVICE_READY=false`は、CI artifactが未署名・実機起動前の境界で作られていることを示す。実機で署名・起動した事実やGPU初期化成功を表す値ではなく、変更しない。

次の作業は、既存trace、stderr抽出、GPU process引数、失敗順序の読み取り専用分析、必要に応じた一時的な診断手段での直接ロード・feature override証明、固定revisionのFamily 1 gateとruntime patchのソース診断の順に進める。CI/VMで修正結果を確認し、別途承認を得た後にのみ新しい実機試行を行う。GPU初期化が成功するまでWebGL、その後にKOOVへ進まない。

## Phase 5 fallback実機 WebGL1結果（2026-10-02）

正確な`.97` fallback artifactを新規test copyへ適用した承認済み実機試験では、
ANGLEロード、GPU/EGL初期化、非WebGL ES3→ES2 fallback、WebGL1 context生成と最小
clear描画まで成功した。WebGL実行中の同一GPU helper processについて、raw `lsof`/
`vmmap`がtest copy内の`libEGL.dylib`と`libGLESv2.dylib`を示した。

WebGL2は`context-null`で、ES3要求の`EGL_CONTEXT_CLIENT_VERSION (0x3098)=3`
拒否を能力境界として記録した。fallbackはWebGL contextをES2へ降格しないため、
WebGL1成功とは矛盾しない。KOOVは未実施で、WebGL1結果のレビューと別途人間承認が
成立するまで開始しない。artifact manifestの`RUNTIME_DEVICE_READY=false`はCI生成時の
不変境界であり、実機test copyの成功によって変更しない。

## Phase 3D runtime artifact観測記録

| 項目 | 記録 |
| --- | --- |
| workflow / run | `phase3d-dynamic-angle-vm.yml` / [`36507728136`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36507728136) / success / 3分04秒 |
| commit | `73e04a42b0375e06a41b096fa45bd216d0f5abc7` |
| input artifact | `angle-macos-x86_64-chrome-154.0.8037.57-angle-1ff8799c-36501314503` / manifest SHA-256 `fc0c39145695fa5501039b7aa1093326aadf7af71022e6b30294f464604dbdc2` |
| diagnostics artifact | `phase3d-dynamic-angle-36501314503-36507728136` / GitHub digest `sha256:0e313e79fc1d16f76aa4c7cad6b1e65ad349031195e57cfc8f7695060c4f36ea` |
| dynamic boundary | historical `DYNAMIC_ANGLE_OUTCOME=both-replacement-libraries-gpu-loaded`; browser/GPU ANGLE flags `true`; each library had GPU-correlated dyld evidence, but old aggregation did not establish same-PID loading |
| initialization boundary | `EGL_INITIALIZATION_FAILURE_OBSERVED=true`; `GPU_DISABLED_FALLBACK_OBSERVED=true`; browser remained alive; probe exit `0` |
| stock control | EGL initialization failure `false`; GPU disabled fallback `true`; `CONTROL_INTERPRETATION=dynamic-angle-differs-from-stock-control` |
| evidence limits | process-map observation `false`; dynamic collector failure count `1`; post-run dylib SHA unchanged; VMはApple Paravirtualized Graphics Deviceで実機結果ではない |

## Phase 3D WebGL smoke観測記録（2026-09-29）

| 項目 | 記録 |
| --- | --- |
| workflow / run | `phase3d-dynamic-angle-vm.yml` / [`36514821653`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36514821653) / success / 3分52秒 |
| commit | `e42e51f` |
| input artifact | `angle-macos-x86_64-chrome-154.0.8037.57-angle-1ff8799c-36501314503` / manifest SHA-256 `fc0c39145695fa5501039b7aa1093326aadf7af71022e6b30294f464604dbdc2` |
| diagnostics artifact | `phase3d-dynamic-angle-36501314503-36514821653` / GitHub digest `sha256:bf931a2be9b2060ba1366de67dea36c5231c59c225c9c4b387dd037be079be53` |
| dynamic WebGL | page loaded `true`; WebGL2/WebGL1 context `false`; draw `false`; errors `context-null` |
| stock WebGL | page loaded `true`; WebGL2/WebGL1 context `false`; draw `false`; errors `context-null` |
| comparison | `WEBGL_INTERPRETATION=dynamic-webgl-blocked-by-egl-initialization`; dynamicはEGL初期化失敗`true`、stockは`false` |
| boundary | WebGL smokeの入力・失敗境界はCIで記録済み。描画成功、Intel HD Graphics 5000互換性、KOOV動作は未証明 |
