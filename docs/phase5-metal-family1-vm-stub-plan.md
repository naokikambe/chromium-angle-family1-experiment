# Phase 5: Metal Family 1 capability stub (VM-first)

作成日: 2026-09-26
更新日: 2026-09-29

状態: 設計確認済み・admission record確認済み・実装済み・runtime artifact CI/Phase 3D VM検証成功・WebGL/実機未実施

## 結論

GitHub Actions の macOS Intel VMで、Intel HD Graphics 5000そのものを再現することはできない。しかし、ANGLE Metal backendの初期化判断をFamily 1相当の能力プロファイルで再現し、初期化のどの段階で停止するかを検証することは可能である。

実装はAppleの`MTLDevice`をVM上で偽装するのではなく、ANGLE内部の能力問い合わせと初期化結果に、テスト専用の注入境界を設ける。通常のMetal実装経路は既定値として変更しない。

## Phase 5開始条件と一次記録

実装またはCI実行を開始する前に、次の入場記録を埋める。値が未確定の項目は推測で補わず、成功runと保存済みartifactを確認してから記録する。親エージェントによる読み取り専用のdiagnostics artifact検証により、以下の記録は完了した。

| 項目 | 記録する値 |
| --- | --- |
| Phase 3B synthetic fixture 成功run | `36241793357` / success / commit `3b116228de6c2af80b14cdfb36ff6fec1af6db38` / diagnostics `phase3b-synthetic-fixture-diagnostics-36241793357` / archive SHA-256 `2299e7085280d7ef80bec61f4f4a0d3de26cef8a1e7680eb3f633b4e4646ccab` / `fixture-exit-status.txt=0`, `phase3b-fixture-exit-status.txt=0`, `release-artifact-exit-status.txt=0` |
| Phase 3C synthetic preflight fixture 成功run | `36241795968` / success / commit `3b116228de6c2af80b14cdfb36ff6fec1af6db38` / diagnostics `phase3c-preflight-synthetic-diagnostics-36241795968` / archive SHA-256 `d33c4e301f023ce9870e2a8faba139fb9415c5109aca9584d080ad661ac9ec03` / exit status `0` |
| Phase 3D VM観測 成功run | `36071196477` / success / commit `e9002f5ba7f70ec6b23f6b82453c9580a33a399b` / diagnostics `phase3d-dynamic-angle-36065655290-36071196477` / archive SHA-256 `8f142e7503555fe3d9a75f0716daf8777509b28089e17b1bb4a8cfef7aabe298` |
| release manifest | schema `angle-release-v1` / Chrome `154.0.8037.57` / manifest SHA-256 `ed01fc7c8a1634193cebc7e016be2fddd4a1d0094e7a77abdc98798d6b078c4f` / sidecar validation success |
| 選択したANGLE artifact | `angle-macos-x86_64-chrome-154.0.8037.57-angle-1ff8799c-36065655290` / build run `36065655290` |
| ANGLE revision | `1ff8799c596d4fc9acea28343610b1f33650a6fa` |

選択したartifactのdylib SHA-256は、`libEGL.dylib`が`f4a8a7575183a41373404f7c25b4f56e1a1540c5b1578d11437c180b1f698db8`、`libGLESv2.dylib`が`9506dcc5ac798befddbab3a9e76a3ce21117d4ef1a8457ed0fcf064dbbbd6dd7`である。

`phase-status.md`と`phase3d-vm-observability.md`の記述が一致しない場合、GitHub Actionsの実runと保存artifactを一次情報として照合し、Phase 5実行前に両文書を同じ状態へ更新する。run ID、manifest digest、artifact名、revisionを未確認のまま固定値として書かない。

このadmission recordはPhase 5のソース実装を開始するために完了した。後続のCI dispatchとartifact検証はHuman承認後に実施済みだが、実機の署名・配置・Chrome起動・実機操作を許可する記録ではない。

## Phase 5専用CI一次記録（2026-09-29確認）

固定revisionに対するtest-only stubの実装と専用workflowの検証は、次の成功runで完了した。これはstub buildとtargeted EGL testの証跡であり、Chrome/GPUログを伴うVM観測や実機試験の記録ではない。

| 項目 | 記録 |
| --- | --- |
| workflow / run | `phase5-metal-family1.yml` / [`36432392861`](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/36432392861) / success |
| commit | `0784dc1731e6709282260a9a8fda25df2fc0194f` |
| artifact | `angle-metal-family1-test-stub-36432392861` / schema `phase5-metal-family1-test-stub-v1` |
| ANGLE revision | `1ff8799c596d4fc9acea28343610b1f33650a6fa` |
| patch SHA-256 | `00a11d2289b306de4642cde3711cba051667b38fd5d97f46a434ba7f24ac5258` |
| manifest SHA-256 | `c99b82bcd19cb564aa8f0aae7c2e0ecd8c18342de168c2d47e5a00b342f2b638` |
| artifact-files SHA-256 | `17b5ee8a79978f01255c13ffb3fb4f2ee01a89e1303d5faa5a681b5886916d0f` |
| test result | exit `0` / `DisplayMtlFamily1Test.*` 4 tests passed |

このrunにより、test-only stub CIとして実機へ進む条件の1〜5は証跡上満たした。条件4（stub無効時のproduction path不変）はcompile-time分離と静的監査で確認している。ただし、このartifactは診断用であり、通常artifactまたは実機用runtime artifactを実機で起動したことを意味しない。

## 実機移行前のCI先行方針

Phase 5の次段階は、実機試験へ直行せず、CIで実機用runtime境界を先に検証する。既存の`phase5-metal-family1-test-stub-v1` artifactは、`DisplayMtlFamily1Test.*`の診断結果だけを保持するtest-only artifactであり、Chromeへ配置する`libEGL.dylib`／`libGLESv2.dylib`や、ChromeからFamily 1プロファイルを選択するruntime経路を提供しない。これを実機用artifactとして再利用しない。

次のCI作業をこの順序で行う。

1. 現行stubとは分離した、明示的opt-inの実機用runtime patchを設計する。既定のproduction path、Family 2以上の挙動、通常artifactを変更せず、Chromeの通常起動から暗黙に選択できない境界を維持する。
2. 固定ANGLE revision `1ff8799c596d4fc9acea28343610b1f33650a6fa`からx86_64の`libEGL.dylib`／`libGLESv2.dylib`を生成する専用CI workflowを追加する。artifact名・manifest schemaはtest-only stubと分離し、patch SHA-256、source revision、dylib SHA-256、GN argsを束縛する。schemaは実装時に確定し、`angle-release-v1`を使う場合もpatch provenanceを失わせない。
3. runtime patchのstatic audit、targeted EGL test、production pathのstub無効監査、artifact manifest検証をCIで実行する。
4. 検証済みruntime artifactをPhase 3DのmacOS Intel VMへ渡し、動的ANGLEロード、GPU processの引数、EGL初期化境界、GPU fallbackを観測する。これはrun `36507728136`で完了した。VMはApple Paravirtualized Graphics Deviceであり、Intel HD Graphics 5000の実機結果とは扱わない。
5. 必要性と入力ページを別途固定したうえで、VM上のWebGL smoke観測を追加する。KOOV、USB、Bluetooth、ユーザーprofileはCI範囲に含めない。

runtime artifact CIとPhase 3D VM観測は完了したが、WebGL smokeと実機試験は未完了である。この順序の残作業を完了した後に限り、実機用artifactのtest copy作成・署名・Chrome起動を別途承認する。CI workflowのdispatchとartifact downloadは今回承認済み範囲で実施したが、署名、xattr、profile操作、実機Chrome起動、KOOV操作は行わない。

### CI先行段階の完了条件

- 実機用runtime patchがtest-only stubと明確に分離され、既定OFFである。
- 固定revision、patch hash、artifact manifest、2本のdylib hashが同一のCI記録に束縛されている。
- targeted test、static audit、artifact validationが成功し、required testのskipがない。
- Phase 3D VMで、少なくとも動的ロードの成否とGPU processのEGL初期化結果を直接記録できる。run `36507728136`で両replacement dylibのGPU-correlated dyld load、EGL初期化失敗、GPU disabled fallbackを記録した。
- VM成功を実機成功と解釈せず、未観測の実機リスクを記録する。

## GitHub Actions workflow実装（45分timeout回避）

実機用runtime patchをCIで検証するworkflowを、現在の専用stub workflowと分離したreusable workflowとして実装した。既存stub artifactや成功記録は変更しない。workflowは明示的なruntime opt-in入力からのみ呼び出し、実機用artifactの生成後も`RUNTIME_DEVICE_READY=false`を維持する。

GitHub Actionsのstep/job timeoutはworkflowで個別に設定でき、公式仕様上の上限はGitHub-hosted runnerでは360分である。ただし、単純にtimeoutを延長して失敗検出を遅らせるのではなく、現在の45分step制限を各build段階の安全予算として維持する。[Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)

### 基本設計

- `gn gen`、source audit、build、test、artifact検証を別stepに分ける。
- 同じ`out/Phase5`を1つのbuild job内で順次再利用し、共有GN/Ninja treeに対する並列Ninja実行は行わない。
- `libEGL.dylib`／`libGLESv2.dylib`とtargeted test binaryだけを対象にし、`angle_end2end_tests`やfull DEQPを起動しない。
- 45分を超える単一Ninja stepを作らない。初回CIで`libEGL`が25分では完了せず`1211/1314`まで進んでtimeoutしたため、同stepを40分へ拡張し、`libGLESv2`は25分、job全体は120分に制限する。各長時間stepに明示的な`timeout-minutes`とstage markerを置く。
- 失敗時は`if: always()`でstage log、GN args、source state、Ninja diagnostics、exit statusを保存する。自動retryは行わず、失敗分類後に新しいrunを開始する。
- `out/`全体をjob間artifactとして転送しない。job間では最終dylib、manifest、検証結果、diagnosticsだけをartifactにする。GitHubのartifactはjob間の生成物受け渡し、cacheは再生成コストの高い依存物の再利用に使い分ける。[Artifacts and dependency caching](https://docs.github.com/en/actions/concepts/workflows-and-actions/dependency-caching)

### 提案するjob構成

```text
phase5-runtime-build  (macos-15-intel, job timeout 120分)
 ├─ static workflow/patch audit                  (5分)
 ├─ exact source checkout / dependency bootstrap (20分)
 ├─ patch apply / source-state record            (5分)
 ├─ GN configuration and graph preflight         (5分)
 ├─ common objects and runtime library build     (最大35分)
 ├─ separate libEGL/libGLESv2 link checks        (各10分以内)
 ├─ targeted Phase 5 test build/run               (最大15分)
 ├─ nm/manifest/hash/artifact validation          (5分)
 └─ final dylib + diagnostics upload

phase5-runtime-vm-observe (separate workflow, job timeout 30分)
 ├─ download and verify final runtime artifact
 ├─ Phase 3D dynamic ANGLE observation
 └─ GPU/EGL/fallback diagnostics upload
```

`phase5-runtime-build`は、runtime artifactへtest-only bridgeやtest-only exportが混入していないことを`gn desc`、target topology、`nm`、artifact file listで検証する。runtime patchとtargeted testが異なるGN条件を必要とする場合は、同一artifactへ混在させず、source revision・patch hashを共有する別build modeとして明示する。runtime artifact buildは同一jobのincremental treeで測定した。初回run `36497660658`ではpatch適用・GN監査まで成功した後、`libEGL` stepが25分timeoutしたが、40分step予算へ修正したrun `36501314503`で全build・監査・artifact uploadが成功した。

依存物のcacheは、source revision、patch SHA-256、GN args SHA-256、runner OSを含む厳密なkeyでのみ再利用する。cache missでも必ず再生成できることを完了条件とし、未検証の`out/` partial cacheを正しいbuildの代替にしない。cacheが効かない初回runでも、各stepのtimeout予算を超えない構成にする。

Phase 3D VM観測はbuild jobから分離し、検証済みruntime artifactのrun IDを入力にする。buildの再実行とVM観測を同じjobへ詰め込まない。これにより、VM側のChrome起動・GPU観測の失敗がANGLE build timeoutの原因と混ざらず、artifactを固定した再観測が可能になる。

この設計の受入条件は、cache hitを前提にせず、各長時間stepが予算内で完了し、job全体が120分以内に終わり、最終artifactのmanifest・patch provenance・dylib hash・diagnosticsが相互に一致することである。run `36501314503`は37分37秒で完了し、`libEGL`（約25分超を含む）と`libGLESv2`、artifact validation、diagnostics uploadが成功した。続くrun `36507728136`は固定artifactのVM観測に成功し、runtime artifact段階とPhase 3D観測段階のCI受入条件を満たした。ただし`RUNTIME_DEVICE_READY=false`であり、WebGL smokeと実機操作は未実施である。

### runtime artifact CIの失敗記録

初回runtime dispatch `36496266565`は、workflowへ接続する前の旧patchが`git apply`で壊れた形式だったため、patch適用段階で失敗した。patchを正規化してSHA-256を`07d7e80d8ce1099cb3d9d3ad5654eabd39b3d33776932ad28e3d76deaf6d4070`へ更新し、commit `6059faf`で修正した。再run `36497660658`は同patchの適用、固定ANGLE source、GN生成、target graph監査まで成功したが、初回依存・未cacheの`ninja libEGL`が25分でtimeoutした。diagnostics artifact `phase5-metal-family1-runtime-diagnostics-36497660658`のbuild logは`1211/1314`まで進んでおり、コンパイルエラーは記録されていない。この結果を受け、libEGL stepのtimeoutを40分へ変更し、別runで再検証する。

修正版run `36501314503`（commit `b7cd00c`）では、`libEGL`が`00:16:58Z`から`00:41:46Z`まで実行して成功し、従来の25分境界を越えて完了した。`libGLESv2`は続けて成功し、runtime artifactとdiagnosticsをuploadした。取得後の`verify-artifact.sh`、`verify-phase5-runtime-artifact.sh`、manifest/sidecar、artifact-files SHA検証も成功した。artifactにはtest-only stub markerがなく、`RUNTIME_DEVICE_READY=false`、x86_64 Mach-O、未署名であることを確認した。runtime artifactはCIで検証済みだが、実機で使用可能とする署名・配置・Chrome起動の承認を意味しない。

Phase 3D run `36507728136`では、同runtime artifactを一時展開したChrome for Testingへ配置し、dynamic probeとstock controlを実行した。dynamic側は両dylibのGPU-correlated dyld loadを確認したが、EGL初期化失敗後にGPU disabled fallbackへ移行した。stock controlはEGL初期化失敗を示さず、両ケースの差分は`CONTROL_INTERPRETATION=dynamic-angle-differs-from-stock-control`として保存された。replacement-library-post-runのSHAはartifactと一致し、runner上の一時bundle以外は変更していない。これはロード経路と失敗境界の証拠であり、WebGL描画成功、実機互換性、KOOV動作の証拠ではない。

## ソースコードによる裏取り

Chrome 154のrelease manifestで固定したANGLE revisionを最終対象とする。現時点で確認したANGLEの`DisplayMtl.mm`では、Metal初期化は次の順序で構成されている。

1. `MTLCopyAllDevices()`または`MTLCreateSystemDefaultDevice()`でデバイスを取得
2. GPU family、MSL version、vendorに関するfeature gateを判定
3. `newCommandQueue`でcommand queueを作成
4. format tableを初期化
5. 内部shader libraryを初期化
6. RenderUtilsを初期化

`initializeImpl()`が`angle::Result::Stop`を返すと、上位の`initialize()`は`EglNotInitialized()`へ変換する。このため、初期化ステージごとの成功・失敗を注入すれば、実機なしで失敗境界を分離できる。

確認した公式ソース:

- [ANGLE DisplayMtl.mm, revision 97a4891213554c6ae278ee621a75736df4939529](https://chromium.googlesource.com/angle/angle/+/97a4891213554c6ae278ee621a75736df4939529/src/libANGLE/renderer/metal/DisplayMtl.mm)
- [ANGLE DisplayMtl.mm, revision d33a22228ee2999ab5e2d2eda4d405c5768555d2](https://chromium.googlesource.com/angle/angle/+/d33a22228ee2999ab5e2d2eda4d405c5768555d2/src/libANGLE/renderer/metal/DisplayMtl.mm)

上記は構造確認用の一次ソースである。最終選択したrelease manifestの`ANGLE_REVISION`は`1ff8799c596d4fc9acea28343610b1f33650a6fa`であり、manifest sidecarの検証成功とともにadmission recordへ記録した。別revisionの差分を黙って混在させない。

## VMで検証するプロファイル

最初のプロファイルは、Intel HD Graphics 5000を完全再現するものではなく、次の能力を明示する。

| 能力 | Family 1プロファイル |
| --- | --- |
| Metal device存在 | あり |
| Mac GPU family 1 | あり |
| Mac GPU family 2 | なし |
| vendor | Intel |
| command queue | 成功／失敗を切替可能 |
| format table | 成功／失敗を切替可能 |
| shader library | 成功／失敗を切替可能 |
| RenderUtils | 成功／失敗を切替可能 |

これにより、単に`requireGpuFamily2`を解除した場合と、その後のMetal初期化が進む場合を分離できる。

MSL 2.1は初期プロファイルの対象外とする。固定対象revisionの`initializeImpl()`に実際のMSL 2.1分岐があることをソース監査で確認できた場合に限り、分岐、期待結果、テストケースを明示して別途追加する。分岐がなければ、MSL 2.1に関する能力・期待値を追加しない。

## 注入境界と安全制約

注入はコンパイル時に閉じたtest-only設定に限定する。通常のANGLE buildではstubコードとstubプロファイルを無効化し、Chromeのコマンドライン引数や環境変数から実行時に選択できない構成にする。通常artifactにはstubプロファイルを含めず、stub有効artifactは専用名と専用manifest schemaで通常artifactから分離する。stubプロファイルの選択はPhase 5 CIのテスト構成でのみ許可し、通常Chromeの起動経路へ到達できないことを静的監査する。

実Metalデバイス全体の偽装、Metal frameworkの置換、DYLDによる実行時注入は行わない。実機操作、署名、Chrome起動、artifact取得・置換、xattr、profile操作、GitHub Actionsのworkflow dispatchは承認境界に置き、Phase 5のプラン実装では実行しない。

## 実装方針

### 5A: 能力問い合わせの抽象化

`DisplayMtl`から、次の問い合わせを小さな内部インターフェースまたはテスト用プロファイルへ切り出す。

- `supportsMacGPUFamily()` / `supportsEitherGPUFamily()`
- `supportsMetal2_1()`などのMSL能力
- vendor判定
- command queue、format table、shader library、RenderUtilsの初期化結果

本番経路では`newCommandQueue`直後にnil guardを置き、nilなら明示的に初期化失敗として後続のformat table初期化へ進まない。これはnil queueという異常状態を明示的に扱う、範囲を限定した安全性の挙動変更である。stubは通常buildでは無効であり、このguard以外の通常経路を変更しない。テスト経路ではqueue作成結果を制御し、queue段階で停止するケースを注入する。stub無効時は、既存の実Metalデバイスに対する成功・失敗挙動が変わらないことを確認する。本番ビルドは従来どおり実`MTLDevice`へ委譲し、テストビルドだけがコンパイル時にFamily 1プロファイルを選択できるようにする。

### 停止段階の診断

test-onlyの内部診断に、次の停止段階を一度だけ記録する。

`device` → `feature-gate` → `command-queue` → `format-table` → `shader-library` → `render-utils` → `success`

各ケースでは、指定段階で停止したこと、後続段階が実行されていないこと、`initialize()`の戻り値が`EGL_NOT_INITIALIZED`であることをassertする。全段階成功ケースではstageが`success`であることをassertする。この記録は公開APIにせず、通常artifactや通常実行時のログへ露出させない。

### 5B: ANGLE単体テスト

少なくとも次を確認する。

- deviceなし → `EglNotInitialized`
- Family 2必須 + Family 1プロファイル → feature gateで停止
- Family 2要件解除 + queue失敗 → queue段階で停止
- queue成功 + format table失敗 → format段階で停止
- shader library失敗 → shader段階で停止
- RenderUtils失敗 → 最終初期化段階で停止
- 全段階成功 → `initialize()`成功
- Family 1で公開されるcapabilityがプロファイルと一致

固定revision `1ff8799c596d4fc9acea28343610b1f33650a6fa`のソース監査を完了した。以下はFamily 1プロファイルのテストoracleであり、実機の完全再現値ではない。

| 確認対象 | 固定する期待値・確認箇所 |
| --- | --- |
| 対象API | EGL初期化、GLES capability生成、Metal renderer capability |
| 最大GLES version | `getMaxSupportedESVersion()`は`mtl::kMaxSupportedGLVersion`を返し、固定revisionの定義ではGLES 3.0。Family 1は`supportsEitherGPUFamily(4, 1)`を満たす。 |
| EGL config | `generateConfigs()`はconformant/renderableな`EGL_OPENGL_ES2_BIT`および`EGL_OPENGL_ES3_BIT_KHR`、`EGL_WINDOW_BIT \| EGL_PBUFFER_BIT`、sample count 0/4の2 variantと、監査済みのdepth/stencil組合せを生成する。 |
| EGL display extensions | `generateExtensions()`が直接設定する次のEGL display extension fieldsを要求する：`createContextRobustness`、`iosurfaceClientBuffer`、`surfacelessContext`、`noConfigContext`、`displayTextureShareGroup`、`displaySemaphoreShareGroup`、`mtlTextureClientBuffer`、`waitUntilWorkScheduled`、`fenceSync`、`waitSync`、`robustResourceInitializationANGLE`、`image`、`imageBase`、`metalCreateContextOwnershipIdentityANGLE`、`mtlSyncSharedEventANGLE`、`mtlSyncCommandsScheduledANGLE`。Intel/non-NVIDIA profileでは`hasEvents`が有効なため、`fenceSync`/`waitSync`を必須とする。これはnative GL extension全体との同値性を主張しない。 |
| Family 1で無効なcapability | Apple GPU familyを持たないプロファイルでは、ソース条件上`compressedTextureEtcANGLE`、`textureCompressionAstcSliced3dKHR`、`textureCompressionAstcHdrKHR`、`multisampledRenderToTextureEXT`はfalse（capability生成まで到達するテストで確認）。 |
| native caps | `supportsEitherGPUFamily(2, 1)`を満たすため`maxDrawBuffers`と`maxColorAttachments`は`mtl::kMaxRenderTargets`（8）。max color target bitsはMac/catalyst値とするが、数値はここでは推測しない。 |
| vendor | Intelは`isIntel`専用workaroundを適用し、NVIDIA拒否分岐には入らない。これはプロファイル述語であり、デバイスのエミュレーションではない。 |

テストでは`getMaxSupportedESVersion()`、`generateConfigs()`、`generateExtensions()`およびMetal renderer capabilityの結果を、上表の監査済み値と比較する。Apple GPU familyはどれも設定しない。vendor値だけを根拠にIntel実機との同一性を主張しない。

既存の`EGLFeatureControlTest`はend-to-endのfeature overrideテストであり、新しいcompile-time-only profileの証明には使わない。初期案では`src/tests/angle_unittests.gni`の`angle_unittests_msl_sources`へMetal専用sourceを追加して`angle_unittests`で実行する方針だった。しかしCI run `36278046375`および`36280291932`で、パッチのコンパイル・リンクには成功した一方、static unit-test binaryでは`eglGetPlatformDisplay()`が`EGL_NO_DISPLAY`を返し、初期化stageへ到達できないことを確認した。さらにfull `angle_end2end_tests`はCI run `36290795681`で1621/1646 objectのコンパイル後に固定45分timeoutへ到達した。これはstub profileの失敗ではなく、runnerまたはtarget規模の問題である。したがって専用sourceは、`$angle_root:libEGL`と`$angle_root:libGLESv2`へ直接linkし、同じ2つのruntime dylibだけを`data_deps`で提供する専用target `angle_metal_family1_test_stub`へ、同じ`angle_enable_metal_family1_test_stub` compile-time条件下で追加し、`angle_metal_family1_test_stub --gtest_filter=DisplayMtlFamily1Test.*`だけを実行する。通常build・公開API・runtime選択経路は変更しない。

### 5C: Phase 3Dへの接続

GitHub VMでは、実MetalデバイスをFamily 1へ変えるのではなく、次を実行する。

- stub-enabled ANGLEのビルド
- stubプロファイルを選択したテスト実行
- 初期化ステージ、feature値、戻り値、ログをartifact化
- 既存の動的ANGLEロード観測とは別に、ソフトウェア境界の結果として記録

Phase 3Dへ曖昧に接続せず、Phase 5専用workflow（`.github/workflows/phase5-metal-family1.yml`）を定義する。形状は次のとおりとする。

```text
macos-15-intel
 ├─ source/static audit
 ├─ ANGLE stub build
 ├─ ANGLE targeted EGL tests
 ├─ optional VM observation
 └─ diagnostics upload
```

runnerは`macos-15-intel`に固定する。初回の専用workflowはjob timeoutを60分、ANGLE build/test step timeoutを45分に固定する。stub-enabled artifactと通常artifactを分離し、専用artifactのmanifest schemaは`phase5-metal-family1-test-stub-v1`、名前は`angle-metal-family1-test-stub-<run-id>`とする。stage診断、test result、compiler/build metadata、GN args／manifest／artifactのSHA-256を保存する。初回workflowはstub buildとtargeted EGL testだけを対象とし、VM観測（Chrome/GPUログを含む）は人の承認を得た後に別段階として追加する。workflow dispatch、CI artifact取得、実機操作は従来どおり別途承認が必要であり、このプランの文書修正だけでは実行許可を与えない。

CIのGN生成で、試行した`angle_end2end_tests.gni`経路ではcompile-time-onlyの`angle_enable_metal_family1_test_stub`の可視性に明示的importが必要なことを確認した。この経路は45分timeoutのため廃止し、専用targetは既に`gni/angle.gni`をimportする`src/tests/BUILD.gn`内で条件付ける。通常buildのruntime選択経路は追加しない。

専用targetのfocused build（CI run `36295094316`）は1411 objectsまで進み、共有loaderが`EGL_EGL_PROTOTYPES=0`を伝播するため、EGL関数prototypeが未宣言になることを確認した。専用targetは`$angle_root:libEGL`へ直接linkするため、test source内でEGL header include前に`EGL_EGL_PROTOTYPES`を1へ復元する。これはcompile-timeの宣言修正であり、runtime選択経路や公開APIを追加しない。

CI run `36297447447`では1411 objectsのcompile後に、`libEGL`が内部C++ symbols（stub制御、native caps、EGL display extensions）をexportしないためlinkに失敗した。このため、stub build時の`libEGL`にだけ、必要なstage制御とcapability snapshotを返すtest-only C ABI bridgeをdefault visibilityで追加し、test sourceは通常のEGL C APIとbridgeだけを呼ぶ。bridgeは通常build・通常artifact・公開headerには含めず、runtime CLI/environment選択も提供しない。

固定revisionの`gl::Version`には`major`/`minor` public fieldがなく、`getMajor()`/`getMinor()` accessorを使う必要があることをCI run `36302295123`のbridge compileで確認した。bridge snapshotはこの固定revision APIに合わせる。

CI run `36304800477`では、`DisplayMtlFamily1Test.mm`の匿名namespace閉じ括弧が重複してbuildが停止し、testは実行されなかった。patchではglobal `TEST`宣言前のnamespace閉じ括弧を1つだけ残すよう対象行を修正し、静的監査でこの構造を確認する。新規source fileのhunkから1行を削除するため、hunk行数も`+1,119`から`+1,118`へ更新する。これを更新しないpatchは`git apply`でcorruptと判定されるため、固定revisionに対する`git apply --check`をcommit前検証に含める。

CI run `36314480823`ではbridgeのC ABI symbolsが未定義のままlinkに失敗し、testは実行されなかった。続くrun `36319692884`で、bridge sourceをtest executableへ直接compileすると`rx::DisplayMtl`などlibEGL内部symbolsがhiddenで解決できないことが確認された。Bridge sourceは`angle_metal_backend`（libEGL）へ戻し、backend target-local defineで`DisplayMtl`実装とC ABI definitionsを同時にcompileする。専用test targetはBridge headerだけを参照し、通常buildでは引き続き無効である。固定revisionへのpatchは`git apply --unidiff-zero --check`で適用可能であることを確認する。

専用targetの本build前に、workflowは`gn desc`でstub targetがBridge `.mm`をcompileせずheaderだけを参照すること、Metal backendがBridge `.mm`とtarget-local defineを含むことを確認し、backend側Bridge objectだけを先にbuildする。`nm`で5つのC ABI symbolsがdefined (`T`/`t`) であることをassertし、出力をdiagnosticsへ保存する。このpreflightはGN graphとBridge objectのtopologyを保証するだけで、最終的な専用targetのcompile/link統合を代替しない。

さらにBridge object確認後、専用targetのfull build前に`libEGL`だけをbuildし、GNが報告したmacOS `libEGL` outputを`nm`で検査する。5つのC ABI symbolsがlibEGL binaryにもglobal external definitionとして存在することを確認し、直前のhidden-symbol link failureをfail-fastで検出する。ただしこれは最終test targetのcompile/link統合そのものを代替しない。

CI run `36349844094`では、このpreflight自体がGN生成時に`defines +=`を`defines = []`宣言より先に評価して停止した。さらに適用後の行位置確認で、同じblockが`public_deps`配列内へ入る可能性を検出した。patchではbackend target-local defineを`defines = []`の直後、`public_deps = [`の前へ明示的context付きで配置し、config側のdefineと併存させた。これはテスト実行前の構成エラーであり、source/build targetの実行結果を意味しない。

CI run `36351199352`ではBridge objectの5 symbolsは`T`だったが、libEGL dylibのexportには存在しなかった。`ANGLE_EXPORT`が固定revisionの内部configで空定義にされ得るため、stub専用header/sourceでは明示的なdefault-visibility macroを宣言・定義へ付与した。通常buildではheader/source自体がtargetへ入らず、通常export setは変更しない。

その後のCI run `36353179445`でもlibEGLのexportが空だったため、macOSのlibEGL targetにstub flag時だけ`-Wl,-exported_symbol,_ANGLE_MetalFamily1Test*`を付与する。Bridge objectの`T`定義、libEGLのexport、最終test targetのlinkを段階的に検証し、通常buildのexport setは広げない。

CI run `36355191172`ではlibEGL target外のexport blockが`Unexpected token if`で停止し、run `36376354124`では直接`ldflags` assignmentが`Assignment had no effect`で停止した。これはlibEGL exportを試した過去の案であり、最終patchでは`metal_family1_test_libglesv2_export_config`をbase libGLESv2 templateへ適用する。
CI run `36380355206`では、`configs`がtemplate invocationの既定変数として宣言されていないため、`configs +=`が`Undefined identifier`で停止した。最終patchではlibEGL invocationへconfigsを渡さず、base libGLESv2 template自身のtarget configsへstub+mac条件付きconfigを追加する。通常buildでは条件不成立のためexport setは広げない。
CI run `36381398889`ではwrapper templateのconfigs forwarding案が`Assignment had no effect`で停止した。この案は廃止し、最終patchではlibEGL wrapperへconfigsを渡さない。

Phase 5 workflowでは、patch適用・source-state記録後に独立した`GN configuration preflight`を実行する。ここで`args.gn`を生成して`gn gen`を一度だけ行い、stub target、Metal backend、libGLESv2 configの`gn desc`結果を診断へ保存・検証する。後続のBuild and testは同じ`out/Phase5`を再利用し、`gn gen`を再実行しない。これによりGN scope/template forwardingの失敗をcompile前に検出する。

CI run `36389469500`ではGN preflight通過後、libEGL compileで既存のinclude configが失われ`common/system_utils.h`を見つけられなかった。原因はwrapper transferの`configs = invoker.configs`がnested targetの既定configsを上書きしたためである。patchではnested target内で`angle_common_configs + invoker.configs`を使い、既存設定を保持したままstub export configを追加する。
追加のartifact分析では当時の`//:libEGL configs`から`//:internal_config`も欠落していた。最終patchではlibEGL側のtransferを使わず、base libGLESv2 templateの既存configsへexport configを追加する。GN preflightはlibGLESv2 configsに`//:internal_config`が存在することもassertする。

CI run `36393176516`ではBridge objectがlibGLESv2に含まれる一方、libEGLへexport flagsを付けたためlink時にsymbolsがundefinedとなった。最終設計ではstub+mac専用export configをbase `angle_libGLESv2` templateへ適用し、専用test targetはlibEGLとlibGLESv2の双方へlinkする。preflightもlibGLESv2 configs/output/nmを検証し、libEGL exportとは主張しない。
CI run `36397819064`ではpreflight後の専用target buildが無関係な`libGLESv1_CM.dylib`のlinkまで誘発し、GL symbolsのundefinedで停止した。原因は専用targetの広い`data_deps = [ "$angle_root:angle" ]`である。data dependencyをlibEGL/libGLESv2に限定し、必要なruntime dylibだけを供給する。これはlinker failureを抑制する変更ではない。
CI run `36402862552`では専用targetのbuild（95/95）は成功したが、テスト起動時に`./libEGL.dylib`を解決できず停止した。dylibの相対install nameに合わせ、workflowは`out/Phase5`をcwdとして`./angle_metal_family1_test_stub`を起動する。DYLD環境変数やlinker検査の緩和は行わない。
CI run `36407337941`では最初のDeviceStageの実行中にSIGSEGV（exit 139）となった。artifactでは失敗した`eglInitialize`後の再`eglTerminate`まで進んだかを区別できないため、初期化失敗ケースでは`eglTerminate`を呼ばないようにし、固定revisionの既存EGLテストと同じ後処理境界に合わせる。また、feature override配列を関数ローカルからstatic storageへ移し、`eglInitialize`までポインタ寿命を保証する。いずれもtest-only harnessの修正であり、本番経路は変更しない。
CI run `36412678542`でもDeviceStageの`[ RUN ]`直後にSIGSEGV（exit 139）が再現した。固定revisionの`CommandQueue::reset()`は`finishAllCommands()`を経由するため、未取得・部分初期化状態での`terminate()`から無条件に呼ばれないよう、production-safeに`mCmdQueue.valid()`を確認してからresetするguardを追加した。`WrappedObject`のnil release自体は安全だが、CommandQueueの部分初期化解放経路を明示的に閉じる。これは通常buildにも適用されるnil/valid安全修正で、stub専用挙動ではない。
CI run `36417938293`でもDeviceStageの`[ RUN ]`直後にSIGSEGV（exit 139）が継続したため、次回workflowではテスト失敗時だけ同じcwdから`lldb --batch`でbacktraceを取得し、diagnosticsへ保存する。これは原因切り分け専用で、テスト結果やlinker/runtime検査を緩和しない。
CI run `36422535441`のlldbではDeviceStage開始直後にEXC_BAD_ACCESS（PC=0）となり、libGLESv2のnm出力にbridge 5シンボル以外のEGL entrypointがありませんでした。loaderの`EGL_GetPlatformDisplay`、`EGL_Initialize`、`EGL_GetError`、`EGL_Terminate`をstub+mac専用libGLESv2 export configへ追加し、workflowのnm preflightでも4つを検証します。通常buildのexport集合とruntime選択経路は変更しません。
CI run `36426804853`ではEGL export preflight通過後、4テストすべてが`eglInitialize`前の`EGL_NO_DISPLAY`で停止した。固定revisionの`IsMetalDisplayAvailable()`がFamily 1をMac2 gateで拒否していたため、stub profile有効時だけ同関数をtrueにするtest-only bypassを追加した。実際のdevice取得と`DisplayMtl::initialize()`の各stageは引き続き実行し、stub無効時のproduction gateは保持する。

Phase 3DのVM上でGPUレンダリングが成功しても、Intel HD 5000での実機成功を意味しない。逆にVMのApple Paravirtualized Graphics Deviceで失敗しても、Family 1実機の結果を直接否定しない。

## 実機へ進む条件

次の条件を満たすまで、実機の署名・起動・KOOV操作は行わない。

1. release manifestのANGLE revisionに対するソース差分確認が完了
2. Family 1プロファイルのtargeted EGL testがCIで成功
3. 各初期化停止段階を再現できる
4. production pathがstub無効時に変わらないことを確認
5. Phase 3B/3C/3DのCI結果とartifactを保存

上記のCI先行段階が完了した後、実機では別途承認された最小のruntime実験patchを使用し、既存のPhase 3手順でANGLEロード、GPU初期化、WebGL、KOOVを段階的に確認する。CI成功だけでは実機操作の承認にならない。

## できないこと・残る不確実性

- VMでApple Intel HD 5000ドライバや実GPU shader compilerを再現すること
- Metal framework全体をDYLD置換して本物の`MTLDevice`を作ること
- stubテストから実機の描画破損、ハング、性能、GPUプロセスクラッシュを保証すること
- VMでの成功をもって、OCLP環境のIntel HD 5000での成功と結論すること

したがって、Phase 5は「実機の代替」ではなく、「実機で試すべきANGLE改修箇所を絞り込むVM-first工程」と位置づける。
