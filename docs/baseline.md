# Chromium / ANGLE 基準資料（Phase 0–1）

作成日: 2026-09-20
対象仕様書: `docs/chromium-angle-family1-koov-experiment-plan.md`
実施範囲: Phase 0、Phase 1 の読み取り・照合のみ。Phase 2 以降の checkout、ビルド、Chrome.app 複製、dylib 配置、署名、起動は未実施。

## Phase 0 — 基準資料の保全状況

このワークスペースには仕様書以外のファイルがなく、仕様書が列挙する次の基準ログおよび実機出力は提供されていなかった。そのため、内容の保存・比較表の作成・実機情報の採取は**未実施**である。ここに値を推定して補わない。

- Chrome 149: `about-gpu-2026-09-13T09-41-17-641Z.txt`
- Chrome 154: `about-gpu-2026-09-13T08-51-02-808Z.txt`、`about-gpu-2026-09-14T12-06-16-324Z.txt`、`about-gpu-2026-09-14T12-56-15-880Z.txt`、`chrome154-gpu-process-command.txt`、`貼り付けられたテキスト（1 点）(20260914-122649).txt`
- 実機: `system_profiler SPDisplaysDataType`、OCLP バージョン、macOS ビルド番号

これらを同じ比較項目（Chrome/Chromium/ANGLE、コマンドライン、GL implementation parts、Display type、GPU Feature Status、GPU crash count、EGL/Metal エラー）で整理するには、原本または読み取り専用コピーが必要である。

## Phase 1 — 固定ソース

| 対象 | 確定値 | 根拠 |
| --- | --- | --- |
| Chromium | `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854` | [`chrome/VERSION`](https://chromium.googlesource.com/chromium/src/+/62d2fcb41a84e4dcefd8c4da7dfa534e6c482854/chrome/VERSION#1) の 1–4 行は `154.0.8037.17`。 |
| ANGLE | `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448` | 同 Chromium コミットの [`DEPS`](https://chromium.googlesource.com/chromium/src/+/62d2fcb41a84e4dcefd8c4da7dfa534e6c482854/DEPS#352) 352 行。 |
| ANGLE checkout | `src/third_party/angle` | 同 [`DEPS`](https://chromium.googlesource.com/chromium/src/+/62d2fcb41a84e4dcefd8c4da7dfa534e6c482854/DEPS#2019) 2019–2020 行が `angle_revision` を URL に展開する。 |

従って、Chrome `154.0.8037.17` と上記 ANGLE コミットの対応は DEPS の固定値で確認済みであり、短縮 SHA `8efd15f71c27` だけで運用しない。

## ANGLE Metal 初期化と Feature 定義

- [`src/libANGLE/renderer/metal/DisplayMtl.mm`](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/src/libANGLE/renderer/metal/DisplayMtl.mm#122) 128–160 行は、Metal device の取得、Feature 初期化、Family 判定、command queue、format table、shader library の順に初期化する。
- 同ファイル [141–145 行](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/src/libANGLE/renderer/metal/DisplayMtl.mm#141) は `requireGpuFamily2` が有効で Mac Family 2 を満たさない場合に停止する。
- 同 [1202–1216 行](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/src/libANGLE/renderer/metal/DisplayMtl.mm#1202) は、条件付き既定値を設定する前に `ApplyFeatureOverrides` を呼ぶ。同 [1314–1316 行](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/src/libANGLE/renderer/metal/DisplayMtl.mm#1314) は `requireGpuFamily2` を既定で有効にする。
- [`include/platform/mtl_features.json`](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/include/platform/mtl_features.json#367) 367–373 行が当該 Feature の生成元であり、「OpenGL ES 2.0 の全機能には Mac GPU Family 2 が必要」と説明する。生成済みの [`FeaturesMtl_autogen.h`](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/include/platform/autogen/FeaturesMtl_autogen.h#305) 305–309 行は CLI 名が `requireGpuFamily2` であることを示す。
- 指定された [`EGLFeatureControlTest.cpp`](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/src/tests/egl_tests/EGLFeatureControlTest.cpp#124) 124–201 行は、Feature override を新しい EGL display に渡し、状態を照合する汎用テストである。389–396 行に Metal パラメータを含む。この固定コミットに `requireGpuFamily2` 専用のテストがあることは、このファイルからは確認できない。
- `requireMsl21` は、上記固定コミットの `mtl_features.json` と `FeaturesMtl_autogen.h` には存在しない。したがって、この Phase 1 では `--disable-angle-features=requireMsl21` の意味・有効性をこのコミットに対して確定しない。

## Feature override の上書き防止（Phase 1 補足）

固定 ANGLE コミット `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448` の [`include/platform/Feature.h`](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/include/platform/Feature.h#16) 16–23 行で定義される `ANGLE_FEATURE_CONDITION` は、対象 Feature の `hasOverride` が `false` の場合にだけ `enabled` を条件値へ設定する。145–147 行のコメントも、override 済み Feature は有効化条件を再評価しない意味を明記する。

- [`src/libANGLE/renderer/renderer_utils.cpp`](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/src/libANGLE/renderer/renderer_utils.cpp#72) 72–76 行の `FeatureInfo::applyOverride` は `enabled` を指定値に設定してから `hasOverride = true` にする。89–107 行の `FeatureSetBase::overrideFeatures` は名前が一致した Feature にこのメソッドを呼ぶ。
- 同 [1715–1721 行](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/src/libANGLE/renderer/renderer_utils.cpp#1715) の `ApplyFeatureOverrides` は enabled 一覧へ `true`、disabled 一覧へ `false` を渡す。したがって、ANGLE に到達した disabled 一覧で `requireGpuFamily2` が名前一致した場合、その Feature は `enabled = false`、`hasOverride = true` になる。
- `DisplayMtl.mm` は前節で確認したとおり `ApplyFeatureOverrides` の後に `ANGLE_FEATURE_CONDITION` で `requireGpuFamily2` の条件付き既定値を設定する。上記マクロの実装により、`hasOverride == true` の場合はその後の既定有効化で `true` へ戻されない。

この結論は、固定コミット内の Feature override と条件付き既定値の実装について**ソースで確認済み**である。一方、Chrome の `--disable-angle-features=requireGpuFamily2` が ANGLE へ正しく渡され、入力文字列が実行時に当該内部 Feature 名として認識・一致したこと、ならびに実機での最終状態は、実機ログまたは Phase 4 の診断ビルドでのみ確認できる。`requireMsl21` はこの固定コミットで存在を確認できていないため、効果があったとは扱わない。

## `--use-dynamic-angle` と GPU プロセス

- Chromium の [`ui/gl/gl_switches.cc`](https://chromium.googlesource.com/chromium/src/+/62d2fcb41a84e4dcefd8c4da7dfa534e6c482854/ui/gl/gl_switches.cc#95) 95–98 行は、`USE_STATIC_ANGLE` ビルドで `--use-dynamic-angle` を定義する。
- 同 [181–210 行](https://chromium.googlesource.com/chromium/src/+/62d2fcb41a84e4dcefd8c4da7dfa534e6c482854/ui/gl/gl_switches.cc#181) は GPU プロセスへコピーする GL switch リストに `kUseDynamicAngle` を含める。
- Chromium の [`content/browser/gpu/gpu_process_host.cc`](https://chromium.googlesource.com/chromium/src/+/62d2fcb41a84e4dcefd8c4da7dfa534e6c482854/content/browser/gpu/gpu_process_host.cc#1476) 1476–1485 行は、そのリストを browser command line から GPU process command line へコピーする。従って、当該ビルド条件を満たす Chrome 154 では switch の伝達経路はソースで確認できる。

## macOS の動的 ANGLE 探索位置と必要ファイル

Chrome 固定コミットの [`ui/gl/init/gl_initializer_mac.cc`](https://chromium.googlesource.com/chromium/src/+/62d2fcb41a84e4dcefd8c4da7dfa534e6c482854/ui/gl/init/gl_initializer_mac.cc#34) による実装は次のとおりである。

1. 34–35 行: 対象名は `libGLESv2.dylib` と `libEGL.dylib`。
2. 41–49 行: app bundle の場合、基準ディレクトリは `base::apple::FrameworkBundlePath().Append("Libraries")`。非 bundle のテスト実行だけは executable の親ディレクトリを使う。
3. 51–87 行: `libGLESv2.dylib` を先に、`libEGL.dylib` を次にそのディレクトリからロードし、EGL の `eglGetProcAddress` を取得する。
4. 95–110 行: static ANGLE build で `--use-dynamic-angle` があると、静的 ANGLE の代わりに前記 dylib ローダーを使う。

ANGLE の同一固定コミットにある [`scripts/update_chrome_angle.py`](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/scripts/update_chrome_angle.py#35) 35–43 行は Canary の concrete path を `/Applications/Google Chrome Canary.app/Contents/Frameworks/Google Chrome Framework.framework/Libraries` とし、必須コピー対象を前記 2 dylib、component build の任意対象を次の 4 dylib とする。109–112 行は任意対象が `is_component_build = true` に必要と明記する。

- `libc++_chrome.dylib`
- `libchrome_zlib.dylib`
- `libthird_party_abseil-cpp_absl.dylib`
- `libvk_swiftshader.dylib`

このため、dynamic loader が直接要求する最小セットは `libGLESv2.dylib` と `libEGL.dylib` である。component build の追加 4 dylib が実際に必要かは、Phase 2 で選ぶ GN args と成果物の `otool -L` で確認するまで確定しない。

ANGLE の [`BUILD.gn`](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/BUILD.gn#1503) 1503–1509 行は `libGLESv2` を共有ライブラリとして定義する。1642–1645 行は `libEGL` を共有ライブラリとして定義し、1638 行で `libGLESv2` を data dependency にする。従って、loader の順序とビルド定義は整合する。

Metal 内部 shader は外部 `.metallib` の配置要件としては確認されていない。Metal backend の [`BUILD.gn`](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/src/libANGLE/renderer/metal/BUILD.gn#70) 70–143 行は `.metallib` を `gDefaultMetallib` のヘッダーへ埋め込み、`DisplayMtl.mm` の [1336–1355 行](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/src/libANGLE/renderer/metal/DisplayMtl.mm#1336) はその静的バイナリから library を生成する。実際の GN 設定でどちらのコンパイル経路になるかは未ビルドのため未確認である。

## 未実施・次の前提

- ローカルの Google Chrome `154.0.8037.17` app bundle はこのワークスペースにないため、実機上の framework bundle path、dylib 依存関係、署名状態は未検証。
- Phase 1 完了時点では Phase 2 の GN args、Ninja target、成果物、`otool -L`、`file`、hash、CI workflow は未作成だった。現在の状態は [`docs/phase-status.md`](phase-status.md) を参照する。
- Phase 3 以降の Chrome.app 変更、codesign、起動、GPU/KOOV 試験は実施していない。
