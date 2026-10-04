# Phase 5 実機観測記録

更新日: 2026-10-04

## 2026-10-03以前の実機観測: Chrome 154.0.8037.97（fallback Case C/WebGL・KOOV URL境界）

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

### source Chromeとのdocument navigation比較（2026-10-03）

test copy固有の境界か、URL・profile・Chrome版・CDP操作に共通する境界かを切り分けるため、
同じ実機で`154.0.8037.97`のsource Chromeと署名済み`.97` test copyを、新規空profileで
`about:blank`から同じ`https://www.koov.io/app/welcome`へ`Page.navigate`した。source Chromeの
基準試験は通常ANGLE、test copyの比較試験は前回と同じdynamic ANGLE引数を使った。いずれも
認証情報の入力、保存、USB/Bluetooth操作は行っていない。

| 対象 | Page.navigate | 実document / event | 判定 |
| --- | --- | --- | --- |
| source Chrome `154.0.8037.97` | 成功（`errorText=null`） | `Page.frameNavigated`後、`https://account.sonyged.com/users/oauth/sign_in`、HTTP 200、ログイン画面の本文を取得 | URL・ネットワーク・Chrome版の基本到達性は確認。KOOV認証後の画面ではない |
| signed test copy（dynamic ANGLE引数） | timeout | 初期page targetは`about:blank`、navigation event 0件 | test copy側のdocument navigation境界で停止 |
| signed test copy（dynamic ANGLE引数なしのLaunchServices起動） | timeout | 初期page targetは`about:blank`、navigation event 0件 | dynamic ANGLE引数だけでは説明できない再現差分 |

この比較では、test copyはdynamic ANGLE指定の有無にかかわらずCDPのdocument遷移を開始できず、
source Chromeは同じURLをSony Global Educationのログインdocumentまで遷移できた。従って、
KOOV UI/WebGLの未判定は維持するが、次に調べる範囲はGPU/EGLではなく、署名済みtest copyの
bundle起動後のnavigation・profile初期化・ページプロセス生成境界である。source Chromeの
ログイン画面到達はKOOV認証成功やKOOV canvas描画を意味しない。

同じ表示バージョンでもbundle実体は同一ではない。読み取り専用のSHA-256比較では、source
Chromeのlauncherは`5c336c15b01b400bf971ee4539506692a075292b8dde3e90f3b735815ac97a38`、
test copyのlauncherは`77b0bf8c4f68d7cbc2cec8a29530afd41ed310ca0af84842411b07f4c8cc209f`であり、
Frameworkの`Current`実体もsourceが`30597be367d698d01ea4b18e0fbe27f023a8f078bac180f0d1766ceda9b4fe86`、
test copyが`9c5e1f665836e5f02c8cdd5ead9356af9f13ec59d575b79a768242cd19880ad3`だった。test copyの
Framework Librariesにはreplacement `libEGL.dylib` / `libGLESv2.dylib`が存在する。この差分は
artifact構成上の既知差分を含むため、直ちに原因とは断定しないが、次の読み取り専用診断では
bundle実体、署名後のFramework整合性、renderer/page-process生成順を比較対象に固定する。

署名とprocess生成の追加確認では、中間証明書不足やtest copyの署名破損は観測されなかった。
test copy本体とFrameworkは`codesign --verify --deep --strict`、valid-on-disk、designated
requirementを満たした。source Chromeのdeep strict verifyだけは、`/Applications`配下の
既存source bundleにある`com.apple.FinderInfo` xattrを理由に失敗したが、sourceのdocument
navigation自体は成功しているため、今回のtest copy未達の直接原因とは扱わない。sourceはDeveloper
ID署名、test copyはApple Development署名で、entitlements構成は同一ではないため、今後の
比較リスクとして保持する。

このentitlements差は署名漏れではなく、リポジトリの`phase3-chromium-base-app-entitlements.plist`
と署名scriptが、test copyへGoogle identity-bound entitlement（application identifier、
keychain group、associated domains、public-key credential）を入れない方針を明示しているためである。
GPU/Renderer helperはsource/testで`allow-jit`を含む主要形状が共通し、helperの差は主に
TeamIdentifierにある。したがって、test copyがsourceと同じGoogle本番identityを持たないことは
既知の設計境界だが、今回のHTTP stream停止の直接原因とはまだ証明していない。

新規profileのprocess sampleでは、source/test copyの双方でGPU process、network/storage
utility、rendererが生成された。test copyにもrendererが存在するため、停止点はrendererの
生成前ではなく、その後のdocument navigation/page初期化である。既存のCDP証跡どおり、test
copyではpage targetが`about:blank`のまま`Page.navigate`がtimeoutし、document-level
navigation eventを取得できない。次の診断は署名変更ではなく、renderer側のnavigation失敗・
crash/termination・bundle由来の起動引数を読み取り専用で確認する。

### renderer由来URL loaderとHTTP streamの追加切り分け（2026-10-03）

KOOV固有の応答、TLS、中間証明書、GPU初期化を分離するため、同じ実機上の新規一時profileと
loopback HTTP serverだけを使い、source Chromeとsigned test copyのNetLogを比較した。既存の
source Chrome、profile、artifact、retry/evidenceは変更していない。

| 観測 | source Chrome | signed test copy | 判定 |
| --- | --- | --- | --- |
| `http://127.0.0.1`へのTCP接続 | 接続完了 | 接続完了するpreconnectを確認 | OSのsocket接続全面失敗ではない |
| HTTP stream | `HTTP_STREAM_REQUEST`、socket bind、`HTTP_TRANSACTION_SEND_REQUEST`まで進行 | `HTTP_STREAM_REQUEST`自体が現れず、HTTP送信・応答なし | test copyのrenderer由来requestはTCP後のstream割当境界で停止 |
| loopback応答 | HTTP 200、body/title取得 | 約10秒後にURL requestをcancel、titleなし | KOOVサーバー固有ではない |
| data URL上のJavaScript `fetch` | — | fetch失敗。loopback serverではhealth check以外のfetch requestを確認できず | main frameだけでなくrenderer由来URL loader経路にも同じ停止傾向 |
| data URL上のscript subresource | — | `<script src="http://127.0.0.1">`のrequestをserver側で確認できず、document titleも初期値のまま | CORS応答以前のrenderer request送信境界を追加確認 |
| background通信 | — | `NetworkDelegate::NotifyBeforeURLRequest`後にChrome更新用HTTP/HTTPS requestは完了 | Network Service全体の停止・全ネットワーク遮断ではない |

外部のSonyログインURLでも、test copyはDNSのAレコード取得、`DIRECT` proxy選択、証明書検証
（`cert_status=0`、`is_valid=true`、`TRUSTED_ANCHOR`、valid pathあり）までは記録したが、
HTTP response、document event、rendererへのbody配信に進まずtimeoutした。従って、現時点の証跡は
中間証明書不足や`ERR_CERT_*`を支持しない。macOS unified logにも、今回の通信を拒否する明示的な
network/sandbox denialは見つかっていない（不在は完全な否定ではない）。

現在の原因候補は、signed test copy固有のrenderer-originated URL loaderからHTTP streamへ渡す
境界、またはその前後のsocket pool再bind処理である。Apple Development署名とsourceのDeveloper
ID署名、main app entitlementsの差はこの境界の候補として残るが、GPU/Renderer helperの主要
entitlementは共通であり、署名差を単独の根因とはまだ断定しない。test copyはKOOV documentや
JavaScript/canvasへ到達していないため、KOOVのクラッシュとは判定しない。

この時点で追加の実機操作に進む前に残る安全な確認は、(1) source/testのNetwork Serviceと
renderer processの起動引数・audit/entitlement差分、(2) HTTP stream生成前後のNetwork Service
verbose log、(3) 署名方式差を隔離した比較入力の承認判断である。実機の認証、KOOV画面操作、
保存、USB/Bluetooth操作は、document到達が回復するまで停止する。

### 未改変source bundleの一時場所比較（2026-10-03）

署名済みtest copyの問題が`/Applications`の場所、CDP、profile、Chrome versionの組み合わせに
依存するかを分けるため、source Chrome bundleを変更せず一時場所へ複製し、同じ新規profile、
`--disable-gpu`、loopback HTTP、CDP条件で起動した。source launcherと`.97` Frameworkの実体
SHA-256は元sourceと一致し、Developer ID署名も保持されていた。元sourceと同様、既存FinderInfo
xattrの影響でdeep strict verifyは失敗したが、署名の再作成やxattr変更は行っていない。

| 入力 | 結果 |
| --- | --- |
| 未改変source bundleの一時コピー | loopback serverが`/probe`を受信し、page titleとHTTP 200を取得 |
| signed test copy（同じ`--disable-gpu`条件） | page URL metadataのみ、titleなし。loopbackの`/probe` requestなし |
| test copyのGPU/ANGLEロード | GPU helperは`--use-gl=disabled`。対象profileの全processでreplacement `libEGL.dylib` / `libGLESv2.dylib`のロード0件 |

この比較により、単純な一時場所、CDP、空profile、Chrome `.97`、またはANGLE dylibの実行時
ロードだけでは停止を説明できない。残る差分は、test copyのApple Development再署名とmain app
entitlements、current-only Framework構成、Librariesへ追加されたreplacement fileを含むbundle
再構成である。`--disable-gpu`ではreplacement dylibがロードされていないため、次に優先すべきは
署名/entitlementsまたはbundle再構成を一つずつ隔離する比較であり、sourceや既存test copyを
変更せず新しい診断入力として作る必要がある。

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
### 公開一次資料との照合（2026-10-03）

今回の停止位置と候補原因を、公開されているChromium/Appleの一次資料と照合した。

| 公開資料 | 今回の観測との対応 | 判定 |
| --- | --- | --- |
| [Chromium: Life of a URL request](https://chromium.googlesource.com/chromium/src/+/show/refs/heads/main/net/docs/life-of-a-url-request.md) | renderer/navigationの要求は、browserが作成したURLLoaderFactoryとMojoを経由してNetwork Serviceへ渡り、URLRequest、HTTP transaction、HttpStreamFactoryへ進む。今回のtest copyはURL要求開始とTCP/preconnectまでは観測できるが、`HTTP_STREAM_REQUEST`、HTTP送信、応答がない。 | 停止位置は公開仕様上のNetwork Service内のURLLoader/HTTP stream handoff付近まで絞れる。 |
| [Chromium Network Service README](https://chromium.googlesource.com/chromium/src.git/+/master/services/network/) | Network Serviceはrendererが直接利用するものではなく、browser側のtrusted interfaceを介して利用する。別プロセスのNetwork Serviceが落ちると既存のURLLoaderFactoryが切断される。今回、background networkは完了し、Network Service全体の終了は観測していない。 | Network Service全体のクラッシュは主因として弱い。ただしURLLoaderFactory/Mojo境界の異常は未解決。 |
| [Chromium macOS sandbox](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/sandbox/mac/) / [process sandboxes by platform](https://chromium.googlesource.com/chromium/src/+/HEAD/docs/security/process-sandboxes-by-platform.md) | macOSのNetwork Serviceは`kNetwork` Seatbelt sandbox対象で、sandbox denyの確認には`--enable-sandbox-logging`が使える。後段のsource対照でdenyを採取したが、Network Serviceのdeny集合はsource/testで一致し、HTTP socket拒否は見つからなかった。 | 一般的なsandbox/policy denyはtest copy固有の原因から後退。IPC境界は候補として残る。 |
| [Chromium macOS signing README](https://chromium.googlesource.com/chromium/src/+/HEAD/chrome/installer/mac/signing/) | official Google Chromeとdevelopment-signed Chromiumではentitlementが異なり、official signing identityに結び付くentitlementをローカル署名へそのまま適用できないことが公開資料に明記されている。今回のtest copyでTeam IDと署名identityがsourceと異なること、official identity-bound entitlementを付与していないことは、この既知の差分と整合する。 | 署名identity/entitlement/bundle再構成は有力な候補。ただし公開資料は今回のHTTP stream停止を直接証明しない。 |
| [Apple Code Signing Tasks](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/Procedures/Procedures.html) | nested codeは内側から正しく署名する必要があり、library validationは同一Team IDまたはApple署名のlibraryを許可し、拒否時はAMFIの`[deny-mmap]`がsyslogに出る。今回のno-GPU再現ではreplacement ANGLE dylibがロードされず、対応するlibrary-validation denyも観測していない。 | library validationだけを直接原因とする根拠は弱い。ただし署名構造・entitlement差分の候補は残る。 |

#### 公開資料から確定できる範囲

- これはKOOV固有のJavaScriptまたは描画処理に到達する前の問題である。source copyではloopbackのmain documentとsubresourceが取得でき、test copyでは同じ条件で取得できない。
- 証明書検証失敗を示す公開仕様上のエラーはなく、external URLでも`cert_status=0`、`is_valid=true`、`TRUSTED_ANCHOR`を観測している。このため、中間証明書不足は今回の停止位置を説明しない。
- ANGLE dylibのロードを止めた`--disable-gpu`再現でも同じloopback停止が残ったため、ANGLEの実行時ロード単独では説明できない。
- したがって、公開資料と観測結果が一致する範囲では、候補は「signed test bundleのidentity/entitlementまたはbundle再構成がNetwork Service/rendererのURLLoaderFactory経路に影響した」か、「Network Service sandbox/IPC境界で要求がHTTP stream生成へ進めない」の二系統である。公開資料だけでは、この二つのどちらかまでは決められない。

公開資料準拠の追加診断として、後段で新規test profileを使って`--enable-sandbox-logging`を付け、sandbox deny、Network Service/rendererのIPC切断、AMFIの`[deny-mmap]`を同時刻で採取した。結果は次節に記録する。これは原因特定のための読み取り用診断であり、source Chrome、既存retry/evidence、artifact、xattr、署名済みbundleを変更していない。

### sandbox loggingのsource対照（2026-10-03）

公開資料に基づく追加診断として、変更していないsource bundleとsigned test copyを、同じ
`--disable-gpu`、`--enable-sandbox-logging`、新規空profile、loopback HTTP、CDP
`Page.navigate`条件で比較した。対象profileは各試行で新規に作成し、既存source Chrome、
既存test copy、retry/evidence、artifactは変更していない。

| 観測 | source bundle | signed test copy | 判定 |
| --- | --- | --- | --- |
| Network Serviceのsandbox deny | `file-read-data /Library/Preferences/com.apple.networkd.plist`、`mach-lookup`のCoreServices/DiskArbitration/ctkd | 同じdeny集合 | test copy固有のNetwork Service sandbox policy差分ではない |
| rendererのsandbox deny | distributed notifications、CoreGraphics/Accessibility preferencesの拒否 | 同じ種類の拒否 | renderer sandboxの一般的なdenyであり、HTTP停止固有の差分ではない |
| AMFI | Crashpadのcore dump拒否 | Crashpadのcore dump拒否 | Chrome本体またはANGLE library validationの`deny-mmap`とは扱わない |
| loopback document | HTTP 200、`Page.navigate`成功、document/title取得 | `Network.requestWillBeSent`後にHTTP responseなし、`Page.navigate`応答なし、server受信なし | sandbox deny集合が同じでもnavigation結果だけが異なる |

この対照により、sandbox loggingで観測されたdenyは今回のtest copyだけに固有の原因では
ない。特にNetwork ServiceについてHTTP socketやloopbackを直接拒否するdenyはなく、
`AMFI: Denying core dump`もCrashpadの補助processに対する記録である。したがって、原因候補は
「署名identity/entitlementまたはbundle再構成がURLLoaderFactoryからHTTP streamへ渡る
アプリケーション経路に影響する」か、「signed test copy固有のNetwork Service/renderer
IPC状態」の二つへさらに絞られる。次に必要なのは、署名方式を変更せずに採取できる
Network Service内部verbose logまたはURLLoaderFactoryのIPC切断証跡である。

### verbose loggingと署名差分の読み取り専用対照（2026-10-03）

公開logging仕様に合わせ、source bundleとsigned test copyへ同じ
`--enable-logging=stderr`、`--v=0`、`--vmodule`（Network Service、`net`、browser loader対象）、
`CHROME_IPC_LOGGING=1`を付け、`--disable-gpu`、新規空profile、loopback、CDP条件を維持して
比較した。Chromiumのrelease artifactでは、URLLoader内部の詳細なIPC切断やHTTP stream生成の
失敗理由までVLOGに出ず、今回得られた対象URLの共通ログは
`NetworkDelegate::NotifyBeforeURLRequest`までだった。

| 観測 | source bundle | signed test copy | 判定 |
| --- | --- | --- | --- |
| 対象URLのrequest開始 | `NetworkDelegate::NotifyBeforeURLRequest` | 同じログを記録 | browser/Network Service入口までは共通 |
| HTTP stream以降 | URLLoader後にHTTP 200、favicon request、CDP navigation完了 | 対象URL後にHTTP stream/responseログなし、server受信なし | test copyだけがstream handoff前後で停止 |
| IPC/terminationの直接証拠 | なし | なし | release VLOGだけではMojo切断またはrenderer terminationを確定できない |
| 全Network Service停止 | background通信が継続 | background通信が継続 | Network Service全体停止ではない |

この結果は、sandbox対照と整合する一方、verbose loggingだけで署名差分を原因と断定する
ところまでは到達しなかった。Chromeのログには対象URLや背景通信のqueryが含まれ得るため、保存した
rawログを公開資料へ転記せず、証跡の要約だけをこの文書へ記録する。

署名・entitlementは既存bundleを変更せず読み取った。test copy本体とFrameworkのdeep strict
verifyは成功し、中間証明書不足や署名破損を示す結果はなかった。source ChromeはDeveloper ID
署名、test copyはApple Development署名で、main appではsourceだけがidentity-boundな
application identifier、keychain group、associated domains、public-key credentialを持ち、
test copyはこれらを持たない。GPU/Renderer helperの主要な`allow-jit`形状は共通だった。
また、今回のno-GPU再現ではreplacement ANGLE dylibはロードされず、Chrome本体やANGLEの
library validationを示す`[deny-mmap]`も見つからなかった。

従って、現時点の判定は「中間証明書不足・一般的sandbox deny・ANGLE dylib load failure・
Network Service全体クラッシュではない」。残る有力な未確定差分は、Apple Development署名と
Developer ID署名のidentity/entitlement差、またはその差を生んだbundle再構成が、rendererの
URLLoaderFactoryからHTTP streamへ渡る経路に影響している可能性である。これはコード上の候補で
あって、直接因果の証明ではない。

### 決定的な比較入力の実施結果と次の承認境界

変更していないsource bundleから新しい隔離test copyを作り、既存のtest copyやretry/evidenceとは
別に、同じApple Development署名方針で再署名してloopback navigationを行う比較を実施した。
新規copyでも同じ停止が再現したため、既存test copyの個別破損ではなく、prepare/re-sign後の
bundle状態に依存する再現性のある問題と判定する。結果の詳細は次節に記録する。

この比較だけではApple Development署名identity/entitlement単独と、current-only化・ANGLE配置を
含むbundle再構成の寄与を分離できないため、下記のANGLEなし・Framework再構成なしcontrolを追加
実施した。control作成中に旧versionのFramework binary seal不整合が判明したが、nested code後に
両versionのFramework binaryを再sealすることでdeep strict verificationを通過させた。

### bundle構造の読み取り専用比較（2026-10-03）

prepare scriptの想定外の欠落を除外するため、変更を加えずsource bundleと既存test copyの
relative file inventoryを比較した。Chrome `.97`のcurrent Framework version配下は、source側
にないtest copy固有の2ファイル（replacement `libEGL.dylib`、`libGLESv2.dylib`）を除き、
test copyに欠落ファイルはなかった。app直下の`Info.plist`と`Resources`も同一だった。

これは、(a) source複製時の非コード資材欠落、(b) current Framework versionの選択ミス、
(c) ANGLE dylib以外の予期しないファイル追加、を今回の比較では支持しない。残るbundle差分は
主に、意図したreplacement dylib、Framework/Mach-Oの再署名、main appのApple Development
entitlement、current-only化である。current Framework内の全Mach-Oが同じ署名後挙動を示すことや、
署名identity差がnavigation停止を生むことは、inventory比較だけでは確定できない。

### 新規署名隔離copyによる再現確認（2026-10-03）

既存test copyの個別破損を除外するため、変更していないsource Chromeから別の隔離copyを作り、
同じ`.97` fallback artifact、同じprepare scriptのcurrent-only/ANGLE配置、同じApple Development
署名scriptを適用した。新規copyのsigning receiptは`STRICT_VERIFICATION=passed`であり、既存
source、既存test copy、既存artifact、保存済みretry/evidenceは変更していない。

新規profile、`--disable-gpu`、loopback fixture、remote debuggingだけで起動した結果は次のとおり。

| 観測 | 結果 |
| --- | --- |
| Chrome main process | 起動継続 |
| CDP target | 対象fixture URLのpage targetを生成。ただしtitleは空 |
| loopback server | fixture request 0件、HTTP responseなし |
| KOOV/GPU/ANGLE | KOOV URL、認証、GPU操作、ANGLE loadは実施していない |

これは既存test copyで観測した「target metadataは生成されるがdocument requestがserverへ届かない」
境界を、新しいsource複製から再現した結果である。従って、既存test copyの偶発的破損、既存profile、
既存証跡の汚染は原因候補から後退し、prepare/re-sign後のbundle状態に依存する再現性のある問題と
判定する。一方、この入力は署名だけでなくcurrent-only化とANGLE dylib追加も含むため、Apple
Development署名identity/entitlementだけが単独原因だとはまだ証明しない。

### ANGLEなし・Framework再構成なしの署名control（2026-10-03）

署名差分だけを残すため、source Chromeをそのまま複製し、Frameworkの`.93`/`.97` versionを保持し、
replacement `libEGL.dylib` / `libGLESv2.dylib`を追加せず、Apple Development署名を適用した。
controlはdeep strict verificationに成功し、既存source、既存test copy、artifact、retry/evidenceは
変更していない。

| 観測 | Developer ID source | bare Apple Development control |
| --- | --- | --- |
| ANGLE replacement dylib | なし | なし |
| Framework version | `.93`/`.97`を保持 | `.93`/`.97`を保持 |
| GPU条件 | `--disable-gpu` | `--disable-gpu` |
| Chrome main process | 起動 | 起動継続 |
| loopback page target | document/title取得 | target URL生成、title空 |
| loopback HTTP request | 取得成功 | 0件、HTTP responseなし |

source側は同じfixtureをHTTP 200まで取得し、bare controlだけがdocument request前後で停止した。
ANGLE load、GPU/EGL、KOOV URL、認証、描画はこのcontrolでは実施していない。この結果により、
`current-only` Framework化、replacement ANGLE dylib、GPU初期化、KOOV固有処理は主因候補から後退し、
Apple Development再署名に伴うidentity/entitlementまたは署名closureの差が、document navigation
停止の直接候補と判定する。

### 署名後entitlement／requirementsの静的比較（2026-10-03）

追加の読み取り専用比較で、sourceのmain appはGoogleの署名主体に結び付いた
`application-identifier`、`keychain-access-groups`、associated-domains、browser
public-key-credentialを保持していた。一方、Apple Development controlはChromiumのbase
device entitlementだけを持ち、これらのGoogle identity-bound entitlementを持たなかった。
GPU/Renderer helperのJIT entitlement形状は共通だった。main appとFrameworkのdesignated
requirementは、sourceのGoogle Developer ID／Team条件から、controlのApple Development
証明書条件へ変わっていた。

この差はChromiumの公開signing仕様と整合する。Google固有entitlementを個人のApple
Development identityへ移せないため、controlへそれらを戻すことは正しい修正候補ではない。
さらに、Google固有entitlementを除いたbare controlでも同じ停止が再現したため、
「Google固有entitlementの欠落だけ」が原因という単純な説明は採用しない。現時点で残る
有力な原因カテゴリは、Apple Development署名identity／designated requirementの変化、または
それに伴うnested codeを含む署名closureとChromeのpage/navigation経路の非互換である。
公開資料はこのHTTP stream停止を直接規定していないため、特定のentitlementキーまたは
Chromiumコード行までの断定はできない。

この比較により、追加のentitlement controlは完了扱いとし、同じ署名済みcopyでのKOOV操作や
既存retry/evidenceの再利用には進まない。次の診断候補は、公開仕様に反しない範囲での
署名requirements・nested closureの読み取り比較と、必要ならChromium側の署名／起動境界を
確認できる別の実行入力である。実機のWebGL/KOOV判定は引き続き保留する。

### 上位候補の再確認と純正Google署名の適用範囲（2026-10-03）

上位候補を分離するため、sourceとbare controlのmain app、Framework root、Frameworkの
`.93`/`.97`実体、各versionのnested helper bundleについて、署名主体、identifier、designated
requirement、entitlementを読み取り専用で再確認した。

| 確認対象 | 結果 | 判定 |
| --- | --- | --- |
| Apple Development identity／requirement差 | sourceはGoogle Developer ID条件、controlはApple Development条件。main appのGoogle identity-bound entitlementもsourceだけに存在 | 上位1候補を強く支持 |
| Framework version | bare controlは`.93`/`.97`を保持し、両versionのFramework実体は同じApple Development署名体系 | current-only化はこのcontrolでは関与しない |
| nested helper bundle | 確認したhelper／updater bundleはcontrol側の同じ開発署名体系で再署名され、異なる署名主体の混在は確認されない | 機械的な署名主体混在は支持しない |
| sealed resource／closure | control作成時のstrict verificationは成功。後続の直接検証で出た`CSSMERR_TP_NOT_TRUSTED`は、この端末の証明書trust評価であり、sealed resource破損とは別の結果 | closureの機械的破損は主因として弱い |

初回のbare control作成中には旧Framework versionのbinary seal不整合が一度発生したが、nested
code後に両versionを再sealしてから比較を完了している。それでもdocument navigation停止が
再現したため、上位2候補のうち「署名closureの単純な破損」より、「Apple Development署名へ
変わったことによるidentity／requirement／実行時ポリシー差」の方を上位とする。

#### 純正Google署名を維持できる範囲

変更しない純正Google署名ChromeをURLアクセスの基準として使うことは可能である。実際、同じ
新規profile・`--disable-gpu`・loopback／CDP条件では、source bundleはHTTP 200とdocument/title
取得に成功した。

ただし、純正署名を維持したまま同じbundle内部へreplacement ANGLE dylibを追加・置換することは
できない。Appleの署名sealはnested codeとbundle resourceを外側の署名へ結び付け、Chromeの
hardened runtimeはLibrary Validationで読み込み可能なlibraryを制限するためである。Library
Validationを緩めるentitlementを追加する場合はappの再署名が必要になり、純正Google署名維持
ではなくなる。

従って、純正Google署名で可能なのは「純正Chromeの組み込みANGLEによるURL／KOOV到達性の
基準確認」までであり、今回のreplacement ANGLE実験と同時には成立しない。replacement ANGLE
を使う場合は、署名済みGoogle Chromeの後改変ではなく、ANGLEを組み込んだChromium開発ビルド
または同一署名体系で生成した別bundleが必要になる。

### CIでのURLLoader／Network Service identity差診断の境界（2026-10-03）

純正Google署名sourceとApple Development再署名copyのURL到達性比較は、同じ新規profile、
`--disable-gpu`、loopback、CDP条件で既に完了している。sourceはHTTP 200とdocument/titleまで
到達し、signed test copyとANGLEなしのbare Apple Development controlは、target metadata生成後に
HTTP stream生成前で停止した。このため、URL到達性の比較は未実施ではなく、現在のCIへ同じ比較を
そのまま移す必要はない。

追加確認として、GitHub Actions APIでrun [`36514821653`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36514821653)
のjob完了状態を読み取り専用で再確認した。runと`dynamic-angle-cft-macos-intel` jobはsuccessで、
ANGLE artifact検証とChrome for Testingのdynamic/stock `file://` WebGL smokeを実行している。しかし、
このworkflowはChromium sourceをcheckout/buildせず、Apple Development identityで署名せず、loopback
HTTP documentを入力にしていない。従ってこのrunはANGLE load、GPU/EGL、WebGLのVM境界を証明するが、
sourceとApple Development署名差のURLLoader診断結果は含まない。

公開Chromium sourceで、次のログ挿入点を特定した。

| 層 | 対象 | 採取すべき最小情報 |
| --- | --- | --- |
| browser／factory生成 | `content/browser/storage_partition_impl.cc` の `GetURLLoaderFactoryForBrowserProcessInternal` / `CreateURLLoaderFactoryForBrowserProcessInternal` | factory生成、既存Mojo remoteの接続状態、connection error、再生成回数、request ID。URL query、cookie、headerは記録しない |
| Network Service入口 | `services/network/url_loader_factory.cc` の `URLLoaderFactory::CreateLoaderAndStart` | process ID、request ID、receiver/clientのvalidity、URLのscheme/host/path hash、`URLLoader`生成と`CorsURLLoaderFactory::OnURLLoaderCreated`到達 |
| HTTP開始 | `services/network/url_loader.cc` の `URLLoader::ScheduleStart` | schedulerによるdefer有無、`url_request_->Start()`到達、NetLog source ID |
| 応答／切断 | `URLLoader::OnResponseStarted`、`URLLoader::NotifyCompleted`、`URLLoader::OnMojoDisconnect` | response/error code、Mojo disconnectの有無、切断がresponse前か後か |

この対応は、[URLLoaderFactoryの実装](https://chromium.googlesource.com/chromium/src/+/master/services/network/url_loader_factory.cc)、
[URLLoaderの実装](https://chromium.googlesource.com/chromium/src/+/master/services/network/url_loader.cc)、
[Network Serviceのプロセス／factory再接続仕様](https://chromium.googlesource.com/chromium/src.git/+/master/services/network/README.md)
に基づく。Network Serviceが落ちた場合は既存URLLoaderFactoryが切断されるため、`OnMojoDisconnect`と
browser側factory再生成を同一のrequest ID系列で採取できれば、今回の「request開始後、HTTP stream前で停止」
がIPC切断なのか、URLRequest開始前の別経路なのかを分離できる。

ただし、この診断を現行CIで実行するには二つの段階がある。

1. **低コストのbaseline**: 現行Chrome for Testing workflowへ、秘密情報を含まないloopback HTTP
   fixtureとdocument/title、request count、NetLog採取を追加する。これはunsigned/CfTのURLLoader経路を
   基準化できるが、Apple Development identity差の因果は判定できない。
2. **決定的なCI診断**: 対応するChromium revision `73c14f6228d7cd537c855007e8f88678969cc0eb`
   で上記の診断ログを入れたfull Chromium buildを別workflowで生成し、loopback fixtureを実行する。
   これは大規模なsource/dependency checkout、長時間build、新規diagnostic artifactを要する。CIに
   Apple Development証明書がなければ、実機と同じ署名identityの再現ではなく、Chromium本体の
   URLLoader／Network Service経路が正常かを分離する診断になる。

現時点では、低コストbaselineもfull Chromium diagnostic buildも未実行である。したがって、今回の
読み取り専用調査で確認できた結論は「純正Chrome比較は完了」「run `36514821653`はidentity差を
検証していない」「identity差をコードで直接判定するにはfull Chromium診断入力が必要」である。
full build workflowの追加、Actions dispatch、diagnostic artifact生成は、現行Phase 3Dの範囲を
越えるため、別途承認が必要である。

### 再利用可能なビルド済みChromiumの探索結果（2026-10-04）

既存状態を変更しない読み取り専用確認として、リポジトリ、作業用tmp領域、一時領域、ユーザー領域の
範囲で`Chromium.app`、`*Chromium*.app`、標準的な`out/Release`／`out/release`を探索したが、
再利用可能なfull Chromium bundleは見つからなかった。リポジトリのPhase 2 CI成果物もChromium全体
ではなく、固定ANGLEの`libEGL.dylib`と`libGLESv2.dylib`および検証メタデータだけを含む。

従って、現時点で実行できるnative Chromium controlは存在せず、次の選択肢は次のいずれかになる。

1. ユーザーが別に保有する未署名Chromium bundleの場所を指定し、revision・bundle構造・署名状態を
   読み取り確認する。
2. Chromium revision `73c14f6228d7cd537c855007e8f88678969cc0eb`を固定したfull Chromium diagnostic
   buildを新規に用意する。この場合は`is_component_build=false`、非branded Chromium、Chromium公式の
   development signing経路、loopback URL controlを別々に固定する。

この探索では署名、xattr、profile作成、Chrome/Chromium起動、artifact取得、Actions dispatchを行って
いない。ビルド済みChromiumが見つからないため、現段階でのブロッカーは「native Chromium control
入力の不存在」である。

#### 公式Chromium snapshotの再利用可能性

指定された[Chromium公式ダウンロード手順](https://www.chromium.org/getting-involved/download-chromium/)
に従い、Mac snapshot archiveの公開状態を読み取り確認した。Chrome `154.0.8037.57` tagは
main branch position `1689415`から分岐しているが、対応する
`Mac/1689415/chrome-mac.zip`はHTTP 404だった。一方、近傍の
`Mac/1689422/chrome-mac.zip`はHTTP 200、zipサイズ193,366,564 bytesで取得可能であり、
archiveの構成は公式設定上`Chromium.app`を含む。

ただし、`Mac/1689422/REVISIONS`はChromium `got_revision=82303c21a18acdc256c6264cd2ed0e1588df99d4`、
ANGLE `got_angle_revision=8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`を記録している。これは今回の
runtime artifactのChromium `73c14f6228d7cd537c855007e8f88678969cc0eb`、ANGLE
`1ff8799c596d4fc9acea28343610b1f33650a6fa`とは一致しない。

従って、`1689422` snapshotは「native Chromiumの開発署名後にloopback URLへ到達できるか」を見る
stock controlとしては再利用候補になるが、Chrome `.57`／今回のANGLE artifactと同一入力ではない。
これをダウンロード、展開、署名、起動する操作はまだ実施していない。厳密な同一revision比較には、
Mac snapshotの代替近傍revisionを使うか、対応revisionからfull Chromiumをbuildする必要がある。

## 2026-10-04 最終URL／再署名因果判定（Chrome C0・Chromium U0/U1・S0/S1）

### 比較結果

今回の最終比較では、URL到達性、ANGLEロード、Intel HD Graphics 5000のMetal/EGL/WebGL1を別々の境界として記録した。CIのU0/U1は専用workflow run `37180857723`で、workflowの実験HEADは`0a8b516e00db6adfd42aed2e4022693372e65022`である。

| ケース | bundle状態 | URL結果 | GPU/WebGL結果 | 範囲・注意 |
| --- | --- | --- | --- | --- |
| U0 | 完全未署名stock Chromium | loopback URL pass | WebGL smoke pass | `INPUT_REVISION_MATCH_CHROMIUM=false`。探索的結果 |
| U1 | U0の別copyへANGLE `libEGL.dylib` / `libGLESv2.dylib`だけを追加、未署名 | loopback URL pass | ANGLE load pass、WebGL smoke pass | `INPUT_REVISION_MATCH_ANGLE=false`。探索的結果 |
| S0 | stock Chromiumを組み立てて凍結後、Apple Developmentで初回署名一回 | strict verify pass。ただしHTTP stream/document前で停止し、loopback `/probe`未到達 | URL停止が先で、ANGLE/GPU結果とは分離 | stockでも失敗するためANGLE追加は必要条件ではない |
| S1 | ANGLE追加済みChromiumを組み立てて凍結後、Apple Developmentで初回署名一回 | S0と同じくHTTP stream/document前で停止 | Intel HD Graphics 5000でMetal/EGL、WebGL1 context/draw pass。WebGL2は`context-null` | URLとGPU/WebGL1は別境界 |
| Chrome official | Google Developer ID署名の公式Chrome `154.0.8037.98` | 同一flags・新規profile・loopbackで`/probe` HTTP 200、DOM/title到達 | URL基準 | 公式sourceは未改変 |
| Chrome C0 | Chrome officialの別copy。replacement ANGLEなし。全内容を凍結後、Apple Developmentで初回署名一回 | 署名後strict verify pass、`/probe`未到達、DOM空 | ANGLE追加なしでURL失敗 | C1は作成しない |

U0/U1のCI result schemaは`phase5-unsigned-chromium-u0u1-result-v1`で、U0/U1 URL、U0/U1 WebGL smoke、U1 ANGLE loadの必須ゲートはすべてpassした。しかし、snapshot側のChromium/ANGLE revisionとPhase 5 runtime artifactのrevisionが一致しなかったため、これは同一入力の正式な因果証明ではなく探索的結果である。未署名状態、manifest/hash、static test、ANGLE load、WebGL smokeのゲートを通過したことと、Apple Development署名後のURL挙動が成功することは別である。

### Chrome C0の厳密なcontrol

公式sourceとC0には、同じrestricted headless flags、別々の新規profile、別portのloopback fixtureを使用した。公式sourceはserver logで`GET /probe`のHTTP 200を記録し、dump-domにtitle/markerが存在した。C0はhealth check以外の`/probe` requestを受けず、dump-domは空だった。C0のプロセスは規定観測後、PID・command・親子関係を確認して停止した。停止処理に由来するexit `127`は、URL判定後の終了処理の結果なので、URL失敗の根拠にはしない。

C0は、bundle、Framework、既存dylib、Resources、Info.plist、entitlementを凍結し、replacement ANGLEを追加せず、コピー時点のxattrがないことを確認してから署名した。署名後はdeep strict verify、entitlement、requirement、bundle詳細、xattr最終確認を保存し、verifyはpass、xattr出力は空、署名後のファイル変更はなかった。C0の初回署名は一回だけで、再署名、署名やり直し、Applications置換、ANGLE追加、署名後のbundle変更は行っていない。

公式sourceの作業用コピーでは、nested official helperについてhost側のpre-sign deep strict verify差が記録されたが、公式source自体のURL controlは成功した。したがって、deep strict verify単独のpass/failをURL到達性の根拠にせず、公式source対C0の同条件request/DOM比較と、C0署名後strict verifyを併記して判定する。

### 署名順序と停止判断

C0で実際に使用した正しい順序は次のとおりである。

1. 現行Framework version内のnested Mach-Oを署名する。
2. nested `.app`／`.bundle` containerを最深部から外側へ署名する。
3. Framework rootを署名する。
4. main executableを署名する。
5. outer appを署名する。

この順序で32段階の初回署名操作を行い、その後にstrict verifyした。検証失敗時に再署名する経路は使用していない。C0でANGLEなしの再署名差が再現し、Chromiumでもstock S0が同じURL境界で失敗していたため、「ANGLEを追加した後の再署名」が必要条件ではないことが確認できた。目的の白黒判定が成立したので、C1を追加して署名すること、失敗copyを再署名すること、署名後に内容やxattrを変更することは行わない。

### 最終判定と未確定事項

テストした範囲では、URLアクセス不可に対する「再署名」は白ではなく黒である。ChromeとChromiumの双方で、未署名または公式Google署名sourceはloopback URLのHTTP/document到達に成功し、Apple Developmentへ再署名したbundleはHTTP stream/document前で停止した。このため、両者は少なくとも同じ因果カテゴリ、すなわち署名identity・designated requirement・entitlement・nested signing closure、またはそれに伴うmacOS実行時ポリシーの変化を共有すると扱う。

一方、直接の単一キー、単一entitlement、単一コード行まで特定したわけではない。今回の証拠から「ChromeとChromiumで同じ署名方式差の層が再現した」とは言えるが、「同じ一つの属性だけが原因」とは断定しない。S1で観測したMetal/EGL/WebGL1成功、WebGL2 `context-null`、`RUNTIME_DEVICE_READY=false`の維持、KOOVのdocument未到達・認証・保存・USB/Bluetooth未実施は、URL原因の確定と別の状態として残る。

追加の原因特定が必要になった場合の次段階は、署名や実機再試行ではなく、別途承認されたCI・source診断である。`URLLoaderFactory::CreateLoaderAndStart`、`URLLoader::ScheduleStart`、`OnResponseStarted`、`OnMojoDisconnect`、browser側factory再生成をrequest ID系列で記録し、署名差がIPCまたはHTTP stream境界へどのように現れるかを調べる。C1、再署名、署名後変更、xattr変更、Applications置換、KOOV操作は本実験では実施しない。

Chromium再開用に、runtime artifactと同じChromium/ANGLE revisionをCIでfull buildする
`.github/workflows/phase5-chromium-url-diagnostic.yml`を追加した。source patchは
URLLoaderFactory生成、URLLoader生成・開始、response、completion、Mojo disconnect、browser側factory生成を
`[PHASE5_URL_DIAG]` markerで記録する。local source U0/U1経路とstatic auditは準備済みだが、CIのfull build・診断結果はまだ取得していない。これがpassするまで新規署名・実機再試行へ進まない。
