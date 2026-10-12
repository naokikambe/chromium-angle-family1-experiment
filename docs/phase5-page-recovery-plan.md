# ページ表示問題の具体施策・実行計画

2026年10月12日作成。前の再計画を、実機で実行できる手順とスクリプトに具体化したもの。

## 目標と根本解決の判定

目標は、公式の未署名・ビルド済みChromiumへ独自ANGLEを組み込み、Apple Development証明書で初回署名した実機アプリで、HTTPページとKOOVを正常に表示すること。

根本解決と判断するには、停止した条件と修正差分が対応し、通常GUI・通常の保護設定でページが表示でき、独立した新規profileで3回再現する必要がある。HTTP 200、署名検証成功、アプリ起動、画像ファイルの存在だけで完了とはしない。

現時点で原因は未確定であり、この計画の作成だけで解決を保証するものではない。原因を具体的に検証し、修正の採否を判定できる実行手段を用意した。

## 実行手段

クラウド上の準備からMacBookAir6,1実機での作業へ移る。GitHubの`naokikambe/chromium-angle-family1-experiment`、`phase5-page-recovery`ブランチを実機へclone、または既存checkoutでfetchして別worktreeへ展開する。取得コマンドとGUIユーザー・Keychainの開始確認は[実機向け引き継ぎプロンプト](phase5-page-recovery-handoff.md)に記載した。実験用app・過去ログ・証明書は実機の保存物を使用する。

リポジトリの [`scripts/page-recovery/`](../scripts/page-recovery/README.md) をMacで使用する。Python 3.10以上と、MacのGUIログインユーザーのTerminalを使用する。追加Pythonパッケージは不要。

- `probe.py inventory`：本体・全Mach-Oの署名者、Team ID、署名要件、entitlement、flags、hashを記録する。
- `probe.py probe`：同じ内容をdata／file／HTTPで開き、本文、JavaScript、追加fetch、画面画像、緑色ピクセル、2D canvas readbackを検証する。対象ページのCDPイベント・NetLog・stderrを保存する。
- `sign_once.py prepare`：完全未署名の原本から新規コピーを作り、Helper別の署名設定と実行順序を生成する。
- `sign_once.py execute`：生成した一覧に従い、新規コピーへ初回署名し、各実行結果とstrict verifyを保存する。

実行コマンド・入力変数は[キットREADME](../scripts/page-recovery/README.md)に記載。既存S0、完全未署名の原本、REVISIONS、Apple Development証明書SHA-1の4点を実機側で対応付ける。次の担当者へ渡す指示は[引き継ぎプロンプト](phase5-page-recovery-handoff.md)を使用する。

## 初日の作業順序

| 順序 | 施策 | 作業時間の目安 | その場で得る判断 |
| --- | --- | --- | --- |
| 1 | 保存済みS0のinventoryと、data／file／HTTPの基準試験 | 30〜60分 | 起動、ローカル文書、HTTP、描画のどこで失敗するか |
| 2 | 最初の失敗に対応する対照を一つ実施。HTTPのみ失敗ならGPU無効化、起動エラーならCrashpad・GUI起動元を確認 | 20〜40分 | GPU・起動環境がページ停止と関係するか |
| 3 | 署名receiptと実際のHelper設定を固定ソースと照合 | 30〜60分 | 修正する具体的な署名設定、または署名仮説を後退させる証拠 |
| 4 | 設定差が見つかった場合、新規unsigned原本から設定を修正したstockコピーを作り初回署名・同じ試験 | 30〜60分 | 本体ビルドなしでページ表示が復旧するか |
| 5 | 成功ならGUI確認と独立した3回の新規profile試験。失敗なら対象requestの最初のエラー・切断を特定 | 30〜60分 | 修正採用、または次の具体的な観測点 |

初回は2〜4時間を区切りとする。アプリ・証跡・証明書がそろっている場合の作業予算で、解決期限ではない。丸一日を超えて同じ試験や候補ビルドを繰り返さず、得られた失敗段階と不足する観測を報告する。

## 最初に実施する修正候補

### Helper別の署名設定を正す

固定版のChromium公式署名手順は、通常Helper、Renderer、GPUでflagsとentitlementを使い分ける。Renderer／GPUはJIT許可とlibrary validationの扱いが異なる。

確認した既存Chrome用スクリプトはHelper名に `Google Chrome` を含む場合を特別扱いしている。このコードをChromiumにそのまま使うと、必要な設定が適用されない可能性がある。ただし、当時のS0/S1が実際にこの処理を使ったか、署名結果が誤っていたかはまだ未証明である。実際のreceipt／inventoryとの照合を先行させる。

キットの初回署名アダプターは `Chromium Helper` とAperitifの役割を識別し、固定版のflagsとentitlementを明示する。本体やFramework全体へ同じ設定を一律適用しない。全Mach-Oが未署名であることを確認し、別コピーを凍結してから内側より署名する。失敗したコピーの再署名は行わない。

この一回の比較で成功しても、直ちに単一のflag／entitlementが原因とはしない。新旧の署名差分と、失敗requestのログを対応付けて原因条件を確定する。

### 実行時の署名検証を観測する

ChromiumのProcessRequirementは、Team IDだけでなく証明書種別も照合する。静的codesign verifyだけでは、この実行時条件を確認できない。キットは通常のネットワークログに加え、ProcessRequirementやMach port rendezvousのVLOGを採取する。

固定版ソースはApple Development証明書を扱うコードを持つ。したがって「Apple Developmentだから必ず通信できない」という説明は採用しない。また、参照版ではMach port peer validationの強制拒否は既定OFFである。警告ログを見つけただけで根因とせず、失敗request・実際のプロセス終了／切断・適用された実行条件との相関を確認する。

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

## stock復旧後のANGLEとKOOV

1. ページ表示に成功した公式snapshotを固定する。
2. そのDEPSのANGLE版にFamily 1修正を合わせ、ANGLEだけをビルドする。既存e12217f3版との不一致を放置しない。
3. 新しい未署名Chromiumへ組み込み、成功した署名policyで完成後に初回署名する。
4. stockと同じHTTP／本文／JS／画面の基準を確認する。
5. 独自ANGLEの同一GPU PIDロード、WebGL1 context・draw・readbackを確認する。
6. KOOVのdocument、画面、基本操作、30分程度の安定性、必要な機器連携を順に確認する。

ANGLEの版合わせの見積もりはstock復旧後の差分確認で出す。HTTP停止が残ったままANGLE移植・小規模プログラムの追加コンパイルを進めない。

## 作成済みと未実施

作成済み：診断キット、具体的な署名修正試験のprepare／execute手順、結果別の分岐、合格条件。

クラウド上で10件の検証を実施。Mac実機のcodesign、本物のChromium、GUI、KOOVでの実行は未実施である。これはMac実機で実行するための準備成果で、根本解決済みの報告ではない。

小規模ビルドの候補追加は打ち切りを提案する。別チャットで進行するCIの停止・方針変更は本作業では操作していない。
