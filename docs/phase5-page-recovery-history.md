# Chromium／ANGLE実験の経過整理

確認時点：2026年10月12日 07:53 JST。
実機実験の10月2〜5日という日付は既存実験記録の表題による。CIの時刻は日本時間。

追記（同日08:30以降のコード確認）：U0の`WEBGL_SMOKE=pass`の判定条件はテストページの読み込みであり、WebGL context／draw成功は必須ではなかった。U1の独自ANGLE試験には別途context／drawの検証がある。以下のU0成功をWebGL描画成功とは扱わない。後続の具体施策は[ページ復旧計画](phase5-page-recovery-plan.md)に記録した。

## 目的と現在地

目的は、Mac上のFamily 1 GPUで独自ANGLEを使い、KOOVの描画・操作まで確認すること。

独自ANGLEのロード、Metal／EGL初期化、WebGL1の最小描画には実機で成功している。一方、Apple Development署名を行った実験用ブラウザのHTTPページ読み込みが停止し、KOOVの画面・操作には到達していない。その直接原因は未特定。

現在の小規模ビルド試験は、追加診断のためのビルド環境確認である。元のHTTP停止の原因を直接検証する試験ではなく、成功数を増やしてもChromium本体が段階的に完成する構成ではない。

## 時系列

### 1. 10月2〜3日の記録：ANGLE初期化からWebGL1描画へ

- Family 1の入口制限と、実機がES 2.0までである能力境界を切り分けた。
- 非WebGLのES3要求をES2へ切り替えるfallbackにより、Metal／EGL初期化とWebGL1の最小描画に成功した。
- 同一GPUプロセスに独自libEGL／libGLESv2がロードされた証拠を取得した。
- KOOVはページの実体へ遷移せず、about:blankのまま停止した。
- 同じ実機の純正Chromeはログインページへ到達した。調査対象はGPU初期化からブラウザのページ読み込みへ移った。

### 2. 10月3日の記録：署名・通信経路の切り分け

- 外部サービスに依存しない端末内HTTPサーバーでも停止を再現した。
- Chrome比較ではTCPのpreconnectや背景通信は動作したが、対象ページのHTTP stream生成・HTTP送信・応答へ進まなかった。
- ANGLEを追加しない署名済みChromeコピーでも停止した。Framework構成を維持する比較も実施した。
- 署名検証、署名者、署名要件、権限設定、sandboxログ、Network Serviceログを比較した。
- 一般的な通信全面遮断、ANGLEのロード失敗、単純な署名破損を主因とする根拠は弱くなった。
- 署名に伴う実行時条件とページ通信の関係が有力候補になったが、具体的な原因属性やコード行は未特定だった。

### 3. 10月4〜5日の記録：未署名のビルド済みChromiumで比較

使用した原本は公式Mac x64 snapshot `Mac/1689422/chrome-mac.zip`。

- Chromium：`82303c21a18acdc256c6264cd2ed0e1588df99d4`
- 原本が指定するANGLE：`8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`
- 使用した実験用ANGLE：`e12217f3e133cb1029b050d893b1806d141483be`

| ケース | 組み立てと署名 | 観測環境・結果 |
| --- | --- | --- |
| U0 | 未署名Chromiumそのまま | CIでHTTPページ・WebGLテストページ読み込みに成功。WebGL描画成功は判定条件に含まれない |
| U1 | 未署名Chromiumに独自ANGLEを追加し、未署名を維持 | CIでHTTPページ・ANGLEロード・WebGL基本試験に成功 |
| S0 | 未署名Chromiumの新規コピーを完成させ、Apple Developmentで初回署名 | 実機で署名検証・起動は成功、HTTPページは停止 |
| S1 | 未署名Chromiumの別コピーにANGLEを組み込み、完成後にApple Developmentで初回署名 | 実機で署名検証・起動・Metal／EGL・WebGL1最小描画は成功、HTTPページは停止 |

10月5日の新規S0/S1でも、内側から外側への初回署名を各一回だけ実施し、署名後は構成を変更せず、同じURL停止を再現した。

これは「未署名のChromiumにANGLEを組み込み、Apple Developerの証明書で署名して起動確認する」という手順を、Apple Development証明書で既に試した記録である。未署名のまま実機利用する案とは異なる。

当時の文書には「再署名は黒」「実験完了」という表現がある。正確には、比較実験の実施が完了し、署名に関連する条件が有力になった段階である。初回署名のS0/S1と、署名済みChromeを署名し直した比較を区別する必要がある。

また、未署名成功はCI、初回署名後の失敗は実機という環境差がある。Chromeの同一実機比較は補強材料だが、Chromiumの初回署名だけを単独原因とする完全な比較にはなっていない。ANGLEの版も一致しておらず、探索的結果である。

### 4. 10月6日夜〜7日未明：追加ログを入れる本体ビルドへ

既存のrelease版のログでは、ページ要求が内部でどこで止まるかを特定できなかった。そのため、URLLoaderFactory生成、要求開始、応答、完了、Mojo通信切断などを記録する診断パッチを作った。

本体の自前ビルドへ進んだ理由は、追加診断ログを入れることと、Chromium／ANGLEの入力版をそろえることだった。「未署名のビルド済みChromiumが存在しない」ためではない。

Run 37464208418は10月6日21:34ごろ開始し、7日03:39ごろに終了。準備約49分、コンパイル約5時間11分という記録で、約79,594タスク中7,277タスクの時点でジョブの時間上限に達した。コンパイルエラーとしての失敗ではなく、時間切れである。

診断用Chromiumは完成せず、この追加ログによる根本原因調査は実施できていない。

### 5. 10月7〜9日ごろ：無料CIでの事前確認へ

- ソース・依存関係、パッチ適用、ビルド設定、依存グラフ生成を確認する経路に切り替えた。
- その事前確認は成功したが、コンパイルや実行の成功ではない。
- 小さな対象の必要タスク数を計測する仕組みを追加した。
- 対象名の解決、計測タイムアウト、進捗表示、時間制限など、検証基盤の修正が増えた。

### 6. 10月10〜11日：小規模ビルドの成功

zlibライブラリ、zlib_bench、minigzip、zpipe、brotli、opus_compare、opus_demoなどで成功記録が得られた。

直近の実行では、ソース取得に約22〜26分、コンパイル自体に約1〜2分、ジョブ全体に約30〜35分かかった。ソース・出力の永続保存はなく、キャッシュは復元専用でmissが続いている。

これらはビルドの基礎動作を確認する成果である。URLLoaderの診断、初回署名後のHTTP停止、KOOVの動作を確認した成果ではない。

### 7. 10月11日夜〜12日朝：候補選別を継続

- cwebpは2,516タスクで2,000の上限を超え、コンパイルされなかった。runの終了異常も報告され、最終状態はcancelled。
- その後、上限超過はその候補だけ除外し、通信障害・コンパイル失敗・時間切れ・run終了異常ではバッチを止める条件へ変更された。
- 別環境でproxy接続エラーが発生したが、このチャットの環境ではGitHub読み取りが成功した。
- 次の候補はsqlite_shell、decode_encode_profile_test、bssl_bench。
- Run 38180664558は12日07:30開始。07:53確認時点でソース取得を終え、依存グラフ生成・候補計測の段階。新候補の成功はまだ確認していない。

## 現在の整理

| 区分 | 状態 |
| --- | --- |
| 独自ANGLEの実機ロード・Metal／EGL・WebGL1最小描画 | 成功記録あり |
| 未署名の配布版にANGLEを組み込み、Apple Developmentで初回署名・起動 | 実施済み。起動・描画は成功、HTTPページ読み込みは失敗 |
| 署名後のHTTP停止の直接原因 | 未特定 |
| 診断ログ入りChromium本体 | 未完成 |
| 小規模ターゲットのビルド環境 | 複数の成功実績あり |
| KOOV画面・操作・安定性・USB／Bluetooth | 未確認 |

`RUNTIME_DEVICE_READY=false`はCI成果物の境界を表す記録であり、「実機試験を一度もしていない」という意味ではない。

## 今後の判断に必要な点

本来の問題は初回署名後のHTTP停止である。小規模ターゲットの追加試験には終了条件を設け、同じ実機・同じChromium入力・同じ起動条件で署名の影響をどこまで比較済みかを証跡から再点検する必要がある。

ビルド済みChromiumにANGLEの版を合わせる方法は、本体再ビルドを省く候補になる。ただし、それだけで署名後のHTTP停止が解消するとは言えない。追加ログが不可欠なら、本体ビルドを完了できる環境設計に戻る必要がある。

## 根拠資料

- [実機観測記録（固定コミット）](https://github.com/naokikambe/chromium-angle-family1-experiment/blob/292c7e2bab8bd06e9cf2ec50d7d20a451393290d/docs/phase5-real-device-observation.md)
- [未署名Chromium・初回署名比較の記録](https://github.com/naokikambe/chromium-angle-family1-experiment/blob/292c7e2bab8bd06e9cf2ec50d7d20a451393290d/docs/phase5-unsigned-chromium-one-sign-experiment-plan.md)
- [本体ビルドの実行記録](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/37464208418)
- [無料CI事前確認と小規模ビルドの記録](https://github.com/naokikambe/chromium-angle-family1-experiment/blob/8df3e449d2dff8ca4532bbb44a56dbfc5d86b28b/docs/phase5-ci-preflight-free-decision.md)
- [確認時点の実行中CI](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/38180664558)

本書は既存文書とGitHub Actionsの状態を照合した整理であり、新規署名・起動試験を実施したものではない。
