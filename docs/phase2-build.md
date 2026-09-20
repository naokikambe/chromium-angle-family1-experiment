# Phase 2A — 無改造 ANGLE の macOS x86_64 ビルド構成

更新日: 2026-09-20
状態: **Phase 2B 完了**。この文書は固定ソースで確認した事実、設定上の判断、CI または実機でのみ確認できる事項を区別する。Family 1 向け変更、診断ログ追加、Chrome.app 操作は含まない。

## Phase 2B 初回実行記録

- 実行日時: 2026-09-20 07:00:24 UTC
- GitHub repository: `https://github.com/naokikambe/chromium-angle-family1-experiment`（public、default branch `main`）
- 対象commit: `4d5904ed745a26019ea3d8f2bf2fe0b109db7171`
- GitHub workflow ID: `362502195`。唯一作成されたrunは [`35495704110`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/35495704110)（event `push`、結論 `failure`、created/updated ともに 07:00:24 UTC）である。
- 明示した `gh workflow run build-angle-macos-x64.yml --ref main` はrunを作成できず、HTTP 422 で停止した。GitHubが報告した最初の本質的エラーは、workflow 22–24行の `runner.temp` が job-level `env` では利用できないため `Unrecognized named-value: 'runner'` である。
- runnerは割り当てられず、jobsは0件、run logは存在しない。したがって所要時間は実質0秒であり、depot_tools SHA、GN生成、Ninja、Metal toolchain、容量推移、artifact名、dylib一覧、SHA-256、署名状態、ライセンス収集はすべて未取得である。
- 原因分類はGN、Ninja、Metal toolchain、容量、timeout、runner供給ではなく、GitHub workflow context validationである。修正候補は、`runner.temp` をjob-level expressionから除き、各 `run` stepで提供される `RUNNER_TEMP` を用いる構成へ変更すること。ただし初回失敗後にworkflow、GN args、runner、timeout、dependency設定を変更または再実行しないというPhase 2B制約に従い、本作業では変更しない。
- artifactが存在しないため、追加dylib、install name、`@rpath` / `@loader_path` / `@executable_path`、absolute runner path、未解決非system依存、x86_64 Mach-O、署名有効性を判定できない。Phase 3へは進めない。

## Phase 2B follow-up 実行記録

- 修正commit: `6fa13ad51faec33e93a67e4badfa7b76943a52e9`。job-level `env` から `${{ runner.temp }}` を除去し、最初の job step が既定の `$RUNNER_TEMP` を使って `ANGLE_ROOT`、`DEPOT_TOOLS_ROOT`、`ARTIFACT_DIR` を `$GITHUB_ENV` に設定した。他の入力、GN args、target、runner、timeout は変更していない。
- 実行日時: 2026-09-20 07:42:43–08:06:40 UTC（23分57秒）。手動dispatchのrunは [`35497602637`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/35497602637)（commit `6fa13ad51faec33e93a67e4badfa7b76943a52e9`、event `workflow_dispatch`、結論 `failure`）である。このfollow-up以外の再実行はしていない。
- runnerは正常に割り当てられた。実測は `runner.os=macOS`、`runner.arch=X64`、`uname -m=x86_64`、4 CPU、macOS 15.7.9 (24G830)、Xcode 16.4 (16F6)、macOS SDK 15.5、Apple clang 17.0.0、Python 3.14.7、Ninja 1.12.1 である。開始時の使用可能ディスクは108 GiBだったため、実際のhost容量は公開標準runner仕様の14 GB前提より大きい。
- 固定ANGLE checkoutと `gclient sync` は成功した。sync後の実HEADは `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`、depot_tools実HEADは `0306e4682b4ac35287c726fa35a983157a625902`。worktree使用量は checkout後 `8805476 KiB`、GN後 `8819920 KiB`、build後 `8881416 KiB` であり、容量不足・timeoutは発生していない。
- GNは17秒未満で成功し、指定した `is_component_build = false` を含む `args.gn` から1324 targetsを生成した。`ninja -C out/Release libEGL libGLESv2` は1314/1314で成功し、runner上の出力は `libEGL.dylib` 68 KiB、`libGLESv2.dylib` 6.1 MiBだった。Metal backend objectのコンパイルもbuild logで確認した。
- 最初の本質的エラーは `Assemble and verify artifact` stepの `verification failed: libEGL.dylib has an unexpected non-system dependency: ./libEGL.dylib` である。run logには`otool`の結果ファイルが残らないため、その項目が実際に先頭だったこと自体はartifactから再確認できない。一方、失敗時のscriptは `otool -L` の全`NR > 1`項目を実依存として処理しており、macOSの`otool -L`で先頭に出る自己`LC_ID_DYLIB`を意味的に除外していなかった。`libGLESv2.dylib`の検証には到達せず、他の検証エラーもこのrunからは観測されていない。2 dylibはartifact staging directoryへコピー済みだったが、検証scriptが終わる前に失敗したためupload stepはskipされた。よってdownload可能なartifact、`otool`、`file`、`lipo`、install name、追加dylib、absolute path混入、署名状態、SHA-256、収集済みライセンスは確認できない。
- 原因分類はGN、Ninja、Metal toolchain、runner供給、容量、timeoutではなく、自己`LC_ID_DYLIB`と`LC_LOAD_DYLIB`を区別しない検証ロジックである。review済み最小修正は、x86_64の`otool -D`からinstall nameを取得し、x86_64の`otool -L`の先頭項目がその値と完全一致する場合だけ自己IDとして除外することである。自己ID以外の `./*.dylib` は従来どおり失敗させる。この修正は下記の手動runで確認し、artifactの実 `otool -L`、install name、署名、hashを記録した。
- GitHubは `actions/checkout` のNode 20 deprecation annotationを出したが、Node 24へ強制移行してcheckoutは成功した。これは今回の失敗原因ではない。Phase 3へは、有効なartifactのuploadと全検証の成功がないため進めない。

## Phase 2B 2回目follow-up 実行記録

- 修正commitは `cb334c0a4fc73110b85e716689bb4883ea7a8077`（`Distinguish dylib install names from dependencies`）。workflowのANGLE SHA、GN args、runner、timeout、Action SHAは変更していない。`scripts/verify-artifact.sh` は、各x86_64 dylibの`otool -D`からinstall nameを1件だけ取得し、x86_64の`otool -L`先頭項目がその値と完全一致する場合だけ自己`LC_ID_DYLIB`として除外する。以降の`./*.dylib`を含む全項目は従来どおり実依存として検査する。
- ローカル回帰は`bash -n`と`git diff --check`を通過した。一時的なx86_64 dylibで、自己IDとsystem依存を含む未署名artifactは成功、必須`libGLESv2.dylib`欠落・自己ID以外の`./missing.dylib`・模擬した無効署名はそれぞれ失敗することを確認した。テスト生成物はcommitしていない。
- 手動dispatchのrunは [`35501697418`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/35501697418)（commit `cb334c0a4fc73110b85e716689bb4883ea7a8077`、2026-09-20 09:13:11–09:40:14 UTC、26分59秒、結論`success`）である。これがこの修正に対する唯一の手動runであり、retryはしていない。
- runnerはmacOS 15.7.9 (24G830)、`runner.arch=X64`、`uname -m=x86_64`、4 CPU、Xcode 16.4 (16F6)、SDK 15.5、Apple clang 17.0.0、Python 3.14.7だった。ANGLE実HEADはcheckout後と`gclient sync`後の両方で `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`、depot_toolsは `0306e4682b4ac35287c726fa35a983157a625902`。使用量はcheckout後 `8828760 KiB`、GN後 `8843204 KiB`、build後 `8904700 KiB`。GNは1324 targets、Ninjaは1314/1314で成功した。build stepはNinja 1.12.1を記録し、artifactの環境スナップショットはNinja 1.13.2を記録しているため、この差異は実行環境の記録として残し、原因は未確認とする。
- upload artifact名は `angle-macos-x86_64-35501697418`（artifact ID `10602489653`、zip `4214588` bytes）。Git管理外へdownloadして再検証した。全922ファイルのうちrootは`ANGLE_REVISION`、`LICENSE`、`args.gn`、`build-environment.txt`、`checksums.sha256`、`codesign-results.txt`、`file-results.txt`、`lipo-results.txt`、`otool-results.txt`、2 dylibであり、残る911ファイルは`licenses/`配下の第三者license/NOTICEである。
- artifact直下のdylibは`libEGL.dylib`と`libGLESv2.dylib`のみ。両方ともthin x86_64 Mach-Oで、install nameはそれぞれ`./libEGL.dylib`、`./libGLESv2.dylib`である。前回エラーの`./libEGL.dylib`は`libEGL.dylib`自身の`LC_ID_DYLIB`であり、今回の検証では実依存として扱われなかった。`libGLESv2.dylib`の`LC_LOAD_DYLIB`に`./libEGL.dylib`は存在しない。
- 実依存は両dylibとも`/System/Library/...`または`/usr/lib/...`だけである。`libEGL`はMetal、Foundation、CoreFoundation、libSystemをloadし、`libGLESv2`はweak MetalとFoundation、CoreFoundation、libobjc、CoreGraphics、IOKit、IOSurface、QuartzCore、Cocoa、CoreServices、libSystemをloadする。両方の`LC_RPATH`は`@executable_path/`である。`otool-results.txt`にrunner固有絶対パスはなく、未解決の非system依存もない。
- 両dylibは`codesign`で未署名と記録され、Phase 2の許容条件である（有効・無効署名ではない）。SHA-256は`libEGL.dylib`が `f4a8a7575183a41373404f7c25b4f56e1a1540c5b1578d11437c180b1f698db8`、`libGLESv2.dylib`が `2e0aadc21e76b0bb1adcfb3b908e757906995b75abb9e90edb3dfb5c1d1adef0`。artifactの値とローカル再計算は一致した。
- `artifact verification passed`、upload、ローカル再検証まで成功したためPhase 2Bの成功判定を満たす。ただしChrome 154へのload、`@executable_path/`がChrome bundleで解決すること、Library Validation、実機Metal、Feature override、KOOVは未確認である。Phase 0の基準ログ保全を完了し、artifact結果をレビューするまでPhase 3へは進めない。

## 固定入力と runner

- ANGLE は `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448` のみを最終ビルド入力にする。workflow は空の Git repository でこの SHA を `fetch --depth=1` し、detach checkout の直後と `gclient sync` 後の両方で `HEAD` が期待値と一致することを検証する。不一致なら `set -e` と `test` により停止する。Chromium 全体は取得しない。
- Chrome `154.0.8037.17` / Chromium `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854` とこの ANGLE SHA の対応は、既に [`docs/baseline.md`](baseline.md) に記録した Chromium [`DEPS` 352 行](https://chromium.googlesource.com/chromium/src/+/62d2fcb41a84e4dcefd8c4da7dfa534e6c482854/DEPS#352) で確認済みである。
- `runs-on: macos-15-intel` を採用する。確認日 2026-09-20 時点の GitHub 公式 [GitHub-hosted runners reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners#standard-github-hosted-runners-for-public-repositories) は、公開 repository では標準 runner が無料・無制限であり、この label は Intel、4 CPU、14 GB RAM、14 GB SSD と記載する。公式 `actions/runner-images` の [#13045](https://github.com/actions/runner-images/issues/13045) は、同 label が 2027 年 8 月まで提供される最後の x86_64 image と告知する。ただし、無料は無制限の供給・実行を保証しない。[Billing and usage](https://docs.github.com/en/actions/concepts/billing-and-usage) が示す Actions の利用制限・policy、[Additional Product Terms](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features) の不正利用防止規定、runner image の供給状況の影響を受ける。実行時の image、CPU、SDK、Xcode は変動し得るため、workflow が実値をログと `build-environment.txt` に保存する。
- depot_tools は公式 repository の `0306e4682b4ac35287c726fa35a983157a625902` に固定する。workflow は空の Git repository でこの SHA だけを `fetch --depth=1` し、detach checkout直後と `gclient sync` 後に実HEADが期待値と一致することを検証する。`DEPOT_TOOLS_UPDATE=0` は job-level環境変数として設定し、実行中の自己更新を抑止する。固定commitの公式 [`gclient` 10–12 行](https://chromium.googlesource.com/chromium/tools/depot_tools/+/0306e4682b4ac35287c726fa35a983157a625902/gclient#10) と [`update_depot_tools` 105–106 行](https://chromium.googlesource.com/chromium/tools/depot_tools/+/0306e4682b4ac35287c726fa35a983157a625902/update_depot_tools#105) は、値 `0` のときupdate処理をskipすると実装している。`build-environment.txt` には期待SHAと実SHAを別々に記録する。Phase 2Bの過去3 runはこの固定化前であり、実SHAとして同じ値を記録したが、workflow入力としては固定・検証していなかった。

## workflow 実行と Action 固定

workflow は現在 `workflow_dispatch` 専用であり、`pull_request` trigger は持たない。レビュー済みの ref で意図して一回ずつ実行し、PR による macOS runner 消費および PR が変更した script の自動実行を避ける。top-level `concurrency` は `angle-macos-x64-${{ github.ref }}` を group とし、同じ ref の新しい手動実行が古い実行を cancel する。

最初の実行は dependency sync、GN generation、Metal shader generation、dylib build を含むため `timeout-minutes: 120` とする。CI 実績で各工程と総時間を得た後に、余裕を残した最短値へ短縮するかをレビューする。

第三者 Action は追加しない。GitHub 公式の [secure use reference](https://docs.github.com/en/actions/reference/security/secure-use) が immutable release のため full-length SHA pin を推奨するため、確認日 2026-09-20 に公式 release を照合して次へ固定した。

| Action | release | 完全 SHA | 公式 URL |
| --- | --- | --- | --- |
| `actions/checkout` | `v4.2.2` | `11bd71901bbe5b1630ceea73d27597364c9af683` | [release](https://github.com/actions/checkout/releases/tag/v4.2.2)、[commit](https://github.com/actions/checkout/tree/11bd71901bbe5b1630ceea73d27597364c9af683) |
| `actions/upload-artifact` | `v4.6.2` | `ea165f8d65b6e75b540449e92b4886f43607fa02` | [release](https://github.com/actions/upload-artifact/releases/tag/v4.6.2)、[commit](https://github.com/actions/upload-artifact/tree/ea165f8d65b6e75b540449e92b4886f43607fa02) |

`actions/checkout` は `persist-credentials: false` を指定する。checkout v4 の [README](https://github.com/actions/checkout/tree/11bd71901bbe5b1630ceea73d27597364c9af683#checkout-v4) は、既定で token を local git config に保存し、この input で opt-out できると説明する。

## checkout と 14 GB 制約

固定 ANGLE の公式手順は [`doc/DevSetup.md` 46–50 行](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/doc/DevSetup.md#46) の `fetch angle` である。本 workflow は同じ standalone 構成を、固定 SHA を先に検証できるように `scripts/bootstrap.py` と `gclient sync --no-history` で行う。`bootstrap.py` は `.gclient` を生成する実装である（[`scripts/bootstrap.py` 15–38 行](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/scripts/bootstrap.py#15)）。

`gclient` custom vars では、固定 [`DEPS`](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/DEPS#12) が列挙する OpenCL、Dawn、internal、Mesa、PartitionAlloc、restricted/extra trace の checkout を無効にする。workflow は `bootstrap.py` が生成した唯一の `solutions` entry を検証し、既存 `custom_vars` が dict であることを検証して複製してから、必要な7値だけを `update()` する。既存値を置換しないため、bootstrap が持つ値と矛盾しない。これは今回の Metal-only `libEGL` / `libGLESv2` に不要な依存を避ける設定であり、ANGLE source の改変ではない。`--no-history` は各 pin の内容を変えず履歴だけを省く。source、deps、成果物を後段へ残さず job 終了で runner を破棄するため、再現用情報は SHA、`args.gn`、toolchain 情報、hash を artifact に残す。checkout 後、GN 後、build 後に KiB 単位の使用量を CI log へ出す。

固定 `DEPS` の [`568–603 行`](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/DEPS#568) は standalone 用 `build` / `buildtools` pin と macOS GN CIPD package を定義する。これが Chromium 全体を checkout せず standalone build に必要な build 設定を同期する根拠である。

## 採用 GN args

workflow が artifact にそのまま保存する `out/Release/args.gn` は次である。

```gn
is_debug = false
is_component_build = false
target_cpu = "x64"
use_system_xcode = true
clang_use_chrome_plugins = false
mac_deployment_target = "13.0"
mac_min_system_version = "13.0"
angle_assert_always_on = false
angle_enable_metal = true
angle_enable_gl = false
angle_enable_vulkan = false
angle_enable_swiftshader = false
angle_enable_null = false
angle_enable_wgpu = false
angle_enable_cl = false
angle_build_tests = false
build_angle_deqp_tests = false
symbol_level = 0
```

### 根拠と分類

- **Chrome 154 と揃える必要がある入力:** `target_cpu = "x64"` は Intel Chrome 向けの必須出力条件であり、ANGLE の [`DevSetup.md` 79–83 行](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/doc/DevSetup.md#79) も x64 を選択肢および既定値として示す。Chrome/ANGLE の source pairing は DEPS で確認済みだが、実際の Google Chrome binary との ABI/load 成否は Phase 3 まで未確認である。
- **Release と診断範囲:** `is_debug = false`、`angle_assert_always_on = false`、`symbol_level = 0` は debug symbols、asserts、debug layers を増やさない。`DevSetup.md` 74–92 行は release と assertion setting を説明し、ANGLE [`gni/angle.gni` 178–180 行](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/gni/angle.gni#178) は debug layers が assertion / debug に依存すると定義する。固定 build dependency の [`config/compiler/compiler.gni` 153–161 行](https://chromium.googlesource.com/chromium/src/build/+/18940f0d92f236dd7b8672516700afa2b1f3d123/config/compiler/compiler.gni#153) は `symbol_level = 0` を「no symbols」と定義する。これは CI 容量と時間のための単体ビルド選択であり、Chrome ABI の確認ではない。
- **macOS toolchain:** `use_system_xcode = true` は runner の Xcode を使う明示指定である。固定 ANGLE [`build_overrides/build.gni` 9–29 行](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/build_overrides/build.gni#9) は macOS で system / hermetic Xcode を選択する処理を持つ。通常の Xcode clang は Chrome plugin を持たないため、`clang_use_chrome_plugins = false` は `DevSetup.md` 87–89 行の指示に従う。固定 `build` dependency の [`config/mac/mac_sdk.gni` 17–38 行](https://chromium.googlesource.com/chromium/src/build/+/18940f0d92f236dd7b8672516700afa2b1f3d123/config/mac/mac_sdk.gni#17) の既定値が deployment / minimum system version ともに `13.0` であるため、同値を明示する。macOS 15.7.9 はこの minimum 以上だが、Google Chrome 154 の実際の ABI との一致は出力検査と Phase 3 で確認する。
- **Metal only:** 固定 [`gni/angle.gni` 229–263 行](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/gni/angle.gni#229) は macOS で OpenGL、Vulkan、Null、Metal、WebGPU の既定を定義する。不要な OpenGL、Vulkan、SwiftShader、Null、WebGPU、OpenCL を明示的に無効化し、Metal のみを有効にする。SwiftShader は [`342–351 行`](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/gni/angle.gni#342) で Vulkan に依存するが、設定意図を artifact の args だけで判断できるよう明記した。テストと dEQP は [`gni/angle.gni` 40–48 行](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/gni/angle.gni#40) に対応する無効化である。
- **shader:** Metal backend は [`src/libANGLE/renderer/metal/BUILD.gn` 70–143 行](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/src/libANGLE/renderer/metal/BUILD.gn#70) で `.air`、`.metallib` を生成し `gDefaultMetallib` として header に埋め込む。従ってこの設定は外部 `.metallib` を artifact 必須ファイルとして仮定しない。実際の生成経路は CI build log / output で確認する。
- **RTTI、exceptions、libc++、visibility:** これらはこの workflow で推測して上書きしない。固定 build dependency の [`config/compiler/BUILD.gn` 71–75 行](https://chromium.googlesource.com/chromium/src/build/+/18940f0d92f236dd7b8672516700afa2b1f3d123/config/compiler/BUILD.gn#71) は RTTI を既定では off にする条件を定義する。ANGLE standalone の [`build_overrides/build.gni` 40–65 行](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/build_overrides/build.gni#40) は macOS で libc++ hardening の既定を定義する。`libEGL` の export visibility は [`BUILD.gn` 1611–1624 行](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/BUILD.gn#1611) にある。最終 dylib の C++ runtime / exported symbols / load ABI は CI の `otool` と Phase 3 の Chrome load で確認すべきであり、現時点では互換と断定しない。

## Ninja target と component 判断

実行 target は `ninja -C out/Release libEGL libGLESv2` である。固定 [`BUILD.gn` 1464–1509 行](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/BUILD.gn#1464) は `libGLESv2` shared-library target、[`1599–1645 行`](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/BUILD.gn#1599) は `libEGL` shared-library target と `libGLESv2` の data dependency を定義する。`angle` group は [`1896–1907 行`](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/BUILD.gn#1896) で `libGLESv1_CM` と Vulkan secondaries も含み得るため採用しない。

`is_component_build = false` を採用する。`DevSetup.md` 79–80 行は false が dependencies の static link を強制すると説明し、[`scripts/update_chrome_angle.py` 35–43 行](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/scripts/update_chrome_angle.py#35) は macOS の主要コピー対象を 2 dylib、component build 用の任意対象を `libc++_chrome.dylib`、`libchrome_zlib.dylib`、`libthird_party_abseil-cpp_absl.dylib`、`libvk_swiftshader.dylib` とする。これは単にファイル数を減らすためではなく、standalone non-component に特化する [`BUILD.gn` 1299–1312 行](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/BUILD.gn#1299) と整合する選択である。

この判断は build 実行前の設計である。`scripts/verify-artifact.sh` は `otool -L` の各非 system dylib を artifact 内で解決できることを必須とするため、追加 dylib が生じた場合は CI を失敗させる。CI 成功後にのみ、2 本だけで十分だったかを `otool` 結果から判断する。

## artifact、検証、成功判定

artifact は少なくとも次を含む。

- `libEGL.dylib`、`libGLESv2.dylib`、`ANGLE_REVISION`、`args.gn`、`build-environment.txt`
- `checksums.sha256`、`file-results.txt`、`lipo-results.txt`、`otool-results.txt`、`codesign-results.txt`
- ANGLE root の `LICENSE` と、同期済み source tree 内の `LICENSE*` / `NOTICE*` を相対パスで収集した `licenses/`

`scripts/verify-artifact.sh` は空白を含む artifact path を引用して扱い、主要2 dylib の存在を先に必須検査する。その後 artifact 直下の全 `*.dylib` を `LC_ALL=C` の stable order で列挙し、各 dylib に対して `file`、`lipo -info`、`otool -D`、`otool -L`、`otool -l`、`codesign -dvvv`、`codesign --verify --verbose=4`、`shasum -a 256` を実行する。追加 dylib も x86_64、install name、依存関係、CI path 混入、署名状態を同じ条件で検査し、全dylibを `checksums.sha256` に記録する。x86_64 が無い、install name が無い、system 外依存 dylib が artifact に無い、`otool` の load 情報に CI temporary/workspace path が含まれる場合は失敗する。

署名状態は「unsigned (Phase 2 では許容)」「signed and valid」「signed but invalid」を `codesign-results.txt` に区別して記録する。未署名は CI 生成物として想定内であり、Phase 3 の実験用 Chrome copy で別途扱う。署名あり・無効は、署名後の破損または期待しない変更を示し、再現可能な artifact として扱えないため fatal にする。codesign の診断出力に出る検査対象ファイルの絶対パスは埋め込み依存ではないため、CI path 検査対象にはしない。

成功判定は「固定 SHA が二度検証され、GN と Ninja が成功し、x86_64 を含む 2 dylib と付随情報が upload され、検証 script が成功すること」である。GitHub Actions 実行前の本 Phase 2A ではこの条件を満たしたとは扱わない。

## ローカル再現と Actions 実行

macOS Intel host で Xcode、Python 3、Git を用意し、workflow の `Get depot_tools` から `Assemble and verify artifact` までを同じ環境変数・同じ順で実行する。特に depot_tools を `PATH` に加え、ANGLEとdepot_toolsの両方の固定 SHA 検証を省略しない。ローカル再現は runner と SDK が異なる可能性があるため、`build-environment.txt` と `otool-results.txt` を CI artifact と比較する。

レビュー後の Phase 2B で GitHub Actions の **Actions → Build unmodified ANGLE for macOS x86_64 → Run workflow** を手動実行する。push、repository 作成、実行は本 Phase 2A では行わない。

## 既知の未確認事項と Phase 3 条件

- CI 実行後にしか、固定 SHA の fetch / dependency sync、Xcode Metal toolchain の可用性、GN / Ninja 成功、dylib の実 install name・依存・size・hash、追加 dylib の要否は確認できない。
- CI runner は Intel HD Graphics 5000 / OCLP / MacBookAir6,1 ではない。Metal initialisation、`requireGpuFamily2` override の実行時認識、Chrome 154 の実 load ABI、codesign / Library Validation、WebGL、KOOV は実機だけで確認できる。
- `requireMsl21` は固定コミットに存在を確認できていない。args、workflow、検証、文書のいずれも当該 Feature を前提にしない。

Phase 3 へ進む条件は、Phase 0 の基準ログ保全を完了し、Phase 2B の artifact が上記成功判定を満たし、レビューで `otool` の依存とライセンス収集結果を承認することである。Chrome.app への dylib 配置、再署名、起動はこの条件を満たすまで実施しない。
