# Phase 状態

更新日: 2026-10-26

## 次段階候補: Chrome Stable 156 + Family 1 ANGLE

2026-10-26の公開リリース情報ではChrome 156.0.8078.48がMac向けStableとして告知され、Chrome 157はMacで小規模Early Stable rollout予定とされている。Stableの展開は段階的なため、実際にbuildを開始する日に版を再確認する。Chrome tag `156.0.8078.48`のChromium commitは`d0c02bfad08ec92a6ffcf989e53cd995e6381a4c`で、tagged `DEPS`のANGLE pinは`3b89d84e9d59f75675ac4e2bef58fc068a9f0577`。

これはbuild候補のsource pinであり、ANGLE全体のbuild、Chrome Stable bundleへの組込み、Chrome実行、KOOV受入の完了を意味しない。候補patchとbuild範囲は[Chrome Stable 156 + Family 1 ANGLE build candidate](phase5-chrome-stable156-angle-build.md)を参照。

## 現在の作業

KOOVの現行対象はChrome for Testing 154.0.8037.0とFamily 1 ANGLE revision `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`の組み合わせである。Chromiumだけで行ったKOOV向け動画・codec調査は過去の比較であり、KOOVの受入経路ではない。KOOV用途ではそのChromium動画問題を追究せず、Chromeのcodec構成を使う。

Chrome + Family 1 ANGLEでの動画・WebGL確認結果は[現行KOOVの起動入力と受入準備](phase5-koov-current-entry.md)に記録した。公開手順から同じ確認を再現するには、再配布可能な合成メディア入力とCfT + ANGLE appの取得・組立・署名手順が必要である。KOOV受入は未完了である。

別トラックとして、Chromium stockのページ復旧と通常Keychainの検証は[Keychain経路を中心にした再計画](phase5-page-recovery-replan.md)に従う。現行S0・GPU無効化条件での原因調査は完了したが、この範囲を超える一般化はしていない。このChromiumトラックの結果をKOOVの受入に使わない。

旧Chromiumページ復旧計画では、HTTP停止の原因特定を実験完了条件としていた。この条件とChromium経由のKOOV手順は現行KOOVの受入経路から外れている。Chromium stock／Keychainトラックは別途、その限定された原因調査と復旧条件を追跡する。

| 項目 | 状態 | 証拠と限界 |
| --- | --- | --- |
| 過去の実機ANGLE／Metal／EGL／WebGL1最小描画 | 成功記録あり | 固定コミットの[実機観測記録](https://github.com/naokikambe/chromium-angle-family1-experiment/blob/292c7e2bab8bd06e9cf2ec50d7d20a451393290d/docs/phase5-real-device-observation.md)。新キットによる実行結果ではない |
| 未署名のビルド済みChromiumのHTTPページ | CI成功記録あり | snapshot 1689422を使用したU0/U1。実機の初回署名後結果とは環境・入力版が異なる |
| HTTP停止の原因調査 | 現行S0・GPU無効化の範囲で完了 | 未応答試行と、拒否・APIエラー返却後に開始した要求のHTTP・描画成功を区別。mockの独立profile3件はHTTP・DOM・JS・canvasと実GUI確認に成功した。callback各段階にはソース推定を含み、結論は現行S0・GPU無効化条件に限定する |
| 通信診断ログ入りChromiumの全体ビルド | 未完成 | run 37464208418は時間切れ。小規模対象の成功で完成済みとは扱わない |
| ページ復旧キット | portable test suiteとsymlink root alias fix | `scripts/page-recovery/`。symlink regression covers internal aliases and rejects external or broken links. Platform behavior, GUI confirmation, and product acceptance require separate validation |
| 別トラック：Chromium stock／Keychain | 通常Keychainでのstock復旧 | 正常な鍵取得、通常GPUでの独立profile3件と実GUI、同じ検証profileの再起動・暗号化cookie利用を一括で検証する。これはKOOVの起動・受入経路ではない。必要な許可操作と環境変更は既存同意から推定しない |
| stock受入の現在の阻害要因 | Allow試行のAPI境界と署名信頼を未確認 | 同じAllow試行の返却stackは未取得。別の未応答試行のstackは転用しない。署名検証の信頼エラーとidentity検索0件を読み取り専用で切り分け、追加Allowの既存回答を確認する |
| 復旧の後続工程 | 通常Keychainの継続利用条件を検証 | 正常アクセス、同じ署名済みappと独立login Keychainの比較、対象appに限定した信頼条件または利用分離の方針を選択。環境作成・権限変更は現在の原因調査とは別の実行範囲 |
| KOOVの画面・基本操作・機器連携 | Chrome + Family 1 ANGLEで動画・3Dの実操作は定性的に良好 | 合成H.264／VP8の再生、WebGL1 draw/readbackと同じGPU processのANGLE/Metal mappingを確認した。KOOV画面自体のcodec・frame・WebGL callは未計測。第三者が再現するための合成メディア入力とCfT + ANGLE appの組立手順、PWA登録起動、保存／再読込、約30分の利用、正常終了後の再起動、音声・機器連携は未確認 |

実行順序は[具体施策・実行計画](phase5-page-recovery-plan.md)、コマンドは[キットREADME](../scripts/page-recovery/README.md)、次のエージェントへの指示は[引き継ぎプロンプト](phase5-page-recovery-handoff.md)に記録した。過去の整理と現在までの経緯は[経過資料](phase5-page-recovery-history.md)を参照。

Keychain経路を優先する続行指示は[続行プロンプト](phase5-keychain-investigation-handoff.md)に記録した。公開資料は一般的な手順と判定条件を示し、個人情報・実機固有値は含めない。

一部の旧`WEBGL_SMOKE=pass`はテストページの読み込みだけを必須条件にしていた。context／draw、HTTP本文、画像、実GUIを別々に判定する。`RUNTIME_DEVICE_READY=false`はCI成果物の境界であり、過去に実機試験がなかったことを意味しない。

現行S0の原因特定とmockのGUI3件は完了した。10月5日の適用範囲の確認と、Chromium stock／通常Keychain・通常GPUの受入は別トラックで未完了。Chrome for Testing 154 + Family 1 ANGLEでのKOOV動画・3D操作には肯定的な定性的観察があるが、登録済みPWA起動、保存／再読込、約30分の利用、正常終了後の再起動、音声・機器連携は未確認である。Chromium-only動画診断は過去の比較であり、現行KOOVの受入項目ではない。拒否後の暗号化不可での表示成功とmock診断は製品復旧を意味しない。`71d5bb1`の起動待機改善を取り込み、追加の焦点テストをクラウドでも確認した。

## 2026-09-20時点のbaseline記録

以下は当時の記録として保持する。現在のPhase 3以降の状態は上の表と固定された後続記録を参照する。

| Phase | 状態 | 記録 |
| --- | --- | --- |
| Phase 0 | 保留 | 基準資料の比較設計は完了。基準ログを用いた比較表作成は未完了。Phase 3 の実機試験前に完了させる。 |
| Phase 1 | 完了 | Chromium `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854`、ANGLE `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`、dynamic ANGLE の探索位置と主要 dylib を固定ソースで確認済み。Feature override が後続の条件付き既定値で上書きされない根拠を `docs/baseline.md` に追記した。 |
| Phase 2 | Phase 2B 完了 | 初回run `35495704110` と失敗follow-up run `35497602637` の記録は保持する。2回目のfollow-up run [`35501697418`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/35501697418) は固定ANGLE checkout、`gclient sync`、GN、Ninja、artifact検証、uploadに成功した。artifactはx86_64の`libEGL.dylib`と`libGLESv2.dylib`のみを含み、各自己install name以外に非system依存はなく、署名は未署名（Phase 2では許容）である。 |
| Phase 3 以降 | 未着手・Phase 0完了待ち | Chrome.app への配置、署名変更、実機起動、KOOV 試験、Family 1 向け変更、診断ログ追加はいずれも実施していない。Phase 2Bのartifact条件は満たしたが、Phase 0の基準ログ保全と比較表作成、Chrome実loadのレビューが未完了のためPhase 3へは進めない。 |
