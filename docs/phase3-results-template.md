# Phase 3 実機結果テンプレート

状態: **未実施テンプレート**。この文書は実機ログではない。公開時はユーザー名、ホームディレクトリ、serial number、profile path、Cookie、tokenを削除または置換する。実データはGit管理外の`local-results/`に保全する。

| Case | Chrome version | Chromium revision | ANGLE revision | ANGLE dylib SHA | dynamic ANGLE load evidence | command-line override | GPU process result | EGL initialization | ANGLE backend | WebGL | Compositing | GPU crash count | observed error | 判定 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 未実施 | `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854` | 内蔵 | 該当なし | 未確認 | なし | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 |
| B | 未実施 | `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854` | `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448` | `f4a8a7575183a41373404f7c25b4f56e1a1540c5b1578d11437c180b1f698db8` / `2e0aadc21e76b0bb1adcfb3b908e757906995b75abb9e90edb3dfb5c1d1adef0` | 未確認 | なし | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 |
| C | 未実施 | `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854` | `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448` | `f4a8a7575183a41373404f7c25b4f56e1a1540c5b1578d11437c180b1f698db8` / `2e0aadc21e76b0bb1adcfb3b908e757906995b75abb9e90edb3dfb5c1d1adef0` | 未確認 | `--disable-angle-features=requireGpuFamily2` | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 |
| D | 未実施 | 未実施 | Family 1実験版 | 未実施 | 未確認 | 同上 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 |
| E | 未実施 | 未実施 | Family 1実験版 | 未実施 | 未確認 | 同上 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 |
| F | 未実施 | 未実施 | Family 1実験版 | 未実施 | 未確認 | 同上 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 | 未実施 |

## 証拠の記録規則

- dynamic ANGLE load evidenceは、GPU processに対する`lsof`、`vmmap`、または同等に直接的なdyld記録で2本のdylib絶対パスを確認できた場合だけ「確認済み」とする。
- command lineに`--use-dynamic-angle`があるだけでは、ロード確認済みとは記録しない。
- Case CのswitchがANGLE内部Feature名として認識され、`requireGpuFamily2`がoverrideされたかは、診断ログまたは実行時証拠がなければ未確認とする。
- `chrome://gpu`からGPU process crash count、GL implementation parts、Display type、GL_VENDOR、GL_RENDERER、WebGL、Compositing、Rasterizationを保存する。画面全体やprofile情報を公開用文書へ混入させない。
