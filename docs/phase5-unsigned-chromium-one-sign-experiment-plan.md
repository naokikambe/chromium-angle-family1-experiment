# Phase 5: 未署名Chromium・初回署名のみ実験計画

更新日: 2026-10-06

状態: 初回署名実験とChrome/Chromiumの再署名差比較は完了。同一revisionのChromium source側URLLoader診断workflowは対象branchへpushし、run `37464208418`を実行した。static audit、ANGLE入力、source/deps取得、両patch適用は成功したが、full Chromium buildは親jobの360分上限でキャンセルされ、unsigned bundleとU0/U1診断は未完である。C1（ANGLE追加後の別bundle署名）、追加署名、KOOV操作、`RUNTIME_DEVICE_READY=false`の変更は行わない。

## 1. 目的と結論

目的は、署名済みGoogle Chromeの再署名で発生したURL document navigation停止と、ANGLE追加・Metal 1/WebGL1の成否を分離することである。

今回の実験では、次の順序を固定する。

1. 完全未署名のChromium bundleを入力とする。
2. stock用とANGLE追加用を別の新規コピーとして組み立てる。
3. 実機で起動するコピーだけ、組み立て完了後に一度だけ署名する。
4. 初回署名後は、bundle内のファイル、Framework、dylib、entitlement、xattrを変更しない。
5. 初回署名後の再署名、ANGLE追加後の再署名、署名のやり直しは一切行わない。

完全未署名のままのURL/GPU診断はVMまたはCIで可能である。実機での起動に署名が必要な場合は、未署名のまま組み立てた最終bundleを一度だけ署名してから実機確認する。この構成なら、「署名済みbundleへ後からANGLEを追加して再署名した場合」と、「ANGLEを先に組み込んで最後に一度だけ署名した場合」を分離できる。

ただし、完全に同一のChromium/ANGLE revisionで揃わない場合は探索的結果であり、Phase 5の厳密な同一入力証明とは扱わない。

## 2. ここまでに判明した事実

### 2.1 Google署名sourceと再署名copyのURL差分

既存の実機比較では、同じChrome version、新規空profile、`--disable-gpu`、loopback HTTP、CDP条件で次を確認した。

| 入力 | 結果 |
| --- | --- |
| 変更していないGoogle Developer ID署名source Chrome | loopback request、HTTP 200、document/titleまで到達 |
| Apple Development署名のANGLE追加test copy | page metadata後、HTTP stream/document前で停止 |
| ANGLEなしのbare Apple Development control | 同じ停止を再現 |
| ANGLE引数なしのsigned test copy | 同じdocument navigation停止を再現 |

`--disable-gpu`のbare controlでも停止したため、ANGLEの実行時ロードだけではURL失敗を説明できない。現在の有力候補は、Apple Development identity/requirement、main app entitlement、nested signing closure、またはそれらが変えたrenderer/Network ServiceのURLLoaderFactoryからHTTP streamへの境界である。

loopbackではTCP/preconnectまでは進むが、test copyは`HTTP_STREAM_REQUEST`、HTTP送信、応答、document eventへ進まない。background通信は完了しており、全Network Service停止、KOOVサーバー不存在、中間証明書不足、単純なTLS検証失敗とは判定していない。

詳細は[`docs/phase5-real-device-observation.md`](phase5-real-device-observation.md)のsource比較、NetLog比較、公開一次資料照合を参照する。

ここでの「現在の有力候補」は、Chrome C0とChromium S0/S1の追加比較前に置いた仮説である。2.8の比較により、再署名差がURL失敗の原因カテゴリとして黒であることは確定したが、identity、requirement、entitlement、nested closureのどれが直接原因かはなお未分離である。

### 2.2 CI run 36514821653の範囲

CI run `36514821653`はsuccessだったが、対象はANGLE artifact検証とChrome for Testingのdynamic/stock `file://` WebGL smokeである。次は含まない。

- full Chromium source build
- Apple Development署名とGoogle署名のidentity比較
- loopback HTTP document
- URLLoader内部診断
- 実機のIntel HD Graphics 5000

したがって、このrunのsuccessはURLアクセスや再署名差の証明ではない。

### 2.3 現在のPhase 5 artifactと実機境界

現在の主要なfallback artifactは次である。

| 項目 | 値 |
| --- | --- |
| runtime CI | `37009376538` / success |
| artifact | `angle-macos-x86_64-chrome-154.0.8037.97-angle-e12217f3-family1-experiment-37009376538` |
| artifact digest | `sha256:247f0ee4be552c8e4f8790db04c39753631abc62312b78318dcdd5a80808652d` |
| manifest SHA-256 | `97b03d254b67b604173436bdf64a9c09c93f61d468b66880b36508c5e8d3bab2` |
| ANGLE revision | `e12217f3e133cb1029b050d893b1806d141483be` |
| `libEGL.dylib` SHA-256 | `44116767b6d4d02362b2dd117cf16af2e719ef143b573f9a52b4837c1415b470` |
| `libGLESv2.dylib` SHA-256 | `750d1a917cb88235d6e7cc0b2483b44800ee3cb39261dc21535d70ef60be0913` |
| fallback patch SHA-256 | `7bd8a40eaa6311c4ca37ebd68c19ab3d9822b936000e38dbadea70b92667a014` |
| device readiness | `RUNTIME_DEVICE_READY=false` |

このartifactを使った過去の承認済み実機観測では、Intel HD Graphics 5000で次を確認した。

- `requireGpuFamily2`の明示的無効化
- Metal device、command queue、shader library、render utilities初期化
- `eglInitialize_return_success`
- `max_es_version=2.0`
- 非WebGLのES3要求からES2 frontendへのfallback
- WebGL1 context生成と最小clear/draw成功
- WebGL2は`context-null`
- WebGL実行中の同一GPU Helper PIDでreplacement `libEGL.dylib` / `libGLESv2.dylib`を`lsof`/`vmmap`確認

一方、KOOVではpage targetのURL metadata後にdocumentが`about:blank`のまま停止し、画面描画、認証、保存、USB/Bluetooth連携には到達していない。`RUNTIME_DEVICE_READY=false`は、CI artifactを実機準備済みとみなさない境界値であり、この実験で変更しない。

### 2.4 未署名Chromium候補とrevision差

公式Chromium snapshotの近傍Mac archive `Mac/1689422/chrome-mac.zip`には`Chromium.app`が含まれ、x86_64の未署名Chromium候補である。`REVISIONS`の値は次のとおりである。

| 項目 | snapshot | 現在のPhase 5 `.97` artifact |
| --- | --- | --- |
| Chromium revision | `82303c21a18acdc256c6264cd2ed0e1588df99d4` | `b510e9d7cd3a2fbd78d0ddc42234103206c5f78d` |
| ANGLE revision | `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448` | `e12217f3e133cb1029b050d893b1806d141483be` |

このsnapshotはnative ChromiumのURL controlには使えるが、Phase 5 artifactと同一入力ではない。ANGLE追加試験に使う場合は、結果を探索的と明示する。厳密な試験には、Phase 5 artifactと同じChromium revisionで`is_component_build=false`、非branded、x86_64の未署名Chromiumをfull buildする必要がある。

2026-10-05の読み取り確認では、公式Mac snapshotの`REVISIONS`をposition `1689414`〜`1689423`で確認したが、取得できたのは`1689422`だけだった。そこに記録されたChromiumは`82303c21a18acdc256c6264cd2ed0e1588df99d4`、ANGLEは`8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`であり、対象のPhase 5 runtime inputとは一致しない。full Chromium source buildは承認経路ではないため、この範囲で厳密一致する未署名prebuilt binaryは未成立として扱う。

### 2.5 公式資料から分かる再署名の影響範囲

「再署名したChromiumはURLアクセス不能になる」という一般的な公式既知問題は確認できていない。しかし、公式資料から次の影響経路は確認できる。

- bundle変更は既存signature sealを壊す。
- nested codeは内側から外側へ署名する必要がある。
- 署名identityが変わるとdesignated requirementが変わる。
- entitlementは実行時にmacOSが与える権限を決める。
- TCCの権限記録は署名identityに依存し得る。
- Hardened Runtimeのlibrary validationはTeam IDやApple署名を検査する。
- Chromiumのdevelopment-signed buildは公式Google署名buildとentitlementが異なる。
- macOSはApplication Firewall等の処理でdetached signatureを記録する場合がある。

従って、公式資料だけから「再署名がURLを止める」という一般的既知問題を主張することはできない。一方、今回の実測ではChrome C0とChromium S0/S1で同じ署名方式差のURL停止を再現した。この実測結果と公式資料上の影響経路は、2.8の最終判定で分けて記録する。

### 2.6 Edge・第三者署名Chromiumの扱い

原因切り分けの最初の対象はEdgeではなく、上流Chromiumに近い第三者Chromiumまたは公式未署名Chromiumとする。EdgeはMicrosoft固有のpatch、Root Store、EdgeUpdater、bundle構造、OS対応条件が追加の変数になるため、後段に置く。

今回の実験では、第三者署名版ではなく、完全未署名Chromiumを優先する。第三者署名版は署名identityの比較には使えるが、「ANGLE追加後に最後に一度だけ署名する」実験の入力としては、最初から署名済みであるため適さない。

### 2.7 KOOVへの影響

KOOVの公式資料では、最新のChrome/Edge、WebGL対応環境、Bluetooth 4.0以上が前提である。現在のダウンロードページはデスクトップmacOS 14以上と最新Chrome/Edgeを案内している。旧PC版のサポート終了日も2026-03-31とされている。

そのため、未署名または独自署名ChromiumでURL/WebGLが成功しても、KOOVの公式サポート環境に入ったことは意味しない。KOOV判定には別途、document到達、画面描画、認証、保存、Bluetooth、USBを確認する必要がある。今回の実験ではKOOV操作を行わない。

### 2.8 2026-10-04 U0/U1・S0/S1・Chrome C0の最終比較

承認後、完全未署名ChromiumのCI比較、既存の承認済み実機用S0/S1比較、公式Google Chromeを複製してApple Developmentで一度だけ署名するC0 controlを実施した。結果は次のとおりである。

| ケース | 入力と署名 | URL / GPU結果 | 判定範囲 |
| --- | --- | --- | --- |
| U0 | 完全未署名stock Chromium | loopback URL pass、WebGL smoke pass | 最新CI run [`37314180383`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/37314180383)。`INPUT_REVISION_MATCH_CHROMIUM=false`のため探索的 |
| U1 | U0の別copyへANGLE 2 dylibだけを追加、未署名のまま | loopback URL pass、ANGLE load pass、WebGL smoke pass | 最新CI run [`37314180383`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/37314180383)。`INPUT_REVISION_MATCH_ANGLE=false`のため探索的 |
| S0 | stock Chromiumを凍結後、Apple Developmentで初回署名一回 | strict verify pass。ただしHTTP stream/document前にURL失敗、`/probe`未到達 | stockでも失敗するためANGLE追加は必要条件ではない |
| S1 | ANGLE追加済みChromiumを凍結後、Apple Developmentで初回署名一回 | S0と同じURL失敗。Intel HD Graphics 5000ではMetal/EGL、WebGL1 context/draw pass、WebGL2は`context-null` | URL失敗とGPU/WebGL1到達は別境界 |
| Chrome official | Google Developer ID署名のChrome `154.0.8037.98`、未改変source | 同一flags・新規profile・loopbackで`/probe` HTTP 200、DOM/title到達 | URL基準 |
| Chrome C0 | official sourceの別copy。ANGLE replacementなし、bundle凍結後にApple Developmentで初回署名一回 | 署名後strict verify pass、xattr変更なし。ただし`/probe`未到達、DOM空 | Chromeでも再署名差を再現 |

U0/U1のCI結果は、result schema `phase5-unsigned-chromium-u0u1-result-v1`の全必須ゲート（U0/U1 URL、U0/U1 WebGL smoke、U1 ANGLE load）をpassした。最新の公式未署名snapshot runは`37314180383`で、sourceからのfull Chromium buildは使用していない。ただし、CIで使ったChromium snapshot/ANGLE revisionとPhase 5 runtime artifactのrevisionが一致せず、正式な同一入力の因果証明ではなく探索的結果として扱う。U0/U1のCI成功は、S0/S1のApple Development署名後のURL成功を保証しない。

Chrome C0では、公式sourceとC0に同じrestricted headless flags、loopback fixture、新規profileを使用した。公式sourceは`/probe`のHTTP 200とDOMを取得した一方、C0は規定観測時間内に`/probe`へ到達せずDOMも空だった。C0終了時のプロセス停止に伴うexit `127`は、すでにURL判定を終えた後の停止処理によるため、URL失敗の根拠には使わない。C0にはreplacement ANGLEを追加していないため、ChromeでANGLE追加がURL失敗の必要条件ではないことも確認できた。公式sourceの作業用コピーでnested helperのhost-side deep verify差が出た点は別の証跡として保存し、URL判定は公式sourceの実測結果とC0の署名後strict verify・request結果で行う。

この結果から、テストした範囲では「再署名」は白ではなく、URL document navigationを止める原因カテゴリとして黒と判定する。ChromeとChromiumで、未署名または公式Google署名sourceはURLに到達し、Apple Developmentへ再署名したbundleはHTTP stream/document前で止まるという同じ層の差を再現した。ただし、identity、designated requirement、entitlement、nested signing closure、またはそれに伴うmacOS実行時ポリシーのどの属性が直接原因かは未特定であり、「同じ原因カテゴリ」であって「同じ単一キー」とまでは断定しない。ANGLE追加自体はS0とChrome C0で必要条件から除外できる。

C0で実際に用いた署名順序は、(1) 現行Framework内のnested Mach-O、(2) 最深部からのnested `.app`／`.bundle` container、(3) Framework root、(4) main executable、(5) outer appである。bundle、Framework、dylib、Resources、Info.plist、entitlementを凍結してからこの順序で初回署名を行い、strict verifyを通過させた。C0は32段階の初回署名操作を一回だけ行い、署名後の再署名、bundle変更、xattr変更、Applications置換は行っていない。verify失敗時に再署名する経路も使用していない。C0で目的の差が確定したため、C1の追加署名・ANGLE追加後再署名・再試行は不要かつ禁止とする。

### 2.9 2026-10-05 CI成功後の新規S0/S1証跡

専用U0/U1 workflow run [`37314180383`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/37314180383) は、static audit、未署名状態、manifest/hash、U0/U1 loopback URL、U0/U1 WebGL smoke、U1 ANGLE loadの必須ゲートをすべてpassした。workflowのHEADは`fe1d32095737d946c9484f6ddb5647352fe37edf`である。公式snapshotはposition `1689422`、Chromium `82303c21a18acdc256c6264cd2ed0e1588df99d4`、ANGLE `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`で、runtime artifactのChromium `b510e9d7cd3a2fbd78d0ddc42234103206c5f78d`／ANGLE `e12217f3e133cb1029b050d893b1806d141483be`とは一致しない。このため、今回も探索的比較として扱う。sourceからのfull Chromium buildは使用していない。

CI成功後、公式snapshotからS0とS1を別々の新規bundleとして組み立て、未署名状態、bundle構造、ANGLE差分、Resources、Info.plist、entitlement、xattrを凍結してから初回署名を行った。証跡名は`phase5-s0s1-after-ci-37314180383-20261005-b`である。

| ケース | 署名・検証 | URL / 実機結果 |
| --- | --- | --- |
| S0 | 26 targetsを内側から外側へ一回だけ署名。署名直後のdeep strict verifyはstatus 0 | `--disable-gpu`でbrowserは起動したが、loopbackの`/probe`へ到達せず、HTTP stream/document前で停止。`frameStartedNavigating`後に`frameNavigated`、title、HTTP responseは得られなかった |
| S1 | S0と別bundle。28 targetsを同じ順序で一回だけ署名。署名直後のdeep strict verifyはstatus 0 | S0と同じURL停止。ANGLE/Metal/WebGL1は下記のとおり成功 |

署名後は再署名、署名やり直し、ANGLE追加、Framework/dylib/Resources/Info.plist/entitlement変更、xattr変更、Applications置換を行っていない。観測後に再計算したmain executable、Framework、S1の`libEGL.dylib`／`libGLESv2.dylib`、Info.plistのhashは署名直後のreceiptと一致した。

最初の手動WebGL観測は通常sandboxから起動したため、Crashpadの`bootstrap_check_in ... Permission denied`で有効なページ結果を作れなかった。同じbundleの通常sandbox検証が`CSSMERR_TP_NOT_TRUSTED`を返したが、その環境では`security find-identity`が0件だった。署名時と同じホスト権限での読み取り専用再検証はS1 pre/postともstatus 0で、`valid on disk`かつdesignated requirementを満たした。したがって、この2つはbundle破損ではなく観測環境差として記録し、再署名は行っていない。

新規profileで、Crashpad起動を抑制する`--disable-breakpad`を追加した読み取り専用観測を実施した。S1のfull runtime opt-inは`--disable-angle-features=requireGpuFamily2,requireMsl21`であり、bundleは変更していない。Metal/EGLログは`libEGL_loaded`、`libGLESv2_loaded`、`metal_device_selection=success`、`require_gpu_family2 enabled=false has_override=true`、`command_queue=success`、`display_initialize_result=success`、`eglInitialize_return_success`、`max_es_version=2.0`、`family1_es3_to_es2_fallback requested=3.0 max_supported=2.0`、`context_initialize_success`を記録した。WebGL smokeの結果はpage loaded、WebGL1 context、最小drawがすべて`true`で、rendererは`ANGLE (Intel, ANGLE Metal Renderer: Intel HD Graphics 5000, Unspecified Version)`、versionは`WebGL 1.0 (OpenGL ES 2.0 Chromium)`だった。今回のページは`#webgl1-only`なので、今回の結果だけではWebGL2の成否を新たに判定しない。既存の別観測におけるWebGL2 `context-null`は能力境界として別記録する。

このfresh runでも、URLとGPU/WebGL1は別境界である。U0/U1の未署名CI URLがpassし、S0/S1のApple Development初回署名後URLがfailしたため、テスト範囲では再署名差は黒のままである。`RUNTIME_DEVICE_READY=false`は変更していない。KOOV、認証、保存、USB/Bluetoothは実施していない。

### 2.10 2026-10-06 同一revision source URLLoader diagnostic CI

同一revision入力で、source側のURLLoader内部ログを含むunbranded Chromiumを作るworkflowを
Human承認のもとで実行した。

| 項目 | 結果 |
| --- | --- |
| workflow / run | `phase5-chromium-url-diagnostic.yml` / [`37464208418`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/37464208418) |
| branch / HEAD | `phase3-dynamic-angle-prep` / `f444054a141b808043b69c6e0bf0ebfb57008dd4` |
| Chromium revision | `b510e9d7cd3a2fbd78d0ddc42234103206c5f78d` |
| ANGLE revision | `e12217f3e133cb1029b050d893b1806d141483be` |
| ANGLE build run | `37009376538` / success |
| static audit | success |
| source/deps、Xcode patch、URLLoader patch | success |
| full Chromium build | parent jobの360分上限でcancelled |
| unsigned bundle / U0/U1 | 未生成 / 未実施 |
| diagnostics | build diagnostics artifactを保存 |

build logにはコンパイルエラーはなく、`offline mode`、`fastlocal=1->0`、`localexec/4`の長時間待ちが
記録された。空のoutディレクトリから`autoninja -C out/Phase5URLDiagnostic chrome`を実行し、約84,000
タスクをローカルで処理した。build開始前の準備に約49分、buildは約5時間11分継続したが、約
79,594タスク中7,277タスクでjob timeoutに到達した。従って、今回の未完了はsource/compiler error
ではなく、clean full buildの実行性能とjob timeout設計の不一致である。

次回候補は、同じIntel/x64/Xcode条件の高性能・永続runner、Siso fast localまたはRBE/remote cache、
revision・GN args・patch SHA単位のbuild cacheである。`use_clang_modules=false`、
`use_unified_system_module=false`、`enable_precompiled_headers=false`はXcode互換性のための設定で
あり、速度改善目的で変更する場合は正式比較とは別の探索として扱う。単純なtimeout延長や同一条件の
無目的な再実行は行わない。

## 3. 署名方針

### 3.1 VM/CIの完全未署名経路

VM/CIでGatekeeperが実行を許す場合、次の2つを完全未署名のまま比較する。

- `U0`: stock Chromium、ANGLE変更なし
- `U1`: 同じChromiumの別コピーへANGLE dylibだけを追加

この経路では`codesign --sign`、ad-hoc signing、entitlement追加、xattr変更を行わない。署名状態は読み取り専用で確認する。Gatekeeperが未署名bundleの起動を拒否した場合は、署名やxattr変更で回避せず停止する。

### 3.2 CI優先の実施順と実機移行ゲート

この実験は、実機でしか判定できない項目以外を先にCIで消化する。実機操作は、CIで次のゲートを満たした後に限る。

| CIで先に実施する項目 | 実機へ渡す判定・証跡 |
| --- | --- |
| 入力archiveのarchitecture、bundle構造、`REVISIONS`、Chromium/ANGLE revision | stock/ANGLEの入力が同定され、revision不一致が明示されている |
| stockとANGLE追加copyのmanifest、dylib hash、Mach-O依存、配置先 | U0/U1の入力差分がANGLE dylibだけとして記録されている |
| stock/ANGLEの署名状態とbundle sealの読み取り | U0/U1が完全未署名、または署名状態が試験目的に反しないことを確認する |
| `--disable-gpu`でのloopback URL、HTTP 200、document/title、CDP navigation | U0をURL基準、U1をANGLE追加後のURL比較として判定する |
| `file://`またはfixtureでのdynamic/stock WebGL smoke、ANGLE load marker、起動ログ | CIで再現可能なANGLEロード・WebGL範囲を固定する。これは実機GPU能力の証明ではない |
| static test、workflowの対象、artifact manifest、digest、保存可能な診断ログ | 実機投入するartifactと証跡の取り違えがないことを確認する |

CIで一つでも必須ゲートが失敗した場合、または未署名bundleをrunnerが起動できない場合は、署名・xattr・profile・実機操作で回避せず停止する。既存workflowで足りないCI確認がある場合は、workflow変更またはdispatchを別途承認してから行う。CIの成功だけでは、Apple Development identityの初回署名後のURL挙動、Intel HD Graphics 5000のMetal/EGL、実機WebGL、KOOVを合格とはしない。

CIで証明できない項目は次のとおりである。

- 実機のIntel HD Graphics 5000が選択されること
- 実機のMetal device、command queue、shader library、EGL初期化
- 実機での`requireGpuFamily2`境界、ES3からES2へのfallback
- 実機GPU Helperでのreplacement dylibロード
- 初回署名identityとmacOS実行時のURLLoader/renderer境界の相互作用
- KOOVのdocument到達、画面描画、認証、保存、USB/Bluetooth

したがって、実機開始条件は「CIが成功した」だけではなく、「CIのU0/U1 URL比較と入力証跡が揃い、実機でしか判定できない項目だけが残っていること」とする。`RUNTIME_DEVICE_READY=false`はこのゲートを自動的に解除しない。

### 3.3 実機の初回署名経路

実機で署名が必要な場合の許可範囲は、各最終bundleへの初回署名一回だけとする。

1. 未署名Chromium bundleの署名状態を確認する。
2. stock用とANGLE追加用を別々の新規コピーへ組み立てる。
3. ANGLEの配置、revision、manifest、dylib hash、bundle構造を読み取り確認する。
4. 各最終bundleを凍結する。
5. 凍結後、nested codeを内側から外側へ一度だけ署名する。
6. deep strict verify、entitlement、requirement、component hashを読み取る。
7. verify失敗時は再署名せず、そのcopyを失敗証跡として停止する。
8. verify成功時だけ新規一時profileで起動する。

実際のC0で確認したnested signingの順序は、現在のFramework内Mach-O、最深部のnested `.app`／`.bundle`、Framework root、main executable、outer appの順である。各bundleは組み立てと凍結を完了してからこの順序で署名する。`--deep`だけの不透明な再署名はこの実験の順序ではない。

禁止事項は次のとおりである。

- ANGLE追加後に、すでに署名済みのbundleを再署名すること
- 初回署名失敗後の再試行署名
- 署名済みbundleへのdylib、Framework、Resources、Info.plistの追加・変更
- `--deep`だけによる不透明な再署名
- source Chrome、既存retry/evidence、既存profile、既存artifactの変更
- xattr操作、Applicationsへの置換、Updaterによる自動更新

## 4. 実験ケース

| ケース | 入力 | 起動条件 | 目的 |
| --- | --- | --- | --- |
| U0 | 完全未署名stock Chromium | `--disable-gpu` | 未署名URL基準 |
| U1 | 完全未署名Chromium + ANGLE | `--disable-gpu` | ANGLE追加だけのURL影響 |
| S0 | stock bundleを最後に一度だけ署名 | `--disable-gpu` | 実機用初回署名control |
| S1 | ANGLE追加済みbundleを最後に一度だけ署名 | URL + Metal flags | 実機用target |
| M0 | 任意のstock bundle | Metal flags | stock ANGLEのGPU/WebGL比較 |

S0とS1は、署名後に一切bundleを変更しない。S0とS1は別の新規コピーであり、同じcopyを使い回さない。

## 5. 当初計画のコマンドと実施結果

以下は実験設計時に固定した代表コマンドである。U0/U1、S0/S1、Chrome C0の実施結果は2.8と実機観測記録にまとめた。実際のFramework名とGPU Helper名は、各起動前の読み取り専用inventoryで確定した。

### 5.1 未署名確認

```sh
file "$CHROMIUM_APP/Contents/MacOS/Chromium"
plutil -p "$CHROMIUM_APP/Contents/Info.plist"
cat "$CHROMIUM_APP/Contents/REVISIONS"
codesign -dvvv --strict "$CHROMIUM_APP"
codesign -dvvv --strict "$CHROMIUM_FRAMEWORK"
codesign -dvvv --strict "$LIBEGL_DYLIB"
codesign -dvvv --strict "$LIBGLESV2_DYLIB"
```

各Mach-Oについて、署名なしであることを確認する。署名が存在する対象、architecture不一致、想定外の依存がある場合は停止する。

### 5.2 未署名stock URL

```sh
"$CHROMIUM_EXEC" \
  --disable-gpu \
  --no-first-run \
  --no-default-browser-check \
  --disable-sync \
  --enable-logging=stderr \
  --remote-debugging-port="$CDP_PORT" \
  --user-data-dir="$TEMP_PROFILE" \
  "$LOOPBACK_URL/probe"
```

### 5.3 未署名ANGLE URL

```sh
ditto "$STOCK_CHROMIUM_APP" "$ANGLE_CHROMIUM_APP"
cp "$LIBEGL_DYLIB" "$ANGLE_FRAMEWORK/Libraries/libEGL.dylib"
cp "$LIBGLESV2_DYLIB" "$ANGLE_FRAMEWORK/Libraries/libGLESv2.dylib"
```

配置後に5.2と同じ`--disable-gpu`条件でURLを確認する。ここでは署名コマンドを呼ばない。

### 5.4 初回署名後の実機URL/WebGL

ANGLE追加済みbundleを凍結し、承認済みidentityで一度だけ署名した後、次の条件で起動する。

```sh
"$ANGLE_CHROMIUM_EXEC" \
  --use-gl=angle \
  --use-angle=metal \
  --use-dynamic-angle \
  --disable-angle-features=requireGpuFamily2 \
  --no-first-run \
  --no-default-browser-check \
  --disable-sync \
  --enable-logging=stderr \
  --vmodule=gl_display=3,gl_initializer_mac=3 \
  --remote-debugging-port="$CDP_PORT" \
  --user-data-dir="$TEMP_PROFILE" \
  "$LOOPBACK_URL/probe"
```

URL成功後、`tests/fixtures/phase3d-webgl-smoke.html`を開く。WebGL1のcontext/drawを合格条件とし、WebGL2の`context-null`はIntel HD Graphics 5000のES3能力境界として別記録する。

## 6. 成功判定と取得証跡

### URL

- loopback serverがrequestを受信する
- HTTP 200を取得する
- document/titleを取得する
- CDP `Page.frameNavigated`とnavigation完了を取得する
- HTTP stream生成前のcancelで終わらない

### ANGLE/GPU/EGL

- `--use-gl=angle`、`--use-angle=metal`、`--use-dynamic-angle`がGPU processへ伝わる
- replacement `libEGL.dylib`と`libGLESv2.dylib`が同一GPU Helper PIDで観測される
- Intel HD Graphics 5000が選択される
- `eglInitialize_return_success`
- `max_es_version=2.0`
- `requireGpuFamily2` override/fallback markerが記録される

### WebGL

- page loaded
- WebGL1 context作成成功
- 最小clear/draw成功
- renderer情報がIntel HD Graphics 5000を示す
- WebGL2は別の能力境界として記録する

### 証跡

- source `REVISIONS`
- bundle version、bundle ID、architecture、署名状態
- ANGLE manifest、artifact digest、ANGLE revision、dylib hash
- 初回署名前後のcomponent hash
- 初回署名receipt、entitlement、designated requirement
- browser stderr、GPU startup trace、NetLog
- GPU process command line
- `lsof`、`vmmap`、dyld load evidence
- loopback request log、CDP navigation log
- WebGL smoke結果

## 7. 停止条件とrollback

次の場合は次段階へ進まない。

- U0/S0のURL基準が失敗する
- ChromiumまたはANGLE revision不一致を確認しないまま正式結果と扱う
- ANGLEのarchitecture、manifest、hashが一致しない
- 初回署名前にbundleが完全未署名でない
- 初回署名後のstrict verifyが失敗する
- 初回署名後に変更が必要になる
- GPU processでreplacement dylibの同一PIDロードが確認できない
- WebGL1のcontext/draw結果とWebGL2結果を混同する
- KOOV URL/document未到達のままKOOV WebGL/Bluetooth結果を推測する

実施結果として、U0/U1のURL基準はCIでpassし、S0/S1のURL基準はHTTP stream/document前でfailした。このfailは署名後bundleを修正して回避するための条件ではなく、再署名差の観測結果として停止・保存した。その後のChrome C0は、白黒判定を確定するために別途承認されたcontrolであり、失敗したS0/S1を再署名・再構成したものではない。

rollbackは、stock copy、ANGLE copy、profile、結果ディレクトリを分離することで行う。失敗時は証跡を保存して停止し、source Chrome、既存retry/evidence、既存artifact、既存profileを復元対象にしない。新規copyやprofileの削除は、証跡確認後に別途承認する。

## 8. 人間承認の境界

| 操作 | 承認 |
| --- | --- |
| 資料・manifest・revision・署名状態の読み取り | 不要（読み取り専用） |
| 未署名Chromiumの取得・artifact取得 | 必要 |
| 新規test copy作成 | 必要 |
| ANGLE dylib配置 | 必要 |
| 初回署名 | 必要。一つの最終bundleにつき一回だけ |
| 初回署名後のverify | 読み取り専用 |
| profile作成・Chromium起動 | 必要 |
| Intel HD Graphics 5000実機でのGPU/WebGL | 必要 |
| KOOV起動、認証、保存、USB/Bluetooth | この計画では実施しない。別承認 |
| GitHub Actions dispatch、artifact再取得、push | U0/U1の専用CIと必要な入力取得は承認済みで実施済み。追加のdispatch・artifact再取得・pushは本実験では行わない |

## 9. 実験完了後の扱い

U0/U1の必須CIゲート、S0/S1の一回限り初回署名後の実機確認、Chrome official/C0の同条件controlまで完了した。したがって、本計画の目的である「URLアクセス不可が再署名差と同じ因果カテゴリか」の判定は完了し、再署名は黒と記録する。S0/S1のrevision差を含むU0/U1結果は探索的であり、厳密な同一revisionの完全因果証明ではない。

今後必要になり得るのは、追加の署名や実機再試行ではなく、別途承認されたCI・Chromium source側の診断である。具体的には、URLLoaderFactory生成、`CreateLoaderAndStart`、`ScheduleStart`、`OnResponseStarted`、`OnMojoDisconnect`、browser側factory再生成をrequest ID系列で記録し、identity／requirement／entitlement／nested closureのどの差がIPCまたはHTTP stream境界に現れるかを調べる。C1、再署名、署名後変更、xattr変更、Applications置換、KOOV操作は実施しない。

Chromium再開用に、`.github/workflows/phase5-chromium-url-diagnostic.yml`と
`patches/phase5-chromium-url-loader-diagnostics.patch`を追加した。このworkflowは、runtime artifactと同じChromium `b510e9d7...`／ANGLE `e12217f3...`を入力として、unbranded `is_component_build=false`のfull ChromiumをCIでbuildし、source patchを適用したU0/U1を未署名のまま比較する。local source bundleを受け取る経路では公式snapshotのrevision mismatchを迂回するが、manifest、Chromium/ANGLE revision、未署名状態、U0/U1の入力差分を検証する。static auditは実行済みであり、CI実行結果が出るまで署名・profile・実機操作へ進まない。

### 9.1 2026-10-06 採用したCI実行構成

初回full buildの余裕を確保するため、sourceツリーを別Jobへ転送する分割は採用しない。Chromium source/depsと生成物は大きく、Job間artifact化で転送時間と整合性リスクが増え、`autoninja`が既に依存グラフを並列化しているためである。採用する構成は次の3Jobとする。

1. `prepare-angle`: `macos-15-intel`で既承認のANGLE artifactを取得・検証し、tarとSHA-256だけを保存する。
2. `build-chromium`: `macos-15-intel`の同一runner内でdepot_tools、exact Chromium source/deps、Xcode 16互換patch、URLLoader診断patch、unbranded `is_component_build=false` x64 full buildを実施する。完成した未署名`Chromium.app`だけをtar化し、revision、patch hash、未署名状態とともにartifact化する。
3. `diagnose-u0-u1`: Job 1/2のartifactをSHA-256検証後に展開し、ANGLEを再取得せず、未署名のままU0/U1のloopback URL、URLLoader診断、ANGLE load、WebGL smokeを実行する。

Job 2が失敗またはtimeoutした場合はJob 3を実行しない。Job 3で使用するartifactはJob 2の生成物とJob 1の検証済みANGLE入力に限定し、署名、xattr、profile、Applications、実機操作は行わない。初回clean buildではcacheを成功条件にせず、depot_tools/CIPD/Siso cacheはrevision、DEPSのANGLE revision、診断patch hash、GN argsを束縛できる場合に限って再実行用の任意最適化とする。高性能Intel runnerは利用可能性と承認を別途確認するまで採用しない。

この構成の時間管理は次のとおりである。

| 対象 | 通常見積もり | 強制上限 |
| --- | ---: | ---: |
| `build-chromium` | 2.5〜5時間 | 360分（build stepは330分） |
| `diagnose-u0-u1` | 30〜60分 | 150分 |
| 初回CI全体 | 4〜7時間 | 8時間30分（Job 1はJob 2と並列） |

GitHub Actionsのqueue待ちはこの上限に含めない。timeout、revision/manifest/hash不一致、未署名検証失敗、URLLoader必須ゲート失敗時は、署名や実機操作で回避せずartifactと診断ログを保存して停止する。新構成のstatic audit、push、dispatch、full build実行はそれぞれHuman承認の範囲で扱い、CI成功後にのみ実機用S0/S1の別判断へ進む。
