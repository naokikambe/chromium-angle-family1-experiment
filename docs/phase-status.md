# Phase 状態

更新日: 2026-10-12

## 現在の作業

Phase 5のページ表示復旧へ計画を立て直した。目標は、公式未署名のビルド済みChromiumへ独自ANGLEを組み込み、Apple Developmentで初回署名した実機アプリでHTTPページとKOOVを表示すること。

現在は[Keychain経路を中心にした再計画](phase5-page-recovery-replan.md)を適用する。現行S0・GPU無効化の範囲で原因特定完了の担当者報告を受領した。[実機向け一括プロンプト](phase5-device-completion-handoff.md)は署名信頼と通常Keychainのstock復旧、DEPSに対応するFamily 1 ANGLEの組み込みと初回署名、KOOVの実画面・基本操作・再起動・安定性までを対象とする。各工程の開始条件を満たしてから次へ進む。10月5日の適用範囲の調査は並行し、現在の検証を止める条件にはしない。

今回の実機調査は、ページ描画不可の根本原因を実行時の証拠と原因条件だけを変えた対照実験で特定するまでを完了条件とする。従来の「再署名が原因」を維持する結論には、具体的な故障の仕組みを示す追加証拠が必須であり、既存結果の再掲では完了としない。初回署名でも失敗した事実を説明し、既存根拠と追加証拠を比較して報告する。ANGLE移植・KOOV全体の確認は原因特定後の後続工程とする。

| 項目 | 状態 | 証拠と限界 |
| --- | --- | --- |
| 過去の実機ANGLE／Metal／EGL／WebGL1最小描画 | 成功記録あり | 固定コミットの[実機観測記録](https://github.com/naokikambe/chromium-angle-family1-experiment/blob/292c7e2bab8bd06e9cf2ec50d7d20a451393290d/docs/phase5-real-device-observation.md)。新キットによる実行結果ではない |
| 未署名のビルド済みChromiumのHTTPページ | CI成功記録あり | snapshot 1689422を使用したU0/U1。実機の初回署名後結果とは環境・入力版が異なる |
| HTTP停止の原因調査 | 現行S0・GPU無効化の範囲で完了報告受領 | 未応答試行と、拒否・APIエラー返却後に開始した要求のHTTP・描画成功を区別。mockの独立profile3件は実GUI確認済みとの報告。callback各段階にはソース推定を含む。実機生ログはクラウドで未再監査 |
| 通信診断ログ入りChromiumの全体ビルド | 未完成 | run 37464208418は時間切れ。小規模対象の成功で完成済みとは扱わない |
| ページ復旧キット | portable test suiteとsymlink root alias fix | `scripts/page-recovery/`。symlink regression covers internal aliases and rejects external or broken links. Platform behavior, GUI confirmation, and product acceptance require separate validation |
| 次の作業 | 通常Keychainでのstock復旧 | 正常な鍵取得、通常GPUでの独立profile3件と実GUI、同じ検証profileの再起動・暗号化cookie利用を一括で検証する。必要な許可操作と環境変更は既存同意から推定しない |
| stock受入の現在の阻害要因 | Allow試行のAPI境界と署名信頼を未確認 | 担当者報告では同じAllow試行の返却stackは未取得。別の未応答試行のstackは転用しない。署名検証の信頼エラーとidentity検索0件を読み取り専用で切り分け、追加Allowの既存回答を確認する |
| 復旧の後続工程 | 通常Keychainの継続利用条件を検証 | 正常アクセス、同じ署名済みappと独立login Keychainの比較、対象appに限定した信頼条件または利用分離の方針を選択。環境作成・権限変更は現在の原因調査とは別の実行範囲 |
| KOOVの画面・基本操作・機器連携 | 未確認 | ページ表示復旧、独自ANGLE、WebGL1の確認後に進める |

実行順序は[具体施策・実行計画](phase5-page-recovery-plan.md)、コマンドは[キットREADME](../scripts/page-recovery/README.md)、次のエージェントへの指示は[引き継ぎプロンプト](phase5-page-recovery-handoff.md)に記録した。過去の整理と現在までの経緯は[経過資料](phase5-page-recovery-history.md)を参照。

Keychain経路を優先する続行指示は[続行プロンプト](phase5-keychain-investigation-handoff.md)に記録した。公開資料は一般的な手順と判定条件を示し、実機固有の結果はローカルの最新調査レポートへ保存する。

一部の旧`WEBGL_SMOKE=pass`はテストページの読み込みだけを必須条件にしていた。context／draw、HTTP本文、画像、実GUIを別々に判定する。`RUNTIME_DEVICE_READY=false`はCI成果物の境界であり、過去に実機試験がなかったことを意味しない。

現行S0の原因特定とmockのGUI3件は完了報告を受領した。10月5日証跡との照合、通常Keychain・通常GPUでのstock受入、ANGLE／KOOVは未完了。拒否後の暗号化不可での表示成功とmock診断は製品復旧を意味しない。`71d5bb1`の起動待機改善を取り込み、追加の焦点テストをクラウドでも確認した。

## 2026-09-20時点のbaseline記録

以下は当時の記録として保持する。現在のPhase 3以降の状態は上の表と固定された後続記録を参照する。

| Phase | 状態 | 記録 |
| --- | --- | --- |
| Phase 0 | 保留 | 基準資料の比較設計は完了。実機ログがワークスペースに未提供のため、ログ保全と比較表作成は保留。Phase 3 の実機試験前に完了させる。 |
| Phase 1 | 完了 | Chromium `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854`、ANGLE `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`、dynamic ANGLE の探索位置と主要 dylib を固定ソースで確認済み。Feature override が後続の条件付き既定値で上書きされない根拠を `docs/baseline.md` に追記した。 |
| Phase 2 | Phase 2B 完了 | 初回run `35495704110` と失敗follow-up run `35497602637` の記録は保持する。2回目のfollow-up run [`35501697418`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/35501697418) は固定ANGLE checkout、`gclient sync`、GN、Ninja、artifact検証、uploadに成功した。artifactはx86_64の`libEGL.dylib`と`libGLESv2.dylib`のみを含み、各自己install name以外に非system依存はなく、署名は未署名（Phase 2では許容）である。 |
| Phase 3 以降 | 未着手・Phase 0完了待ち | Chrome.app への配置、署名変更、実機起動、KOOV 試験、Family 1 向け変更、診断ログ追加はいずれも実施していない。Phase 2Bのartifact条件は満たしたが、Phase 0の基準ログ保全と比較表作成、Chrome実loadのレビューが未完了のためPhase 3へは進めない。 |
