# Phase 3 実機結果テンプレート

状態: **未実施テンプレート**。この文書は実機ログではない。公開時はユーザー名、ホームディレクトリ、serial number、profile path、Cookie、tokenを削除または置換する。実データはGit管理外の`local-results/`に保全する。

| Case | Chrome version | Chromium revision | ANGLE revision | ANGLE dylib SHA | dynamic ANGLE load evidence | command-line override | GPU process result | EGL initialization | ANGLE backend | WebGL | Compositing | GPU crash count | observed error | 判定 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 未実施 | `731082f0a26ce4b3976c3d82943092f5d13daf13` | 内蔵 | 該当なし | 未確認 | なし | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 |
| B | 未実施 | `731082f0a26ce4b3976c3d82943092f5d13daf13` | `72b8f72a7587ec776d7d2a57d275a6e9b1781b1d` | CI未実行 | 未確認 | なし | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 |
| C | 未実施 | `731082f0a26ce4b3976c3d82943092f5d13daf13` | `72b8f72a7587ec776d7d2a57d275a6e9b1781b1d` | CI未実行 | 未確認 | `--disable-angle-features=requireGpuFamily2` | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 |
| D | 未実施 | 未実施 | Family 1実験版 | 未実施 | 未確認 | 同上 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 |
| E | 未実施 | 未実施 | Family 1実験版 | 未実施 | 未確認 | 同上 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 |
| F | 未実施 | 未実施 | Family 1実験版 | 未実施 | 未確認 | 同上 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 |

## 証拠の記録規則

- dynamic ANGLE load evidenceは、GPU processに対する`lsof`、`vmmap`、または同等に直接的なdyld記録で2本のdylib絶対パスを確認できた場合だけ「確認済み」とする。
- command lineに`--use-dynamic-angle`があるだけでは、ロード確認済みとは記録しない。
- Case CのswitchがANGLE内部Feature名として認識され、`requireGpuFamily2`がoverrideされたかは、診断ログまたは実行時証拠がなければ未確認とする。
- `chrome://gpu`からGPU process crash count、GL implementation parts、Display type、GL_VENDOR、GL_RENDERER、WebGL、Compositing、Rasterizationを保存する。画面全体やprofile情報を公開用文書へ混入させない。
