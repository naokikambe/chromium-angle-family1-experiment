# Phase 5 実機観測記録

更新日: 2026-10-03

## 最新の実機結論: Chrome 154.0.8037.97（fallback Case C/WebGL・KOOV URL境界、2026-10-03）

`.97`の正確なfallback runtime artifactを新しい隔離test copyへ投入し、Apple
Development署名とdeep strict verificationを通過させた。`requireGpuFamily2`を
明示的に無効化したIntel HD Graphics 5000では、`eglInitialize`、Metal backendの
初期化、非WebGLのES3要求からES2へのfallback、WebGL1 context生成と最小clear描画
まで成功した。WebGL2は`context-null`だったが、fallbackはWebGL contextをES2へ
降格しない設計であるため、WebGL1成功とは独立したES3能力境界として記録する。

初回のfallbackなしCase Cでは、`max_es_version=2.0`に対するES3 context要求の
`0x3098=3`（`EGL_CONTEXT_CLIENT_VERSION`）が`EGL_BAD_ATTRIBUTE`になり、ES2の
同じ属性`0x3098=2`は成功した。したがって、Intel HD 5000上で拒否された属性は
`EGL_CONTEXT_CLIENT_VERSION`の値3と特定済みである。fallback適用後はこの非WebGL
GPU情報context境界を越えてWebGL smokeへ進めた。

### 現在の判定: WebGL1は検証可能、KOOV document到達とWebGL2は未完了

| 境界 | 判定 | 根拠 |
| --- | --- | --- |
| ANGLEロード | PASS | WebGL実行中の同一GPU helper processについて`lsof`と`vmmap`の双方がtest copy内の`libEGL.dylib`/`libGLESv2.dylib`を指示 |
| GPU/EGL display初期化 | PASS（fallback Case C） | `require_gpu_family2 enabled=false has_override=true`、Metal初期化成功、`eglInitialize_return_success`、`max_es_version=2.0` |
| 非WebGL GPU context初期化 | PASS（fallback実験） | ES3要求をES2 frontendへ切り替え、`context_initialize_success`と`family1_es3_to_es2_fallback`を記録 |
| WebGL1 | PASS | page loaded、WebGL1 context、最小clear描画がすべて`true`。rendererはIntel HD Graphics 5000 |
| WebGL2 | PENDING（能力境界） | contextは`null`。ES3要求の`0x3098=3`拒否を独立に記録し、ES2へ暗黙降格していない |
| KOOV App ID方式 | BLOCKED（起動境界） | `Local State.app_shims`を含む隔離コピーでも`--app-id`はpage targetを作らず、service workerのみ。GPU/EGL失敗ではない |
| KOOV URL app-mode | BLOCKED（document到達） | page targetのURL metadataは現れたが、CDP上のdocumentは`about:blank`のまま。`Page.navigate`もtimeoutし、canvasは0 |
| ES3→ES2 fallback実験 | PASS（実機WebGL1まで） | `.97` exact artifactでGPU/EGL継続、WebGL1 context/draw成功。WebGL2は対象外のまま |

今回のソース確認では、macOSのChromium側でGLES3非対応時の自動fallbackが既定で
無効になり、`--disable-angle-features`だけではChromeのES3要求をES2へ変更しない
ことが分かった。そこで、Family 1実験に限定した
`patches/phase5-metal-family1-context-es2-fallback.patch`を追加した。このpatchは
最大対応versionがES2で、要求がES3、かつWebGL contextではない場合だけGPU情報用
contextをES2 frontendへ切り替える。WebGL contextを対象外とするためWebGL2を暗黙に
ES2へ降格せず、WebGL1を含む後続の挙動はCI/実機で別途確認する。

| fallback実験の証跡 | 値 |
| --- | --- |
| patch SHA-256 | `7bd8a40eaa6311c4ca37ebd68c19ab3d9822b936000e38dbadea70b92667a014` |
| compile-time define | `ANGLE_PHASE5_METAL_FAMILY1_ES2_FALLBACK_EXPERIMENT` |
| 適用範囲 | Family 1 experiment artifactの明示opt-inのみ。通常artifact・実機準備済み判定には反映しない |
| 現在のmanifest境界 | 正確な`.97` fallback artifactはCI build・manifest検証済み。実機test copyは署名・起動済みだが、artifactの`RUNTIME_DEVICE_READY=false`は変更しない |

正確なChrome `.97` / ANGLE `e12217f3...` fallback artifactのCI build・manifest検証と、
承認済みの実機test copy署名・配置・Chrome起動・WebGL1 smokeは完了した。KOOVはURL
app-modeでpage targetのURL metadataまで確認したが、documentは`about:blank`のままであり、
画面描画・基本操作・認証・保存・USB/Bluetooth連携は未実施である。

### 現行`.97` CI入力とVM availability boundary

| 対象 | 証跡・結果 |
| --- | --- |
| `.97` runtime build | [`36964161986`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36964161986) / success |
| artifact | `angle-macos-x86_64-chrome-154.0.8037.97-angle-e12217f3-family1-experiment-36964161986` / GitHub digest `sha256:cf4e9c149e387f94c9f5b9401802f6255c8bc0426d353d73b0d6981c390782ef` |
| manifest | SHA-256 `99f3b38400814b1c7919008a26b62ba1a6328171e1dcedd5540d1de165628603`; ANGLE `e12217f3e133cb1029b050d893b1806d141483be`; `RUNTIME_DEVICE_READY=false` |
| `.97` VM observation | [`36966677898`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36966677898) / CfT archive HTTP 404でbrowser起動前に停止 |
| `.97` device impact | test copy準備・署名・Chrome起動・Case B/CのGPU/EGL診断・WebGL1 smokeを実施。KOOV、xattr操作、artifact置換は未実施 |

CfT known-good indexに`.97`がないため、`.97` artifactをそのままVMへ渡すことはできなかった。workflowには、CfTに存在する同系列`.92`とANGLE `802a8704ca940b633b731493ee192e0661eb8cdd`を`cft_compatibility=true`で明示的にbuildするVM専用経路を追加した。このcompatibility artifactは実機用ではなく、test-copy準備でも拒否する。

### CI run 37009376538 の再構築artifactによる実機再確認（2026-10-02）

前回と同じChrome `.97` / ANGLE revisionのfallback artifactを、CI run
`37009376538`で再構築し、新しいtest copyだけへ適用した。既存source Chrome、保存済み
retry/evidence、前回artifactは変更していない。CI artifactの`RUNTIME_DEVICE_READY=false`
は維持し、実機では署名済みtest copyを使用した。

| 対象 | 証跡・結果 |
| --- | --- |
| runtime CI / artifact | [`37009376538`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/37009376538) / success; `angle-macos-x86_64-chrome-154.0.8037.97-angle-e12217f3-family1-experiment-37009376538` |
| artifact digest | `sha256:247f0ee4be552c8e4f8790db04c39753631abc62312b78318dcdd5a80808652d` |
| manifest / ANGLE | manifest SHA-256 `97b03d254b67b604173436bdf64a9c09c93f61d468b66880b36508c5e8d3bab2`; ANGLE `e12217f3e133cb1029b050d893b1806d141483be` |
| runtime libraries | `libEGL.dylib=44116767b6d4d02362b2dd117cf16af2e719ef143b573f9a52b4837c1415b470`; `libGLESv2.dylib=750d1a917cb88235d6e7cc0b2483b44800ee3cb39261dc21535d70ef60be0913` |
| runtime profile | `phase5-metal-family1-family1-experiment-v1`; context fallback patch applied; `RUNTIME_DEVICE_READY=false` |
| Case C GPU/EGL | `metal_device_selection`、command queue、format table、shader library、render utils、display initialize、`eglInitialize`が成功。`max_es_version=2.0`、ES3要求3回をES2へfallbackし、`context_initialize_success`を3回記録 |
| Case C context analyzer | `EGL_BAD_ATTRIBUTE_COUNT=0`; `FAMILY1_ES3_TO_ES2_FALLBACK_COUNT=3`; `CONCLUSION=no-egl-bad-attribute-observed` |
| WebGL smoke | page loaded、WebGL1 context、最小clear描画は成功。WebGL2は`context-null` |
| WebGL context analyzer | 5 calls、ES3要求4回、ES2要求1回。`EGL_BAD_ATTRIBUTE_COUNT=2`、`CONTEXT_ERROR_ATTRIBUTE_KEYS=0x3098`、`CONTEXT_ERROR_ATTRIBUTE_VALUES=3`、`CONTEXT_INITIALIZE_SUCCESS_COUNT=4` |
| renderer / version | `ANGLE (Intel, ANGLE Metal Renderer: Intel HD Graphics 5000, Unspecified Version)` / `WebGL 1.0 (OpenGL ES 2.0 Chromium)` |
| ANGLEロード | WebGL実行中の同一GPU helper processのraw `lsof`/`vmmap`が、test copy内の`libEGL.dylib`/`libGLESv2.dylib`を両方指示 |
| KOOV | App ID方式はpage target未到達。URL app-modeはtarget metadataのみで、document到達・画面描画・基本操作は未実施 |

この再確認により、`EGL_BAD_ATTRIBUTE`はWebGL2のES3要求に限って再現し、拒否された
属性は`EGL_CONTEXT_CLIENT_VERSION (0x3098)`の値3であることを、CI run 370のartifact
でも確認した。非WebGLのGPU情報contextはfallbackでES2へ継続でき、WebGL1はES2として
描画できるが、WebGL2をES2へ暗黙降格していない。標準CfT probeは`.97`公開archiveの
HTTP 404で起動前に停止したため、WebGL結果は署名済みtest copyを直接起動した実機
証跡として扱う。

### CI run 37009376538 artifactによるKOOV起動境界の実機観測（2026-10-03）

WebGL1受入れ後の最小KOOV確認として、同じ署名済み`.97` test copyを使い、既存source
Chromeと保存済みretry/evidenceを変更せず、新規の隔離profileを2種類だけ作成した。
認証情報の入力、保存操作、USB/Bluetooth接続は行っていない。

| 対象 | 結果 |
| --- | --- |
| 入力artifact | CI run `37009376538`の`angle-macos-x86_64-chrome-154.0.8037.97-angle-e12217f3-family1-experiment-37009376538`; artifact digest `sha256:247f0ee4be552c8e4f8790db04c39753631abc62312b78318dcdd5a80808652d` |
| ANGLE revision / manifest | `e12217f3e133cb1029b050d893b1806d141483be`; manifest SHA-256 `97b03d254b67b604173436bdf64a9c09c93f61d468b66880b36508c5e8d3bab2` |
| App ID方式 | `--app-id=kpmcfooelenggiklfmbljpognolignpg`。`Local State.app_shims`の登録を含めてもpage targetは生成されず、service workerのみ。ブラウザ終了は正常 |
| URL app-mode | 新規空profileで同URLのpage target metadataを取得したが、CDPのdocumentは`about:blank`、canvasは0。`Page.navigate`はtimeoutし、KOOV画面の描画・基本操作には到達しなかった |
| 通常タブ / 最終URL / 独立probe | `/app/welcome`とHTTPリダイレクト先の`https://www.koov.io/`を`--new-window`で直接指定しても、実documentへのnavigation eventなし。CDP `Page.navigate`もtimeoutした。空document上の独立WebGL1 probeはIntel HD 5000/ANGLEで成功、WebGL2は失敗したが、KOOVの結果とは扱わない |
| ANGLE / GPU / EGL | URL app-modeの同一GPU helper processでreplacement `libEGL.dylib`/`libGLESv2.dylib`を`lsof`/`vmmap`確認。Metal初期化、`eglInitialize_return_success`、ES3要求からES2へのfallbackとcontext初期化成功を確認 |
| 後処理 | テストChromeの対象PIDと隔離profileを検証してTERM終了。終了後の対象profileプロセスは0件 |
| 境界 | `RUNTIME_DEVICE_READY=false`は変更しない。source Chrome、既存profile、既存artifact、保存済みretry/evidenceは変更していない |

この観測により、ANGLE/GPU/EGLはKOOV起動試行中も継続して動作した。一方、旧KOOV App Shimを
`--app-id`で起動する経路はChrome 154の隔離profileでpage targetを作らず、URL app-modeも
target metadataの後にdocumentへ遷移しなかった。従って、KOOVのcanvas/WebGL描画、画面操作、
認証後の機能、保存、USB/Bluetooth連携は未判定であり、次の承認境界として残る。
なお、同URLへの読み取り専用HTTP確認は`https://www.koov.io/`へ到達したため、今回の未到達は
サーバーURLの不存在ではなく、実機test copy内のdocument navigation境界として扱う。

### `.92` compatibility VM観測（実機入力ではない）

`.97`のCfT配布境界を切り分けるため、VM専用compatibility modeでChrome
`.92`とANGLE `802a8704ca940b633b731493ee192e0661eb8cdd`をbuildし、Phase 3D
観測まで完了した。

| 対象 | 証跡・結果 |
| --- | --- |
| runtime CI / artifact | [`36968691106`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36968691106) / success; `angle-macos-x86_64-chrome-154.0.8037.92-angle-802a8704-family1-experiment-36968691106` |
| artifact digest | `sha256:7e94b75d860be33c7451c731f42c6b438a3385b90e97d4122e5edb8c73715250` |
| manifest | SHA-256 `747ea00759790040bdbef84c947610cf63c2078880249aadf36dd83ae74aef2c`; `CFT_COMPATIBILITY=true`; `RUNTIME_DEVICE_READY=false` |
| VM observation / diagnostics | [`36970918937`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36970918937) / success; digest `sha256:4275c91c7384791bea90db704765e8283dcfda005bbc24330303f91119a987cc` |
| VM result | dynamic/stockともEGL display初期化成功、GPU fallback、WebGL1/2 context未作成・draw未達。dynamicの直接context traceは`EGL_BAD_ATTRIBUTE attribute=0x3098 value=3`、ES2要求は成功。 |

この結果はApple Paravirtualized Graphics Device VMに限定され、Intel HD Graphics
5000上の実機結論ではない。実機で使用する入力は引き続き正確な`.97` artifactであり、
`.92` compatibility artifactの署名・配置・Chrome起動・WebGL・KOOVへの使用は行わない。

### ES3→ES2 fallback experimentの`.92` VM結果（2026-10-02）

Family 1とcontext fallbackを同時に有効化した`.92` compatibility artifactを、
Phase 3D VMで読み取り専用に観測した。これはfallback実験のCI/VM受入れ記録であり、
Intel HD Graphics 5000実機の結果ではない。

| 対象 | 証跡・結果 |
| --- | --- |
| runtime CI / artifact | [`36984467242`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36984467242) / success; `angle-macos-x86_64-chrome-154.0.8037.92-angle-802a8704-family1-experiment-36984467242` |
| artifact digest | `sha256:7f01d71d8638017cc2a6ec9240c5c3a3a784668c9510d293652566ce4cf7fad6` |
| manifest | SHA-256 `877027a4b176d7ce8bbc295b77cab145cc315a0c4e3858773b81d90b0f421661`; ANGLE `802a8704ca940b633b731493ee192e0661eb8cdd`; `CONTEXT_ES2_FALLBACK_EXPERIMENT=true`; `CFT_COMPATIBILITY=true`; `RUNTIME_DEVICE_READY=false` |
| VM observation / diagnostics | [`36987425607`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36987425607) / success; diagnostics digest `sha256:1ba3b9e69062385d4d7e3623a56f34fd368ae5a26f7a6ab37e540dc5f8b6f37e` |
| fallback trace | `FAMILY1_ES3_TO_ES2_FALLBACK_COUNT=4`; `eglInitialize` failure `false`; GPU disabled fallback `false` |
| dynamic WebGL smoke | page loaded `true`; WebGL1 context `true`; draw `true`; WebGL2 context `false`; `webgl2_error=context-null`; rendererはApple Paravirtual device |
| stock control | WebGL1/WebGL2 context `false`; draw `false`; GPU disabled fallback `true` |

このVMでは、非WebGLのES3要求4件がES2へfallbackし、WebGL1のcontext生成と描画が
成功した。一方、WebGL2要求はfallback対象外のためcontext未作成である。したがって、
「VM上のWebGL1経路は検証可能」は確認できたが、「Intel HD Graphics 5000上のWebGLが
検証可能」または「WebGL2が利用可能」とは結論しない。正確な`.97` fallback artifactの
CI build・manifest検証まで完了しており、次は別途承認された実機でまずGPU/EGL、次に
WebGL1だけを段階的に確認する。

### 正確な`.97` fallback artifact CI結果（2026-10-02）

Chrome `.97` / ANGLE `e12217f3...`へ同じfallback patchを適用したruntime artifactを
CIでbuildし、artifactとmanifestを読み取り専用で検証した。これは実機への配置・署名・
起動を意味しない。

| 対象 | 証跡・結果 |
| --- | --- |
| runtime build | [`36988193107`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36988193107) / success |
| artifact | `angle-macos-x86_64-chrome-154.0.8037.97-angle-e12217f3-family1-experiment-36988193107` / GitHub digest `sha256:984225daa95e44dd621dee93e604cce9fea414015287ba1b3fa7eb2cb7ff7bc7` |
| manifest | SHA-256 `73e94ae3b306086201401bfc31540296362aac5505d4af478537abed6391e961`; Chrome `154.0.8037.97`; Chromium `b510e9d7cd3a2fbd78d0ddc42234103206c5f78d`; ANGLE `e12217f3e133cb1029b050d893b1806d141483be` |
| fallback provenance | `CONTEXT_ES2_FALLBACK_EXPERIMENT=true`; patch SHA-256 `7bd8a40eaa6311c4ca37ebd68c19ab3d9822b936000e38dbadea70b92667a014`; `CFT_COMPATIBILITY=false` |
| device boundary | `RUNTIME_DEVICE_READY=false`; artifactのdownload、manifest/dylib hash検証のみ実施。署名、test copy配置、Chrome起動、WebGL、KOOVは未実施 |

exact `.97`のCfT archiveはHTTP 404のため、同じ`.97` artifactをVMで起動する観測は
できていない。したがって、`.92` compatibility VMのWebGL1結果を`.97`の実機結果へ
拡張せず、実機では正確な`.97` fallback artifactを入力としてGPU/EGLからWebGL1まで
別途確認した。次段階のKOOVはWebGL1結果のレビューと別の人間承認を要する。

### `.97` Intel HD Graphics 5000実機 Case B/C（2026-10-02）

CIで生成した正確な`.97` artifactを使い、既存source Chrome、保存済みretry/evidenceを変更せず、新規test copyだけで確認した。Case B/CともWebGLページ操作とKOOV操作は行っていない。

| 対象 | 証跡・結果 |
| --- | --- |
| runtime CI / artifact | [`36964161986`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36964161986) / success; `angle-macos-x86_64-chrome-154.0.8037.97-angle-e12217f3-family1-experiment-36964161986` |
| artifact digest | `sha256:cf4e9c149e387f94c9f5b9401802f6255c8bc0426d353d73b0d6981c390782ef` |
| manifest / ANGLE | manifest SHA-256 `99f3b38400814b1c7919008a26b62ba1a6328171e1dcedd5540d1de165628603`; ANGLE `e12217f3e133cb1029b050d893b1806d141483be` |
| runtime libraries | `libEGL.dylib=44116767b6d4d02362b2dd117cf16af2e719ef143b573f9a52b4837c1415b470`; `libGLESv2.dylib=d909e2dfbcda92ccae5842740d87f0108cb55cda99f3d3ebfe538ff9c476e2e0` |
| preflight / signing | preflight dry-run completed; new test copyのみApple Development署名、deep strict verification passed。`RUNTIME_DEVICE_READY=false`のmanifestは変更していない |
| Case B | `require_gpu_family2 enabled=true has_override=false`。`eglGetPlatformDisplay_return_display`後、Family 2 gateで`eglInitialize`が`EGL_NOT_INITIALIZED`となりGPU processが終了 |
| Case C | `--disable-angle-features=requireGpuFamily2`を指定。`require_gpu_family2 enabled=false has_override=true`、`eglInitialize_return_success`まで到達 |
| adapter / capability | `Selected adapter: Intel HD Graphics 5000`; `max_es_version_gpu_family4_or1=false`; `max_es_version=2.0` |
| context trace | 6 calls、ES 3.0要求4回、ES 2.0要求2回。ES 3.0の4回は`0x3098=3`で`EGL_BAD_ATTRIBUTE`、ES 2.0の2回は`0x3098=2`で`context_initialize_success` |
| 非version属性 | ES 3.0/ES 2.0で同一。analyzerは`CONCLUSION=egl-bad-attribute-from-context-error-attribute`、`CONTEXT_ERROR_ATTRIBUTE_KEYS=0x3098`、`CONTEXT_ERROR_ATTRIBUTE_VALUES=3` |
| JSON trace | parse成功、`traceEvents=3619` |

Case BはFamily 2 availability gateによる初期化失敗、Case Cはそのgateを明示的に無効化した後のcontext version境界を示す。Case Cで観測した`EGL_BAD_ATTRIBUTE`は、属性列の他のキーではなく、要求ES versionを表す`EGL_CONTEXT_CLIENT_VERSION (0x3098)`の値3に対応する。ES2で同じ非version属性列が成功したため、少なくともこのtraceでは非version属性やEGL config選択を原因とは判定しない。

`load-evidence.txt`は同一GPU PIDのreplacement dylib直接ロードを確定する記録になっていないため、ANGLEロードの直接証明としては使用しない。stderrのANGLE計装、adapter名、EGL/context traceは有効な一次診断証拠として保持する。

### `.97` fallback実機 WebGL1 smoke（2026-10-02）

上記の初回Case CでES3 context拒否を確認した後、CIで生成した正確な`.97`
fallback artifactを新規test copyへ適用し、同じ実機でWebGL smokeを実施した。
source Chrome、保存済みretry/evidence、既存artifactは変更していない。WebGL用の
一時profileとloopback DevToolsだけを使用し、KOOVや既存profileには触れていない。

| 項目 | 実機結果 |
| --- | --- |
| 入力artifact | `angle-macos-x86_64-chrome-154.0.8037.97-angle-e12217f3-family1-experiment-36988193107` |
| artifact digest | `sha256:984225daa95e44dd621dee93e604cce9fea414015287ba1b3fa7eb2cb7ff7bc7` |
| manifest / ANGLE | manifest SHA-256 `73e94ae3b306086201401bfc31540296362aac5505d4af478537abed6391e961`; ANGLE `e12217f3e133cb1029b050d893b1806d141483be` |
| GPU/EGL | `eglInitialize_return_success`; Metal device selection、command queue、format table、shader library、render utilsが成功 |
| fallback | `max_es_version=2.0`; 非WebGL ES3要求をES2へfallbackし、`context_initialize_success`を記録 |
| ANGLEロード | WebGL実行中の同一GPU helper processの`lsof`/`vmmap`で、test copy内の`libEGL.dylib`と`libGLESv2.dylib`を両方確認 |
| WebGL page | `page_loaded=true` |
| WebGL1 | `context_created=true`; `draw_operation_completed=true` |
| WebGL2 | `context_created=false`; `webgl2_error=context-null` |
| renderer / version | `ANGLE (Intel, ANGLE Metal Renderer: Intel HD Graphics 5000, Unspecified Version)` / `WebGL 1.0 (OpenGL ES 2.0 Chromium)` |
| KOOV | 未実施。WebGL1結果のレビューと別途承認が必要 |

WebGL smokeのstderrを同じanalyzerへ通した結果は、`CONTEXT_CALL_COUNT=5`、
`ES3_CALL_COUNT=4`、`ES2_CALL_COUNT=1`、`CONTEXT_VERSION_REJECTION_COUNT=1`、
`CONTEXT_ERROR_ATTRIBUTE_KEYS=0x3098`、`CONTEXT_ERROR_ATTRIBUTE_VALUES=3`、
`FAMILY1_ES3_TO_ES2_FALLBACK_COUNT=3`、`CONTEXT_INITIALIZE_SUCCESS_COUNT=4`、
`CONCLUSION=egl-bad-attribute-from-context-error-attribute`だった。これはWebGL2の
ES3要求をfallback対象外として記録したものであり、WebGL1のES2 context/draw成功と
矛盾しない。

collectorの総括`load-evidence.txt`はobserver不完了のため保守的な未確定表示だが、
WebGL実行中に取得した同一GPU helper processのraw `lsof`/`vmmap`がより直接的な
証拠である。`RUNTIME_DEVICE_READY=false`はCI artifactが未署名・実機起動前に
生成された境界値であり、今回のtest copy署名・起動・WebGL1成功によってmanifestを
変更しない。

### `.97` fallback実機 `chrome://gpu`確認（2026-10-02）

WebGL1 smokeとは別の新規一時profileで同じ署名済みtest copyを起動し、loopback
DevTools経由で`chrome://gpu`のshadow DOM本文を保存した。source Chrome、既存profile、
既存artifactは変更していない。

| `chrome://gpu`項目 | 結果 |
| --- | --- |
| Graphics Feature Status | Canvas、Compositing、Rasterization、Video Decode/Encode、WebGL、WebGPUが`Hardware accelerated`; OpenGLは`Enabled` |
| Direct Rendering Display Compositor | `Disabled`。今回のWebGL1描画成功とは別の表示合成機能の状態 |
| GPU / backend | Intel HD Graphics 5000; `GL implementation parts=(gl=egl-angle,angle=metal)`; `Display type=ANGLE_METAL` |
| GL renderer/version | `ANGLE (Intel, ANGLE Metal Renderer: Intel HD Graphics 5000, Version 15.7.9)` / `OpenGL ES 2.0` |
| ANGLE feature | `requireGpuFamily2`は`Disabled`（明示overrideと一致） |
| GPU process crash count | `0` |
| Problems Detected | Intel/Mac向けMSAA、stencil、float format等の既知workaroundを表示。今回のGPU crashやEGL初期化失敗を示す項目は確認されない |
| ANGLEロード | 同じGPU helper processの`lsof`/`vmmap`でreplacement `libEGL.dylib`/`libGLESv2.dylib`を確認 |

`chrome://gpu`の表示はWebGL1 smokeのcontext/draw成功を補強するが、WebGL2の利用可能性
やKOOV動作を証明するものではない。ページ本文・JSON trace・GPU process raw証跡は
新規`case-e-gpu-page`結果ディレクトリに保存した。

### `.59`実機の過去記録（最新結論ではない）

`.59`用runtime artifactのbuild、Phase 3D VM観測、実機Case BのGPU startup trace取得まで完了した。
CI runの成功は診断workflowが完了した意味であり、GPU初期化・WebGLが成功した意味ではない。

実機ではIntel HD Graphics 5000 / Metal adapter選択後にEGL初期化が3回失敗し、各GPU processが終了した。
その後のGPU processは`--use-gl=disabled`で動作した。JSON traceは3,434 eventsを含み、
`gpu_init::SetupGLDisplayManagerEGL`を記録した。ANGLE replacement dylibの直接ロードは確認できず、
ロード済みとも未ロードとも判定しない。GPU初期化の停止条件により、実機WebGLとKOOVは実施していない。

新しいtest copyのpreflight、Apple Development署名、deep strict verification、Case B起動は完了した。
source ChromeとそのFrameworkは観測前後とも`154.0.8037.59`であり、既存retry/evidenceは変更していない。
起動時にGoogleUpdaterの`--wake-all`が開始・正常終了したが、この観測期間内のsource更新は確認されなかった。

### `.59`保存済み実機traceの読み取り専用再確認（2026-10-02）

既存の実機証跡を変更せず、`.59`系の保存済みstderrを今回追加したcontext
trace analyzerで再解析した。通常のCase B診断・live maps診断では、
`[ANGLE_PHASE5_LOAD] libEGL_loaded`の後にEGL display初期化失敗と
`GLDisplayEGL::Initialize failed`が記録され、`eglCreateContext`到達は0件、
`EGL_BAD_ATTRIBUTE`も0件だった。platform-display診断では
`eglGetPlatformDisplay_enter`の直後に
`eglGetPlatformDisplay_return_no_display`となり、`eglInitialize`と
`eglCreateContext`には到達していない。

従って、`.59`の保存済み実機証跡だけからは「どの属性が`EGL_BAD_ATTRIBUTE`になるか」は
判定できなかった。これは`.97` Case Cで解消され、次の実機診断で必要だった
`eglGetPlatformDisplay_return_display`、`eglInitialize_return_success`、続く
`context-trace-analysis.txt`が取得できた。`.97`でもWebGL/KOOVへ進む条件は別途未成立である。

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
| Phase 3B synthetic CI | [`36963092889`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36963092889) / success; diagnostics digest `sha256:0ce6b2e4e05e374fc5298dad50e5bdd6c765b701f09f2b370ea1ca401a905e3c`; fixture/release-artifact exit `0`; no skipped or unexpected diagnostics |
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

### `.97` Case C段階別判定

| 段階 | 判定 | 根拠 |
| --- | --- | --- |
| ANGLEロード | PENDING | dynamic-angle起動とANGLE計装は観測したが、終了後の`lsof`/`vmmap`収集が完了せず、同一GPU PIDによる両replacement dylibの直接ロード証拠は未確定 |
| GPU初期化 | BLOCKED | `eglInitialize`自体は成功したが、`max_supported=2.0`のためES 3.0 context要求が`EGL_CONTEXT_CLIENT_VERSION=0x3098, value=3`で`EGL_BAD_ATTRIBUTE`となり、GPU processが終了 |
| WebGL | PENDING | context失敗後の停止条件によりページ操作・WebGL1/2 context・drawは未実施 |
| KOOV | PENDING | WebGLの受入れ前であり、KOOV操作は未実施 |

ここでの`GPU初期化=BLOCKED`は、ANGLE display初期化が成功したことと、Chromeが必要とするES 3.0 contextを作成できないことを分けた判定である。属性原因の特定は完了したが、WebGLへ進むには、ES2 fallbackを採用するのか、ES3要求を抑制・変更するのかを別途設計・承認する必要がある。

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

- 初回のfallbackなしCase B/Cではreplacement dylibの同一GPU PID loadが未確定だった。fallback WebGL1試行では、WebGL実行中の同一GPU helper processについてraw `lsof`/`vmmap`が両replacement dylibを示した。過去記録の保守的な`load-evidence.txt`総括はそのまま保持する。
- `.97` Case BではFamily 2 availability gateが`eglInitialize`前の停止原因として確認できた。Case Cでそのgateを無効化するとdisplay初期化は成功したため、初期化失敗の最初の原因境界は分離できた。
- `.97` Case CではMetal capabilityが`max_es_version=2.0`であることを実機で確認した。ES 3.0要求時の`EGL_BAD_ATTRIBUTE`は`EGL_CONTEXT_CLIENT_VERSION (0x3098)`の値3と特定済みであり、非WebGL GPU情報contextだけをES2へ切り替えるfallback experimentを実機へ明示適用した結果、GPU/EGL継続とWebGL1 context/drawまで確認した。WebGL2、長時間安定性、性能、KOOVは未確定である。
- runtime patchは`newCommandQueue`直後のnil guardを追加するだけで、Family 1
  availability gateを迂回しない。
- manifestの`RUNTIME_OPT_IN`は`--disable-angle-features=requireGpuFamily2,requireMsl21`
  を記録するが、Case Cスクリプトは`requireGpuFamily2`だけを指定する。
  固定revisionで`requireMsl21`の存在と効果は未確認である。
- WebGL1の最小描画は成功した。WebGL2のES3能力、長時間安定性、性能、KOOV連携は未判定である。

`RUNTIME_DEVICE_READY=false`は、CI artifactを未署名・実機起動前の状態で生成した
ことを示す不変の境界値である。今回のtest copyで署名・起動し、実機GPU初期化と
WebGL1が成功しても、CI artifactのmanifest値は変更しない。

## 次の判断ツリー

### 1. 読み取り専用分析（属性原因の判定済み）

`.97` Case Cの`chrome-gpu-startup-trace.json`、`stderr.log`、`run-metadata.txt`、
`gpu-processes.txt`を用いた時系列照合は完了した。確定事項は次のとおりである。

- GPU process生成からEGL failure、fallback、終了までの順序
- Case B/Cの引数差分と、`requireGpuFamily2 enabled=false has_override=true`の内部認識
- `eglInitialize_return_success`後のES3/ES2 context差分、`0x3098=3`の`EGL_BAD_ATTRIBUTE`
- 既存traceやstderrがdynamic ANGLEのロードを示すか。引数の伝播、traceの存在、JSON要求だけではロード証拠にしない

### 2. 診断証拠の改善（ANGLEロードは実機raw証跡で確認済み）

collectorはcommit `5cb3dbf`でGPU process type基準に修正し、専用/汎用helperを扱う
focused fixtureがpassした。fallback WebGL1試行ではfeature override認識に加え、
WebGL実行中の同一GPU helper processの`lsof`/`vmmap`で両replacement dylibを確認済みで
ある。collectorのpost-run総括が保守的でも、コマンドライン引数だけでなくraw per-PID
証跡を根拠とする。追加retryはWebGL1のためには不要である。

### 3. ソース診断とCI/VM確認

固定ANGLE revisionのFamily 1 gate、`max_es_version`計算、context version拒否の到達順序は
ソースと`.97`実機traceで対応づけ済みである。追加したfallback experimentは、まずtargeted
test、static audit、artifact validation、VM観測で確認する。`requireMsl21`は実装と効果を
確認するまで追加しない。

### 4. WebGL以降の実機試行

fallback experimentを明示適用した実機で、GPU/EGL、WebGL1 context、最小drawまで成功した。
WebGL2は`context-null`を能力境界として記録し、KOOVはWebGL1結果のレビューと別途の
人間承認が成立するまで開始しない。次段階でも各段階の失敗では結果を保全して停止する。

## 状態の境界

`.58`/`.59`の過去試行と最新`.97`試行は別のtest copy/evidenceである。`.97` fallback
試行ではtest copy準備、署名検証、Chrome起動、Intel HD Graphics 5000のadapter選択、
`eglInitialize`成功、ES3 context拒否属性の特定、同一GPU PIDのANGLEロード証跡、WebGL1
context/drawまで完了した。WebGL2とKOOVは未完了であり、過去のretry/evidenceを上書きしない。
