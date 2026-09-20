# Phase 状態

更新日: 2026-09-20

| Phase | 状態 | 記録 |
| --- | --- | --- |
| Phase 0 | 保留 | 基準資料の比較設計は完了。実機ログがワークスペースに未提供のため、ログ保全と比較表作成は保留。Phase 3 の実機試験前に完了させる。 |
| Phase 1 | 完了 | Chromium `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854`、ANGLE `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`、dynamic ANGLE の探索位置と主要 dylib を固定ソースで確認済み。Feature override が後続の条件付き既定値で上書きされない根拠を `docs/baseline.md` に追記した。 |
| Phase 2 | Phase 2A: 構成作成済み、CI 未実行 | 無改造 ANGLE 用 workflow と成果物検証スクリプトを作成済み。GitHub Actions 実行、ANGLE の実ビルド、成果物 ABI 検証は未実施。 |
| Phase 3 以降 | 未着手 | Chrome.app への配置、署名変更、実機起動、KOOV 試験、Family 1 向け変更、診断ログ追加はいずれも実施していない。 |
