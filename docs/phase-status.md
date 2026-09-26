# Phase 状態

更新日: 2026-09-26

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

Phase 3C preflight is being migrated to verified release manifests and dynamic
attempt roots. New artifacts use `angle-release-v1`; source Chrome's exact
version must match the selected artifact manifest. Existing retry0–12 and their
evidence remain immutable historical records. New attempts use a fresh
`attempt-YYYYMMDD-HHMMSS` root with output and results as direct children. The
current-only Framework policy discovers `Versions/Current` from the selected
Chrome release rather than pinning `.17` or `.45`. Formal acceptance is only
the pinned Phase 3B/3C synthetic Actions workflows; local full fixtures are
prohibited. CI success is required before requesting separate human approval
for new real-device work. Any separately approved historical device-test record remains historical and does not authorize a new signing, Chrome, or KOOV operation.

| Phase | 状態 | 記録 |
| --- | --- | --- |
| Phase 0 | 保留 | 基準資料の比較設計は完了。実機ログがワークスペースに未提供のため、ログ保全と比較表作成は保留。Phase 3 の実機試験前に完了させる。 |
| Phase 1 | 完了 | Chromium `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854`、ANGLE `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`、dynamic ANGLE の探索位置と主要 dylib を固定ソースで確認済み。Feature override が後続の条件付き既定値で上書きされない根拠を `docs/baseline.md` に追記した。 |
| Phase 2 | Phase 2B 完了 | 初回run `35495704110` と失敗follow-up run `35497602637` の記録は保持する。2回目のfollow-up run [`35501697418`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/35501697418) は固定ANGLE checkout、`gclient sync`、GN、Ninja、artifact検証、uploadに成功した。artifactはx86_64の`libEGL.dylib`と`libGLESv2.dylib`のみを含み、各自己install name以外に非system依存はなく、署名は未署名（Phase 2では許容）である。Phase 2B時点では未実行だった固定depot_tools `0306e4682b4ac35287c726fa35a983157a625902` のbootstrap付き構成は、Phase 3A run `35515036255`で初めて実行・検証された。 |
| Phase 3A | legacy artifact記録 | Chrome `154.0.8037.45`向けartifact `35515036255`は過去の固定SHA・形式・依存・署名検証結果として記録する。新形式のrelease manifestを持たず、新しい実機試験には使用しない。 |
| Phase 3B | synthetic fixture CI成功・実機試験未実施 | `angle-release-v1`はChrome/Chromium/ANGLE/depot_tools識別子、dylib SHA、artifact/run metadataを束縛する。test-copy manifestはrelease manifest SHAを記録し、Libraries baselineを保持したままANGLE 2本だけ追加する。正式なsynthetic fixture判定は下記のrunで成功した。ローカルfull fixtureは実行しない。retry0–12は保存済み履歴として不変保持し、新規attempt rootは別名で作成する。元Chromeのxattr、実署名、実機起動は行わない。 |
| Phase 3B 以降 | synthetic 3B/3C成功、Phase 3D VM観測成功・新規実機試験未承認 | Phase 3D文書に記録された、別途承認済みの過去のユーザー所有機器テスト・署名・Chrome起動記録は履歴として保持する。今回確認した3B/3C/3D run metadataは新規の実機作業を承認せず、Family 1向け変更も実施していない。Phase 0の基準ログ保全・比較表、人間レビュー、およびPhase 5の詳細な入場記録が満たされるまで、新たな実機・署名・Chrome/KOOV操作へ進めない。 |

## Phase 3の一次記録（2026-09-26確認）

親エージェントが確認した公開GitHub Actionsのrun metadataと、読み取り専用で取得したdiagnostics artifactの検証結果を記録する。3B/3C/3Dのrunはそれぞれ別artifactであり、3B/3Cのdiagnostics成功と、3Dで選択されたrelease manifest/artifactの検証結果を混同しない。

| 対象 | run | commit | diagnostics / artifact | 一次記録 |
| --- | --- | --- | --- | --- |
| Phase 3B synthetic fixture | `36241793357` / success | `3b116228de6c2af80b14cdfb36ff6fec1af6db38` | `phase3b-synthetic-fixture-diagnostics-36241793357` / archive SHA-256 `2299e7085280d7ef80bec61f4f4a0d3de26cef8a1e7680eb3f633b4e4646ccab` / exit `0` | [Actions run](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36241793357) |
| Phase 3C synthetic preflight fixture | `36241795968` / success | `3b116228de6c2af80b14cdfb36ff6fec1af6db38` | `phase3c-preflight-synthetic-diagnostics-36241795968` / archive SHA-256 `d33c4e301f023ce9870e2a8faba139fb9415c5109aca9584d080ad661ac9ec03` / exit `0` | [Actions run](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36241795968) |
| Phase 3D dynamic ANGLE VM observation | `36071196477` / success | `e9002f5ba7f70ec6b23f6b82453c9580a33a399b` | `phase3d-dynamic-angle-36065655290-36071196477` / archive SHA-256 `8f142e7503555fe3d9a75f0716daf8777509b28089e17b1bb4a8cfef7aabe298` | [Actions run](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36071196477) |

Phase 3D diagnostics artifactの`ANGLE_RELEASE_MANIFEST`はsidecar検証に成功した。schemaは`angle-release-v1`、Chromeは`154.0.8037.57`、manifest SHA-256は`ed01fc7c8a1634193cebc7e016be2fddd4a1d0094e7a77abdc98798d6b078c4f`、選択artifactは`angle-macos-x86_64-chrome-154.0.8037.57-angle-1ff8799c-36065655290`、ANGLE revisionは`1ff8799c596d4fc9acea28343610b1f33650a6fa`、build runは`36065655290`である。これにより、Phase 5の詳細なadmission recordはソース実装開始に必要な範囲で完了した。ただし、新規Actions dispatch、artifact download、署名、Chrome起動、実機操作を承認するものではない。
