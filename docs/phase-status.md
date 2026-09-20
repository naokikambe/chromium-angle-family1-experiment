# Phase 状態

更新日: 2026-09-20

| Phase | 状態 | 記録 |
| --- | --- | --- |
| Phase 0 | 保留 | 基準資料の比較設計は完了。実機ログがワークスペースに未提供のため、ログ保全と比較表作成は保留。Phase 3 の実機試験前に完了させる。 |
| Phase 1 | 完了 | Chromium `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854`、ANGLE `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`、dynamic ANGLE の探索位置と主要 dylib を固定ソースで確認済み。Feature override が後続の条件付き既定値で上書きされない根拠を `docs/baseline.md` に追記した。 |
| Phase 2 | Phase 2B: follow-up build失敗、再実行禁止 | 初回run `35495704110` の job-level `runner.temp` 検証失敗は保持する。follow-up run [`35497602637`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/35497602637) はrunner割当、固定ANGLE checkout、`gclient sync`、GN、Ninjaを成功したが、artifact検証が `./libEGL.dylib` を非system依存として誤検出して失敗した。artifact upload、`otool`、署名、hash、ライセンスの確認は未完了。今回の1回の再実行後は修正・再実行しない。 |
| Phase 3 以降 | 未着手・Phase 2で停止 | Chrome.app への配置、署名変更、実機起動、KOOV 試験、Family 1 向け変更、診断ログ追加はいずれも実施していない。Phase 2 の有効なartifactがないためPhase 3へ進めない。 |
