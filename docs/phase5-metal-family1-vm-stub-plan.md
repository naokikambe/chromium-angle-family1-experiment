# Phase 5: Metal Family 1 capability stub (VM-first)

作成日: 2026-09-26  
状態: 設計確認済み・未実装

## 結論

GitHub Actions の macOS Intel VMで、Intel HD Graphics 5000そのものを再現することはできない。しかし、ANGLE Metal backendの初期化判断をFamily 1相当の能力プロファイルで再現し、初期化のどの段階で停止するかを検証することは可能である。

実装はAppleの`MTLDevice`をVM上で偽装するのではなく、ANGLE内部の能力問い合わせと初期化結果に、テスト専用の注入境界を設ける。通常のMetal実装経路は既定値として変更しない。

## Phase 5開始条件と一次記録

実装またはCI実行を開始する前に、次の入場記録を埋める。値が未確定の項目は推測で補わず、成功runと保存済みartifactを確認してから記録する。

| 項目 | 記録する値 |
| --- | --- |
| Phase 3B synthetic fixture 成功run | run ID / artifact名 / 判定 |
| Phase 3C synthetic preflight fixture 成功run | run ID / artifact名 / 判定 |
| Phase 3D VM観測 成功run | run ID / artifact名 / 判定 |
| release manifest SHA-256 | SHA-256 |
| 使用artifact名 | 完全なartifact名 |
| ANGLE revision | `ANGLE_REVISION`の完全な値 |

`phase-status.md`と`phase3d-vm-observability.md`の記述が一致しない場合、GitHub Actionsの実runと保存artifactを一次情報として照合し、Phase 5実行前に両文書を同じ状態へ更新する。run ID、manifest digest、artifact名、revisionを未確認のまま固定値として書かない。

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

上記は構造確認用の一次ソースである。`1ff8799c596d4fc9acea28343610b1f33650a6fa`は既存文書に記載された候補revisionに過ぎず、今回のrun-metadata確認で現行artifactの値として検証されたものではない。Phase 5の実装前に、最終選択したrelease manifestの`ANGLE_REVISION`で同じ箇所を再確認し、admission recordへ記録する。別revisionの差分を黙って混在させない。

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

capabilityの期待値は固定revisionのソース監査で埋める。推測値は記載しない。

| 確認対象 | 固定する期待値・確認箇所 |
| --- | --- |
| 対象API | EGL初期化、GLES capability生成、Metal renderer capability |
| 最大GLES version | `getMaxSupportedESVersion()`の戻り値（監査後に記入） |
| 必須extension | `generateExtensions()`の生成結果（監査後に列挙） |
| 禁止extension | Family 1で公開してはならない拡張（監査後に列挙） |
| config | `generateConfigs()`の生成結果（監査後に列挙） |
| vendor | IntelはNVIDIA拒否分岐を通らないプロファイルとして使用（実機の完全再現値とは扱わない） |

テストでは`getMaxSupportedESVersion()`、`generateConfigs()`、`generateExtensions()`およびMetal renderer capabilityの結果を、上表の監査済み値と比較する。vendor値だけを根拠にIntel実機との同一性を主張しない。

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

runnerは`macos-15-intel`に固定し、job timeoutとbuild timeoutはCI定義前に決定して記録する（未決定のまま実行しない）。stub-enabled artifactと通常artifactを分離し、stage診断、test result、compiler/build metadata、manifestとartifactのSHA-256を保存する。VM観測を行う場合はChrome/GPUログも診断artifactとして保存する。workflow dispatch、CI artifact取得、実機操作は従来どおり別途承認が必要であり、このプランの文書修正だけでは実行許可を与えない。

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
