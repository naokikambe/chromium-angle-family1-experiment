# ページ表示復旧・実機実行キット

現在の施策と工程別の判定は[再計画](../../docs/phase5-page-recovery-replan.md)を参照する。Keychain承認応答後の復旧を調べる際は、post-observationのdocument・画像とserver／NetLogを対応付ける。通常のresult.jsonには待機前のdocument値と試行全体のserver受信が含まれ、classificationだけでは応答後の状態を判定できない。

既存の初回署名済みstock Chromiumの停止位置を確認し、署名部品の設定差が見つかった場合に、新規コピーでその修正を試すためのキット。Python 3.10以上、MacのGUIログインユーザーのTerminal、Apple Development証明書を使用する。

`probe.py`は既存アプリを変更しない。新規の一時profileで起動し、テスト後はその起動に属するブラウザだけを終了する。`sign_once.py`は完全未署名の原本から新しいコピーを作る試験用署名アダプターで、Chromium公式の全パッケージング・notarization処理を代替するものではない。参照するHelper別flags／entitlementは下記の固定ソースに基づく。

## 入力を設定する

リポジトリの`scripts/page-recovery/`ディレクトリへ移動してから、次の変数を実際の保存場所に設定する。比較用stock appと署名用原本は別のcopyを使い、原本は完全未署名のChromium.appとする。

```bash
cd scripts/page-recovery
```

計画は[具体施策](../../docs/phase5-page-recovery-plan.md)、次の担当者への指示は[引き継ぎプロンプト](../../docs/phase5-page-recovery-handoff.md)を参照。

```bash
kit_dir="$PWD"
task_dir="$HOME/Desktop/chromium-page-recovery-$(date +%Y%m%d-%H%M%S)"
mkdir -m 700 "$task_dir"
old_stock_app="/実際の保存場所/stock-copy/Chromium.app"
unsigned_app="/実際の保存場所/chrome-mac/Chromium.app"
revisions_file="/実際の保存場所/REVISIONS"
identity_sha1="Apple Development証明書の40桁SHA1"
```

パスは対象環境の保存場所に置き換える。比較用stock app、未署名原本、REVISIONS、署名identityの対応付けが必要である。

## 1. 元の失敗を取得する

```bash
python3 "$kit_dir/probe.py" inventory --app "$old_stock_app" --out "$task_dir/old-stock-inventory"
python3 "$kit_dir/probe.py" probe --app "$old_stock_app" --out "$task_dir/old-stock-normal"
```

`probe`のexit 2は診断で失敗を検出した意味。正常な観測結果として`result.json`、`summary.json`、NetLog、stderr、ページ画像を保存する。原本アプリのhash・署名情報はinventoryに保存する。

初回は通常GUI・GPU設定で実行する。HTTPだけが失敗する場合の次の対照はGPU無効化。同一アプリで一つの条件だけ変更する。

```bash
python3 "$kit_dir/probe.py" probe --app "$old_stock_app" --out "$task_dir/old-stock-no-gpu" --browser-arg=--disable-gpu
```

起動自体がCrashpadエラーで止まる場合だけ、別結果ディレクトリで`--browser-arg=--disable-breakpad`を追加する。起動元の権限が異なる試験を混ぜない。CLIはrootやGUI所有者でないユーザーからの実行を拒否する。

同じ実機の純正Chromeを、観測系の対照として使う場合：

```bash
python3 "$kit_dir/probe.py" probe --app "/Applications/Google Chrome.app" --out "$task_dir/official-chrome-control"
```

これはサーバー・CDP・GUIの動作対照であり、別ブラウザの差だけで署名因果を断定しない。

## 2. 判定を読む

各`data`／`file`／`http`フォルダの`result.json`で次を確認する。

| classification | 観測結果 | 次の施策 |
| --- | --- | --- |
| CDP_OR_STARTUP_FAILED | 起動またはページプロセスとの接続が成立しない | stderrのCrashpad・bootstrap・process requirementエラー、GUI起動元を確認 |
| LOCAL_DOCUMENT_FAILED | HTTPを使わない文書も読めない | renderer起動・終了、署名したRendererのJIT entitlementとflagsを照合 |
| HTTP_REQUEST_NOT_RECEIVED | ローカル文書は読めるが、HTTPサーバーに対象GETが来ない | 対象requestのNetwork.loadingFailed、URLLoader／IPC・実行時署名のログを確認 |
| HTTP_RESPONSE_TO_DOCUMENT_FAILED | サーバー受信後に本文・JSが成立しない | response／navigationの中断・プロセス終了を照合 |
| SUBRESOURCE_FETCH_FAILED | 本文は読めるが同一originの追加fetchが失敗 | main documentとrenderer由来fetchのrequest IDを分けて追跡 |
| DOCUMENT_OK_VISUAL_CHECK_FAILED | 本文・JSは成立するが緑色の描画領域を確認できない | page.pngと通常GUI、compositor／GPUログを照合 |
| DOCUMENT_OK_CANVAS_FAILED | 文書は成立するが2D canvas readbackが失敗 | GPU／software描画の対照へ |
| FIXTURE_PASS_GUI_CONFIRMATION_PENDING | HTTP／本文／JS／fetch／描画ピクセル／2D canvasの自動確認が成功 | 保存画像と通常GUIの実表示を確認して署名済みstockの基準を成立させる |

HTTP 200や画像ファイルの存在だけでは合格にしない。試験ごとのnonceで、前のページや別ケースの通信を成功証拠にしない。CDP画像はウィンドウやディスプレイ全体の表示を保証しないため、GUIの最終確認は人間が行う。

stderrには`process_requirement=2`などのログを追加する。`ProcessIsSignedAndFulfillsRequirement`、`HasSameTeamIdentifier`、Mach port rendezvous、Mojo切断などを確認する。署名検証の警告があるだけでHTTP停止の原因とはしない。参照版ではMach port peer validationは既定ON、enforcementは既定OFFであり、検証失敗が通信を実際に止めた証拠が必要である。

### KeychainのSafe Storage待ちを診断する

実機での続行手順と完了条件は[Keychain調査の続行プロンプト](../../docs/phase5-keychain-investigation-handoff.md)を参照する。通常→mock→通常の対照を承認状態変更の前に行い、未応答の承認待ちと拒否応答が返った状態を区別する。`--observe-seconds`を指定すると、待機前の記録を保ったまま、待機後に別のCDP sampleを採取し、`post-observation/result.json`と同ディレクトリの画像へ保存する。記録には観測時刻、document/runtime値、待機開始後に新たに収集したnetwork response/failure event、取得エラーが含まれる。`network_events`は待機開始時点のevent index以降の差分で、`network_events_snapshot_at`はその配列を採取した時刻を示す。個別eventの発生時刻ではない。`http_document_200_event_during_wait`はその差分内でdocumentのHTTP 200を観測した場合だけtrueになる。差分が空、またはこの値がfalseでも、待機前にHTTP 200がなかったことを意味しない。これは待機後の状態を示す追加sampleであり、待機中に人が応答した時刻や応答自体を証明せず、元のresultや分類も変更しない。UIへの入力や応答操作は行わない。

CDPのpage targetを待つ起動猶予は`--startup-timeout`（5〜60秒、既定12秒）で独立して指定できる。これはChromiumの起動引数やnavigation timeoutとは別のprobe側待機時間である。Keychain応答直後にtargetがまだ現れない試行では、例えば`--startup-timeout 45`として観測窓を延ばし、targetがないままfixture navigationを開始したと誤認しない。`context.json`に指定値を記録する。待機延長だけでHTTP要求やcallback成功を証明することはできず、追加のKeychain応答操作には明示的なオーナー同意が必要である。

Chromium Safe Storageへのアクセス拒否や、非同期暗号化providerのcallback待ちは、HTTP navigationが開始しない場合に調べる候補である。診断では各runに新しいprofileを使い、app、browser arguments、fixtureを揃えて一度に一つの条件だけを変える。必要なら`--use-mock-keychain`を対照条件として使い、通常Keychainとの差を比較する。GPU設定など別条件も比較する場合は、どの条件を固定し、どれを変更したかを記録する。

同フラグだけの対照でHTTP fixtureの結果が変わった場合、Keychain provider経路が関係する可能性を示す。ただし、それ単独では特定の過去trialの原因や製品受入を証明しない。判断を強めるには、同じ時刻・processに結び付くruntime wait、Keychain/securityd authorization、read-only trusted-app metadata、request timelineを対応付ける。SecretsやKeychain item contentsを取得せず、ACLを変更しない。Chromiumの`KeychainKeyProvider`はKeychain workerの完了までOSCryptAsync initialization callbackを待ち、cookie callbacksが完了する前にURL requestがHTTP transactionを遅らせる可能性がある。

署名policyの比較は同一snapshotから作った新しいcopyで行い、nested signing plan、role flags、entitlements、verification resultを確認する。初回署名と後の再署名の記録は分ける。helper rolesの設定が合っていても、それだけでSafe Storage authorizationやHTTP停止を説明しない。signing correlationだけから因果を断定しない。

`--use-mock-keychain`は診断用に限り、通常動作やproduct fixとして扱わない。Ordinary-Keychain acceptanceには通常GUIでの人間確認と、独立した3つのfresh profilesによる成功が必要である。Archived historical evidenceとの対応も確認する。過去trialの原因を未照合のまま一般化しない。

固定ソースの追跡箇所は[Keychain key provider](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/components/os_crypt/async/browser/keychain_key_provider.mm)、[macOS Keychain password handling](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/components/os_crypt/common/keychain_password_mac.mm)、および[URL request job](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/net/url_request/url_request_http_job.cc)である。固定コードは調査の手掛かりであり、特定環境の実行時原因を単独で証明するものではない。

### 正常終了後の暗号化cookie再利用

`persistent_cookie_runner.py`は受入試験専用の新しいprofileを一つ作り、同じstock appを二度起動します。最初の起動ではfixtureが非機密のsynthetic cookieを設定し、通常終了後にSQLiteをread-onlyで調べて、cookieの平文欄が空で暗号化欄に値があり、有効期限が未来であることだけを記録します。二回目は同じprofileを使い、fixtureへの再送信とページのHTTP・DOM・JS・fetch・canvas・2D描画を確認します。cookie値・Keychain秘密値は記録しません。

seed URLがbrowserのsession restore等で再表示されても、fixtureは最初のseed responseで一度だけcookieを発行します。以降のseed responseでは`Set-Cookie`を返さないため、復元されたseed tabがrestart後のcookie再送信を作り直すことはありません。

このrunnerのCDP `Page.navigate` timeoutは`--navigation-timeout`（5〜120秒、既定60秒）で指定し、seedとrestartの両phaseに同じ値を使います。値はcontextとphase結果に記録され、timeoutは当該phaseの失敗です。timeoutを理由に追加起動やretryは行わず、正常に完了したseedの後だけ予定されたrestartを行います。これはpage targetを待つ`--startup-timeout`や、navigation後にDOM／JS／fetch状態を待つ`--page-wait-seconds`とは別です。このrunnerのstartup defaultは45秒で、`probe.py`のstartup default 12秒とは異なります。いずれの待機値も人の操作や観測がその長さ続く保証にはなりません。

実機のGUIログインユーザーから実行します。stockのGPU既定値を使い、`--disable-gpu`も`--use-mock-keychain`も追加しません。実行前に必要なKeychain操作を明示的に承認してください。最初の起動で一致するSafe Storage promptが現れた場合、承認済みの一度だけ **Allow** を選びます。**Always Allow**は選びません。正常終了後の再起動でpromptが再び現れたら応答せず記録します。これは継続利用条件を満たさない結果です。

```bash
python3 persistent_cookie_runner.py \
  --app "$stock_app" \
  --out "$task_dir/normal-keychain-cookie-restart" \
  --startup-timeout 45 --navigation-timeout 60 \
  --page-wait-seconds 60 --observe-seconds 20
```

結果は`PERSISTENT_COOKIE_PASS`または`PERSISTENT_COOKIE_FAIL`です。GUI確認は各phaseを表示している間にオーナーが行い、trial ID・phase・nonceへ対応付けて別途記録します。raw NetLogとverbose network loggingはcookie headerを保存し得るため、このrunnerでは使わず、request URL/statusだけを含む安全なCDP要約とfixture eventを保存します。このrunnerのfocused testはfixtureと暗号化metadataの判定だけを検査し、MacのKeychain・Chromium・GPU動作は検証しません。

同じrunnerには、stockの通常GPU試験と分けたFamily 1 ANGLE実験モードがあります。実験を明示的に選んだ場合だけ、固定snapshotで定義を確認した次の4引数を両方の起動へ同じ順序で渡し、子プロセス環境に`ANGLE_PHASE5_ENABLE_METAL_FAMILY1=1`を設定します。

`--app`には、stock appへパッチや再署名を行わず、実験用に新しく組み立てたfirst-signing前のcopyを指定します。stock appはこの実験の入力に使いません。

```bash
python3 persistent_cookie_runner.py \
  --app "$experiment_app" \
  --out "$task_dir/family1-angle-cookie-restart" \
  --metal-family1-experiment \
  --browser-arg=--use-gl=angle \
  --browser-arg=--use-angle=metal \
  --browser-arg=--use-dynamic-angle \
  --browser-arg=--disable-angle-features=requireGpuFamily2 \
  --startup-timeout 45 --navigation-timeout 60 \
  --page-wait-seconds 60 --observe-seconds 20
```

この引数集合以外の`--browser-arg`、一部だけの指定、重複指定は拒否され、出力directoryやprofileの作成とbrowser起動より前に終了します。環境に同じopt-in変数が予期しない値で設定されている場合も拒否します。`context.json`と各`launch.json`には実際のargvと、このopt-in変数だけを記録します。stock試験では`--browser-arg`と`--metal-family1-experiment`を省略し、従来どおりの起動引数と通常GPU設定を使います。両モードとも独立した新しい`--out`を指定し、実験の成功は実機確認前には主張しません。SwiftShaderやnull backendへの切替は許可されません。

### Stage B WebGL1 shader fixture

`webgl1_runner.py`は、署名検証済みの新しい実験用Chromium copyと新規profileで、nonce付きloopback fixtureを一度起動します。seed/restore用の2D canvasやCSS色には頼らず、WebGL1 context、GLSL ES 1.00 vertex/fragment shader compile、program link、fullscreen triangle draw、中央pixel `readPixels`のRGBA `[0,160,0,255]`、`GL_NO_ERROR`を検査します。失敗ログはshader／programごと4096文字まで記録し、取得可能なGL version、vendor／renderer、debug renderer extensionのunmasked名は512文字まで記録します。page上の`DRAW_OK`／`READBACK_OK`または`FAIL`とpixel値、state観測時刻、GUI観察開始・終了UTC時刻を残し、CDP state・canvas中央のscreenshot patch・通常ページscreenshotも保存します。raw NetLogは使わず、fixture server eventにはnonce、path、statusだけを残します。

起動したfresh profileの`DevToolsActivePort`からlocal browser CDP endpointを検証して`SystemInfo.getInfo`／`getProcessInfo`を読み、限定したGL renderer/vendor/version、display type、feature status、GPU PIDとbrowser PIDをprivateな`gpu-info.json`へ記録します。API失敗は型だけを含む別diagnosticにし、WebGLのpass/failやerrorsへ混ぜません。browser-root CDP connectionはcloseしますが、capture helperからBrowser.closeは送りません。

```bash
python3 webgl1_runner.py \
  --app "$experiment_app" \
  --out "$task_dir/family1-webgl1" \
  --startup-timeout 45 --navigation-timeout 60 --observe-seconds 20
```

Runnerは既定のFamily 1用4引数と`ANGLE_PHASE5_ENABLE_METAL_FAMILY1=1`だけを適用します。boundsはMac／app検査と出力作成より先に確認され、appはlaunch前に`codesign --verify --deep --strict`で読み取り検証されます。WebGL stateのCDP確認は最大20秒、GUI観察時間は`--observe-seconds`で別に指定し、その秒数の観察が保証されるわけではありません。自動結果がpassでも、GUI確認と同一GPU PIDにおける独自dylib／Metal loadの親reviewは別途必要です。結果分類はreview待ちを明示し、単独ではStage Bの実機受入を意味しません。失敗時の自動retryや強制終了は行いません。

Program link後に`drawArrays`は返るもののpixelが期待色にならない場合は、acceptance runnerとディレクトリを分けて次のcomponent診断を使う。これは同じstrict app検証、Family 1 argv、env opt-inを使い、指定した新規`--out`だけを作る。

```bash
python3 webgl1_diagnostic_runner.py \
  --app "$experiment_app" \
  --out "$task_dir/family1-webgl1-diagnostic" \
  --startup-timeout 45 --navigation-timeout 60 --observe-seconds 20
```

16段階を順に記録する。最初は元の受入triangleと同じRGB `[0,160,0]` をdefault framebufferへ描き、明示clearや`gl.finish()`より前のraw `readPixels`と、finish後の再readbackを記録する。続いてdefault framebuffer clear、scissor clear、VBO triangle、uniform color triangle、通常canvasのconstant-attribute point、offscreen RGBA/UNSIGNED_BYTE framebuffer clear／triangle、antialias-disabled canvasのclear/VBO triangleを実行し、その同じsingle-sample contextでconstant-attribute yellow point、tightly-packed VBO point、12-byte stride interleaved VBO point、vec4/16-byte-stride VBO triangle、`bufferData(size)`+`bufferSubData`によるvec2 VBO triangle、clip内に収まるvec2 VBO triangleを比較した後、同じ3頂点・upload・attribute descriptorを使う`POINTS` count 3を追加対照として描く。matrix pointは同じ位置`(1/32,1/32)`・8px point、triangleはgreen readback、3点対照はyellow readbackを使う。記録するvertex attribute stateはenabled／size／type／normalized／stride／buffer一致／offsetと、constant pathの安全なvec4値に限定し、WebGL objectを保存しない。`bufferSubData`は実装内部で別のMetal storage pathを保証するものではなく、結果差は診断材料として扱う。最初のcanvasはacceptance fixtureと同じく`antialias:true`を要求し、実際の`getContextAttributes()`と`SAMPLE_BUFFERS`／`SAMPLES`を記録する。single-sample canvasは`antialias:false`を要求し、別contextの値とpixelを記録する。この比較は原因切り分けだけに使い、antialias-disabled成功を通常contextの受入へ置き換えない。各段階にdraw mode／first／count、viewport・scissor・cull・depth・stencil・blend・sampleのbounded raster state、draw call発行の有無、attribute／buffer／upload条件、期待pixelと実readback、bounded GL errorsを別々に保存する。shader/program logsは4096文字まで、pixelのreadbackはRGBA/UNSIGNED_BYTEのみ。最初のraw triangle後の段階では各操作前にGL stateをresetする。通常のGL error後は他の独立段階を続け、先行GL errorに`OUT_OF_MEMORY`またはcontext-lossが含まれる場合は以後のGL処理とmatrix stageをskipする。

Canvasは実WebGLの描画/readbackを表示し、2D canvas・CSS色・mock backendやWebGL extensionを使わない。`draw_call_issued`はAPI callが発行された記録であり描画成功を意味しない。色はreadback pixelで個別に照合する。結果はloopbackのnonce付き正確なdocument URLとraw state nonceを検証し、既知の16段階とdraw／raster metadataが重複・欠落・順序違いなく記録された場合だけcomplete markerを認める。全段階を記録できた場合もclassificationは`WEBGL1_DIAGNOSTIC_CAPTURED_REVIEW_PENDING`のままで、受入・conformance判定ではない。page画像、画面の段階一覧、`result.json`を次の判断材料として確認する。元の緑pixel acceptance fixtureは変更しない。

## 3. 署名設定の修正を、新規コピーで試す

この試験は、保存済みinventory／receiptで公式のHelper別設定との差が見つかった場合、または以前の署名処理対象を復元できず基準copyが必要な場合に実施する。

`sign_once.py`は次の設定を明示する。

- main app／通常Helper：`runtime,kill,restrict,library`
- Renderer／GPU／AperitifのRenderer・GPU：`runtime,kill,restrict`と各JIT entitlement
- Framework／dylib：hardened-runtime flagsを流用しない
- main appとJIT Helperのdevelopment entitlements：固定版のテンプレートに`get-task-allow`を追加
- 署名者はすべて同じ、現在有効なApple Development証明書
- main executableを単独で署名してからappで重ねて署名する処理は行わず、各ホストbundleを内側から一回ずつ署名

新規コピーと実行予定の一覧を作る：

```bash
python3 "$kit_dir/sign_once.py" prepare --source "$unsigned_app" --revisions "$revisions_file" --identity "$identity_sha1" --out "$task_dir/stock-role-policy"
python3 -m json.tool "$task_dir/stock-role-policy/signing-plan.json"
```

`prepare`では署名しない。原本の全Mach-Oが未署名であること、対象がsnapshot 1689422／thin x86_64／org.chromium.Chromiumであることを確認し、別コピーを作る。アプリの全ファイルとsymlinkを凍結し、署名対象・順序・flags・entitlementを一覧にする。全署名設定を適用する比較なので、成功後に必要なら差分をさらに絞り、単一キーの原因を推測しない。

一覧を確認した後の実行：

```bash
python3 "$kit_dir/sign_once.py" execute --plan "$task_dir/stock-role-policy/signing-plan.json"
python3 "$kit_dir/probe.py" inventory --app "$task_dir/stock-role-policy/Chromium.app" --out "$task_dir/new-stock-inventory"
python3 "$kit_dir/probe.py" probe --app "$task_dir/stock-role-policy/Chromium.app" --out "$task_dir/new-stock-normal"
```

署名を一つでも失敗した場合はそのコピーとreceiptを保存して停止する。実行済みコピーで署名をやり直さない。全体のstrict verificationに成功しても、ページ表示の合格とは別に判定する。

別のGUIユーザーが署名済みcopyを使う場合は、署名者側のstrict verificationだけでなく、対象ユーザーが各nested bundleの`_CodeSignature/CodeResources`を読み取れ、そこまでの親directoryを検索できることをread-onlyで確認する。macOSではsymlinkの`readlink`権限はリンク自体のmodeに依存するため、リンク先を開けることだけでは別ユーザーがリンクを読める証明にならない。`prepare`は安全なinternal symlinkを保ったうえで、別ユーザーに必要なread bitがないsymlinkを署名前に拒否する。future first-signではcodesign書込みsubprocessだけにumask `022`を渡し、新規signature resourceを他ユーザーから読めるmodeで生成する。signing plan、entitlements、receipt、command logはprivateのまま維持する。preflightに失敗した既存署名copyへad hocなchmodや再署名をせず、必要な対応は新しいfresh copyを使う手順として別途評価する。

このアダプターはsnapshot 1689422の署名部品設定専用。別snapshotに対しては対応する固定ソースを確認して更新する。原本とREVISIONSの結び付けには既存archive hash／取得記録も使う。REVISIONSファイルの一致だけでは、ローカルappの出所の証明にはならない。

## 4. 修正の採否

新規stockが成功したら、旧stockとの差分を署名receiptとinventoryで比較する。旧失敗を説明する実行時ログか再現条件を確認し、通常の設定へ戻した状態で3回の独立した新規profile試験に成功することを修正採用条件とする。

GUIの最終確認では、HTTPページを20秒間表示してから終了する次のコマンドを使う。固定文字列・JS marker・緑の四角が実ウィンドウで見えることを確認し、確認者と時刻を結果フォルダに記録する。

```bash
python3 "$kit_dir/probe.py" probe --app "$task_dir/stock-role-policy/Chromium.app" --transports=http --observe-seconds=20 --out "$task_dir/new-stock-gui"
```

新規stockも同じHTTP停止なら、同じ署名試行を追加しない。新旧のdocument／network／stderrを照合し、失敗requestと関係する最初のエラー・切断を決める。既存ログで分からない時のソース診断候補は、browserのURLLoaderFactory生成、networkのCreateLoaderAndStart／ScheduleStart／OnMojoDisconnect／NotifyCompleted。そのうちどの分岐を判別するかを選んでから本体ビルドの要否を判断する。

## 5. ANGLEへ進む条件

初回署名stockのHTTPページ・本文・JS・画面が成功してから、snapshotのDEPSが指定するANGLE `8efd15f...`へFamily 1対応を合わせる。新しい未署名コピーへdylibを組み込み、完成後に同じ署名policyで初回署名する。HTTP基準を再確認した後、独自ANGLEの同一GPU PIDロード・WebGL1 context・draw・readback、KOOVの画面・操作へ進む。

本キットはANGLEの版合わせ・ビルド・配置を自動化しない。現在のHTTP停止を先に解決するための実行手段である。

## 検証と出典

The portable suite checks HTTP failure classification, image validation, fixture isolation, signing policy, frozen-file detection, and bundle symlink handling. The symlink regression accepts internal links when the bundle root is reached through an aliased parent, while continuing to reject external and broken links. The mock browser exercises the CDP lifecycle but does not validate Chromium rendering or establish Keychain behavior. Use the GUI and fresh-profile acceptance criteria above for product acceptance.

```bash
python3 -m unittest -v test_kit.py
```

- CDP transport：ユーザーのリポジトリの固定[phase5-unsigned-cdp-probe.py](https://github.com/naokikambe/chromium-angle-family1-experiment/blob/292c7e2bab8bd06e9cf2ec50d7d20a451393290d/scripts/phase5-unsigned-cdp-probe.py)をそのまま同梱。
- Helper別署名policy：[固定Chromium parts.py](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/chrome/installer/mac/signing/parts.py)。
- 開発署名：[固定Chromium README](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/chrome/installer/mac/signing/README.md)。
- 実行時署名検証：[固定ProcessRequirement](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/base/mac/process_requirement.cc)。
- peer検証の既定値：[固定MachPortRendezvous](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/base/apple/mach_port_rendezvous_mac.cc)。
- 同梱entitlementの出典とSHA-256は`reference/provenance.json`、Chromiumのライセンスは`reference/LICENSE`。
