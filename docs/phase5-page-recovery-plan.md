# ページ表示問題の具体施策・実行計画

現在の判断と次の工程は[Keychain経路を中心にした再計画](phase5-page-recovery-replan.md)を参照する。以下は初期の計画と診断候補を保持した記録であり、実施順序は再計画を優先する。

2026年10月12日作成。前の再計画を、実機で実行できる手順とスクリプトに具体化したもの。

## 今回の完了条件と製品の目標

今回の調査は、ページ描画不可問題の根本原因を実機の証拠と対照実験で特定するまでを完了条件とする。再現条件、停止させた具体的な設定・処理と仕組み、原因条件だけを変えた成功／失敗の対照、主要な別の説明の検討、追試可能な証跡をすべて必要とする。表示が一度復旧しても原因を説明できなければ未完了である。

署名変更を原因とする場合は、署名だけを変えた対照に加えて、実行時に対象requestを止めた処理とその仕組みを示す。初回署名と後の署名操作を区別し、両方で同じ問題が見られる場合は両者に共通する条件も検証する。過去の比較の再掲だけでは原因を確定しない。詳細な必須条件と追加証拠の報告形式は[引き継ぎプロンプト](phase5-page-recovery-handoff.md)に記載する。

製品としての最終目標は、公式の未署名・ビルド済みChromiumへ独自ANGLEを組み込み、Apple Development証明書で初回署名した実機アプリで、HTTPページとKOOVを正常に表示すること。ANGLE移植・KOOV全体の確認は今回の原因特定後の後続工程とする。

原因検証の成功判定にはHTTP本文・JS・画像・実GUIを使用し、復旧した条件では独立した新規profileで3回確認する。診断用の限定変更による因果の証明と、製品への恒久修正の採用は区別する。製品として根本解決と判断するには、原因に対応する恒久修正と、通常GUI・通常の保護設定での3回の成功が必要である。HTTP 200、署名検証成功、アプリ起動、画像ファイルの存在だけで完了とはしない。

ページ停止の原因はまだ確定していない。Chromium Safe Storage authorizationや非同期暗号化callbackの待ちを含む候補を、実行時stack、securityd authorization情報、read-only trusted-app metadata、network request timelineで調べる。調査は継続中であり、2026-10-05の試行条件への適用範囲、GUI owner confirmation、通常Keychain条件でのproduct acceptance、ANGLE/KOOV確認は未完了である。

## 実行手段

クラウド上の準備から対象Macでの作業へ移る。GitHubの`naokikambe/chromium-angle-family1-experiment`、`phase5-page-recovery`ブランチをMacへclone、または既存checkoutでfetchして別worktreeへ展開する。取得コマンドとGUIユーザー・Keychainの開始確認は[実機向け引き継ぎプロンプト](phase5-page-recovery-handoff.md)に記載した。試験用appと署名identityは適切なアクセス制御の下で扱い、公開記録には再現可能な条件・結果要約を記載する。

リポジトリの [`scripts/page-recovery/`](../scripts/page-recovery/README.md) をMacで使用する。Python 3.10以上と、MacのGUIログインユーザーのTerminalを使用する。追加Pythonパッケージは不要。

- `probe.py inventory`：本体・全Mach-Oの署名者、Team ID、署名要件、entitlement、flags、hashを記録する。
- `probe.py probe`：同じ内容をdata／file／HTTPで開き、本文、JavaScript、追加fetch、画面画像、緑色ピクセル、2D canvas readbackを検証する。対象ページのCDPイベント・NetLog・stderrを保存する。
- `sign_once.py prepare`：完全未署名の原本から新規コピーを作り、Helper別の署名設定と実行順序を生成する。
- `sign_once.py execute`：生成した一覧に従い、新規コピーへ初回署名し、各実行結果とstrict verifyを保存する。

実行コマンド・入力変数は[キットREADME](../scripts/page-recovery/README.md)に記載。比較対象の既存stock app、完全未署名の原本、REVISIONS、Apple Development identityを適切に対応付ける。次の担当者へ渡す指示は[引き継ぎプロンプト](phase5-page-recovery-handoff.md)を使用する。

## 初日の作業順序

| 順序 | 施策 | 作業時間の目安 | その場で得る判断 |
| --- | --- | --- | --- |
| 1 | 保存済みstock appのinventoryとdata／file／HTTP基準試験 | 30〜60分 | 起動、ローカル文書、HTTP、描画のどこで失敗するか |
| 2 | 最初の失敗に対応する対照を一つ実施。HTTPのみ失敗ならGPU無効化、起動エラーならCrashpad・GUI起動元を確認 | 20〜40分 | GPU・起動環境がページ停止と関係するか |
| 3 | 署名receiptと実際のHelper設定を固定ソースと照合 | 30〜60分 | 修正する具体的な署名設定、または署名仮説を後退させる証拠 |
| 4 | 設定差が見つかった場合、新規unsigned原本から設定を修正したstockコピーを作り初回署名・同じ試験 | 30〜60分 | 本体ビルドなしでページ表示が復旧するか |
| 5 | 成功なら原因条件だけを変えた失敗／成功の対照と、GUI・独立した3回の新規profile試験。失敗なら対象requestの最初のエラー・切断を特定 | 30〜60分 | 原因特定の証拠がそろったか、次に何を観測するか |

初回は2〜4時間を中間報告の区切りとする。必要な入力・実行環境・権限がそろっている場合の作業予算で、調査の終了条件ではない。根本原因の特定まで検証を続ける。新しい測定を加えない反復を避け、停止段階と不足する観測を報告して次の検証を選ぶ。権限・入力・実行資源の不足で中断する場合は未完了と明示し、再開条件を記録する。

## 最初に実施する修正候補

### Helper別の署名設定を正す

固定版のChromium公式署名手順は、通常Helper、Renderer、GPUでflagsとentitlementを使い分ける。Renderer／GPUはJIT許可とlibrary validationの扱いが異なる。

既存Chrome用スクリプトの一部はHelper名に `Google Chrome` を含む場合を特別扱いする。このコードをChromiumにそのまま使うと、必要な設定が適用されない可能性がある。ただし、以前の試験で実際にこの処理が使われたか、署名結果が誤っていたかは別途確認が必要である。receipt／inventoryとの照合を先行させる。

キットの初回署名アダプターは `Chromium Helper` とAperitifの役割を識別し、固定版のflagsとentitlementを明示する。本体やFramework全体へ同じ設定を一律適用しない。全Mach-Oが未署名であることを確認し、別コピーを凍結してから内側より署名する。失敗したコピーの再署名は行わない。

この一回の比較で成功しても、直ちに単一のflag／entitlementが原因とはしない。新旧の署名差分と、失敗requestのログを対応付けて原因条件を確定する。

### 実行時の署名検証を観測する

ChromiumのProcessRequirementは、Team IDだけでなく証明書種別も照合する。静的codesign verifyだけでは、この実行時条件を確認できない。キットは通常のネットワークログに加え、ProcessRequirementやMach port rendezvousのVLOGを採取する。

固定版ソースはApple Development証明書を扱うコードを持つ。したがって「Apple Developmentだから必ず通信できない」という説明は採用しない。また、参照版ではMach port peer validationの強制拒否は既定OFFである。警告ログを見つけただけで根因とせず、失敗request・実際のプロセス終了／切断・適用された実行条件との相関を確認する。

### KeychainのSafe Storage待ちを診断する

続行する実機担当者は[Keychain調査の続行プロンプト](phase5-keychain-investigation-handoff.md)を使用する。次は、承認状態を変える前の通常→mock→通常の対照、独立した3試験の実GUI確認、承認応答前後のAPI／callback／HTTP timeline、10月5日の試行条件への適用範囲の確認を進める。アクセス拒否がAPIから返った状態と、未応答の承認待ちで返らない状態を区別する。根本原因の特定と通常Keychainでの製品受入は別の判定である。

現在の`probe.py`はGUI観察待機前にdocumentと画像を採取する。待機中にダイアログへ応答する試験では、応答後の観測を改めて採取し、応答前の結果で復旧を判定しない。

Chromium Safe Storage authorizationや、暗号化providerの非同期callback待ちは、HTTP navigationが始まらない場合に調べる候補である。各試行にはfresh profileを使い、app、arguments、fixtureなどの条件を揃えて一つの要因だけを変える。`--use-mock-keychain`を対照にする場合も、それ以外のbrowser argumentsと環境条件を固定する。GPU設定など別要因の対照を行うときは、変更した条件を明示する。

候補を評価するには、process stack、同じ時刻のsecurityd authorization記録、read-only trusted-app metadata、nonce付きnetwork request timelineを相互に対応付ける。確認対象は、Keychain item accessのauthorization待ち、OSCryptAsync initialization callback、cookie-store callback、およびHTTP transaction開始の順序である。`--use-mock-keychain`で結果が変化しても、それだけで機構や製品原因を確定しない。SecretsやKeychain item contentsを取得せず、ACLを変更しない。

| 証拠 | 確認する内容 | 解釈の限界 |
| --- | --- | --- |
| 署名情報・静的検証 | app、nested bundles、role flags、entitlements、初回署名と後続操作の来歴 | 署名との相関だけでは、runtime navigation stopの因果を示さない |
| runtime／Keychain記録 | 同一process・時刻のKeychain access waitやauthorization、async callback完了 | stackやpermission prompt単独では、対象HTTP requestとの結び付きを示さない |
| network timeline | request開始、cookie processing、HTTP stream開始、server受信を照合 | status codeやGUI画像単独では、ユーザーに見える画面を確認しない |
| paired mock-keychain diagnostic | fresh profilesでKeychain providerだけを切り替え、同じfixtureを再試行 | 診断介入であり、通常Keychainでのproduct acceptanceや全履歴の原因確認ではない |

署名policy比較では同一snapshot由来のunsigned sourceと別のnew outputを使い、complete signing planとrole settingsを確認する。初回署名と後の再署名を区別し、適切なrole policyでも問題が続く場合はKeychain authorizationなど他要因を調べる。`--use-mock-keychain`は診断介入であり、製品修正として採用しない。Ordinary-Keychain acceptanceには、通常GUIの人間確認と通常設定での独立した3 fresh profilesの成功が必要である。2026-10-05の試行条件への適用範囲も確認する。

コード経路の参照は固定commit `82303c21` の`components/os_crypt/async/browser/keychain_key_provider.mm`、`components/os_crypt/common/keychain_password_mac.mm`、`net/url_request/url_request_http_job.cc`。中間のcallback依存は`components/os_crypt/async/browser/os_crypt_async.cc`、`services/network/network_context.cc`、`net/extras/sqlite/sqlite_persistent_cookie_store.cc`で確認し、実際の入力版・実行時証拠と対応付ける。

### 観測環境を正す

既存記録には、通常sandboxからの試行で証明書identityが見えず、CrashpadのPermission deniedが発生した例がある。キットはGUI所有ユーザーから実行する。root、別ユーザー、別sandboxの結果を混ぜない。

Crashpadエラーで起動できない場合は、起動元を正した同じアプリで確認する。必要なら一試行の追加フラグとして`--disable-breakpad`を使用し、ページ通信の問題と起動エラーを分ける。

## 結果ごとの具体的な修正方向

| 確認した失敗 | 次の施策 |
| --- | --- |
| RendererのJIT entitlement／flagsが不足 | 新しいunsignedコピーのRenderer署名だけを適切な役割設定にした比較を準備し、ローカル文書とHTTPを再確認 |
| 実行中Helperの署名者・証明書種別が不一致 | 正しい一つのApple Development identityで全対象を初回署名するコピーを準備し、該当切断とHTTP停止が消えるか確認 |
| GUI・証明書trust可視性の違いで起動失敗 | 同じGUIユーザー・同じ有効identityを使う起動経路に固定し、既存アプリを変更せず再観測 |
| ローカル文書成功、HTTPのGETだけ未受信 | stockでもGPU無効化でも同じか確認し、renderer由来requestとbrowser由来通信のログを区別。署名修正で変化がなければURLLoader／IPCの観測へ |
| HTTP応答・DOM・JS成功、画像が空白 | documentの問題として扱う調査を終了し、compositor／GPUの通常・無効化対照へ |
| stockは成功し、独自ANGLE追加後だけ失敗 | ANGLEの版・dylibの配置と依存・同一GPU PIDロードを確認し、差が初めて出るGPU条件だけを変更 |

## 本体ビルドを行う場合の条件と対象

最初からChromium全体をビルドする計画にはしない。署名policyと起動環境の比較を終え、既存ログで判別できない具体的な分岐が残った場合に採用する。

追加診断の対象は次のうち、欠けた観測に必要な箇所に限定する。

1. browserの`StoragePartitionImpl::CreateURLLoaderFactoryForBrowserProcessInternal`：factory生成・再生成・接続状態。
2. networkの`URLLoaderFactory::CreateLoaderAndStart`：対象requestの到達・loader生成。
3. `URLLoader::ScheduleStart`：deferと要求開始。
4. `URLLoader::OnMojoDisconnect`／`NotifyCompleted`：切断とエラーコード。

生成した診断アプリを問題が再現する同じ実機・署名条件で使うところまで設計する。未署名CIだけを実行して署名後問題の検証済みとはしない。前回時間切れになった環境の再利用は、永続workspace／出力cacheや実行速度の改善を確認してから判断する。

## 原因特定・stock復旧後の後続工程：ANGLEとKOOV

以下は製品の最終目標への後続工程であり、今回の根本原因調査の完了条件には含めない。

1. ページ表示に成功した公式snapshotを固定する。
2. そのDEPSのANGLE版にFamily 1修正を合わせ、ANGLEだけをビルドする。既存e12217f3版との不一致を放置しない。
3. 新しい未署名Chromiumへ組み込み、成功した署名policyで完成後に初回署名する。
4. stockと同じHTTP／本文／JS／画面の基準を確認する。
5. 独自ANGLEの同一GPU PIDロード、WebGL1 context・draw・readbackを確認する。
6. KOOVのdocument、画面、基本操作、30分程度の安定性、必要な機器連携を順に確認する。

ANGLEの版合わせの見積もりはstock復旧後の差分確認で出す。HTTP停止が残ったままANGLE移植・小規模プログラムの追加コンパイルを進めない。

## 作成済みと未実施

作成済み：診断キット、具体的な署名修正試験のprepare／execute手順、結果別の分岐、合格条件。portable tests cover fixture classification, mock-browser CDP flow, signing policy, frozen-file checks, and symlink containment. Platform and product acceptance require their own validation.

キットのsymlink検証では、resolved targetを未解決のapp pathと比較していたため、macOSの`/var`と`/private/var`の別名を通る内部リンクを誤って拒否する問題が見つかった。app rootをcanonicalizeして比較する修正とsymlink parent alias regressionを追加した。portable regression checks that internal links through an aliased parent are accepted while external and broken links are rejected.

ページ表示の原因調査は継続中であり、現在の資料は根本原因を確定しない。2026-10-05の試行条件への適用範囲、GUI owner confirmation、ordinary-Keychain product acceptance、ANGLE/KOOVは未完了。`--use-mock-keychain`によるdiagnostic resultだけでproduct recoveryとは判定しない。

小規模ビルドの候補追加は打ち切りを提案する。別チャットで進行するCIの停止・方針変更は本作業では操作していない。
