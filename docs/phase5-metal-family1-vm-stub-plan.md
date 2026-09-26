# Phase 5: Metal Family 1 capability stub (VM-first)

作成日: 2026-09-26  
状態: 設計確認済み・admission record確認済み・未実装

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

このadmission recordはPhase 5のソース実装を開始するために完了した。ただし、Actions dispatch、新規artifact download、署名、Chrome起動、実機操作を許可するものではない。

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

既存の`EGLFeatureControlTest`はend-to-endのfeature overrideテストであり、新しいcompile-time-only profileの証明には使わない。実装時は`src/tests/angle_unittests.gni`の`angle_unittests_msl_sources`（`angle_enable_metal`時）へMetal専用sourceを追加し、`src/tests/BUILD.gn`から`angle_unittests`へ統合する方針とする。これは実装待ちであり、通常buildや公開APIの変更を意味しない。

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
 ├─ ANGLE unit tests
 ├─ optional VM observation
 └─ diagnostics upload
```

runnerは`macos-15-intel`に固定する。初回の専用workflowはjob timeoutを60分、ANGLE build/test step timeoutを45分に固定する。stub-enabled artifactと通常artifactを分離し、専用artifactのmanifest schemaは`phase5-metal-family1-test-stub-v1`、名前は`angle-metal-family1-test-stub-<run-id>`とする。stage診断、test result、compiler/build metadata、GN args／manifest／artifactのSHA-256を保存する。初回workflowはstub buildとunit testだけを対象とし、VM観測（Chrome/GPUログを含む）は人の承認を得た後に別段階として追加する。workflow dispatch、CI artifact取得、実機操作は従来どおり別途承認が必要であり、このプランの文書修正だけでは実行許可を与えない。

Phase 3DのVM上でGPUレンダリングが成功しても、Intel HD 5000での実機成功を意味しない。逆にVMのApple Paravirtualized Graphics Deviceで失敗しても、Family 1実機の結果を直接否定しない。

## 実機へ進む条件

次の条件を満たすまで、実機の署名・起動・KOOV操作は行わない。

1. release manifestのANGLE revisionに対するソース差分確認が完了
2. Family 1プロファイルの単体テストがCIで成功
3. 各初期化停止段階を再現できる
4. production pathがstub無効時に変わらないことを確認
5. Phase 3B/3C/3DのCI結果とartifactを保存

その後、実機では最小の実験パッチを適用し、既存のPhase 3手順でANGLEロード、GPU初期化、WebGL、KOOVを段階的に確認する。

## できないこと・残る不確実性

- VMでApple Intel HD 5000ドライバや実GPU shader compilerを再現すること
- Metal framework全体をDYLD置換して本物の`MTLDevice`を作ること
- stubテストから実機の描画破損、ハング、性能、GPUプロセスクラッシュを保証すること
- VMでの成功をもって、OCLP環境のIntel HD 5000での成功と結論すること

したがって、Phase 5は「実機の代替」ではなく、「実機で試すべきANGLE改修箇所を絞り込むVM-first工程」と位置づける。
