# Chromium / Chrome + 独自ANGLE + KOOV 実験計画

作成日: 2026-09-15
状態: 実行開始前（方針合意済み）
最終ゴール: **MacBookAir6,1上で、Google Chrome 154が独自ビルドのANGLEを動的に読み込み、WebGLを有効化した状態でKOOVを起動し、描画と基本動作の挙動を確認する。**

---

## 1. この計画の目的

Chrome 152以降でmacOSの従来のCGL/OpenGL経路が利用できなくなった後、OCLPでmacOS 15.7.9を動かしているHaswell世代のMacBookAir6,1（Intel HD Graphics 5000）では、Chrome 154のANGLE/MetalがEGL Displayを初期化できず、WebGLを含むGPUアクセラレーションが無効化される。

本計画では、ChromeやKOOVを全面的にビルド・改造するのではなく、Chromiumが用意した `--use-dynamic-angle` を使用して独自ANGLE共有ライブラリをGoogle Chrome 154へサイドロードする。段階的に初期化失敗箇所を特定し、Mac GPU Family 1でANGLE/Metalを実験的に初期化できる最小変更を作り、WebGLとKOOVで実害が出るかを実機で観察する。

この実験の主目的は、Family 1を正式サポートすると先に結論づけることではなく、次を実測することである。

- Family 1の制限を越えてANGLE/Metalを初期化できるか
- WebGL 1/2が有効になるか
- Intel HD Graphics 5000で描画破損、GPUプロセスクラッシュ、ハング、ソフトウェア描画へのフォールバックが起きるか
- KOOVが実用上問題なく表示・操作できるか
- 問題がある場合、どの機能または処理で再現するか

---

## 2. 対象環境と確定済み情報

### 2.1 実機

| 項目 | 値 |
| --- | --- |
| Mac | MacBookAir6,1（2013年） |
| CPU世代 | Intel Haswell |
| GPU | Intel HD Graphics 5000 |
| PCI Device ID | `0x0a26` |
| macOS | 15.7.9（24G830） |
| パッチ環境 | OpenCore Legacy Patcher（OCLP） |
| KOOV実行ユーザー | `<KOOV_GUI_USER>`（一般ユーザー） |
| 管理作業ユーザー | `<ADMIN_USER>`／必要時のみrootまたはsudo |

この環境はAppleおよびGoogleがChrome 154向けにサポートする正規のHaswell + macOS 15構成ではない。OCLPが復元したLegacy Metalドライバと新しいmacOSフレームワークの組み合わせであるため、結果はOCLP環境固有となる可能性がある。

### 2.2 ブラウザとANGLEの固定バージョン

| 項目 | 値 |
| --- | --- |
| Google Chrome | `154.0.8037.17`（x86_64） |
| Chromiumリビジョン | `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854` |
| ANGLEリビジョン（短縮） | `8efd15f71c27` |
| ANGLEリビジョン（固定値） | `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448` |
| ANGLE系統 | Chromium branch-head 8037系（要DEPS照合） |

独自ANGLEは、最初に必ずこのANGLEリビジョンから作る。ANGLE `main` や別のChromeバージョンのANGLEを混ぜない。最終的にはChromeの上記Chromiumリビジョンの `DEPS` が指すANGLEコミットと完全一致することを確認し、CIログにも残す。

### 2.3 既存の比較基準

#### Chrome 149：成功基準

- バージョン: `149.0.7827.201`
- ANGLE/OpenGL経路でGPUアクセラレーションとKOOV起動を確認済み
- 基準ログ: `about-gpu-2026-09-13T09-41-17-641Z.txt`
- KOOVは次のApp IDで起動している。

```text
kpmcfooelenggiklfmbljpognolignpg
```

#### Chrome 154：失敗基準

- バージョン: `154.0.8037.17`
- `GLDisplayEGL::Initialize failed`
- `Initialization of all (1) EGL display types failed`
- GPUプロセス初期化失敗後、`--use-gl=disabled`へフォールバック
- Canvas、Compositing、Rasterization、WebGL等がSoftware onlyまたはDisabled
- 一方でDawnは `Metal backend - Intel HD Graphics 5000` を認識しているため、Metalデバイスの存在そのものは確認できている
- 基準ログ:
  - `about-gpu-2026-09-13T08-51-02-808Z.txt`
  - `about-gpu-2026-09-14T12-06-16-324Z.txt`
  - `about-gpu-2026-09-14T12-56-15-880Z.txt`
  - `chrome154-gpu-process-command.txt`
  - `貼り付けられたテキスト（1 点）(20260914-122649).txt`

#### 実施済みANGLE Feature override

次の指定はChromeの親プロセスだけでなく、初回のGPUプロセスへ伝達されたことをプロセス一覧で確認済みである。

```text
--disable-angle-features=requireGpuFamily2
```

さらに次も実施済みだが、EGL初期化失敗は継続した。

```text
--disable-angle-features=requireGpuFamily2,requireMsl21
```

したがって、**単に `requireGpuFamily2` 判定を削除しただけでは解消しない可能性が高い**。最初の改造は制限解除ではなく、初期化経路を可視化する診断ログ追加とする。

---

## 3. 技術構成

```text
GitHub公開リポジトリ
  ├─ 再現用workflow
  ├─ ANGLE固定リビジョン情報
  ├─ 診断／実験パッチ
  ├─ テストスクリプト
  └─ x86_64成果物（libEGL.dylib / libGLESv2.dylib）
                    │
                    ▼
Google Chrome 154 ANGLE Test.app（ローカル複製）
  ├─ --use-dynamic-angle
  ├─ --use-gl=angle
  ├─ --use-angle=metal
  ├─ 独立したテスト用Chromeプロファイル
  └─ 独自ANGLE dylib
                    │
                    ▼
MacBookAir6,1 / Intel HD Graphics 5000 / OCLP macOS 15.7.9
  ├─ ANGLE読込確認
  ├─ chrome://gpu
  ├─ WebGL 1/2試験
  ├─ GPU安定性・描画確認
  └─ KOOV試験
```

`--use-dynamic-angle` は共有ライブラリの任意パスを値として受け取るスイッチではない。静的リンクされたANGLEの代わりに、Chromeのモジュール位置から `libEGL.dylib` と `libGLESv2.dylib` をロードする経路へ切り替える。実際の配置先はChrome 154の固定ソースとANGLE公式スクリプトを確認してから決定し、推測でコピーしない。

---

## 4. 守るべき安全条件

### 4.1 既存環境を壊さない

- 動作確認済みの `/Applications/Google Chrome 149.app` を変更しない。
- GoogleからインストールされたChrome 154本体を直接改造しない。
- 実験には明確に名前を変えた複製だけを使う。

```text
/Applications/Google Chrome 154 ANGLE Test.app
```

- `<KOOV_GUI_USER>` の既存Chromeプロファイルを直接Chrome 154実験版で開かない。
- KOOVを含む既存プロファイルは、Chromeを完全終了してからテスト専用ディレクトリへ複製する。
- 初期段階では毎回新しい一時プロファイルを使い、同期を無効にする。
- 実験版を通常のWebブラウジング、パスワード保存、決済、個人情報入力に使わない。

### 4.2 コード署名

Chromeアプリバンドルへdylibを追加・交換すると、Googleの署名は無効になる。必要な場合は、**実験用コピーだけ**をad-hoc署名する。

```bash
codesign --force --deep --sign - "/Applications/Google Chrome 154 ANGLE Test.app"
```

これはGoogleの署名や公証を維持する操作ではない。署名後のアプリはローカル実験用改造バイナリとして扱う。元の署名済みChromeを上書きしない。

### 4.3 公開物とライセンス

GitHubへ公開してよいもの:

- 自作パッチ
- GitHub Actions workflow
- ビルド・テストスクリプト
- ANGLEのライセンス条件に従った独自ANGLE成果物
- 個人情報、トークン、ローカルパスを除去したログ
- 再現手順と実験結果

GitHubへ公開しないもの:

- Google Chrome.appまたはその構成ファイル一式
- KOOV.app、KOOVの著作物・教材・アセット
- Chromeユーザープロファイル
- Cookie、保存パスワード、同期情報、USB/Bluetooth識別情報
- GoogleまたはKOOVの認証情報

独自ANGLEを配布する場合は、ANGLEおよび同梱される第三者コードの `LICENSE`／`NOTICE` を成果物に含める。Chromeと組み合わせた完成アプリの再配布は行わず、各利用者が正規入手したChromeへローカルで適用する方式とする。

---

## 5. GitHubリポジトリ方針

### 5.1 公開リポジトリを使う理由

GitHub Actionsの標準macOSランナーは、公開リポジトリでは無償で利用できる。対象はIntel版の次のランナーとする。

```yaml
runs-on: macos-15-intel
```

2026-09時点の標準構成は4 CPU、14GB RAM、14GB SSDである。14GB SSDはANGLEのcheckout、ビルド、成果物作成には余裕が少ないため、使用量を各段階で記録し、不要なターゲット・デバッグシンボル・キャッシュを抑える。`macos-15-intel` は2027年8月までの提供予定であり、それ以後は別ビルド基盤が必要になる。

### 5.2 推奨リポジトリ構成

```text
README.md
LICENSE
docs/
  baseline.md
  experiment-log-template.md
  koov-test-checklist.md
patches/
  0001-angle-metal-init-diagnostics.patch
  0002-angle-family1-experimental.patch
scripts/
  verify-artifact.sh
  install-angle-into-chrome-copy.sh
  launch-chrome-angle-test.sh
.github/workflows/
  build-angle-macos-x64.yml
ANGLE_REVISION
```

ANGLE本体の完全なコピーをリポジトリへ恒久的に置く必要はない。workflow内で公式リポジトリから固定リビジョンを取得し、パッチを適用する方式を基本とする。

### 5.3 成果物に必ず含める情報

- `libEGL.dylib`
- `libGLESv2.dylib`
- 必要なら関連するANGLEデータファイル
- `ANGLE_REVISION`
- `args.gn`
- Xcode／SDK／clangバージョン
- `file`、`otool -L`、`codesign -dvvv` の結果
- 各ファイルのSHA-256
- ビルドログ
- パッチ一覧
- ビルド種別（unmodified／diagnostic／experimental）

---

## 6. 実行フェーズ

## Phase 0 — 基準資料の保全

### 作業

1. 上記のChrome 149成功ログとChrome 154失敗ログを読み取り専用の基準資料として保存する。
2. 各ログから次を表にまとめる。
   - Chrome／Chromium／ANGLEバージョン
   - コマンドライン
   - GL implementation parts
   - Display type
   - GPU Feature Status
   - GPUプロセスクラッシュ数
   - GPUプロセスの最終コマンドライン
   - EGL／Metal関連エラー
3. `system_profiler SPDisplaysDataType`、OCLPバージョン、macOSビルド番号を保存する。

### 完了条件

- Chrome 149成功とChrome 154失敗を同じ項目で比較できる。
- 後続のテスト結果がこの基準と混ざらない。

---

## Phase 1 — ソースと実装バージョンの固定

### 作業

1. Chromium `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854` の `DEPS` を確認する。
2. `DEPS`のANGLE pinが `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448` と一致することを確認する。
3. 同リビジョンの次を保存する。
   - `DisplayMtl.mm`
   - ANGLE Feature定義
   - `EGLFeatureControlTest.cpp`
   - `update_chrome_angle.py`
4. Chromium側の次を確認する。
   - `ui/gl/gl_switches.cc`
   - `ui/gl/init/gl_initializer_mac.cc`
   - `--use-dynamic-angle`のGPUプロセスへの伝達
   - macOSにおけるdylib探索位置
5. 確認したURLとコミットを `docs/baseline.md` に記録する。

### 完了条件

- Chrome 154とANGLEソースの対応を推測ではなくコミットで説明できる。
- dylibの正確な配置先と必要ファイルがソースから確定している。

---

## Phase 2 — 無改造ANGLEのGitHub Actionsビルド

### 目的

Family 1向け変更を加える前に、ビルド環境・ABI・アーキテクチャ・動的ロード手順を検証する。

### 作業

1. 公開GitHubリポジトリを作成する。
2. `macos-15-intel`上でdepot_toolsとANGLEを取得するworkflowを作る。
3. ANGLEを固定コミットへcheckoutする。
4. 公式のmacOS Chrome注入手順と当該リビジョンのビルド定義から、`libEGL.dylib`と`libGLESv2.dylib`を生成する最小GN args／Ninja targetを決める。
5. 最初のビルドにはソース変更を一切入れない。
6. 可能な範囲でANGLEの単体テストとFeature overrideテストを実行する。
7. 成果物と再現情報をGitHub Actions artifactとして保存する。

### 注意

- GitHubランナーにはIntel HD Graphics 5000がないため、ここでMetal/Haswellの成否は判定できない。
- CI上のMetalテスト結果をMacBookAir6,1の代用にしない。
- ディスク不足時は、全Chromium checkoutへ拡張する前に不要ファイル、ターゲット、デバッグ情報を削減する。

### 完了条件

- x86_64の `libEGL.dylib` と `libGLESv2.dylib` が再現可能に生成される。
- workflowを再実行して同一ソース・同一パッチから成果物を作れる。
- SHA-256、コミット、GN args、ツールチェーンが記録されている。

---

## Phase 3 — 無改造ANGLEのChrome 154サイドロード確認

### 目的

独自ANGLEをChromeが実際にロードしていることを、Family 1修正とは独立して証明する。

### 作業

1. Chromeを完全終了する。
2. Chrome 154を実験専用名で複製する。
3. 独立した一時プロファイルを作る。
4. 成果物のアーキテクチャ、依存関係、ハッシュを確認する。
5. Phase 1で確定した配置先へdylibを入れる。
6. 必要な場合のみ実験用コピーをad-hoc署名する。
7. 次を基本として起動する。最終的なコマンドはソース確認後に確定する。

```bash
"/Applications/Google Chrome 154 ANGLE Test.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/tmp/chrome154-dynamic-angle-profile" \
  --no-first-run \
  --no-default-browser-check \
  --disable-sync \
  --enable-logging=stderr \
  --v=1 \
  --use-dynamic-angle \
  --use-gl=angle \
  --use-angle=metal \
  --ignore-gpu-blocklist
```

8. GPUプロセスのコマンドラインを保存する。
9. `lsof`、`vmmap`、起動ログまたは一時的な識別ログにより、実験用dylibのロードを確認する。
10. `chrome://gpu`を保存する。

### 合格条件

- GPUプロセスへ `--use-dynamic-angle`、`--use-gl=angle`、`--use-angle=metal` が届く。
- Chromeバイナリ内の静的ANGLEではなく、実験用 `libEGL.dylib`／`libGLESv2.dylib` がロードされた証拠が得られる。
- 無改造版が既存のChrome 154と同様に失敗した場合でも、「動的ロード経路の確立」というPhase 3の目的は達成とする。

### 停止条件

- dylibがロードされている証拠を得られない。
- ABI不一致、missing symbol、署名／Library Validationエラーが出る。

停止時はFamily 1パッチへ進まず、配置、ビルド構成、ABI、署名だけを修正する。

---

## Phase 4 — 診断ANGLEの作成

### 目的

既存スイッチによってFamily 2制限を越えた後、どの初期化段階で停止しているかを特定する。

### 診断項目

少なくとも次を明示的にログ出力する。

- ANGLEコミットと実験ビルド識別子
- Metal device名、vendor、registry ID（公開ログでは必要に応じマスク）
- Metal GPU Family判定結果
- `requireGpuFamily2.enabled`
- `requireGpuFamily2.hasOverride`
- `requireMsl21.enabled`
- Feature override適用前後の値
- `newCommandQueue`の成否
- Format table初期化の開始／終了
- 内蔵Metal shader libraryのロード方法
- `newLibraryWithData`／`newLibraryWithSource`等が返す `NSError`全文
- RenderUtils等、後続初期化の開始／終了
- EGL error codeとANGLE ResultがStopになった直前の場所

### 作業

1. 動作を変えないログ追加パッチを作る。
2. CIでdiagnosticビルドを作る。
3. Phase 3と同じChromeコピー／一時プロファイルで実行する。
4. 次の2条件を別々に記録する。

```text
A: Feature overrideなし
B: --disable-angle-features=requireGpuFamily2,requireMsl21
```

5. ログ差分から最初に失敗する箇所を特定する。

### 完了条件

- `GLDisplayEGL::Initialize failed`より内側の、最初の具体的失敗位置とエラー内容が得られる。
- `requireGpuFamily2` overrideが有効か否かをログで断定できる。

---

## Phase 5 — Family 1実験パッチ

### 方針

- 原因が確定してから最小変更を作る。
- Family 2以上の既存挙動を変えない。
- Family 1は明示的なオプトイン時だけ通す。
- Metal非対応GPUは通さない。
- 単にGPU FamilyをOS全体でFamily 2へ偽装しない。
- Family 2固有機能は、個別の能力判定またはFamily判定を維持する。
- 未対応機能を呼ぶ場合は、可能なら明示的に無効化または安全な経路へフォールバックさせる。

### 実装候補

優先順位は次のとおり。

1. 既存の `--disable-angle-features` で入口を越え、実際の失敗箇所だけを修正する。
2. 必要なら既定OFFのANGLE Featureを追加する。
3. Chromium側スイッチ追加は、ANGLE単体のFeature overrideで表現できない場合だけ検討する。

提案名の例（実在するFeature名ではない）:

```text
allowUnsupportedMacGpuFamily1
```

### 必須テスト

- Feature overrideのEnabled／Disabledが反映されるテスト
- 既定OFFで現在のFamily 1拒否が維持されるテスト
- オプトイン時のみFamily 1経路へ進むテスト
- Family 2以上ではフラグON/OFFにかかわらず既存Feature選択が変わらないテスト
- Metal非対応ケースを通さないテスト
- 初期化失敗時にEGLエラーを返し、ブラウザ全体を巻き込まないテスト

物理Family 1 GPUをGitHub Actionsで再現できない部分は、能力判定をテスト可能な関数へ分離するか、モックしたMTLDevice／Feature setによる単体テストを検討する。実機試験が必要な項目は明示する。

### 完了条件

- 実験パッチの意図と影響範囲がコードとテストで説明できる。
- Family 2以上に回帰を起こさない設計になっている。
- MacBookAir6,1でANGLE/MetalのEGL初期化が次の段階へ進む、または新しい具体的な失敗位置を得られる。

---

## Phase 6 — WebGL・描画・安定性試験

### 比較マトリクス

| ケース | ブラウザ | ANGLE | 目的 |
| --- | --- | --- | --- |
| A | Chrome 149 | 内蔵ANGLE/OpenGL | 成功基準 |
| B | Chrome 154 | 内蔵ANGLE | 失敗基準 |
| C | Chrome 154 Test | 無改造dynamic ANGLE | サイドロード同等性 |
| D | Chrome 154 Test | diagnostic ANGLE | 原因特定 |
| E | Chrome 154 Test | Family 1実験ANGLE | 本試験 |

### 起動条件

- Chromeプロセスが残っていないことを確認する。
- ケースごとに別の `--user-data-dir` を使う。
- 同じディスプレイ、解像度、macOS設定を使う。
- `--disable-gpu-sandbox`は通常試験では使用しない。診断上必要な場合だけ別ケースとして記録する。
- `--disable-gpu-watchdog`も通常試験と分ける。
- `--ignore-gpu-blocklist`の有無を混同しない。

### 確認項目

1. `chrome://gpu`
   - `GL implementation parts`
   - `Display type`
   - `GL_VENDOR`、`GL_RENDERER`、`GL_VERSION`
   - Canvas、Compositing、Rasterization、WebGL、Video Decode
   - GPU process crash count
   - Problems Detected
   - Log Messages
2. WebGL
   - WebGL 1 context作成
   - WebGL 2 context作成
   - ANGLE／WebGL conformance testの代表セット
   - 2D/3Dテクスチャ、blend、depth/stencil、MSAA、framebuffer、readback
   - shader compile/link
   - context lostと復帰
3. 視覚確認
   - 色化け
   - 透明度／blend異常
   - テクスチャ破損
   - 欠落、ちらつき、黒画面
   - ウィンドウresize、最小化、復帰、外部ディスプレイ接続時
4. 安定性
   - GPUプロセスクラッシュ
   - macOS WindowServer／画面全体の異常
   - ハング、極端なCPU使用率、メモリ増加
   - 失敗後にSoftware renderingへ安全に移るか

### 緊急停止条件

- 画面全体の継続的な破損
- WindowServerの反復クラッシュ
- OSフリーズまたは強制再起動が必要になる状態
- GPUプロセスのクラッシュループ
- ファイルシステムまたはChromeプロファイル破損

停止後は実験用アプリと一時プロファイルを終了し、動作確認済みChrome 149へ戻す。OS全体のGPU Family偽装やシステムMetal Frameworkの改変には進まない。

### WebGL段階の合格条件

- `GL implementation parts` がANGLE/Metalを示す。
- WebGL 1またはKOOVが必要とするWebGLコンテキストが作成できる。
- 少なくとも15～30分の代表試験でGPUプロセスがクラッシュループしない。
- 描画差異をスクリーンショットとログで再現可能に記録できる。

完全無欠のWebGL CTS合格は、KOOV試験へ進むための絶対条件とはしない。ただし、失敗項目とKOOVで使う機能との関係を記録する。

---

## Phase 7 — KOOV用テストプロファイルの準備

### 既知のKOOV情報

| 項目 | 値 |
| --- | --- |
| App ID | `kpmcfooelenggiklfmbljpognolignpg` |
| 既存ユーザーデータ | `$KOOV_USER_HOME/Library/Application Support/Google/Chrome` |
| 既存プロファイル | `Default` |
| 旧ランチャー | `$KOOV_USER_HOME/Applications/Chrome Apps.localized/KOOV旧ランチャー.app` |
| 実験用ランチャー候補 | `$KOOV_USER_HOME/Applications/KOOV 154 ANGLE Test.app` |

Chrome 149の実測では、Chrome本体がKOOV App IDで起動した後、旧 `app_mode_loader` が子プロセスとして現れた。Dockに旧ランチャーのアイコンが出ても、それだけで旧Chromeが起動したとは限らない。判定はChrome親プロセスの実行パス、バージョン、GPUプロセスの引数で行う。

### 作業

1. `<KOOV_GUI_USER>`でChromeとKOOVを完全終了する。
2. 既存プロファイルをテスト専用の場所へ複製する。
3. 複製後、同期と一般ブラウジングを無効にする。
4. KOOVのApp ID、Web Applicationデータ、必要な拡張が複製に含まれることを確認する。
5. テスト用Chromeへ次を渡す専用ランチャーまたはスクリプトを作る。

```text
--user-data-dir=<KOOV専用複製プロファイル>
--profile-directory=Default
--app-id=kpmcfooelenggiklfmbljpognolignpg
--use-dynamic-angle
--use-gl=angle
--use-angle=metal
--no-first-run
--no-default-browser-check
--disable-sync
```

6. ランチャーは必ず `<KOOV_GUI_USER>` のGUIログインセッションから起動する。rootの非GUIセッションから `launchctl asuser ... open` を実行した際には `RBSRequestErrorDomain Code=5`／`OSLaunchdErrorDomain Code=125` が発生した実績があるため、この経路を標準手順にしない。

### 完了条件

- 既存の `<KOOV_GUI_USER>` プロファイルを変更せず、複製プロファイルからKOOV App IDを起動できる。
- Chromeの実行パスが `Google Chrome 154 ANGLE Test.app` を示す。
- GPUプロセスが独自ANGLEを使っている証拠が取れる。

---

## Phase 8 — Chrome + 独自ANGLE + KOOV 最終試験

### 試験項目

1. KOOV起動
   - 正しいApp IDで開く
   - 起動時間
   - 白画面、黒画面、クラッシュの有無
2. 描画
   - メイン画面
   - ブロック／プログラム編集画面
   - 3DまたはWebGL描画領域
   - 色、透明度、テクスチャ、文字、アイコン
   - スクロール、拡大縮小、ウィンドウresize
3. 操作
   - プロジェクトを開く
   - ブロックをドラッグする
   - 保存操作（テストデータのみ）
   - 画面遷移を繰り返す
4. 安定性
   - 30分以上の連続利用
   - GPUプロセスクラッシュ数
   - context lost
   - CPU／メモリの異常増加
   - スリープ／復帰後の表示
5. KOOVデバイス連携
   - USB／Bluetooth接続は、描画試験が安定してから実施する
   - 権限ダイアログ、デバイス認識、転送を確認する
   - 実機デバイス試験を行わない場合は「未試験」と明記する

### 比較方法

- 同一のKOOV画面・同一プロジェクトをChrome 149とChrome 154実験版で表示する。
- 同じウィンドウサイズでスクリーンショットを撮る。
- 可能なら画像差分を作る。ただしアンチエイリアス差を即座に不具合と判定しない。
- 各操作時刻とChrome/GPUログを対応させる。

### 最終ゴールの達成条件

次をすべて満たした時点で、このプランの最終ゴールを達成とする。

1. Chrome 154が `--use-dynamic-angle` により独自ビルドANGLEをロードしていることを証明できる。
2. MacBookAir6,1のIntel HD Graphics 5000でANGLE/Metal初期化結果を取得できる。
3. WebGLサポート状態を `chrome://gpu`、WebGLテスト、ログで確認できる。
4. 独自ANGLEを使用したChrome 154からKOOVを起動できる。
5. KOOVの描画と基本操作を実際に試し、正常・破損・クラッシュ・フォールバックのいずれかを再現可能な形で記録できる。

「問題なし」を最終ゴールの必須条件にはしない。**成功でも失敗でも、独自ANGLEが使われたことを証明したうえで、KOOVまで到達して挙動を記録できれば実験として完了**とする。

---

## 7. 各実験で残す記録

実験ごとに次のテンプレートを埋める。

```markdown
## Experiment ID

- Date/time:
- Operator:
- Machine: MacBookAir6,1
- macOS/OCLP:
- Chrome version/revision:
- ANGLE revision:
- Patch revision:
- dylib SHA-256:
- Chrome app path:
- User-data-dir:
- Full command line:
- Code-sign status:
- Dynamic library load evidence:
- chrome://gpu export:
- GPU process command line:
- GPU log:
- WebGL 1:
- WebGL 2:
- KOOV:
- Visual defects:
- GPU process crash count:
- OS-level symptoms:
- Result: PASS / PARTIAL / FAIL / BLOCKED
- Next action:
```

スクリーンショットとログのファイル名にはExperiment IDを含める。公開前にユーザー名、ホームディレクトリ、トークン、Cookie、デバイス固有情報を確認する。

---

## 8. 想定される分岐

| 結果 | 次の対応 |
| --- | --- |
| 無改造dylibをロードできない | 配置先、ABI、GN args、依存dylib、署名を修正。Family 1改修へ進まない |
| overrideが適用されていない | Chromium→EGL属性→ANGLE Featureの伝達を追跡し、テストを追加 |
| `newCommandQueue`失敗 | OCLP Metal device/queue互換性を調査。Family判定解除だけでは解決不可 |
| shader library生成失敗 | NSError、MSLバージョン、オフラインshader生成物、macOS SDK差を特定 |
| EGL初期化成功、WebGL作成失敗 | Context/Config/Surface作成のどこで失敗するか追加診断 |
| WebGL成功、描画破損 | 最小WebGL再現ケースを切り出し、Family 2固有機能・ドライバworkaroundを調査 |
| GPUプロセスクラッシュ | crash log、context lost、最後のGL呼出しを取得。自動再試行を抑えて原因を分離 |
| KOOVのみ失敗 | KOOVが使用するWebGL機能、プロファイル、App ID、権限を切り分ける |
| KOOVが正常 | 反復試験、比較画像、既知の制約をまとめ、上流提案の根拠にする |

---

## 9. このプランの範囲外

次は本計画では実施しない。

- macOSやOCLPのMetal Framework／GPUドライバそのものの改造
- OS全体に対するMac GPU Family 2の偽装
- Chrome 149の改造または削除
- Google Chrome改造版の第三者配布
- KOOVアプリ・教材・アセットの再配布
- Family 1の正式サポート宣言
- 全WebGL CTS・全Mac機種での適合保証
- Chrome自動更新を恒久的に無効化する一般運用構成

---

## 10. 上流提案へ進む場合の出口条件

本プランの最終ゴール達成後、次が揃った場合に限りANGLE／Chromiumへの提案を検討する。

- 最小パッチ
- Family 2以上の挙動を変えないテスト
- MacBookAir6,1／HD Graphics 5000での実測結果
- WebGLの成功・失敗テスト一覧
- KOOVでの比較結果
- 描画破損がある場合の最小再現コード
- OCLP環境であることの明示
- 明示的オプトイン、unsupported／own-riskという位置付け
- セキュリティとクラッシュ時のフォールバック説明

正式採用を求める最初の提案は、無条件のFamily 1サポートではなく、次のいずれかを候補とする。

1. Family 1実機調査を可能にする既定OFFの実験Feature
2. 初期化失敗位置を明確にする診断ログ
3. Family 1を通す専用テストと能力別フォールバック
4. 実証されたIntel Haswell固有workaround

---

## 11. 公式参照資料

- Chromium: `--use-dynamic-angle` 実装コミット
  https://chromium.googlesource.com/chromium/src/+/eba6e1a7a957aafe323fb9b401621d23639e0111%5E%21/
- ANGLE公式: Testing with Chrome Canary
  https://chromium.googlesource.com/angle/angle/+/HEAD/doc/DebuggingTips.md#testing-with-chrome-canary
- 対象ANGLE固定コミット
  https://chromium.googlesource.com/angle/angle/+/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448
- Chromium対象コミット
  https://chromium.googlesource.com/chromium/src/+/62d2fcb41a84e4dcefd8c4da7dfa534e6c482854
- ANGLE Feature control test
  https://github.com/google/angle/blob/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/src/tests/egl_tests/EGLFeatureControlTest.cpp
- GitHub-hosted runners
  https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- GitHub Actions billing
  https://docs.github.com/en/billing/concepts/product-billing/github-actions
- GitHub Intel macOS runner lifecycle
  https://github.com/actions/runner-images/issues/13045

---

## 12. 後続エージェントへの開始指示

後続エージェントは、いきなりFamily 1制限のコードを書き換えないこと。次の順序を守る。

1. Phase 0の既存ログを整理する。
2. Phase 1でChrome 154の `DEPS`、ANGLE pin、dylib探索位置をソースで確定する。
3. GitHub Actionsの14GB制約内で、無改造ANGLEの共有ライブラリを生成できる最小workflowを作る。
4. MacBookAir6,1で無改造dynamic ANGLEの読込証拠を取る。
5. その後にのみ診断パッチを作る。

不明点は推測で埋めず、固定コミットのソース、ビルドログ、実機ログのどれで確認したかを記録する。特に次の三点を混同しない。

- コマンドラインにスイッチが表示されたこと
- GPUプロセスへスイッチが伝達されたこと
- 独自dylibが実際にロードされ、そのコードが実行されたこと

この三つは別々に証明する必要がある。
