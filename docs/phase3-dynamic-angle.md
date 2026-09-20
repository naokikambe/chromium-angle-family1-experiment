# Phase 3A — dynamic ANGLE 実機試験の準備

更新日: 2026-09-20
状態: **準備完了、実機Chromeロード試験は未実施**

このPhaseはMacBookAir6,1（Intel HD Graphics 5000、macOS 15.7.9、OCLP）での安全な比較試験を準備するだけである。この文書と付属scriptはChrome、KOOV、既存プロファイル、`/Applications/Google Chrome.app`を変更または起動しない。Family 1用ANGLEの改修も含まない。

## 固定入力とartifact保全

- Chrome: `154.0.8037.17`、Chromium: `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854`
- ANGLE: `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`、depot_tools: `0306e4682b4ac35287c726fa35a983157a625902`
- 成功run: [`35501697418`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/35501697418)、artifact: `angle-macos-x86_64-35501697418`
- `libEGL.dylib`: `f4a8a7575183a41373404f7c25b4f56e1a1540c5b1578d11437c180b1f698db8`
- `libGLESv2.dylib`: `2e0aadc21e76b0bb1adcfb3b908e757906995b75abb9e90edb3dfb5c1d1adef0`

Phase 3AでartifactをGit管理外の一時領域に取得し、`ANGLE_REVISION`、2本のSHA-256、`args.gn`、`build-environment.txt`、911個の第三者license/NOTICEを確認した。両dylibはthin x86_64 Mach-O、install nameはそれぞれ`./libEGL.dylib`、`./libGLESv2.dylib`、署名は未署名である。artifact保存期限後にも再検証できるよう、利用者はGit管理外の保全先を作り、次を実行してそのディレクトリとchecksumsを保管する。

```sh
scripts/download-angle-artifact.sh "$ARTIFACT_ARCHIVE_DIRECTORY"
```

このscriptはrepository内へのdownload、既存出力の上書き、SHAまたはANGLE revisionの不一致を拒否する。artifactの未署名dylibをChromeへ配置することは、署名・Library Validationを含む明示的なPhase 3B判断まで行わない。

## 比較ケース

| Case | ANGLE | Feature override | 目的 | Phase 3Aの状態 |
| --- | --- | --- | --- | --- |
| A | Chrome内蔵 | なし | Chrome 154の既存失敗基準 | 実行準備のみ |
| B | 外部の標準ANGLE | なし | dynamic ANGLEのロード経路と標準挙動確認 | 実行準備のみ |
| C | 外部の標準ANGLE | `requireGpuFamily2`無効 | override伝達後の初期化段階確認 | 実行準備のみ |
| D | 外部のFamily 1実験版 | `requireGpuFamily2`無効 | Family 1でMetal/WebGLが初期化可能か確認 | 未実装・未実施 |
| E | Case D | 同上 | WebGLテスト | 未実装・未実施 |
| F | Case D | 同上 | KOOV試験 | 未実装・未実施 |

Case Bが実機で外部standard ANGLEの直接ロード証拠を得るまで、Family 1用コード改修へ進まない。Case Cは入力switchを渡すだけであり、ANGLE内部Feature名として認識されたこと、overrideが実際に適用されたことはPhase 4の診断ログまたは実機証拠なしに断定しない。`requireMsl21`は固定ANGLEで未確認のため、使用しない。

## 配置根拠と安全境界

Chromium固定commitの[`gl_initializer_mac.cc` 34–110行](https://chromium.googlesource.com/chromium/src/+/62d2fcb41a84e4dcefd8c4da7dfa534e6c482854/ui/gl/init/gl_initializer_mac.cc#34)は、app bundleで`FrameworkBundlePath().Append("Libraries")`から`libGLESv2.dylib`、`libEGL.dylib`を順にloadする。ANGLE固定commitの[`update_chrome_angle.py` 35–43行](https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/scripts/update_chrome_angle.py#35)も`Google Chrome Framework.framework/Libraries`をコピー先として示す。このためprepare scriptは**コピー後のテストappだけ**のFramework実体内`Libraries`を対象にする。元appと同一出力、`/Applications`配下への出力、既存appの暗黙上書き、再署名、SIP/Gatekeeper/AMFI/Library Validationの回避は拒否する。

`scripts/inspect-chrome-for-dynamic-angle.sh`は読み取り専用で、対象version、architecture、Framework実体、Libraries候補、app/main executable/Framework/GPU Helperの署名、TeamIdentifier、Hardened Runtime表示、entitlements、既存dylibを記録する。Hardened Runtimeと`com.apple.security.cs.disable-library-validation`の有無は、各対象の`codesign`詳細・entitlements出力を人間が確認する必要がある。未署名dylibの配置後に署名が無効なら、prepare scriptは再署名せず停止する。

## 実機実行順序（Phase 3B以降、今回実行しない）

1. `scripts/inspect-chrome-for-dynamic-angle.sh "$SOURCE_CHROME_APP"` を読み取り実行し、Chrome 154/x86_64と元appの署名を確認する。
2. `scripts/download-angle-artifact.sh "$ARTIFACT_DIRECTORY"` でartifactをGit管理外へ保全・再検証する。
3. `scripts/prepare-chrome-angle-test-copy.sh "$SOURCE_CHROME_APP" "$ARTIFACT_DIRECTORY"` を実行する。署名無効化が記録されたら、Phase 3Bの人間レビューで停止する。
4. 承認済みの有効なテストcopyだけに対して、`scripts/run-dynamic-angle-test.sh CASE_B "$TEST_APP" "$RESULTS_DIRECTORY"` を実行する。Case Bに`--disable-angle-features`は付与しない。
5. Case Bの直接ロード証拠が得られた後だけ、`CASE_C`を実行する。Case Cだけが`--disable-angle-features=requireGpuFamily2`を付与する。
6. `scripts/collect-phase3-evidence.sh "$TEST_APP" "$RESULTS_DIRECTORY"` と手動の`chrome://gpu`保存手順で結果を保全する。

run scriptは既存Chrome processを検出すると停止し、`open -a`を使わずtest appのexecutableだけを起動する。各runは新規`mktemp`の`--user-data-dir`を使い、既存profileを指定・削除・利用しない。結果は`local-results/`など`.gitignore`対象に置き、profileは自動削除しない。

ローカル専用の保全構造は次を想定する。これらはGitへ追加しない。

```text
local-results/
  phase0/
    chrome149-success/
    chrome154-failure/
  phase3/
    case-b-dynamic-stock/
    case-c-dynamic-stock-family1-override/
```

## ロード判定と未確認事項

`--use-dynamic-angle`がcommand lineやGPU process command lineに現れるだけでは外部ANGLEロードの証拠にならない。`collect-phase3-evidence.sh`はGPU processが存続する場合、`lsof`または`vmmap`でtest bundle内の`libEGL.dylib`と`libGLESv2.dylib`の**絶対パスの両方**を確認したときだけ`load-evidence.txt`に直接ロード証拠として記録する。短時間終了、権限不足、またはpath未検出なら「未確認」であり成功と推測しない。信頼できるdyld load記録も同等の証拠として扱える。

実機でのみ未確認なのは、Chrome 154がこのtest copyを起動・loadできるか、未署名dylibに対する署名・Library Validation、GPU processの存続、Metal/EGL初期化、`requireGpuFamily2`入力認識、WebGL/Compositing/Rasterization、GPU crash count、KOOV動作である。Chrome本体、KOOV、実機profileを変更・起動する前に、これらの境界と結果公開時の秘匿情報を人間がレビューする。
