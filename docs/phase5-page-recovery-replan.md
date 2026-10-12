# ページ表示復旧：Keychain経路を中心にした再計画

更新日：2026-10-12。実機側の計測改善 `383310b` を前提とする。これは実行計画の更新であり、新しい実機試験の結果ではない。個別のPID・時刻・hash・生ログは実機ローカルの最新調査レポートに保持する。

仕様上の根拠と対策の限界は[公開資料の調査記録](phase5-keychain-public-evidence.md)を参照する。AppleのAPI・ACL・コード識別の資料を固定版Chromiumに対応付けている。

## 判断の変更

次の主作業は、Safe Storageへのアクセス承認と暗号化初期化がHTTP開始を待たせる仕組みの確認である。署名はKeychain項目の信頼条件を変える契機になり得るが、署名操作の来歴だけで停止を説明しない。正しい署名policyは保持し、署名設定の変更による探索を第一手にしない。

現行S0の原因特定を締める試験を先に行い、その結果に応じて通常Keychainでの復旧を検証する。10月5日の原因照合は並行する。過去の証跡未回収を理由に、現在のS0で実行できる検証を止めない。全事例の共通原因とするには、それぞれの証拠が必要である。

## 分かったことと証拠の範囲

以下の実測に関する整理は担当者報告に基づく。クラウドから実機の生ログを再監査したものではない。公開文書は判断の根拠と限界を示し、個別結果はローカル報告を参照する。

| 整理 | 現時点で言えること | 残る確認 |
| --- | --- | --- |
| 通常Keychain／mockの対照 | 測定したコピーではKeychain providerの切替がHTTP・文書・JS・描画の自動検査結果を変える。現行S0には通常→mock→通常の対照もある | provider切替の効果と、具体的な承認状態・API返却を区別する |
| unsigned・適切な初回署名版も停止 | 再署名という操作履歴は、報告された停止に必要な条件ではない | 署名属性が既存Keychainの信頼条件にどう関係するか |
| S0の同一試行のruntime／network証拠 | Keychain待機、securitydのprompt記録、HTTP stream開始前の停止が対応付けられた。承認待ちによる停止が強く支持される | オーナーの実際の応答、API返却後の挙動、callbackの直接観測範囲 |
| mock診断の成功 | 試験ページを読み込み描画できる経路が存在する。HTTP停止の調査は送信前の処理を優先できる | 実GUIの3件確認。ANGLEロード・WebGL・KOOVは別途検証 |
| 固定版のコード経路 | Keychain workerの返却に暗号化初期化、cookie取得、HTTP開始が依存する。拒否が返った場合にも初期化を進める経路がある | 実行した版・プロセス構成とruntime結果の対応 |
| 10月5日の試行 | 原因への適用範囲は未確定 | アーカイブの回収と入力・起動条件・停止境界の照合 |

「画面が描けない」という症状について、現在の主な停止位置はHTTP送信前として調べる。空白画面だけをGPU故障の根拠にしない。mockでの成功も、通常Keychainでの製品復旧や全履歴の原因確定と同一視しない。

## まず締める原因調査

今回の委任作業の完了条件は根本原因の特定である。[続行プロンプト](phase5-keychain-investigation-handoff.md)と[当初の因果証拠の条件](phase5-page-recovery-handoff.md)を適用する。

1. 既存の通常→mock→通常と同一試行の対応表を再利用する。入力・引数・profile・Keychain状態に不明な差がある場合だけ補う。
2. GUI観察と一度だけの拒否試験を、オーナーが応答できる一回の測定枠にまとめる。既に送信した質問の回答を使い、必要な操作だけ具体的に依頼する。拒否が実際に同じPID・対象項目へ反映されたことを確認する。
3. `API返却／未返却 → 暗号化初期化 → cookie取得 → HTTP stream → server受信 → DOM・JS・画像・実GUI`を対応付ける。Browser・Network serviceなどのPIDと親子関係を記録し、別プロセスの処理を同じPIDだと仮定しない。直接観測とソースからの推定を分ける。
4. 成功した条件は独立した3つの新規profileと実GUIで確認する。既存試験の観察を確認できれば再利用し、不足分だけ実施する。
5. 現行S0の原因、他の測定コピーへの適用範囲、未照合の過去試行、恒久修正の未実施を別々に報告する。

拒否操作やGUI確認を行えない場合は、その完了条件は未達とする。証跡分析や復旧案の準備を進め、実施待ちを完了と扱わない。2〜4時間は中間報告の区切りであり、調査終了の期限ではない。

## 次の結果で選ぶ施策

| 実測結果 | 判断と次の施策 |
| --- | --- |
| 拒否後にAPIが返り、HTTP・描画が進む | 未応答の承認待ちが停止条件だった説明が強まる。暗号化鍵が使えないままの表示成功を製品受入とせず、正常に鍵を取得する条件へ進む |
| 拒否の記録はあるがAPIが返らない | 応答した項目・PID・要求が正しいか、追加promptや別のKeychain待ちがないか確認する |
| APIは返るがHTTPが止まる | provider初期化、cookie callback、URLRequestの順に、最初に完了しない処理を特定する。追加観測をその境界に限定する |
| prompt記録はあるが実画面に出ない | GUIセッション・表示先・起動元を確認し、オーナーが実際に応答できる起動経路で再測定する |
| 通常Keychainの一度の許可で表示する | 正常アクセスの復旧候補になる。次に再起動と鍵の再利用を検証し、一回のプロセス限りの許可と持続する条件を区別する |

一度の許可は、対象app・項目・操作についての既存の明示的な同意がある場合に限る。同意がなければ試験を具体化して確認する。今回の原因調査でACL編集・Always Allow・既存項目削除は行わない。

## 原因特定後：通常Keychainでのstock復旧

この工程は後続の実行計画であり、今回の調査完了を宣言するために製品受入まで要求するものではない。

### 1. 本体ビルドを要しない正常アクセスを試す

同一snapshotから正しいrole policyで初回署名したstockコピーを使い、通常Keychainでの正常な承認応答によりfixtureを表示できるかを確認する。入力・署名identity・bundle identifier・実際の署名要件を固定し、既存アプリへ上書きしない。

再起動のたびに手動応答が必要か、同じprofileの鍵を再利用できるかを記録する。一度だけの許可は因果の確認に使えるが、継続利用の解決と判断するには不十分である。

### 2. 独立した通常Keychain環境で比較する

先に、秘密値を読まずにSafe Storage itemの実所属Keychainと検索順を確認する。Apple TN3137によればユーザーの検索一覧にはloginと共有Systemが含まれる。対象itemがSystemにある場合や同名itemが複数ある場合、別ユーザーでも同じitemへ到達し得るため、loginの分離だけで完全隔離したと判断しない。

既存の検証用GUIユーザーがあれば、それを優先する。ない場合は、同じMacに検証用ユーザーと独立したlogin Keychainを用意する案を具体化し、必要なシステム変更の承認後に実施する。同じ署名済みappを変更せず使用し、他ユーザーのKeychain・秘密鍵・既存profileは移さない。appのhash・署名検証と新しいGUI所有ユーザーを記録する。

独立環境でもmockを使わず、Safe Storage項目の作成／取得とcallbackの完了を確認する。項目がない場合に新しい鍵を作成する経路は固定版ソースに存在するが、このMacで成功することを保証するものではない。

ここで成功すれば、既存ユーザーのKeychain項目・信頼条件との関係を調べる根拠になる。ユーザー変更は他の環境差も含むため、それ単独で因果確定せず、アクセス結果と要求のtimelineを合わせて評価する。

### 3. 継続利用するKeychainの方針を選ぶ

独立環境で正常動作する場合、既存ユーザーでの復旧について次の候補を比較する。

- **対象アプリに限定した信頼条件の整備。** 対象項目・現在のtrusted-app要件・署名済みappの要件・提案差分を読み取り専用で整理する。採用時はオーナーの明示的な承認を得て対象項目だけに適用し、既存の暗号化データと利用アプリへの影響、復元手順を検証する。これは現在の原因調査の権限に含めない。
- **実験アプリのKeychain利用を分離。** 検証用ユーザーによる分離を継続する、または将来のアプリ構成で専用Safe Storage名と安定した署名要件を設計する。専用名の実行時設定が手元のビルドで利用できるかを確認し、使えない場合は必要な本体変更とビルド費用を見積もる。

固定版の既定service/account名はbrandingで決まる。新規profile、`CFBundleName`、bundle identifierの変更だけで専用Safe Storageへ切り替わるとは想定しない。既存の項目を削除して作り直す方法や、全アプリに許可する方法は採用しない。

対象appの個別許可はApple Supportにも説明がある通常の機能である。採用時はfile-based ACLかdata protectionのaccess groupかを確かめ、正しい方式を使用する。一般的なaccess-group entitlementの追加だけで既存file-based itemのACL問題が解決すると想定しない。

### 4. 通常動作として受け入れる条件

mock、GPU無効化、保護機能の無効化を使わず、正しい初回署名済みstockで次を確認する。

1. HTTP・本文・JS・fetch・画像・実GUIが独立した3つの新規profileで成功する。
2. 通常のKeychainアクセスが完了し、再起動ごとに未応答のpromptで停止しない。
3. 同じ検証用profileを再起動し、非機密のテスト用persistent cookieなどで鍵の再利用と暗号化保存を検証する。単なるcookieの存在確認だけでは暗号化の検証済みとしない。実アカウントの認証情報は使わない。
4. 新規profileで表示できることと、既存データの安全な継続利用を別々に確認する。実ユーザーのデータ移行は別途範囲を決める。

現在の`probe.py`は試行ごとに新規profileを作るため、同じprofileの再起動試験は別の小さな受入runner、または限定した拡張で実施する。非機密のpersistent cookieをfixtureで発行し、正常終了後に同じprofileで再起動して送信・復号を確認する。作成したプロセスだけを終了し、既存profileを入力に使わない。暗号化保存の確認は対象テストcookieの保存形式と取得結果を対応付け、鍵や実ユーザーのcookieを出力しない。

これをstock復旧の基準とし、ANGLE追加後にも同じ基準を適用する。

## 本体コード変更へ進む条件

正常な承認応答・独立した通常Keychainでの比較を行っても、具体的なAPI／callbackが完了しない場合に検討する。最初の対象はKeychain provider、OSCryptAsync、CookieOSCryptAsyncDelegate、SQLitePersistentCookieStoreのうち観測で決まった境界とする。URLLoader／IPCはその先に未説明の停止が残る場合に調べる。

恒久修正が必要なら、アクセス待ちの可視化、適切な失敗通知・再試行、暗号化初期化の完了条件を設計する。鍵がない状態で暗号化が成功したように扱う修正や、既存暗号化データを破棄する修正は行わない。必要なコード差分と検証を決めてから、永続出力・cache・実行時間を備えたビルド環境を用意する。

無関係な小規模targetの追加ビルドは、この停止の検証には数えない。今回の計画更新ではCI dispatch／cancelを行っていない。

## stock復旧後：ANGLEとKOOV

1. 成功した公式snapshotとDEPSのANGLE revisionを固定する。
2. Family 1対応をそのANGLE版へ合わせ、必要なANGLEライブラリをビルドする。
3. 新規の完全未署名Chromiumへ組み込み、完成後に同じidentity・role policyで初回署名する。
4. 通常Keychainでstockと同じ受入試験を行い、独自ANGLEの同一GPU PIDロード、WebGL1 context・draw・readbackを確認する。
5. KOOVのdocument・画面・基本操作・再起動後の利用・安定性を確認する。認証情報入力や機器連携は承認された範囲で行う。

## 作業時間と現在の境界

| 工程 | 実作業の予算 | 前提 |
| --- | --- | --- |
| 拒否応答・実GUI・現行S0の因果整理 | 30〜90分 | オーナーが測定枠に参加できる。新しい停止が見つかれば再見積もり |
| 通常Keychainの正常アクセス／独立環境の比較 | 1〜3時間 | 入力appと実行権限がそろっている。ユーザー準備・承認待ちは別 |
| 継続利用条件の整備とstock受入 | 比較結果後に見積もる | Keychain方針とデータ影響を確認してから実行 |
| ANGLE版合わせ・KOOV | stock復旧後に見積もる | Family 1差分とビルド環境を確認する |

これらは解決期限ではない。現在の未完了は、拒否応答後の観測と実GUI確認、10月5日の適用範囲、通常Keychainでの継続利用条件である。原因調査の完了と、製品の復旧完了を別々に判定する。

計測では`383310b`の`post-observation/`を利用する。document・画像の採取時刻、オーナー応答時刻、server受信、NetLogを対応付ける。CDPイベント配列のsnapshot時刻をイベント発生時刻と同一視しない。通常の`result.json`は待機前のdocument値と試行全体のserver受信を含むため、classificationやexit codeだけで応答後の復旧を判定しない。

実機の結果はローカルの調査レポートへ保存し、公開文書は手順・判定条件・限界を更新する。コードを変更する場合は必要な検証と関連ドキュメントを同じコミットにまとめ、作業ブランチへpushする。

## 参照

- [Keychain調査の続行プロンプト](phase5-keychain-investigation-handoff.md)
- [計測キットと結果の解釈](../scripts/page-recovery/README.md)
- [初期の実行計画](phase5-page-recovery-plan.md)
- [固定版KeychainPassword](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/components/os_crypt/common/keychain_password_mac.mm)
- [固定版KeychainKeyProvider](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/components/os_crypt/async/browser/keychain_key_provider.mm)
- [固定版OSCryptAsync](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/components/os_crypt/async/browser/os_crypt_async.cc)
