# Phase 状態

更新日: 2026-09-20

| Phase | 状態 | 記録 |
| --- | --- | --- |
| Phase 0 | 保留 | 基準資料の比較設計は完了。実機ログがワークスペースに未提供のため、ログ保全と比較表作成は保留。Phase 3 の実機試験前に完了させる。 |
| Phase 1 | 完了 | Chromium `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854`、ANGLE `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`、dynamic ANGLE の探索位置と主要 dylib を固定ソースで確認済み。Feature override が後続の条件付き既定値で上書きされない根拠を `docs/baseline.md` に追記した。 |
| Phase 2 | Phase 2B 完了 | 初回run `35495704110` と失敗follow-up run `35497602637` の記録は保持する。2回目のfollow-up run [`35501697418`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/35501697418) は固定ANGLE checkout、`gclient sync`、GN、Ninja、artifact検証、uploadに成功した。artifactはx86_64の`libEGL.dylib`と`libGLESv2.dylib`のみを含み、各自己install name以外に非system依存はなく、署名は未署名（Phase 2では許容）である。 |
| Phase 3 以降 | 未着手・Phase 0完了待ち | Chrome.app への配置、署名変更、実機起動、KOOV 試験、Family 1 向け変更、診断ログ追加はいずれも実施していない。Phase 2Bのartifact条件は満たしたが、Phase 0の基準ログ保全と比較表作成、Chrome実loadのレビューが未完了のためPhase 3へは進めない。 |
