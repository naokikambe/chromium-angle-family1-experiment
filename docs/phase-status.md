# Phase 状態

更新日: 2026-10-12

## 現在の作業

Phase 5のページ表示復旧へ計画を立て直した。目標は、公式未署名のビルド済みChromiumへ独自ANGLEを組み込み、Apple Developmentで初回署名した実機アプリでHTTPページとKOOVを表示すること。

| 項目 | 状態 | 証拠と限界 |
| --- | --- | --- |
| 過去の実機ANGLE／Metal／EGL／WebGL1最小描画 | 成功記録あり | 固定コミットの[実機観測記録](https://github.com/naokikambe/chromium-angle-family1-experiment/blob/cc781c1063261ffbe227939ff607ecefb51f6b2b/docs/phase5-real-device-observation.md)。新キットによる実行結果ではない |
| 未署名のビルド済みChromiumのHTTPページ | CI成功記録あり | snapshot 1689422を使用したU0/U1。実機の初回署名後結果とは環境・入力版が異なる |
| ANGLE追加なし／ありの初回署名済みChromium | 起動成功、HTTP document前で停止 | 10月4〜5日の実機S0/S1記録。署名に関連する条件は候補だが、単一の直接原因は未特定 |
| 通信診断ログ入りChromiumの全体ビルド | 未完成 | run 37464208418は時間切れ。小規模対象の成功で完成済みとは扱わない |
| ページ復旧キット | 作成・portable検証10件成功 | `scripts/page-recovery/`。CDP結合確認はmock使用。Macのcodesign・本物のChromium・GUIでは未検証 |
| 次の実機作業 | GitHubから実機へ取得して開始 | `phase5-page-recovery`ブランチをMacBookAir6,1へ取得。GUIユーザー・既存S0・完全未署名原本・REVISIONS・有効なApple Development identityを対応付け、ANGLE追加前のページ表示を基準化する |
| KOOVの画面・基本操作・機器連携 | 未確認 | ページ表示復旧、独自ANGLE、WebGL1の確認後に進める |

実行順序は[具体施策・実行計画](phase5-page-recovery-plan.md)、コマンドは[キットREADME](../scripts/page-recovery/README.md)、次のエージェントへの指示は[引き継ぎプロンプト](phase5-page-recovery-handoff.md)に記録した。過去の整理と現在までの経緯は[経過資料](phase5-page-recovery-history.md)を参照。

一部の旧`WEBGL_SMOKE=pass`はテストページの読み込みだけを必須条件にしていた。context／draw、HTTP本文、画像、実GUIを別々に判定する。`RUNTIME_DEVICE_READY=false`はCI成果物の境界であり、過去に実機試験がなかったことを意味しない。

クラウドで作成したキット・計画・記録は、GitHubの`phase5-page-recovery`ブランチから実機へ引き継ぐ。初期追加コミットは`fa2f3f7`。その後のプロンプト更新を含むブランチ先頭を取得し、試験時のHEADを記録する。実機署名・起動は実行待ちで、この準備作業ではCI dispatch／cancelを行っていない。小規模候補の追加探索は打ち切る方針とし、実行中の別作業については次の担当者が最新状態を確認する。

## 2026-09-20時点のbaseline記録

以下は当時の記録として保持する。現在のPhase 3以降の状態は上の表と固定された後続記録を参照する。

| Phase | 状態 | 記録 |
| --- | --- | --- |
| Phase 0 | 保留 | 基準資料の比較設計は完了。実機ログがワークスペースに未提供のため、ログ保全と比較表作成は保留。Phase 3 の実機試験前に完了させる。 |
| Phase 1 | 完了 | Chromium `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854`、ANGLE `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`、dynamic ANGLE の探索位置と主要 dylib を固定ソースで確認済み。Feature override が後続の条件付き既定値で上書きされない根拠を `docs/baseline.md` に追記した。 |
| Phase 2 | Phase 2B 完了 | 初回run `35495704110` と失敗follow-up run `35497602637` の記録は保持する。2回目のfollow-up run [`35501697418`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/35501697418) は固定ANGLE checkout、`gclient sync`、GN、Ninja、artifact検証、uploadに成功した。artifactはx86_64の`libEGL.dylib`と`libGLESv2.dylib`のみを含み、各自己install name以外に非system依存はなく、署名は未署名（Phase 2では許容）である。 |
| Phase 3 以降 | 未着手・Phase 0完了待ち | Chrome.app への配置、署名変更、実機起動、KOOV 試験、Family 1 向け変更、診断ログ追加はいずれも実施していない。Phase 2Bのartifact条件は満たしたが、Phase 0の基準ログ保全と比較表作成、Chrome実loadのレビューが未完了のためPhase 3へは進めない。 |
