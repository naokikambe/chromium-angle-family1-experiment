# Phase 5: 未署名Chromium・初回署名のみ実験計画

更新日: 2026-10-04

状態: 計画確定前の文書化。今回の更新ではChromium取得、ANGLE配置、署名、xattr変更、profile作成、Chromium起動、実機操作、KOOV操作を行っていない。

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

従って、既存観測は「公式仕様として再署名がURLを止める」とは言えないが、「署名方式差を除外した入力が必要」という判断を支持する。

### 2.6 Edge・第三者署名Chromiumの扱い

原因切り分けの最初の対象はEdgeではなく、上流Chromiumに近い第三者Chromiumまたは公式未署名Chromiumとする。EdgeはMicrosoft固有のpatch、Root Store、EdgeUpdater、bundle構造、OS対応条件が追加の変数になるため、後段に置く。

今回の実験では、第三者署名版ではなく、完全未署名Chromiumを優先する。第三者署名版は署名identityの比較には使えるが、「ANGLE追加後に最後に一度だけ署名する」実験の入力としては、最初から署名済みであるため適さない。

### 2.7 KOOVへの影響

KOOVの公式資料では、最新のChrome/Edge、WebGL対応環境、Bluetooth 4.0以上が前提である。現在のダウンロードページはデスクトップmacOS 14以上と最新Chrome/Edgeを案内している。旧PC版のサポート終了日も2026-03-31とされている。

そのため、未署名または独自署名ChromiumでURL/WebGLが成功しても、KOOVの公式サポート環境に入ったことは意味しない。KOOV判定には別途、document到達、画面描画、認証、保存、Bluetooth、USBを確認する必要がある。今回の実験ではKOOV操作を行わない。

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

## 5. 実行予定コマンド

以下は計画上のコマンドであり、この文書の作成時点では実行していない。実際のFramework名とGPU Helper名は、起動前の読み取り専用inventoryで確定する。

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
| GitHub Actions dispatch、artifact再取得、push | この計画では実施しない。別承認 |

## 9. 次のチャットでの開始条件

新しい実験チャットでは、まずこの文書と`AGENTS.md`、`docs/phase-status.md`、`docs/phase3d-vm-observability.md`、`docs/phase5-real-device-observation.md`を読み、未署名inventoryとrevision整合性だけを読み取り確認する。次にCIでU0/U1、manifest/hash、static test、保存可能な診断を優先して実施し、CIゲート未達なら実機へ進まない。初回署名、profile、Chromium起動、実機操作は、CIゲート確認後かつ必要な承認を受けるまで行わない。
