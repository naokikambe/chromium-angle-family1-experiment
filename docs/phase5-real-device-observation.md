# Phase 5 実機観測記録

更新日: 2026-10-02

## 最新の結論: Chrome 154.0.8037.59

`.59`用runtime artifactのbuild、Phase 3D VM観測、実機Case BのGPU startup trace取得まで完了した。
CI runの成功は診断workflowが完了した意味であり、GPU初期化・WebGLが成功した意味ではない。

実機ではIntel HD Graphics 5000 / Metal adapter選択後にEGL初期化が3回失敗し、各GPU processが終了した。
その後のGPU processは`--use-gl=disabled`で動作した。JSON traceは3,434 eventsを含み、
`gpu_init::SetupGLDisplayManagerEGL`を記録した。ANGLE replacement dylibの直接ロードは確認できず、
ロード済みとも未ロードとも判定しない。GPU初期化の停止条件により、実機WebGLとKOOVは実施していない。

新しいtest copyのpreflight、Apple Development署名、deep strict verification、Case B起動は完了した。
source ChromeとそのFrameworkは観測前後とも`154.0.8037.59`であり、既存retry/evidenceは変更していない。
起動時にGoogleUpdaterの`--wake-all`が開始・正常終了したが、この観測期間内のsource更新は確認されなかった。

### 保存済み実機traceの読み取り専用再確認（2026-10-02）

既存の実機証跡を変更せず、`.59`系の保存済みstderrを今回追加したcontext
trace analyzerで再解析した。通常のCase B診断・live maps診断では、
`[ANGLE_PHASE5_LOAD] libEGL_loaded`の後にEGL display初期化失敗と
`GLDisplayEGL::Initialize failed`が記録され、`eglCreateContext`到達は0件、
`EGL_BAD_ATTRIBUTE`も0件だった。platform-display診断では
`eglGetPlatformDisplay_enter`の直後に
`eglGetPlatformDisplay_return_no_display`となり、`eglInitialize`と
`eglCreateContext`には到達していない。

従って、保存済み実機証跡からはまだ「どの属性が`EGL_BAD_ATTRIBUTE`になるか」は
判定できない。次の実機診断で必要な最初の証跡は
`eglGetPlatformDisplay_return_display`、`eglInitialize_return_success`、続く
`context-trace-analysis.txt`であり、これらが得られるまでWebGL/KOOVへ進めない。

今回のCI検証では、保存された`stderr.log`に対して同じcontext trace analyzerを自動実行し、
属性検証拒否のキー、属性値検証拒否のキー、または`Context::initialize()`のES version
拒否を分離した。既存のattempt/evidenceは再収集・上書きしていない。実機については、
CI成功後に別の承認済みattemptでのみこの出力を取得する。

### CIで追加したcontext初期化境界（2026-10-02）

実機操作を増やさずに原因範囲を狭めるため、`eglCreateContext`の属性列、ES version要求、
EGL config選択、および`Context::initialize()`のエラー返却境界を追加計装した。runtime
artifactの再構築とPhase 3D VM観測は次の入力で成功した。

| 対象 | 証跡・結果 |
| --- | --- |
| runtime build | [`36957895411`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36957895411) / success。依存取得503のfailed attempt後、同runの許可済みrerunで完了 |
| runtime artifact | `angle-macos-x86_64-chrome-154.0.8037.59-angle-1ff8799c-family1-experiment-36957895411` / GitHub digest `sha256:3e737b0ef4c9c0b0ab20549978ef12cc2911c430b8c59b845b105f2f11c02d1b` |
| VM observation | [`36961446419`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36961446419) / success / diagnostics digest `sha256:1e9d509171105c72c77360f72e7cfbfef2749b2d187407cb351cffe2d33dee65` |
| ANGLE / runtime patch | `1ff8799c596d4fc9acea28343610b1f33650a6fa` / patch SHA-256 `6abc915e79513ceae887ef4e2a91ae65d40878edc87b0bf77c053adfd5a13e5f` |
| manifest / libraries | manifest SHA-256 `056d14e79bc5aa33dd791af35f877b462e9319e77544d26a2116db23f243b7ba`; `libEGL.dylib=44116767b6d4d02362b2dd117cf16af2e719ef143b573f9a52b4837c1415b470`; `libGLESv2.dylib=7a3a9317e392cd7651d048df86e21658c0e735f3bdf663e3ff8767b9e1fcb6ea` |
| device boundary | `RUNTIME_DEVICE_READY=false`; artifactは未署名で、実機操作には使用していない |

VMの6回の`eglCreateContext`は`config=no_config`で、ES 3.0要求の属性列だけが
`0x3098=3`となった。ES 3.0では`max_supported=2.0`のため
`EGL_BAD_ATTRIBUTE attribute=0x3098 value=3`、続いて
`context_initialize_error code=0x3004 message=Requested version is not supported`
を記録した。同じ残りの属性列を使うES 2.0要求（`0x3098=2`）では
`context_initialize_success`を記録した。したがって、今回のCI/VMで特定できた範囲は
`EGL_CONTEXT_CLIENT_VERSION`のES version拒否であり、属性列中の他属性やEGL config選択が
原因ではない。

この結果はApple Paravirtualized Graphics Device VMの判定であり、Intel HD Graphics 5000
実機で同じ属性が拒否されることを証明しない。保存済み実機traceは依然として
`eglCreateContext=0`、`EGL_BAD_ATTRIBUTE=0`で、`eglInitialize`成功にも到達していない。
Intel実機の確定には、CI成功後に新しい承認済みattemptで
`eglGetPlatformDisplay_return_display`、`eglInitialize_return_success`、続く
context traceを取得する必要がある。実機でGPU/EGL初期化が成功するまでWebGL/KOOVへ進めない。

| 対象 | 証跡・結果 |
| --- | --- |
| Phase 3B synthetic CI | [`36632187071`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36632187071) / success |
| Chrome `.59` runtime artifact CI | [`36632206740`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36632206740) / success |
| runtime artifact | `angle-macos-x86_64-chrome-154.0.8037.59-angle-1ff8799c-36632206740` / `sha256:3b20ea9d3dd1d0bba98afdbb4785cf8ed9e775db0c8fe6bd4956a49b4981c95b` |
| manifest | Chrome `154.0.8037.59`; Chromium `b5a24985a2f5ed35909845221b7203c5d8995c8f`; ANGLE `1ff8799c596d4fc9acea28343610b1f33650a6fa`; release manifest SHA-256 `f07f5c27a0e0c8d79917a277dae393d8546697e75bc068d55f6476192b95fc47`; `RUNTIME_DEVICE_READY=false` |
| runtime patch/libraries | Patch SHA-256 `07d7e80d8ce1099cb3d9d3ad5654eabd39b3d33776932ad28e3d76deaf6d4070`; `libEGL.dylib` SHA-256 `f4a8a7575183a41373404f7c25b4f56e1a1540c5b1578d11437c180b1f698db8`; `libGLESv2.dylib` SHA-256 `d0dedeeddb3b727e645648ee2b90462be43300c07914c3cc8ca7fc3de3b95e5c` |
| Phase 3D VM observation | [`36636862891`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36636862891) / success; diagnostics archive SHA-256 `c22e97e90c155bc440c6f3713f92f8024e10977b0ee2e39a734b6001b1d21a58` |
| VM dynamic | The old probe recorded GPU-correlated dyld evidence per replacement dylib, but did not establish that both belonged to the same GPU PID. EGL initialization failed and Chrome fell back to `--use-gl=disabled`. WebGL page loaded, but neither WebGL 1 nor 2 context was created and no draw completed. |
| VM stock control | No replacement ANGLE load was requested; EGL initialization failure was not observed, but GPU fallback occurred. WebGL 1/2 contexts and drawing were also unavailable in this VM. |
| Real-device preflight/signing | `.59` source/test-copy/Framework versions matched; preflight completed, Apple Development signing receipt recorded strict verification passed. |
| Real-device Case B | JSON trace parsed; 3,434 events. Intel HD Graphics 5000 / Metal selected, then EGL failure, GPU-process exit and disabled fallback. WebGL/KOOV were not run. |

### 実機のANGLEロード証拠とcollector修正

Case Bのprocess snapshotには、test Framework配下の`Google Chrome Helper.app --type=gpu-process`が記録された。
当時のcollectorは`Google Chrome Helper (GPU)`という専用bundle名だけを探していたため、このGPU processを
`gpu-processes.txt`に採取できず、`load-evidence.txt`も「未確認」となった。fallback状態のGPU processに対する
事後`lsof`/`vmmap`では両replacement dylibのpathを見つけられなかったが、これはEGL failure後の状態であり、
起動時にロードされなかった証明ではない。

この誤検出を避けるため、collectorをFramework配下の`--type=gpu-process`で照合する変更をcommit
`5cb3dbf`に記録した。専用helper形式・汎用helper形式のfocused fixtureはローカルでpassした。
Phase 3B full suiteはPinned CIで確認する。collector修正後の実機再試行は別のretryにあたり、
CI成功後に追加承認を得るまで実施しない。

次回の実機試行では、起動前に開始するbounded live observerがGPU processのPID・command、
生存中のbest-effort `lsof`/`vmmap`を保存し、collectorがobserver完了または未完了を明示する。
これは短命processの事後snapshot取りこぼしを減らすが、focused fixtureだけでは実機の
GPU process寿命やmacOS権限を証明しない。両replacement dylibのロード判定は、引き続き
同一GPU PIDからの直接証拠が必要である。

### `.59`段階別判定

| 段階 | 判定 | 根拠 |
| --- | --- | --- |
| ANGLEロード | PENDING | GPU processは起動しdynamic-angle flagsも確認したが、直接load証拠なし。collector name-filter修正後の実機確認が必要。 |
| GPU初期化 | BLOCKED | Intel HD Graphics 5000 / Metal選択後にEGL初期化失敗、GPU process終了、`--use-gl=disabled` fallback。 |
| WebGL | PENDING | GPU初期化失敗で停止。実機WebGLは未実施。 |
| KOOV | PENDING | WebGL成功前のため未実施。 |

`RUNTIME_DEVICE_READY=false`はbuild成功と実機準備を区別するmanifest上の明示的なゲートである。
CI artifactが作成され、署名済みtest copyで起動できたことだけでは、実機GPU初期化やANGLE動作の準備完了を意味しない。
実機GPU初期化・WebGL・KOOVの受け入れ条件が満たされるまで`false`を維持する。

## Chrome 154.0.8037.58 の過去記録

Chrome `154.0.8037.58`用のPhase 5 runtime artifactを使い、新規の隔離test
copyで実機確認を開始した。Phase 3C preflightはexit `0`、
`FINAL_STATE=completed-dry-run`、`REAL_SIGNING_PERFORMED=false`、
`CHROME_LAUNCHED=false`となった。その後、Apple Development署名とdeep strict
verification、Chrome起動、Intel HD Graphics 5000 / Metalのadapter選択まで
成功した。Case BとCase CはGPU初期化で停止した。

両ケースで次の順序を確認した。

1. Intel HD Graphics 5000 / Metalをadapterとして選択
2. `Initialization of all (1) EGL display types failed`
3. `GLDisplayEGL::Initialize failed`
4. GPU process終了
5. `--use-gl=disabled`へfallback

両ケースの`stderr.log`には、このEGL failure、`GLDisplayEGL::Initialize failed`、
GPU process終了の系列が繰り返し記録された。これはstderrの観測結果であり、保存した
未decode traceから導いた所見ではない。

Case Cの追加引数は`--disable-angle-features=requireGpuFamily2`だけである。GPU
processへ引数が届いたことは確認したが、ANGLEのfeature overrideが認識されたことや、
初期化成功を示す証拠ではない。

### `.58`の入力と証跡

| 項目 | 記録 |
| --- | --- |
| attempt | `attempt-20260929-193416` |
| Chrome | `154.0.8037.58` |
| runtime artifact | `angle-macos-x86_64-chrome-154.0.8037.58-angle-1ff8799c-36545744638` |
| artifact digest | `sha256:76a4a04c342edfb263cf4d65157e9a5d5ebfc5c5331d9c896a4614115e89b379` |
| manifest SHA-256 | `c929c2fc2dcae41007599bbb2b86dd8daf7b923a868b85c1e7a2d5d2df12b64e` |
| ANGLE revision | `1ff8799c596d4fc9acea28343610b1f33650a6fa` |
| runtime CI | [`36545744638`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36545744638) / success |
| VM observation | [`36549980089`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36549980089) / success |
| Phase 3B diagnostic change CI | [`36566498600`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36566498600) / success; Phase 3B fixture exit `0`, release-artifact fixture exit `0`, combined exit `0`; no skipped fixtures found |
| preflight | `completed-dry-run`; signing was not performed by preflight |
| signing | new test copy only; receipt schema `phase3-angle-signing-receipt-v3`; deep strict verification passed |
| post-run verification | signed test copy passed final `codesign --verify --deep --strict` |
| source / retained records | source Chrome remained `154.0.8037.58`; source app and retained retry/evidence were unchanged |

初回のCase B観測は親プロセスの保持が不十分で証拠が incomplete だったため、以下の
結論はlive repeatの`case-b-live`と`case-c-live`を基礎にする。

保存した主な結果ファイルは、`run-metadata.txt`、`stderr.log`、
`chrome-gpu-startup-trace.json`、`chrome-log-extract.txt`、
`gpu-processes.txt`、`load-evidence.txt`である。`chrome-gpu-startup-trace.json`は
Case B/Cとも作成されたが、当時は明示的なJSON指定がなく、`.json`という拡張子に
かかわらず`file`ではopaque dataと判定された。これは既定のproto系traceとして扱い、
内容をdecodeしていない。次回の診断モードでは`--trace-startup-format=json`を要求し、
実行後に実際の出力がJSONとして完全かを検証する。JSONは読みやすい一方、ブラウザが
traceのfinalization前に終了すると欠落または切断され得るため、要求フラグやファイルの
存在だけではJSON出力の成立を示さない。stderrと通常のログ・プロセス証拠はtraceとは
独立に取得する。この文書では保存済みtraceの存在だけを記録し、
traceからの個別の所見は主張しない。公開文書には個人情報、署名
identity、profile path、絶対パス、raw logを記録しない。

### JSON startup trace diagnostic retry

Phase 3B CI run `36566498600`の成功後、既存の署名済み`.58` test copyを使い、Case Bを
`--diagnostic-gpu-startup`付きで1回実行した。run metadataはChrome `154.0.8037.58`、
ANGLE revision `1ff8799c596d4fc9acea28343610b1f33650a6fa`、release manifest SHA-256
`c929c2fc2dcae41007599bbb2b86dd8daf7b923a868b85c1e7a2d5d2df12b64e`を記録し、
`--trace-startup-format=json`を含んでいた。traceはJSONとしてparseでき、`traceEvents`
は3,001件だった。GPU/startupカテゴリとGPU初期化イベントを含む一方、ANGLEの直接ロードを
証明するイベントは確認できなかった。stderrにはtrace consumerのack timeoutも記録されて
いるため、JSONとして妥当であることとtraceが完全であることは区別する。

stderrはIntel HD Graphics 5000 / Metalのadapter選択後にEGL初期化失敗、
`GLDisplayEGL::Initialize failed`、GPU process終了を記録した。GPU初期化が通らなかったため、
WebGLとKOOVには進んでいない。replacement dylibの直接ロードも未確認である。

その後の読み取り専用確認で、source Chromeとtest copyのFramework `Current`がともに
`154.0.8037.59`を指していた。結果収集スクリプトはmanifestの`.58`記録とFramework versionの
不一致を検出して停止した。起動stderrにはChromeからGoogleUpdaterの`--wake-all`子プロセスが
開始された記録があるが、それが後のversion変更を実行したことまでは立証できない。従って、
今回のCase Bログは起動時metadataと失敗系列の記録として保持するが、後から収集できなかった
直接load証拠や、現在の`.59` bundleを使う追加試験には流用しない。`.58`向けの再試行には、
Chrome versionとFramework versionを固定した新しい入力・isolated test copyが必要である。

### `.58`段階別判定

| 段階 | 判定 | 根拠 |
| --- | --- | --- |
| ANGLEロード | PENDING | Case B/Cの`load-evidence.txt`はいずれも直接dylib load evidenceなし。`gpu-processes.txt`もcollector時点でmatching GPU processなし。`lsof`、`vmmap`、collectorはいずれも両replacement dylibの直接ロードを証明しなかった。ロード済みとも未ロードとも断定しない |
| GPU初期化 | BLOCKED | Case B/CともEGL初期化失敗、GPU process終了、disabled fallback |
| WebGL | PENDING | GPU初期化失敗の停止条件により未実施 |
| KOOV | PENDING | WebGL成功前のため未実施 |

VMではdynamic側で両replacement dylibのGPU相関loadを確認し、EGL failure=true、
GPU fallback=trueだった。stock側はEGL failure=false、GPU fallback=trueで、
dynamic/stockともWebGL context/drawは未達（`context-null`）だった。VMはApple
Paravirtualized Graphics Deviceであり、Intel HD Graphics 5000実機の代替ではない。

## 未解決リスク

- 実機でreplacement dylibがロードされたかを直接証明できていない。
- EGL失敗の原因が、Family 1 availability gate、runtime patch、Metal初期化、
  またはそれらの組み合わせのどこにあるかは未分離である。
- runtime patchは`newCommandQueue`直後のnil guardを追加するだけで、Family 1
  availability gateを迂回しない。
- manifestの`RUNTIME_OPT_IN`は`--disable-angle-features=requireGpuFamily2,requireMsl21`
  を記録するが、Case Cスクリプトは`requireGpuFamily2`だけを指定する。
  固定revisionで`requireMsl21`の存在と効果は未確認である。
- WebGL描画、GPU安定性、性能、KOOV連携は未判定である。

`RUNTIME_DEVICE_READY=false`は、CI artifactを未署名・実機起動前の状態で
保持する境界値である。今回のtest copyで署名・起動した事実や、実機でGPU初期化が
成功したことを意味しないため、manifestの値は変更しない。

## 次の判断ツリー

### 1. 読み取り専用分析

既存の`chrome-gpu-startup-trace.json`、`stderr.log`、`chrome-log-extract.txt`、
`run-metadata.txt`、`gpu-processes.txt`を用いて、次を時系列で照合する。

- GPU process生成からEGL failure、fallback、終了までの順序
- Case B/Cの引数差分と、既存証拠が`requireGpuFamily2`の内部認識を示しているか
- 既存traceやstderrがdynamic ANGLEのロードを示すか。引数の伝播、traceの存在、JSON要求だけではロード証拠にしない
- VMで直接loadが証明された経路と、実機で証明できなかった観測点

### 2. 診断証拠の改善

collectorはcommit `5cb3dbf`でGPU process type基準に修正し、専用/汎用helperを扱う
focused fixtureがpassした。Pinned Phase 3B CI成功後、両replacement dylibの直接ロードと
feature override認識を同時に記録できるか、別途承認された新しい実機retryで確認する。
コマンドライン引数だけをロード証拠として扱わない。

### 3. ソース診断とCI/VM確認

固定ANGLE revisionのFamily 1 gateと、runtime patchのnil guardの到達順序をソース
レベルで確認する。修正を行う場合は、まずtargeted test、static audit、artifact
validation、VM観測で確認する。`requireMsl21`は実装と効果を確認するまで追加しない。

### 4. 再度の実機試行

collector修正のPinned Phase 3B CI成功後、別途承認を得て新しいisolated test copyで
実機試行を行う。GPU初期化成功後にだけWebGLへ進み、WebGLの
context生成と描画成功後にだけKOOVへ進む。各段階の失敗では結果を保全して停止する。

## 状態の境界

`.58`の過去試行と最新`.59`試行は別のtest copy/evidenceである。`.59`ではtest copy準備、
署名検証、Chrome起動、adapter選択、GPU初期化失敗の観測まで完了した。実機WebGLとKOOVの
実験結果は存在しない。この記録は新しい実機試行を自動承認せず、過去の`.57`/`.58`記録や
retry/evidenceを上書きしない。
