Mac実機で進めているChromiumのページ描画不可問題の調査を続行してください。今回の完了条件は、根本原因を実機の証拠と対照実験で特定することです。直近の報告で絞り込んだKeychain経路を優先し、原因の証明に必要な検証を実行してください。

現在の判断・結果別の分岐・通常Keychainでの復旧案は[再計画](phase5-page-recovery-replan.md)を参照してください。今回の委任作業は原因特定までとし、復旧・Keychain環境整備・ANGLE／KOOVは結果に応じた後続工程です。

## 開始地点

リポジトリは `naokikambe/chromium-angle-family1-experiment`。実機側の変更は `page-recovery-device-20261012` の `383310b`、続行用の資料は、その変更を取り込んだ `phase5-page-recovery` ブランチにあります。既存checkoutのHEAD・dirty状態・AGENTS.mdを確認し、既存作業を保持して最新版の資料を取得してください。

```bash
git fetch origin refs/heads/phase5-page-recovery:refs/remotes/origin/phase5-page-recovery
git log -3 --oneline origin/phase5-page-recovery
git merge-base --is-ancestor 383310b origin/phase5-page-recovery
```

fast-forwardできる場合は取り込み、別の変更がある場合は保持した別worktreeで作業してください。試験のHEADを記録します。関連資料は[実行計画](phase5-page-recovery-plan.md)、[キットREADME](../scripts/page-recovery/README.md)、[当初の完了条件](phase5-page-recovery-handoff.md)です。

対象はMacBookAir6,1／Intel HD Graphics 5000のGUIログイン済みMacです。同じGUIユーザーと適切な実行経路を使い、Keychain・GUIへのsandbox制限をアプリの故障と混同しないでください。

実機上の最新の調査レポート・証跡一覧を読み、各コピーの通常Keychainと `--use-mock-keychain` の結果、stack、securityd、ACL metadata、未確認事項を確認してください。既にユーザーへ送った質問の回答も確認し、同じ質問を繰り返さないでください。実機固有の結果と保存場所は、この公開文書への転載を前提としません。

## 検証する仕組み

優先する仮説は、Safe Storage項目へのアクセスで承認応答を待ち、暗号化初期化callbackが完了せず、cookie取得とHTTP transaction開始が待たされることです。新規profileでも同じユーザーのKeychain項目へアクセスするため、profile作成だけでこの条件は分離されません。

`--use-mock-keychain` はproviderを変更する診断介入です。その結果だけでACL不一致、実際の拒否、未応答の承認待ちのどれが停止原因かを断定しないでください。unsigned・初回署名・後から署名を変更したコピーの結果を区別します。

固定版 `82303c21a18acdc256c6264cd2ed0e1588df99d4` では、Keychain taskの返却後にproviderのcallback、続いてOSCryptAsyncの初期化callbackが実行されます。アクセス拒否がAPIから返った場合にも初期化を進める経路があります。「拒否が返った」と「承認応答を待ってAPIが返らない」は別の状態です。実際の入力版に対応するソースで次を追ってください。

- `crypto/apple/keychain_v2.mm`：`FindGenericPassword`／`SecItemCopyMatching`
- `components/os_crypt/common/keychain_password_mac.mm`：Safe Storage名と取得結果
- `components/os_crypt/async/browser/keychain_key_provider.mm`、`os_crypt_async.cc`：workerと初期化callback
- `services/network/network_context.cc`：`CookieOSCryptAsyncDelegate::Init`／`InitCallback`
- `net/extras/sqlite/sqlite_persistent_cookie_store.cc`：`LoadCookiesForKey`／`CryptoHasInitFromLoad`
- `net/url_request/url_request_http_job.cc`：cookie callbackと`StartTransaction`

これは検証する経路であり、対象requestで実際に起きたことはruntime証拠で確認してください。

## 追加検証の順序

1. **既存証拠を対応付ける。** appの出所・revision・hash・署名来歴、profile、引数、試験ID、対象request、PID、時刻の対応表を作ってください。待っているAPI、securitydの対象項目と要求元、HTTP stream開始前の位置を確認し、今回測定した範囲と未照合の10月5日の範囲を明示します。

2. **承認状態を変える前に、通常→mock→通常の対照を確認する。** 既存記録で成立していれば再利用し、不足する試行だけ追加してください。同じapp・入力版・GUIユーザー・引数・同じ内容のfixtureを使い、各profileと結果ディレクトリは新規にします。変更するbrowser argumentは `--use-mock-keychain` の有無だけです。Keychain設定を変更せず、通常条件に戻すと停止が再現するかを確認します。他の条件が変化した場合は差分を記録してください。

3. **実画面を確認する。** 自動合格3試験のそれぞれの試験IDと、通常GUIのオーナー観察を対応付けてください。CDP画像やwindow存在記録を人間の表示確認へ読み替えません。既存3試験に対応する観察を確認できない場合は、新規profileの3試験を観察できる条件で実施し、本文・JS・fetch・描画の自動結果も保存してください。

4. **承認応答とHTTP開始の前後関係を測る。** まず応答せず、ダイアログの有無・表示先・要求元・対象項目、worker、securityd、対象requestを同じ時系列で記録してください。その後、実機オーナーが試験内容に同意した場合に、拒否、または一度だけの許可を別試行で観察します。既存の明示的な同意はその範囲で使用してください。同意がない許可操作は、対象app・項目・操作を具体的に示して確認してから行います。ユーザー入力が必要なら準備を終えて依頼し、入力内容を取得・記録しません。

   「API返却／待機 → 初期化callback → cookie callback → HTTP stream → server受信 → DOM・JS・描画」を対応付け、直接観測とソースからの推定を区別してください。拒否後も停止する、ダイアログがない、応答が反映されない場合は、前提を見直して追加の停止位置を調べます。

   `383310b`の`probe.py`は待機後に`post-observation/`へ別のdocument・画像・networkイベント差分を採取します。応答時刻を別途記録し、この採取とserver／NetLogを対応付けてください。イベント配列の採取時刻は実際の応答・イベント発生時刻とは区別します。通常の`result.json`には待機前のdocument値と試行全体のserver受信が含まれるため、classificationやexit codeだけで応答後の復旧を判定しません。必要な追加観測を行い、既存結果と採取時点を保持してください。

5. **10月5日の記録を照合する。** 手掛かりは `phase5-s0s1-after-ci-37314180383-20261005-b`。既存資料とユーザー回答から所在を確認し、入力hash・署名来歴・起動条件・停止段階・Keychain関連記録を照合してください。必要な記録がない場合は、現在の測定だけで当時の原因を証明したことにせず、照合できた点と欠ける証拠を明示します。

## 完了条件と結論

次を満たすまで調査完了としないでください。

- 再現条件と、結果を切り替えた最小の条件が固定されている。
- どのKeychainアクセス・承認状態・callback・要求が、どの仕組みで停止したかを実測と対応ソースで説明できる。別の原因なら、その具体的な仕組みを示す。
- 元の条件では失敗し、診断介入では成功する対照が成立している。成功条件は独立した3つの新規profileと実GUIで確認されている。
- unsigned／初回署名／署名変更コピーと主要な代替仮説を説明し、10月5日の事例への適用範囲と証拠の限界を記録している。全事例の共通原因を主張するなら、各事例の証拠が必要である。
- 再現コマンド、比較表、入力情報、試験ID、証跡保存先がそろい、追試できる。

従来の「再署名が原因」を維持する場合は、従来の根拠を超える追加証拠が必須です。署名で変わった具体的属性が実行中にどう評価され、何を停止させたかを示し、その属性だけの対照を追加してください。unsigned・初回署名でも停止した事実を説明し、署名回数自体とKeychain項目の信頼条件との不一致を区別します。「従来の根拠と限界／今回の追加証拠／新たに証明できた因果関係」の比較表を付けてください。

今回の完了条件は原因特定です。通常Keychainでの製品受入、恒久修正、ANGLE移植、KOOV全体の確認は後続工程です。mock診断や一度の許可による成功を、恒久的な製品復旧と表現しないでください。

## 保存・報告・コミット

既存app・S0/S1・profile・証跡を保持し、新規保存先を使ってください。ACL編集、Always Allow、Safe Storage項目の削除、秘密値・秘密鍵の取得や出力、既存appの再署名は今回の検証手段に含めません。承認応答を伴わない証拠分析・対照・準備は続行します。

2〜4時間は中間報告の区切りです。具体的に進められる検証を続け、時間切れや承認待ちを調査完了と扱わないでください。不足する入力・権限・実行資源がある場合は未完了の条件と再開手順を明示します。

スクリプト変更には必要な検証と対応するドキュメント更新を合わせ、同じコミットにまとめて作業ブランチへpushしてください。公開文書は一般的な診断手順・検証の限界を記録し、実機固有の結果・生ログ・profile・秘密情報はローカルの調査レポートへ保存します。force pushやmainへのmergeは行いません。

最終報告には、根本原因、直接観測した因果と推定部分、条件別の結果、GUI確認、10月5日との対応、既存根拠を超える新証拠、未完了事項、証跡保存先、コミットを記載してください。
