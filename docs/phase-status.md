# Phase 状態

更新日: 2026-09-20

## Orchestration

人間がOwner/Approver、親エージェントがOrchestrator/Reviewer、Lunaが
Implementerである。人間は親とのみ通信し、親は一度に一体だけのLunaへ
範囲限定の指示を出し、実diffと検証を独立レビューする。commit、push、署名、
実機・artifact・retry操作は人間の明示承認まで実行しない。通常の修正・fixture
失敗・文書不足・診断は `IN PROGRESS` または `CHANGES REQUIRED` であり、
`BLOCKED` は承認境界、権限、利用不能な外部依存、安全でない統合、必須の人間
設計判断、診断枯渇、または重大な状態不一致に限る。dirty worktree、保存済み
retryディレクトリ、evidenceは消去・reset・cleanしない。

| Phase | 状態 | 記録 |
| --- | --- | --- |
| Phase 0 | 保留 | 基準資料の比較設計は完了。実機ログがワークスペースに未提供のため、ログ保全と比較表作成は保留。Phase 3 の実機試験前に完了させる。 |
| Phase 1 | 完了 | Chromium `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854`、ANGLE `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`、dynamic ANGLE の探索位置と主要 dylib を固定ソースで確認済み。Feature override が後続の条件付き既定値で上書きされない根拠を `docs/baseline.md` に追記した。 |
| Phase 2 | Phase 2B 完了 | 初回run `35495704110` と失敗follow-up run `35497602637` の記録は保持する。2回目のfollow-up run [`35501697418`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/35501697418) は固定ANGLE checkout、`gclient sync`、GN、Ninja、artifact検証、uploadに成功した。artifactはx86_64の`libEGL.dylib`と`libGLESv2.dylib`のみを含み、各自己install name以外に非system依存はなく、署名は未署名（Phase 2では許容）である。Phase 2B時点では未実行だった固定depot_tools `0306e4682b4ac35287c726fa35a983157a625902` のbootstrap付き構成は、Phase 3A run `35515036255`で初めて実行・検証された。 |
| Phase 3A | 完了 | `.45` artifact `angle-macos-x86_64-chrome-154.0.8037.45-angle-72b8f72a-35515036255`を固定SHA・形式・依存・署名状態まで検証済み。実機Chromeは未操作。 |
| Phase 3B | prepare設計修正済み・実機試験未実施 | artifact検証は実機で成功した。初回prepareはsource metadata detritusでStage 1停止し、既知messageのみwarning化した後のretry1は`ditto --noextattr --noqtn` copyにFinderInfoが残ってStage 2停止した。retry1にはdylib、manifest、receiptがない。元Chromeのxattrは変更しない。次回は未使用retry2 pathで、resource fork/HFS metadata・extended attributes・ACL・quarantineを持ち込まない`ditto --norsrc --noextattr --noacl --noqtn`を使う。copy側ではapp/main/Framework/GPU Helperのstrict検証、Google Developer ID、TeamIdentifier、FinderInfo/ResourceFork不在をすべてfatal gateとして、dylib配置より前に検証する。 |
| Phase 3B 以降 | 未着手・Phase 0完了待ち | Chrome実load、署名・Library Validation判断、実機起動、KOOV 試験、Family 1 向け変更、診断ログ追加はいずれも実施していない。Case Bの外部standard ANGLE直接ロード証拠とPhase 0の基準ログ保全・比較表作成、Chrome実loadの人間レビューが完了するまで先へ進めない。 |
