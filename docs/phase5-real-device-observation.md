# Phase 5 実機観測記録

更新日: 2026-09-29

## 現在の結論

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

## 入力と証跡

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

上記のJSON要求を付けたChrome実行は、この記録の時点ではまだ行っていない。

## 段階別判定

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

必要な場合だけ、既存source Chrome・retry・保存済みevidenceを変更しない一時的な
診断手段で、両replacement dylibの直接ロードとfeature override認識を同時に観測
できるかを確認する。コマンドライン引数だけをロード証拠として扱わない。

### 3. ソース診断とCI/VM確認

固定ANGLE revisionのFamily 1 gateと、runtime patchのnil guardの到達順序をソース
レベルで確認する。修正を行う場合は、まずtargeted test、static audit、artifact
validation、VM観測で確認する。`requireMsl21`は実装と効果を確認するまで追加しない。

### 4. 再度の実機試行

CI/VMの証拠が揃い、実機用入力と観測方法が固定された後に、別途承認を得て新しい
isolated test copyで実機試行を行う。GPU初期化成功後にだけWebGLへ進み、WebGLの
context生成と描画成功後にだけKOOVへ進む。各段階の失敗では結果を保全して停止する。

## 状態の境界

今回の実機試行で完了したのは、`.58`入力のtest copy準備、署名検証、Chrome起動、
adapter選択、GPU初期化失敗の観測である。WebGLとKOOVの実験結果は存在しない。
この記録は新しい実機試行を自動承認せず、既存の`.57`記録やretry/evidenceを上書きしない。
