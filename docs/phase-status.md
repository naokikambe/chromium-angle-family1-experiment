# Phase 状態

更新日: 2026-09-20

| Phase | 状態 | 記録 |
| --- | --- | --- |
| Phase 0 | 保留 | 基準資料の比較設計は完了。実機ログがワークスペースに未提供のため、ログ保全と比較表作成は保留。Phase 3 の実機試験前に完了させる。 |
| Phase 1 | 完了 | Chromium `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854`、ANGLE `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`、dynamic ANGLE の探索位置と主要 dylib を固定ソースで確認済み。Feature override が後続の条件付き既定値で上書きされない根拠を `docs/baseline.md` に追記した。 |
| Phase 2 | Phase 2B 完了 | 初回run `35495704110` と失敗follow-up run `35497602637` の記録は保持する。2回目のfollow-up run [`35501697418`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/35501697418) は固定ANGLE checkout、`gclient sync`、GN、Ninja、artifact検証、uploadに成功した。artifactはx86_64の`libEGL.dylib`と`libGLESv2.dylib`のみを含み、各自己install name以外に非system依存はなく、署名は未署名（Phase 2では許容）である。Phase 2B時点では未実行だった固定depot_tools `0306e4682b4ac35287c726fa35a983157a625902` のbootstrap付き構成は、Phase 3A run `35515036255`で初めて実行・検証された。 |
| Phase 3A | `.45` artifact準備完了・実機試験未実施 | 実機Chromeが`154.0.8037.45`へ更新されたため、Chromium `731082f0a26ce4b3976c3d82943092f5d13daf13`とANGLE `72b8f72a7587ec776d7d2a57d275a6e9b1781b1d`へ対象を切替えた。.17向け成功artifactは履歴として保持するが流用しない。初回run [`35514080466`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/35514080466) のGN時bootstrap不足は、固定depot_toolsの公式`ensure_bootstrap`を追加して解消した。修正後run [`35515036255`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/35515036255) はGN、Ninja、artifact検証・uploadに成功し、.45用artifactを検証済みである。Chrome appのcopy/変更、dylib配置、Chrome起動、実機profile利用は未実施である。元app全体のstrict署名検証は`com.apple.FinderInfo`属性で失敗し、main executable、Framework、GPU Helper個別のGoogle署名は有効だった。xattrは変更しない。 |
| Phase 3B 以降 | 未着手・Phase 0完了待ち | Chrome実load、署名・Library Validation判断、実機起動、KOOV 試験、Family 1 向け変更、診断ログ追加はいずれも実施していない。Case Bの外部standard ANGLE直接ロード証拠とPhase 0の基準ログ保全・比較表作成、Chrome実loadの人間レビューが完了するまで先へ進めない。 |
