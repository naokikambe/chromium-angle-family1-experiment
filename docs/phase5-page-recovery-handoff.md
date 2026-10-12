chromium-angle-family1-experimentのPhase 5を、ページ表示の復旧を中心に進めてください。計画の説明だけで終えず、利用できる環境で証拠採取・原因検証・修正・再試験まで実行してください。

最終目標は、MacBookAir6,1／Intel HD Graphics 5000で「一度も署名されていない公式のビルド済みChromiumに独自ANGLEを組み込み、完成後にApple Development証明書で初回署名し、HTTPページとKOOVを表示する」ことです。まずANGLE追加前の初回署名済みstock ChromiumでHTTPページを正常表示できる基準を確立してください。

## 参照するコミットと資料

リポジトリ：`naokikambe/chromium-angle-family1-experiment`。今回の引き継ぎ資料は`work`ブランチのページ復旧キット追加コミットにあります。元のbaseは`8df3e449d2dff8ca4532bbb44a56dbfc5d86b28b`です。リモートへのpushは今回の作業範囲に含めていないため、GitHubだけに新コミットがあると仮定しないでください。

新しいファイルがcheckoutにない場合は、添付の`phase5-page-recovery-handoff.bundle`をインポートしてください。既存変更を保持し、必要なら別worktreeを作ります。

```bash
git bundle verify "/実際の保存場所/phase5-page-recovery-handoff.bundle"
git fetch "/実際の保存場所/phase5-page-recovery-handoff.bundle" work
git worktree add -b page-recovery-20261012 "../chromium-page-recovery-20261012" FETCH_HEAD
```

ブランチ名やディレクトリが既存なら、新しい名前を使用してください。Git bundleはコミットの受け渡しであり、実験用Chromiumや署名証明書を含みません。

作業開始時に実際のリポジトリの`AGENTS.md`などの指示、HEAD、dirty状態、実行環境を確認し、次を読んでください。

1. `docs/phase5-page-recovery-plan.md`
2. `scripts/page-recovery/README.md`
3. `docs/phase5-page-recovery-history.md`
4. `docs/phase-status.md`
5. `scripts/page-recovery/TESTING.md`

## 確認済みの事実と未確定事項

- 完全未署名の公式Mac x64 snapshot `1689422`は既に存在し、CIのU0/U1でHTTPページの成功記録があります。
- 未署名stockへANGLEを追加せず初回署名したS0も、ANGLE追加後に初回署名したS1も、実機でHTTP document前に停止しました。S1はMetal／EGL・WebGL1最小描画に成功しています。
- 純正ChromeとそのApple Development署名コピーの同一実機比較でもページ読み込みに差があります。ただし、Chromiumの初回署名と同じ単一原因だとは証明していません。
- 未署名成功はCI、初回署名後失敗は実機という環境差があり、過去のChromium／実験用ANGLEにも版の不一致があります。
- 「再署名は黒」は原因確定の表現として扱わないでください。初回署名でも失敗しており、直接原因は未特定です。
- 一部の旧`WEBGL_SMOKE=pass`はテストページの読み込みを確認しただけです。HTTP本文、画像、実GUI、WebGL context／drawをそれぞれ判定してください。
- 診断用のChromium本体ビルドはrun `37464208418`で約6時間後に時間切れ。新キットの検証10件はLinuxとmock CDPでの確認で、Macのcodesign・本物のChromium・GUIは未検証です。

## 実行順序

1. 実機のGUIユーザー、OS／OCLP、Python 3.10以上、保存済みS0、完全未署名原本、REVISIONS、有効なApple Development証明書SHA-1、署名receipt・rawログの所在を確認する。保存済み証跡の手掛かりは`phase5-s0s1-after-ci-37314180383-20261005-b`。既存の保存物から確認し、不足するパス・接続だけをまとめてユーザーに尋ねる。
2. リポジトリrootで`python3 -m unittest discover -s scripts/page-recovery -p 'test_kit.py' -v`を実行し、実機で使うコードを独立レビューする。特に`sign_once.py`は公式の全署名pipelineではなく試験用アダプターなので、実際のbundle構造と固定ソースを照合し、必要な修正を先に行う。
3. `probe.py inventory`で既存S0の実際の署名を記録し、`probe.py probe`でdata／file／HTTPを同じ内容・新規profileで測定する。HTTPサーバーのケース固有GET、応答、本文、JS、fetch、画像、緑色ピクセル、2D canvas readbackを確認する。通常GUIの表示は`--transports=http --observe-seconds=20`などで別途確認する。
4. 最初の失敗位置に対応する対照だけを行う。HTTPだけが失敗するなら同じappで`--browser-arg=--disable-gpu`。起動前のCrashpad／trustエラーなら同じGUIユーザー・有効identityで観測経路を正し、必要な一試行だけ`--disable-breakpad`を追加する。各試験は一条件を変更し、別の新規結果ディレクトリを使う。
5. 旧署名receipt／inventoryを、snapshotの固定Chromiumソースが指定する通常Helper・Renderer・GPUのflags／entitlementと照合する。Google ChromeのHelper名に依存する処理がChromiumの署名に使われたかは仮説なので、実際の結果で確認する。署名者・証明書種別の実行時照合を調べ、static verify成功だけで正常と判定しない。
6. 具体的な署名設定差が見つかった場合、または旧署名手順を復元できず基準copyが必要な場合、新しいunsigned原本から`sign_once.py prepare`でcopy・凍結manifest・実行一覧を作る。一覧と入力の出所をレビューしてから`execute`で初回署名し、同じページ試験を行う。原本や旧S0/S1を署名し直さない。失敗copyは保存し、修正が必要なら別の新規copyを使う。
7. stockが成功したら、新旧差分と失敗requestのログを対応付け、通常GUI・通常の保護設定・独立した新規profileで3回成功することを確認する。同じ失敗が残れば、対象requestの最初のエラー・終了・IPC切断を特定する。ProcessRequirement警告だけを根因にしない。参照版のMach port peer enforcementは既定OFFで、警告が要求停止を引き起こした証拠が必要。
8. 既存ログで判別できない具体的な分岐が残ったときに、URLLoaderFactory生成、CreateLoaderAndStart、ScheduleStart、OnMojoDisconnect／NotifyCompletedのうち必要な観測を追加する。その診断アプリを同じ実機・署名条件で試すところまで設計する。全体ビルドの実行速度・永続出力・予算を確認してから実行を判断する。
9. stock復旧後、成功したsnapshotのDEPSにANGLEの版を合わせ、Family 1対応を適用してANGLEだけをビルドする。新しい未署名copyに組み込み、成功した署名policyで初回署名する。HTTP基準、独自dylibの同一GPU PIDロード、WebGL1 context／draw／readback、KOOV document・画面・基本操作・安定性の順に確認する。

キットの変数設定・各コマンドは`scripts/page-recovery/README.md`にあります。snapshot 1689422はChromium `82303c21a18acdc256c6264cd2ed0e1588df99d4`、DEPSのANGLE `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`。原本archiveの既存SHA-256は`cdf57adeb21f946e3cf7b5897bf3656dbfdbec5d95281bfb828202b2d7cf35cf`です。REVISIONSの一致だけで手元appの出所を証明済みとしないでください。

## 作業範囲と保存

この指示の実行では、既存資料・署名・ログの読み取り、診断コードの修正と検証、隔離した新規copy／profileの作成、上記条件の新規copyへのApple Development初回署名、GUI起動・loopbackページ試験を進めてください。署名実行前の準備・独立レビューを完了し、現場で本当に必要な権限や未指定入力が残る場合だけ具体的に尋ねてください。

原本Chrome／Chromium、旧S0/S1、既存profile、保存済みretry／evidence／artifactは保持してください。結果はリポジトリ外の新規専用ディレクトリへ保存します。署名後のbundle変更、署名やり直し、xattr変更、Applications置換、恒久的な保護機能無効化を修正採用の手段にしないでください。KOOVの認証情報入力、実データ保存、USB／Bluetoothなど既存の承認範囲にない操作は、描画基準が成立した後に範囲を確認してください。

小規模対象の追加探索は終了し、現在の問題を直接検証する試験に集中してください。実行中CIがあれば最新状態と終了条件を読み取り、無関係なdispatchを追加しないでください。既存認証を使用し、GH_TOKENを再発行・出力しないでください。

Mac実機にアクセスできない場合はLinux結果を実機結果に読み替えず、取得済みrawログの分析、入力照合、コード修正、portable検証を進めてください。実機作業に必要な接続または保存場所だけを明示し、何を準備済みかと何が実行待ちかを報告してください。

## 完了・報告・コミット

最初の2〜4時間は診断の区切りです。停止位置、試した仮説、変更した一条件、結果、次の一手を報告し、具体的に進められる検証は続行してください。根本解決と判断するには失敗条件と修正差分が対応し、通常設定で3回の独立試験が成功する必要があります。mock成功やビルド成功をページ表示復旧と報告しないでください。

コードや方針を変更する場合は、対応する計画・進捗・検証記録を合わせて更新し、同じコミットに含めてください。rawログ、実機bundle、profile、秘密情報はコミットせず、コミット対象を明示して差分を確認してください。push／PR／mergeは別途指示がある場合に行います。

最終報告には、原因として確定したことと未確定事項、修正差分、入力revision・hash、署名receipt、HTTP・本文・JS・画像・GUI・WebGLの各結果、証跡保存場所、コミット、残作業を記載してください。
