# 実機作業の一括引き継ぎ：stock復旧から独自ANGLE・KOOVまで

対象Macで、公式の完全未署名・ビルド済みChromiumへFamily 1対応ANGLEを組み込み、Apple Developmentで初回署名した実験アプリにより、通常Keychainでページ描画とKOOVの画面・基本操作を成立させてください。今回の委任はstock復旧からANGLE・KOOVまでを含みます。工程ごとに次の指示を求めず、開始条件を満たしたら次へ進んでください。

## 開始と引き継ぐ判断

リポジトリは `naokikambe/chromium-angle-family1-experiment`、ブランチは `phase5-page-recovery`。対象MacのGUIログインユーザーで実施します。最新checkout・HEAD・dirty状態・適用指示を確認し、既存変更を保全して最新版を取得してください。実機の最新調査レポート、runbook、証跡一覧、保留中の同意回答を確認します。実機固有の詳細は公開文書へ転載しません。

### 現在の公開チェックポイント

通常GUIユーザーのstock標準設定では、専用profileで暗号化cookieを保存し、再起動後に再送できることを一度確認しました。この結果だけでは、新規3 profileでの検証は成立していません。同じ試行内でのKeychain API返却値との直接相関も未完了です。

候補fixtureではページ読み込み、fetch、2D canvasが成功しました。先行するDevTools capture timeoutの後に、DevTools view／surface captureの診断が成功しました。candidate seed cookieは暗号化保存され平文欄は空でしたが、確認時には期限切れで、再起動後の復号・再送は未成立です。WebGL VBO triangleのdraw/readback受入は未達で、KOOV検証は未開始です。

直近に承認された候補cookie・再起動・vertex診断の連続試験は、起動前の署名検証で停止しました。private manifestとの実行ファイル／ライブラリhash一致は確認しましたが、現在の `codesign --verify --deep --strict` は `CSSMERR_TP_NOT_TRUSTED` を返します。この試験ではapp、証明書、trust設定、Keychainを変更せず、起動もprofile作成もしていません。署名信頼を読み取り専用で解決し、同じ未変更候補が必須検査を通ってから再開します。

優先する指示はこの一括プロンプトです。[stock復旧の詳細](phase5-normal-keychain-handoff.md)は工程Aに適用します。同文書の「stockまで」という委任境界は、この一括指示では工程B・Cまで拡張します。Keychain操作への同意は拡張しません。

## 委任する操作と確認が必要な変更

- 読み取り専用調査、再現可能なfixture・runner・ANGLEパッチ・build設定の作成、関連文書と検証、新規実験コピーの組み立て、有効な既存Apple Development identityによる初回署名、許容される実行環境での必要なビルド・試験、作業ブランチへのcommit／pushを進めてください。
- Keychainへの追加応答、信頼設定・ACLの変更、証明書操作、検証ユーザーやKeychain環境の作成、既存KOOVデータの複製・移行は、対象・変更差分・影響・復元方法を準備し、既存同意を確認して必要な変更についてまとめて依頼してください。既存の拒否やAllow一回から新しい操作への同意を推定しません。
- 既存S0/S1・アプリ・profile・証跡は変更しません。秘密値・秘密鍵・実ユーザーのcookieを出力せず、秘密鍵をクラウドやCIへ移しません。署名は対象Mac上で行います。既存item削除、全アプリへの許可、OS全体のGPU偽装、system Metalの変更、保護機能の無効化は検証手段にしません。
- KOOVの認証はオーナー入力とし、資格情報を取得しません。USB／Bluetoothや実機への転送は描画が安定してから、対象操作への同意の範囲で行います。機器未提供ならソフトウェア確認と機器連携を別に報告します。

## 工程A：署名信頼と通常Keychainでのstock復旧

1. `CSSMERR_TP_NOT_TRUSTED`とidentity検索0件を、証明書期限・chain・信頼設定・Keychain検索範囲・実行ユーザー／経路に分けて読み取り専用で調べます。封印した内容の整合性も確認し、信頼エラーだけで改変・再署名を原因と断定しません。必要な修復差分を具体化し、同意範囲で実施します。新しいidentityが必要なら正規の有効なidentityを用意し、完全未署名原本から別コピーを初回署名します。
2. 同じ試行のprompt前から応答後まで、対象PID・item・API返却または待機・暗号化利用可否・request source・nonce・server受信を測ります。追加Allowは既存回答の範囲内だけ行います。署名未解決のコピーでの測定は診断として扱います。Allow Once後の別プロセスの再promptだけで、先の応答が反映されなかったと断定しません。
3. 正常な鍵取得と暗号化利用を確認し、必要に応じて独立した検証環境で比較します。別ユーザーでもSystem Keychainは共通なので、itemの所属と検索順を確認します。GPU条件を一つずつ戻し、通常Keychain・通常GPUで新規profile3件のHTTP・本文・JS・fetch・canvas・描画と実GUIを確認します。
4. `persistent_cookie_runner.py`を使い、専用profileの正常終了・再起動で非機密persistent cookieの暗号化保存・復号・再送信を確認します。再起動ごとの手動応答に依存する条件は継続利用の受入としません。独立環境での成功と既存ユーザーの復旧を区別します。
5. KOOVの実体・起動方式・App ID・必要な拡張／パッケージ・認証方法を事前確認します。歴史的なApp ID `kpmcfooelenggiklfmbljpognolignpg`や`--app-id`が対象版で利用可能かを確認し、廃止されたChrome Apps機能や欠けたKOOV入力をGPU障害と混同しません。既存profileの複製を前提とせず、専用環境での必要最小限の準備を具体化してください。

**工程Bの開始条件：** 対象stockの署名検証・正常Keychainアクセス・通常GPUでの3件の自動／GUI試験・暗号化cookie再起動検査が成立していること。成立していなければ最初の未完了境界を調べます。ANGLEソースの調査や入力確認は進められますが、追加ANGLEの実機成功をstock復旧の代用にしません。

## 工程B：ANGLEの版合わせ・組み込み・初回署名

1. 受入済みstockのsnapshot・Chromium revision・DEPSのANGLE pinを固定します。snapshot 1689422を継続する場合はChromium `82303c21a18acdc256c6264cd2ed0e1588df99d4`、ANGLE `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`を実入力と照合します。別入力へ変更する必要があれば理由を示し、署名アダプターを対応版で検証して工程Aの基準を取り直します。
2. 過去のFamily 1 runtimeパッチを固定履歴から回収し、対象ANGLE版へ移植します。旧artifactのrevisionやworkflow既定値を流用しません。Family 1の明示的な実験オプトイン、実機能力に合ったES／Metal機能境界、Family 2以上の既存動作を保持します。架空のFeature名や未対応機能を有効にして通しません。
3. 現在の `.github/workflows/phase5-metal-family1-runtime.yml`は別のChrome／ANGLE版を固定し、現ブランチにないパッチ・検証スクリプトを参照しています。そのままdispatchしません。必要な実装・検証を復元／更新するか、対象revisionを固定した専用ビルド経路を作ります。必要最小限の履歴集約後の内容同一な公開snapshot `292c7e2bab8bd06e9cf2ec50d7d20a451393290d`には `patches/phase5-metal-family1-runtime.patch`、`scripts/verify-phase5-runtime-artifact.sh`、`tests/phase5-metal-family1-runtime-static.sh`があります。復元後は現在の入力と実装に合わせて検証してください。
4. 必要な `libEGL.dylib`／`libGLESv2.dylib`をx86_64でビルドします。revision・patch hash・GN args・toolchain・deployment target・build log・artifact hash・依存・install nameを保存し、対象OSと整合することを確認します。CIやクラウドを使う場合も秘密鍵は持ち込まず、成果物をMacで検証します。既存の無関係なrunをcancelせず、concurrencyで他作業を止めない実行枠を選びます。全体Chromiumビルドは必要な差分が判明した場合だけ具体化します。
5. 完全未署名の公式原本から新規コピーを作り、同じ未署名状態のANGLE dylibを、固定版ソースが示す配置先へ組み込みます。ABI・依存・symlink・全Mach-Oの未署名状態を確認し、組み立て完了後に凍結します。署名済みstockへ追加して再署名する方法は使いません。
6. `sign_once.py`の役割別policyと実対象の対応を確認し、Mac上の有効なApple Development identityで内側から初回署名します。receipt・署名要件・厳密な検証結果を保存します。署名失敗したコピーは証跡として保持し、そのコピーでやり直さず新しい未署名入力から作ります。
7. 工程Aと同じKeychain環境・通常の保護設定でページと暗号化cookieの基準を再確認します。必要なANGLE/Metalの起動引数は固定版で有効なものだけを使い、診断用引数と運用用の実験設定を区別します。独自dylibのロード、ANGLE/Metal、対象GPUを同じGPU PIDで対応付けます。SwiftShaderや別backendへのfallbackをFamily 1 Metal成功へ読み替えません。
8. WebGL1のcontext作成・shader compile/link・draw・readbackをnonce付きfixtureで検証し、実GUIの結果と照合します。[固定版のvertex input診断境界](phase5-vertex-input-diagnosis.md)を使い、定数attribute・VBO fetch・triangle clippingとsample条件を区別します。ES 3／WebGL2が使えるとは仮定せず、KOOVの要求機能との関係を確認します。

**工程Cの開始条件：** 独自ANGLE版の署名・正常Keychain・ページ受入・暗号化cookie再起動が成立し、同一GPU PIDで独自ANGLE/MetalのロードとWebGL1 draw/readbackを確認していること。

## 工程C：KOOVの画面・基本操作・再起動・安定性

現行PC版の公開PWA入力と旧方式との差は [KOOV起動入力の補足](phase5-koov-current-entry.md) を参照してください。実際の専用profileのインストールと受入結果で確認します。

1. 工程Aで確認した起動方式を専用の検証環境へ用意します。正しい実験Chromiumの実パス・version・profile・起動引数・GPU PIDで起動を確認し、Dockのアイコンや旧ランチャー名だけで判定しません。
2. KOOVのdocument・JS・追加fetch・WebGL領域を確認し、オーナーの実画面観察を取得します。nonce付きfixtureの成功と実KOOVの成功を分けて保存します。
3. 非機密のテストプロジェクトで、画面遷移、ブロック編集、保存、再読込、必要な3D描画、resizeを確認します。既存プロジェクトを上書きしません。Chrome Apps互換性、拡張、認証、ネットワーク、WebGLの失敗を分け、最初の未完了境界を調べます。
4. 専用環境で30分程度の連続操作を行い、クラッシュ・context loss・白画面／黒画面・表示破損・CPU／メモリ傾向を記録します。正常終了後に同じ検証環境で再起動し、画面・テストプロジェクト・基本操作とKeychainアクセスの継続を確認します。
5. 機器連携は利用可能な機器と同意がある場合に限り、描画安定後に実施します。未実施ならUSB／Bluetooth・転送を未試験として明記し、ソフトウェア受入の範囲を限定します。

## 失敗時の分岐と続行

| 最初に失敗した境界 | 同じ委任内で行う次の作業 |
| --- | --- |
| 署名信頼・identity・正常Keychain | 工程Aの読み取り専用診断と同じ試行のAPI観測へ戻る。必要な変更をまとめて具体化する |
| ビルド入力・パッチ適用・ABI・依存 | revisionと差分、失敗targetを固定して修正・検証する。無関係な小規模targetの成功で置き換えない |
| 独自dylibがGPUにロードされない | 固定版の探索先・起動引数・install name・署名部品・library validationを照合する。保護機能を無効化して通さない |
| ロード済みだがMetal／WebGLが失敗 | 同じGPU PIDの最初のエラーと能力境界を確認し、Family 1パッチを限定修正する。変更ごとに新規コピーを組み立てて初回署名する |
| fixtureは通るがKOOVが失敗 | KOOVの起動方式・アプリ機能互換性・認証・要求・必要なWebGL機能を切り分け、テストデータで再現する |
| 再起動または安定性が失敗 | 同じprofile・鍵・app・GPU条件を照合し、最初のエラーを修正して該当検査をやり直す |

実験が画面全体の持続的破損、WindowServer反復クラッシュ、OSフリーズ、GPU crash loopを起こした場合は実験を中断し、起動した実験プロセスだけを終了して証跡を保存します。安全に続行できない状態は具体的に報告します。

## 最終完了条件

- stockの署名信頼・正常Keychain・通常GPU・独立profile3件の自動／実GUI・暗号化cookie再起動が成立している。
- 対象ChromiumとDEPSに対応するFamily 1 ANGLEを、新しい完全未署名コピーへ組み込み、Apple Developmentで初回署名した来歴と検証結果がある。
- 独自ANGLE版でも正常Keychain・ページ受入・暗号化cookie再起動が成立し、同じGPU PIDの独自ANGLE/MetalロードとWebGL1 context・draw・readbackを実証している。
- その実験アプリでKOOVの実画面・基本操作・テストデータの保存／再読込・正常終了後の再起動が成功し、連続操作中の安定性を確認している。
- 使用ユーザー・Keychain方針・KOOV起動方式・全引数・必要な実験オプトイン・未対応機能・機器連携の範囲・既存ユーザーとの差が明記され、追試できる。
- パッチ・スクリプト・workflow・関連文書が適切に検証され、作業ブランチへcommit／pushされている。実機固有の生ログ・profile・秘密情報は公開しない。force pushやmainへのmergeは行わない。

一試験や一工程の終了だけで会話を終えず、上記分岐と開始条件に従って続行します。中間報告には進んだ工程・新しい証拠・残る阻害要因を簡潔に記載します。必要なオーナー入力は、操作・理由・回数・観察時間・入力後の工程をまとめて依頼し、回答待ちでも依存しない準備を進めます。

必須の入力・同意・実行資源がなく、他の作業も尽きた場合は未完了として区切り、満たした条件／未達条件／具体的な阻害要因／必要な一括操作／再開手順を記録します。失敗の記録、時間切れ、mockや暗号化不可での表示成功を製品受入完了としません。
