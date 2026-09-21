# Phase 状態

更新日: 2026-09-20

## Orchestration

人間がOwner/Approver、親エージェントがOrchestrator/Reviewer、Lunaが
Implementerである。人間は親とのみ通信し、親は一度に一体だけのLunaへ
範囲限定の指示を出し、実diffと検証を独立レビューする。親はこのbranchの
通常checkpoint/fix commit、push、Phase 3B CIのdispatch/monitorを行える。
main/他branch、force/rebase/merge/tag/release、PR/issue、署名、実機・artifact・retry操作は
引き続き人間の承認境界である。通常の修正・fixture
失敗・文書不足・診断は `IN PROGRESS` または `CHANGES REQUIRED` であり、
`BLOCKED` は承認境界、権限、利用不能な外部依存、安全でない統合、必須の人間
設計判断、診断枯渇、または重大な状態不一致に限る。dirty worktree、保存済み
retryディレクトリ、evidenceは消去・reset・cleanしない。

Phase 3Bの正式acceptanceは、CI job成功、fixture exit `0`、static checksと
`git diff --check`成功、required fixtureのskipなし、unexpected diagnosticsなしを
すべて満たすこととする。fixture stepは20分、jobは30分で、timeoutは失敗である。
CIはrunner/environment情報とfixture stdout/stderr、exit status、diagnostics indexを保持する。
失敗時は親がlogs/artifactをreview・分類し、Lunaがbounded fix、親がreview/static checksを行い、
checkpoint commit/push後に新runを開始する。明確なtransient runner/service failureの場合だけ
1回のrerunを許可し、無目的なrerunはしない。mainと実機は承認境界であり、retry3は保存済みfailure/no-opである。

Phase 3C preflightは実機未実施であり、正式な受入れは固定SHAの
`phase3c-preflight-fixtures.yml` synthetic CIだけで行う。CI fixtureはsource/artifactを
合成し、preflightの全gateと失敗条件を検証する。実preflightではsource Chromeや保存済み
retry/evidenceを変更せず、signはdry-runだけとする。retry0-3は予約済みfailure/no-op、retry4が
次の計画pathであり、人間の承認なしに作成・署名・起動しない。

初回Phase 3C CIのpath-role failureは、read-only sourceまで`/Applications`拒否していた
synthetic fixture mismatchだった。sourceは既存・非symlinkなら許可し、writable output/resultsは
引き続き`/Applications`、root、source/evidence、retry0-3、symlink、既存pathを拒否する。
修正後もreal preflightは未実施であり、再承認なしに実機へ進めない。

| Phase | 状態 | 記録 |
| --- | --- | --- |
| Phase 0 | 保留 | 基準資料の比較設計は完了。実機ログがワークスペースに未提供のため、ログ保全と比較表作成は保留。Phase 3 の実機試験前に完了させる。 |
| Phase 1 | 完了 | Chromium `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854`、ANGLE `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`、dynamic ANGLE の探索位置と主要 dylib を固定ソースで確認済み。Feature override が後続の条件付き既定値で上書きされない根拠を `docs/baseline.md` に追記した。 |
| Phase 2 | Phase 2B 完了 | 初回run `35495704110` と失敗follow-up run `35497602637` の記録は保持する。2回目のfollow-up run [`35501697418`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/35501697418) は固定ANGLE checkout、`gclient sync`、GN、Ninja、artifact検証、uploadに成功した。artifactはx86_64の`libEGL.dylib`と`libGLESv2.dylib`のみを含み、各自己install name以外に非system依存はなく、署名は未署名（Phase 2では許容）である。Phase 2B時点では未実行だった固定depot_tools `0306e4682b4ac35287c726fa35a983157a625902` のbootstrap付き構成は、Phase 3A run `35515036255`で初めて実行・検証された。 |
| Phase 3A | 完了 | `.45` artifact `angle-macos-x86_64-chrome-154.0.8037.45-angle-72b8f72a-35515036255`を固定SHA・形式・依存・署名状態まで検証済み。実機Chromeは未操作。 |
| Phase 3B | prepare設計修正済み・CI fixture acceptance待ち・実機試験未実施 | manifest schema v3はChrome Libraries baselineを保持し、`libEGL.dylib`と`libGLESv2.dylib`だけを追加する。完全なsynthetic fixture suiteの正式判定は`.github/workflows/phase3b-fixtures.yml`の`macos-15-intel` CIだけで行う。ローカルfull fixtureは実行しない。retry3の保存済みfailure/evidenceは変更せず、元Chromeのxattrも変更しない。 |
| Phase 3B 以降 | 未着手・Phase 0完了待ち | Chrome実load、署名・Library Validation判断、実機起動、KOOV 試験、Family 1 向け変更、診断ログ追加はいずれも実施していない。Case Bの外部standard ANGLE直接ロード証拠とPhase 0の基準ログ保全・比較表作成、Chrome実loadの人間レビューが完了するまで先へ進めない。 |
