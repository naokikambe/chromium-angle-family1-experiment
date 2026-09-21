# Phase 3A — dynamic ANGLE 実機試験の準備

更新日: 2026-09-20
状態: **準備完了、実機Chromeロード試験は未実施**

このPhaseはMacBookAir6,1（Intel HD Graphics 5000、macOS 15.7.9、OCLP）での安全な比較試験を準備するだけである。この文書と付属scriptはChrome、KOOV、既存プロファイル、`/Applications/Google Chrome.app`を変更または起動しない。Family 1用ANGLEの改修も含まない。

## 現行固定入力（Chrome 154.0.8037.45）

- Chrome: `154.0.8037.45`、Chromium: `731082f0a26ce4b3976c3d82943092f5d13daf13`
- ANGLE: `72b8f72a7587ec776d7d2a57d275a6e9b1781b1d`、depot_tools: `0306e4682b4ac35287c726fa35a983157a625902`
- Chromium tag [`154.0.8037.45`](https://chromium.googlesource.com/chromium/src/+/refs/tags/154.0.8037.45) の `chrome/VERSION` はこのChrome versionを示し、同commitの [`DEPS` 350–353行](https://chromium.googlesource.com/chromium/src/+/731082f0a26ce4b3976c3d82943092f5d13daf13/DEPS#350) は `angle_revision` を上記SHAへ固定する。
- workflowはこのpairを対象にする。artifact名は `angle-macos-x86_64-chrome-154.0.8037.45-angle-72b8f72a-<run-id>` とし、.17向けartifactとの混同を避ける。最新成功artifactとdylib SHA-256は後述する。

## `.45` workflow 初回実行（失敗、再実行しない）

手動run [`35514080466`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/35514080466) は、commit `60b1c4410ce06ecccd7b1e31c14f6efbfcdc05fa`で2026-09-20 13:38–13:43 UTCに`macos-15-intel` runnerへ割り当てられた。ANGLE SHAとdepot_tools SHA（`0306e4682b4ac35287c726fa35a983157a625902`）は`gclient sync`後に一致確認した。checkout時のdisk使用量は`8791452 KiB`だった。

GN生成stepは`python3_bin_reldir.txt not found. need to initialize depot_tools by running gclient, update_depot_tools or ensure_bootstrap.`で失敗した。このrunの`gclient sync`は完了しているが、固定したdepot_toolsでGNが要求する初期化が完了していなかった。Ninja、dylib作成、artifact検証、uploadはこのrunでは実行されず、artifact・新しいSHA-256は生成されなかった。固定depot_toolsを維持したまま一次ソースでGN前の必要手順を確認し、後述の最小修正を行った。

## 固定depot_tools bootstrap修正と成功run

固定depot_tools [`0306e4682b4ac35287c726fa35a983157a625902` の `ensure_bootstrap`](https://chromium.googlesource.com/chromium/tools/depot_tools/+/0306e4682b4ac35287c726fa35a983157a625902/ensure_bootstrap#15) は、現在のcheckoutでbootstrap programを準備し、`update_depot_tools`と異なりrepositoryをupdate/syncしないと明記する。同SHAの[`ensure_bootstrap` 45–64行](https://chromium.googlesource.com/chromium/tools/depot_tools/+/0306e4682b4ac35287c726fa35a983157a625902/ensure_bootstrap#45)は非Windowsで`bootstrap_python3`を呼び、CIPDと補助programを同期する。[`bootstrap_python3` 23–30行](https://chromium.googlesource.com/chromium/tools/depot_tools/+/0306e4682b4ac35287c726fa35a983157a625902/bootstrap_python3#23)はCIPD Pythonを準備して`bootstrap/bootstrap.py`を呼び、同[`bootstrap.py` 653–655行](https://chromium.googlesource.com/chromium/tools/depot_tools/+/0306e4682b4ac35287c726fa35a983157a625902/bootstrap/bootstrap.py#653)が`python3_bin_reldir.txt`を出力する。[`python-bin/python3` 14–31行](https://chromium.googlesource.com/chromium/tools/depot_tools/+/0306e4682b4ac35287c726fa35a983157a625902/python-bin/python3#14)はこのfileを読み、相対pathのPythonを実行する。

workflow commit `37737c8d508a860fdd7d011eba9b9158ca65149a`は、固定SHAのdetached checkout検証直後、`gclient`より前に公式`ensure_bootstrap` stepを追加した。`DEPOT_TOOLS_UPDATE=0`は維持し、`update_depot_tools`も手作業による`python3_bin_reldir.txt`生成も行わない。stepはbootstrap前後にGit HEADが期待SHAと一致すること、生成fileが非空で相対path配下の`python3`が実行可能であること、公式`python-bin/python3 --version`が成功することを検証する。artifactの`build-environment.txt`へ前後HEAD、相対path、bootstrap Python versionを記録する。

修正後の手動run [`35515036255`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/35515036255) はcommit `37737c8d508a860fdd7d011eba9b9158ca65149a`で成功した（job所要25分5秒）。`macos-15-intel` runnerはmacOS / X64、`x86_64`、4 CPU、Xcode 16.4、macOS SDK 15.5を記録した。bootstrap前後と`gclient sync`後のdepot_tools HEADはすべて`0306e4682b4ac35287c726fa35a983157a625902`で、生成relative pathは`bootstrap-2@3.11.8.chromium.35_bin/python3/bin`、bootstrap Pythonは3.11.8だった。ANGLE SHAも`gclient sync`後に期待値と一致した。

GN、Ninja（`libEGL libGLESv2`、1314 target）、artifact検証、uploadは成功した。disk使用量はcheckout後`8794000 KiB`、GN後`8808444 KiB`、build後`8854780 KiB`だった。artifact `angle-macos-x86_64-chrome-154.0.8037.45-angle-72b8f72a-35515036255` は`libEGL.dylib`、`libGLESv2.dylib`、revision、GN args、environment、検証report、root `LICENSE`と`licenses/LICENSE`を含む。2本だけがdylibで、両方thin x86_64 Mach-O shared library、未署名である。`libEGL.dylib`のSHA-256は`f4a8a7575183a41373404f7c25b4f56e1a1540c5b1578d11437c180b1f698db8`、`libGLESv2.dylib`は`8d3d188d3d4f23cf3f96ecea209b084c6db9c6192244f879cfb6bf0fb2e02cf0`である。

両dylibのinstall nameはそれぞれ`./libEGL.dylib`、`./libGLESv2.dylib`であり、`otool -L`先頭の同名項目は自己IDとして依存判定から除外した。残る依存は`/System/Library`または`/usr/lib`のみであり、非system依存、runner固有絶対path、未解決依存は検出されなかった。これはartifactの形式検証結果であり、未署名dylibをChromeが実機でloadできることを意味しない。Chrome app、xattr、署名、プロファイル、KOOVはこのrunおよびartifact検証で操作していない。

## Phase 3B のtest copyと署名境界（実機未実施）

`scripts/download-angle-artifact.sh`はrun `35515036255`のartifactだけを取得し、`libEGL.dylib`の`f4a8a7575183a41373404f7c25b4f56e1a1540c5b1578d11437c180b1f698db8`と`libGLESv2.dylib`の`8d3d188d3d4f23cf3f96ecea209b084c6db9c6192244f879cfb6bf0fb2e02cf0`を固定して検証する。artifactにはANGLE revision、build environment、GN args、2本のdylib、形式/署名/`otool` report、root `LICENSE`、`licenses/LICENSE`がある。dylibはthin x86_64 Mach-Oで未署名、自己install name以外の依存はsystem libraryだけである。

固定ANGLE [`update_chrome_angle.py` 35–43行](https://chromium.googlesource.com/angle/angle/+/72b8f72a7587ec776d7d2a57d275a6e9b1781b1d/scripts/update_chrome_angle.py#35)はmacOSのCanary Framework `Libraries`を対象に2本のdylibとcomponent build用optional dylibを定義し、[`114–118行`](https://chromium.googlesource.com/angle/angle/+/72b8f72a7587ec776d7d2a57d275a6e9b1781b1d/scripts/update_chrome_angle.py#114)で`xattr -cr`と`codesign --force --sign - --deep`を実行する。Phase 3Bのsign scriptは署名方式を変えず、この方式を**user-owned test copyだけ**に採用する。`--preserve-metadata`などは追加しない。Library Validationやentitlementsへの効果は推測せず、署名前後のdetails、CodeDirectory flags、TeamIdentifier、Authority、Runtime、entitlementsを保存して比較する。

`prepare-chrome-angle-test-copy.sh`はsource/outputを明示指定し、root、`/Applications`、symlink component、既存output、非所有parent、version/x86_64/SHA mismatchを拒否する。copyには`ditto --norsrc --noextattr --noacl --noqtn`を使い、resource fork/HFS metadata、extended attributes、ACL、quarantineを持ち込まない。これはtest-only copyであり、通常利用・配布を目的としない。copyのFinderInfo/ResourceFork不在、Info.plist・Resources・main/Framework/GPU Helperの必要componentと実行属性、strict signature検証成功を確認してから2本だけを配置する。sourceのmain executable、Framework、GPU Helperは前後で読み取り検証する。dylib配置によるcopyのGoogle署名無効化は記録するが、このscriptは再署名も起動も行わない。

prepareはapp外部にread-only manifest v2と別SHA-256 fileを作る。v2は`COPY_POLICY=norsrc,noextattr,noacl,noqtn`を追加し、v1の未署名copyと混同しない。実際のpolicyとsanitized command templateもevidenceへ記録する。manifestにはcanonical test/source app path、source Chrome version、Chromium/ANGLE revision、artifact名、2本のSHA、作成時刻、unsigned stageを記録する。これとdylib再hash、copy policy、およびLibraries内dylibが2本だけであることをsign/run/collectが検証する。所有者がmanifestとchecksumの両方を改変した場合を防ぐ秘密鍵はないため、これは完全な耐改ざん境界ではない。安全境界は`/Applications`、source、rootを拒否し、user-owned test copyだけを署名対象とすることにある。

`sign-chrome-angle-test-copy.sh`はprepared manifest、2本のhash、strict確認済みad-hoc signing receiptを必須にする。`--dry-run`は`xattr`/`codesign`を実行せず、実行には`--confirm-ad-hoc-signing`が必須である。実行時はGoogle Developer ID署名とnotarization状態を失うため、通常利用・通常Web閲覧・既存profileでの使用を禁止する。`run-dynamic-angle-test.sh`はad-hoc receipt、現在のstrict verification、`Signature=adhoc`、new `mktemp` profile、Case B/Cを確認する。Case Bにはoverrideを付けず、Case Cだけが`--disable-angle-features=requireGpuFamily2`を付ける。

`collect-phase3-evidence.sh`は署名前後のsignature/entitlement record、dylib hashと署名、GPU PID/command、`lsof`または`vmmap`を保存する。`--use-dynamic-angle`は要求の証拠に過ぎず、両dylibのtest copy内絶対pathが同一GPU processで確認できた場合だけ外部ANGLEロードを確認済みとする。KOOV、Family 1改修、Case B/C実機起動はさらに後であり、今回未実施である。

### Source metadata とclean copyのstrict gate

Phase 3B prepareの実機初回試行ではartifact検証まで成功したが、source main executableの`codesign --verify --strict`が`resource fork, Finder information, or similar detritus not allowed`でStage 1停止した。test copy、manifest、dylib、signing receiptは生成されていない。このsource-side failureは元Chromeにあるextended attributeの記録であり、元appのxattrは変更しない。

prepare scriptはsource app/main executable/Framework/GPU Helperごとに、strict verificationのstdout/stderr、exit status、`codesign -dvvv`、entitlements、read-only xattr一覧、実行ファイルSHA-256を保存する。strict failureはこの既知message**だけ**をwarningとしてStage 2へ進め、ほかの署名エラーはfatalである。`--ignore-resources`は使用せず、source strict結果を成功へ書き換えない。

retry1では`ditto --noextattr --noqtn`後にもapp root、Contents、Resources、各`.lproj`等にFinderInfoが残り、Stage 2で停止した。dylib、manifest、receiptは生成されていない。次のcopyは`ditto --norsrc --noextattr --noacl --noqtn`を使用する。`--norsrc`はresource forkとHFS metadataを除外し、併記した`--noextattr`、`--noacl`、`--noqtn`はextended attributes、ACL、quarantineを再有効化しない意図を明示する。

このpolicy後のcopyは、app全体の`--verify --deep --strict`、main executable、Framework、GPU Helperの各`--verify --strict`、Google Developer ID Authority、TeamIdentifier `EQHXZ8M8AV`、再帰xattr一覧のFinderInfo/ResourceFork不在を**すべて**満たすまでdylibを配置しない。source/copyの各主要componentは、pathを除いたAuthority/TeamIdentifier/CodeDirectory identityとSHA-256を比較して証拠化する。copy側のmetadata detritus又は署名failureは許容しない。

失敗したprepareのevidence、output、sidecarは削除・上書きしない。retry1も保持する。次の実機試行は`/Users/donkee/tmp/chromium-angle-phase3b-35515036255-retry2/Google Chrome 154 ANGLE Test.app`のような未使用のuser-owned pathを明示して行う。

artifact保存期限後にも再検証できるよう、利用者はGit管理外の保全先を作り、CI完了後に記録するrun IDと2本のSHA-256を指定して次を実行し、そのディレクトリとchecksumsを保管する。

```sh
scripts/download-angle-artifact.sh "$ARTIFACT_ARCHIVE_DIRECTORY"
```

このscriptはrepository内へのdownload、既存出力の上書き、Chrome/Chromium/ANGLE識別子またはSHAの不一致を拒否する。artifactの未署名dylibをChromeへ配置することは、署名・Library Validationを含む明示的なPhase 3B判断まで行わない。

## 履歴artifact（Chrome 154.0.8037.17、流用禁止）

run [`35501697418`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/35501697418) の `angle-macos-x86_64-35501697418` は、Chromium `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854` とANGLE `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448` 向けである。Phase 3AでGit管理外の一時領域へ取得し、`ANGLE_REVISION`、2本のSHA-256、`args.gn`、`build-environment.txt`、911個の第三者license/NOTICEを確認した。`libEGL.dylib`は`f4a8a7575183a41373404f7c25b4f56e1a1540c5b1578d11437c180b1f698db8`、`libGLESv2.dylib`は`2e0aadc21e76b0bb1adcfb3b908e757906995b75abb9e90edb3dfb5c1d1adef0`で、両方thin x86_64 Mach-O・未署名だった。**これはChrome 154.0.8037.45へ流用しない。**

## .45 固定ソース確認と .17との差分

- Chromium [`ui/gl/gl_switches.cc` 95–98、191–196行](https://chromium.googlesource.com/chromium/src/+/731082f0a26ce4b3976c3d82943092f5d13daf13/ui/gl/gl_switches.cc#95) は`USE_STATIC_ANGLE`で`--use-dynamic-angle`を定義し、GPU processへコピーするGL switch一覧に含める。[`gpu_process_host.cc` 1476–1485行](https://chromium.googlesource.com/chromium/src/+/731082f0a26ce4b3976c3d82943092f5d13daf13/content/browser/gpu/gpu_process_host.cc#1476) はこの一覧をbrowser command lineからGPU processへcopyする。
- 同commitの [`gl_initializer_mac.cc` 34–110行](https://chromium.googlesource.com/chromium/src/+/731082f0a26ce4b3976c3d82943092f5d13daf13/ui/gl/init/gl_initializer_mac.cc#34) はapp bundleのFramework `Libraries`から`libGLESv2.dylib`、続いて`libEGL.dylib`をloadし、static ANGLE buildで`--use-dynamic-angle`がある場合はstatic loaderを使わない。
- ANGLE [`mtl_features.json` 367–373行](https://chromium.googlesource.com/angle/angle/+/72b8f72a7587ec776d7d2a57d275a6e9b1781b1d/include/platform/mtl_features.json#367) と生成済み [`FeaturesMtl_autogen.h` 305–309行](https://chromium.googlesource.com/angle/angle/+/72b8f72a7587ec776d7d2a57d275a6e9b1781b1d/include/platform/autogen/FeaturesMtl_autogen.h#305) は`requireGpuFamily2`の定義とCLI名を示す。[`DisplayMtl.mm` 141–145行](https://chromium.googlesource.com/angle/angle/+/72b8f72a7587ec776d7d2a57d275a6e9b1781b1d/src/libANGLE/renderer/metal/DisplayMtl.mm#141) は有効かつMac GPU Family 2非対応時に初期化を停止し、[1209–1213行](https://chromium.googlesource.com/angle/angle/+/72b8f72a7587ec776d7d2a57d275a6e9b1781b1d/src/libANGLE/renderer/metal/DisplayMtl.mm#1209)でoverride適用後、[1314–1316行](https://chromium.googlesource.com/angle/angle/+/72b8f72a7587ec776d7d2a57d275a6e9b1781b1d/src/libANGLE/renderer/metal/DisplayMtl.mm#1314)で既定有効化を行う。
- [`Feature.h` 16–23、143–147行](https://chromium.googlesource.com/angle/angle/+/72b8f72a7587ec776d7d2a57d275a6e9b1781b1d/include/platform/Feature.h#16)の`ANGLE_FEATURE_CONDITION`は`hasOverride`がfalseの場合だけ既定値を設定する。[`renderer_utils.cpp` 72–76、1715–1721行](https://chromium.googlesource.com/angle/angle/+/72b8f72a7587ec776d7d2a57d275a6e9b1781b1d/src/libANGLE/renderer/renderer_utils.cpp#72)ではoverrideが`enabled`を設定して`hasOverride = true`にし、disabled一覧はfalseとして適用する。入力文字列が実機で認識されたこと自体は未確認である。
- `git diff`をChromiumの上記3ファイルとANGLEの上記5ファイルに限定して`.17`固定commitと`.45`固定commitを比較し、これらのdynamic loader、switch転送、`requireGpuFamily2`、override処理に差分がないことを確認した。対象外の変更が動作に無関係と断定するものではない。

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

Chromium固定commitの[`gl_initializer_mac.cc` 34–110行](https://chromium.googlesource.com/chromium/src/+/731082f0a26ce4b3976c3d82943092f5d13daf13/ui/gl/init/gl_initializer_mac.cc#34)は、app bundleで`FrameworkBundlePath().Append("Libraries")`から`libGLESv2.dylib`、`libEGL.dylib`を順にloadする。ANGLE固定commitの[`update_chrome_angle.py` 35–43行](https://chromium.googlesource.com/angle/angle/+/72b8f72a7587ec776d7d2a57d275a6e9b1781b1d/scripts/update_chrome_angle.py#35)も`Google Chrome Framework.framework/Libraries`をコピー先として示す。このためprepare scriptは**コピー後のテストappだけ**のFramework実体内`Libraries`を対象にする。元appと同一出力、`/Applications`配下への出力、既存appの暗黙上書き、再署名、SIP/Gatekeeper/AMFI/Library Validationの回避は拒否する。

`scripts/inspect-chrome-for-dynamic-angle.sh`は読み取り専用で、対象version、architecture、Framework実体、Libraries候補、app/main executable/Framework/GPU Helperの署名、TeamIdentifier、Hardened Runtime表示、entitlements、既存dylibを記録する。Hardened Runtimeと`com.apple.security.cs.disable-library-validation`の有無は、各対象の`codesign`詳細・entitlements出力を人間が確認する必要がある。未署名dylibの配置後に署名が無効なら、prepare scriptは再署名せず停止する。

## 実機実行順序（Phase 3B以降、今回実行しない）

1. `scripts/inspect-chrome-for-dynamic-angle.sh "$SOURCE_CHROME_APP"` を読み取り実行し、Chrome 154/x86_64と元appの署名を確認する。
2. `scripts/download-angle-artifact.sh "$ARTIFACT_DIRECTORY"` でartifactをGit管理外へ保全・再検証する。
3. `scripts/prepare-chrome-angle-test-copy.sh "$SOURCE_CHROME_APP" "$ARTIFACT_DIRECTORY" "$TEST_APP"` を実行し、結果を人間がレビューする。署名無効化が記録されたら、承認まで停止する。
4. 承認後に`sign-chrome-angle-test-copy.sh "$TEST_APP" "$SIGN_RESULTS" --dry-run`を確認し、さらに承認後に`--confirm-ad-hoc-signing`を明示して署名する。
5. 承認済みの有効なtest copyだけに対して、`scripts/run-dynamic-angle-test.sh CASE_B "$TEST_APP" "$RESULTS_DIRECTORY"` を実行する。Case Bに`--disable-angle-features`は付与しない。
6. `scripts/collect-phase3-evidence.sh "$TEST_APP" "$RESULTS_DIRECTORY"` と手動の`chrome://gpu`保存手順で結果を保全する。`lsof`、`vmmap`などで両dylibのtest copy内絶対pathが確認できるまで、外部ANGLEは未確認とする。
7. Case Bの直接ロード証拠が得られた後だけ、`CASE_C`を実行する。Case Cだけが`--disable-angle-features=requireGpuFamily2`を付与する。

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

実機の元Chrome app全体に対する`codesign --verify --deep --strict`は`com.apple.FinderInfo`属性のため失敗した。一方、main executable、Framework、GPU Helperの個別Google署名は有効だった。この差異は未解決事項として記録し、元appの`xattr`は変更しない。
