# Phase 5 CI preflight 設計案

## 状態と適用範囲

- 作成日: 2026-10-06
- 状態: Human承認済みの実装案。workflowは登録前で、まだdispatchしていない。
- 対象: `phase3-dynamic-angle-prep` の Chromium source URLLoader diagnostic CI
- 基準Run: [37464208418](https://github.com/naokikambe/chromium-angle-family1-experiment/actions/runs/37464208418)
- この文書では full Chromium build、artifactのdownload/upload、codesign、xattr、Chrome起動、実機操作、KOOV操作を行わない。
- `RUNTIME_DEVICE_READY=false`は変更しない。

この文書は、同じephemeral runnerへ目的なく再dispatchしたり、GitHub-hosted jobのtimeoutを単純に延長したりする前に、runner・toolchain・Siso・cache・進捗を短時間で計測するための提案である。ここでいう小さいtargetの探索結果は、正式な同一revisionのU0/U1またはfull Chromium比較の結果として扱わない。

## 1. 読み取り専用で確定した基準

### revisionの状態

| 項目 | 値 | 判定 |
| --- | --- | --- |
| local branch | `phase3-dynamic-angle-prep` | 一致 |
| local `HEAD` | `a3bb53b3e0f9e58aff547b26811643a967cdf5fa` | clean |
| remote `phase3-dynamic-angle-prep`（`git ls-remote`） | `a3bb53b3e0f9e58aff547b26811643a967cdf5fa` | local `HEAD`と一致 |
| Run 37464208418 `headSha` | `f444054a141b808043b69c6e0bf0ebfb57008dd4` | Run時点の入力 |
| `a3bb53b..HEAD`相当のRun後差分 | 3つの既存docs、75 insertions / 11 deletions | source/build inputの修正ではない |

従って、Run 37464208418の成否はRunの`headSha`である`f444054...`に対して判定する。現在のlocal/remote `HEAD`がRunのrevisionと同じだとは扱わない。remote最新HEADの確認は`git ls-remote`だけで行い、fetch/pullは行っていない。

### Run/job/step結果

読み取り専用のRun metadataとjob logで次を確認した。

| 対象 | 結果 |
| --- | --- |
| Run 37464208418 | `completed / cancelled` |
| `phase5-chromium-build-macos-intel` (`112271031679`) | `completed / cancelled` |
| `phase5-angle-input-macos-intel` (`112271032063`) | `completed / success` |
| `phase5-chromium-u0-u1-macos-intel` (`112438651883`) | `skipped` |
| Static audit、paths、depot_tools、source/deps、Xcode 16 patch、URLLoader patch | success |
| Build unbranded exact-revision Chromium | cancelled |
| Record Chromium build failure diagnostics | failure（build stepがcancelledなので意図した後段判定） |
| unsigned bundleのfreeze/package、upload | skipped |
| build diagnosticsのupload | success |

build logの診断値は次の通りである。

- jobは`2026-10-06T12:34:27Z`に開始し、約6時間後に終了した。
- build stepは約5時間11分の実行時点で`[7277/79594]`付近だった。
- `offline mode`、`fastlocal=1->0`、`localexec/4`の長時間waitが記録された。
- 記録されたコンパイルコマンドは`exit=0`であり、compiler errorまたはninjaのコンパイル失敗は確認されない。
- `localexec/4`はSisoのlocal execution slot/waitの記録であり、物理CPU数そのものとは断定しない。次回はCPU数とSiso並列度を別々に記録する。

したがってRunの一次分類は、`compiler_failure`ではなく、**GitHub-hosted job予算（6時間上限）に対する実行速度不足によるtimeout/budget exhaustion**である。GitHubのRun表示上の最終値は`cancelled`であり、後段diagnostics stepの`failure`をcompiler failureと再分類してはならない。

## 2. GitHub Freeで確認できる範囲

リポジトリAPIは`private=false`、`visibility=public`を返した。GitHub公式資料の現行記述とこの公開状態から、今回の前提は次の通りである。

| 項目 | 公式資料の要点 | Phase 5への意味 |
| --- | --- | --- |
| 公開repoの標準runner | public repositoryのstandard GitHub-hosted runnerは無料・無制限 | `macos-15-intel`を使えることと、6時間以内にfull buildが終わることは別問題 |
| macOS Intel standard runner | 4 CPU、14 GB RAM、14 GB SSD、Intel | これは仕様上の基準。実際のimage、空き容量、CPU数、Xcode/SDKを毎回ログに記録する |
| GitHub-hosted job上限 | 1 jobあたり6時間。上限到達時はjobが終了する | 既存の360分job timeoutは上限に達しており、単純な延長は解決策にならない |
| Freeのquota（private repo等の通常quota） | 2,000分/月、artifact 500 MB、cache 10 GB/repository | 公開repoでstandard runnerの実行分が無料でも、cache/artifact容量は別に制約される |
| Actions cache | exact key hit/missを判別でき、未使用cacheは7日超で削除される。デフォルトのrepo合計は10 GB | source/out全体ではなく、サイズを計測できる限定的な依存/cacheだけを候補にする |
| artifact | build/test outputをjob間またはrun後に保存する仕組み | 小さい診断ログ以外のChromium source/out保存には使わない。全体保存は500 MB quotaと転送時間に合わない |
| larger runner | TeamまたはEnterprise組織向け | Freeでの実装候補にはしない。導入時は契約・費用・runner labelの承認が必要 |
| self-hosted runner | Actions利用料は無料だが、hardware/OS/softwareの管理責任と機材費は利用者側 | Intel Macの準備、隔離、更新、runner token、label、secret漏えい対策をHuman承認なしに行わない |

参照した公式資料:

- [Actions limits](https://docs.github.com/en/actions/reference/limits)
- [GitHub-hosted runners reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [GitHub-hosted macOS image software](https://github.com/actions/runner-images/blob/main/images/macos/macos-15-Readme.md)
- [Billing and usage](https://docs.github.com/en/actions/concepts/billing-and-usage)
- [Dependency caching reference](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching)
- [Workflow artifacts](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts)
- [Larger runners](https://docs.github.com/en/actions/concepts/runners/larger-runners)
- [Self-hosted runners](https://docs.github.com/en/actions/concepts/runners/self-hosted-runners)

### 今回採用しない選択肢

- job timeoutの単純な延長、または同じ標準ephemeral runnerへの無目的なfull build再dispatch
- FreeのActions artifactへのChromium sourceまたは`out`全体の保存・転送
- self-hosted Intel Macの登録・設定
- RBE、remote execution、remote cacheまたはそのcredentialの設定
- Team以上のlarger runnerの契約・利用

後三者は「技術的に有効かもしれない条件」と「今回実行すること」を分ける。必要条件と安全条件だけをHumanへ報告し、別途承認を受ける。

### 実施せずに報告する候補条件

| 候補 | 必要条件 | 安全条件 | 追加承認 |
| --- | --- | --- | --- |
| self-hosted Intel Mac | x86_64、対象Xcode/SDK、十分なRAM/disk、source/depsを再取得できるclean snapshot | trusted workflowだけにrunner groupを限定し、untrusted PRを載せない。runner token、device、署名鍵、既存profileを同居させず、ジョブ後に状態を破棄または検証する | runner登録、機材/保守費、ネットワーク許可、更新責任、credential保管 |
| RBE / remote cache | compiler/toolchainのdigest、CAS/cache namespace、TLS認証、quota/cost、offline時のfallback、source/patch/GN argsを含む完全なkey | sourceやsecretを意図せず外部へ送らない。cache read/writeを分離し、retention・アクセス主体・再現性・poisoning対策を定義する | 外部サービス選定、egress、credential、cache write権限、費用、障害時の扱い |
| Team以上のlarger runner | TeamまたはEnterprise entitlement、利用可能なmacOS image/label、Xcode/SDK適合性、billingとconcurrency枠 | job上限が消えるとは扱わず、6時間制限とimage差を再確認する。許可repo・runner group・費用上限を固定する | plan変更/契約、runner label、予算、同一revisionでの検証 |

## 3. 提案するpreflightの構成

### 3.1 実行単位と安全境界

Human承認後は、設計レビュー済みの専用script/workflowとして登録する。既存の`phase5-chromium-url-diagnostic.yml`は変更しない。実装対象は[`scripts/phase5-ci-preflight.sh`](../scripts/phase5-ci-preflight.sh)と[`.github/workflows/phase5-ci-preflight.yml`](../.github/workflows/phase5-ci-preflight.yml)である。

将来のworkflowは次の条件を満たす。

```yaml
name: Phase 5 CI preflight (proposal)

on:
  workflow_dispatch:
    inputs:
      target_ref:
        required: true
        type: string
      run_small_target:
        required: true
        type: boolean
        default: false

permissions:
  contents: read

jobs:
  preflight:
    runs-on: macos-15-intel
    timeout-minutes: 30
    steps:
      - name: Check out the explicitly approved ref
        uses: actions/checkout@v4
        with:
          ref: ${{ inputs.target_ref }}
          fetch-depth: 0
          persist-credentials: false

      - name: Collect runner and toolchain facts
        run: ./scripts/phase5-ci-preflight.sh --inventory-only

      - name: Validate revision, DEPS, patches and GN args
        run: ./scripts/phase5-ci-preflight.sh --validate-inputs

      - name: Restore only bounded dependency caches
        if: ${{ inputs.run_small_target }}
        id: cache
        uses: actions/cache/restore@v4
        with:
          path: ~/.cache/phase5-preflight
          key: ${{ env.PREFLIGHT_CACHE_KEY }}

      - name: Explore one approved small target
        if: ${{ inputs.run_small_target }}
        run: ./scripts/phase5-ci-preflight.sh --small-target
```

このYAMLは登録するpreflightの骨格である。`run_small_target`の初期値はfalseとし、今回の承認dispatchでは明示的にtrueを指定する。cacheはrestore-onlyから始め、artifact action、full source/outのcache path、`autoninja ... chrome`、codesign、device操作は含めない。

### 3.2 収集するrunner/SDK情報

各値を生の環境変数dumpではなく、allowlistした名前だけで記録する。

| 分類 | 記録値 |
| --- | --- |
| runner | `runner.os`、`runner.arch`、`RUNNER_LABELS`の選択値、`uname -a`、`uname -m` |
| CPU/RAM/disk | `sysctl -n hw.ncpu`、`sysctl -n hw.memsize`、`df -k`の対象filesystem、空き容量 |
| OS/Xcode | `sw_vers`、`xcodebuild -version`、`xcode-select -p` |
| SDK/compiler | `xcrun --sdk macosx --show-sdk-version`、SDK path、`xcrun --find clang`、`clang --version` |
| build tools | depot_tools revision、`autoninja`の所在、Siso binaryの所在とversion |
| 時刻 | UTC開始・終了、各probeのduration |

token、credential、全環境変数、remote endpointのsecret部分、checkout credentialは記録しない。

### 3.3 Sisoと実行経路の計測

Sisoの「設定値」と「実効値」を分ける。少なくとも次を1行ずつ出力する。

```text
siso_version=<version-or-unknown>
siso_mode_requested=<offline|online|unknown>
siso_mode_effective=<offline|online|unknown>
fastlocal_requested=<0|1|unknown>
fastlocal_effective=<0|1|unknown>
localexec_parallelism_configured=<integer-or-unknown>
localexec_active_slots=<integer-or-unknown>
localexec_wait_seconds=<integer-or-unknown>
remote_execution_configured=<true|false|unknown>
remote_cache_configured=<true|false|unknown>
```

`siso.INFO`等の既存logを読む場合はendpointやcredentialをredactする。`localexec/4`のようなログ文字列だけではCPU数を決めず、`hw.ncpu`と並べて比較する。non-interactive実行により`fastlocal`が無効化されるなら、その理由とrequested/effectiveの両方を記録し、full buildを開始する前のreject条件にする。

RBE/remote cacheは、接続先・認証・cache namespace・source/patchの完全なkey設計・再現性・費用が揃わない限り`configured=false`として扱う。preflightがcredentialを作成・取得・登録することはない。

### 3.4 source/deps/patch/GN args/cache

入力の同一性を検証し、cache keyを一つのrevisionだけに依存させない。最低限の論理keyは次の形にする。

```text
phase5-preflight-v1-
  <runner-os>-<runner-arch>-
  chromium-<chromium-revision>-
  deps-<DEPS-resolved-angle-revision>-<DEPS-file-sha256>-
  gn-<normalized-gn-args-sha256>-
  patch-<URLLoader-patch-sha256>-<Xcode16-patch-sha256>-
  depot-tools-<depot-tools-revision>-
  xcode-<xcode-build>-sdk-<sdk-version>
```

実際のActions keyは512文字以下に収めるため、長い値はSHA-256 digestに置き換える。次の項目をmanifestに残す。

- Chromium revisionとcheckout ref
- `DEPS`のSHA-256と、そこから解決したANGLE revision
- depot_tools revision
- URLLoader diagnostic patch SHA-256
- Xcode 16 compatibility patch SHA-256
- 正規化したGN argsとそのSHA-256
- Xcode build、SDK version、runner OS/architecture
- source/deps取得の有無、duration、cache exact hit / prefix hit / miss
- cache pathごとのbytes、entry数、restore duration

cacheを有効にする場合の対象は、容量上限と内容を測れる依存download/compiler tool cacheに限定する。Chromium source全体、`out`全体、生成されたbundle、署名済みbundleをActions cacheまたはartifactに保存しない。cache miss時に成功したjobが自動saveする動作を避けるため、preflightではrestore-onlyを使用し、saveの採否は別のHuman承認事項とする。

### 3.5 進捗・経過時間・残タスク

小さいtarget probeまたは承認済みのdiagnostic commandだけを対象に、build logを60秒間隔で監視する。ログの`[completed/total] elapsed`形式から次を定期記録する。

```text
sample_utc=<timestamp>
elapsed_seconds=<integer>
tasks_completed=<integer>
tasks_total=<integer>
tasks_remaining=<integer>
completed_per_minute=<number-or-unknown>
estimated_remaining_seconds=<number-or-unknown>
active_wait_class=<localexec|remote|io|unknown>
```

残時間は直近の複数sampleから計算し、sampleが少ない場合は`unknown`とする。小さいtargetのrateを約79,000 taskのfull Chromiumへ外挿して正式な完了予測にはしない。full buildを再開するための判断材料は、少なくとも次の全てが揃った時点で初めて作る。

1. source/deps取得とcache restoreのdurationが実測されている。
2. Sisoのoffline/online、fastlocal、localexec、remote executionの実効値が確定している。
3. 小さいtargetの初回compile rateとwait比率が取得されている。
4. 6時間job上限に対する保守的な余裕を含む見積もりがあり、単なるtimeout延長ではない。

### 3.6 終了理由の分類

Actionsのjob conclusionだけでなく、step outcome、コマンド終了値、build logの最後の進捗を合わせて分類する。

| 分類 | 必須条件の例 | 次の扱い |
| --- | --- | --- |
| `success` | 全probeと許可されたsmall targetが終了、compiler/ninja errorなし | preflight合格。ただしfull build成功を意味しない |
| `timeout` | 内部予算またはjob budgetに到達し、compiler failureなし | 実行速度/予算問題。full buildを再dispatchしない |
| `cancelled` | Human/上位workflow/runner停止でキャンセル、budget到達根拠なし | 外部キャンセルとして記録し、理由を確認 |
| `compiler_failure` | compiler/ninjaが非zero、`FAILED`やcompiler errorがあり、timeoutより前 | source/toolchain差分の調査対象 |
| `environment_failure` | Xcode/SDK/Siso/depot_tools/source/depsが欠落、permission/network/cache復元失敗 | runnerまたは入力の修正対象 |
| `preflight_rejected` | 条件不足、secret/RBE未承認、cache key不確定、full targetが選択された | 実行せずHuman判断へ戻す |

GitHubがjobを強制終了した場合、終了処理そのものが実行されずmarkerを書けないことがある。その場合は「job=`cancelled`、設定budget到達、最後のbuild行にcompiler errorなし」を`timeout/budget exhaustion`として記録し、Runの最終値`cancelled`と混同しない。

## 4. 小さいdiagnostic targetの探索案

これは正式な同一revision full Chromium比較から分離した、toolchain/Siso/patchの経路確認である。U0/U1を生成せず、bundleをfreezeせず、sign/device操作へ進まない。

1. exact ref、DEPS、両patchを検証する。
2. `out/Phase5Preflight`のような専用out dirへGN argsを生成する。既存の`Phase5URLDiagnostic`や既存artifactのoutを再利用しない。
3. `gn desc`または生成済みbuild graphで、URLLoader diagnostic patchの変更ファイルをsource listに含む最小の既存unit-test/library targetを候補化する。
4. target名の存在を確認した後、最初は`ninja -n`/graph inspectionでtask数を測る。
5. Human承認後に限り、その候補を一つだけ、短い内部予算付きでcompileする。候補が存在しない場合は、`services/network`系unit targetを推測して無理に実行しない。
6. 記録するのはrunner/toolchain/source/patchのcompile経路だけであり、small targetのsuccessをChromium executableのURL、WebGL、ANGLE、署名、実機のsuccessとは判定しない。

小さいtargetが速く終わっても、full Chromiumの約79,594 taskを6時間以内に完了できる証明にはならない。逆にsmall targetがcompiler failureになる場合は、full buildを試さずにtoolchain/patch/inputを調査する。

## 5. 合格ゲートとfull build再開条件

preflightの合格は、full buildの自動開始条件ではない。少なくとも次のゲートを別々に承認する。

### preflight合格ゲート

- macOS Intel、architecture、CPU/RAM/disk、Xcode/SDKの実測値が記録される。
- Siso version、offline/online、fastlocal requested/effective、localexec並列度、remote設定が確定する。
- source/depsのrevisionとpatch/GN args SHAがmanifestとcache keyに一致する。
- cache hit/missとrestore時間が記録され、source/out全体を転送していない。
- small targetまたはgraph-only probeの終了理由が分類される。
- logにtoken、credential、remote secret、署名済みbundleが含まれない。

### full buildを別途Human承認する条件

- exact source/DEPS/patch/GN args revisionを固定すること
- preflightの実測から、6時間上限内に収まる根拠と安全余裕を示すこと
- standard ephemeral runnerで再試行する場合のcache/source/deps戦略を明示すること
- standard runnerで根拠が不足する場合、self-hosted Intel Mac、RBE/remote cache、larger runnerのどれを選ぶか、費用・credential・アクセス範囲・再現性を明示すること
- full build後のunsigned input、U0/U1、artifact、実機・署名境界を既存planと再確認すること

## 6. 次にHuman承認が必要な操作

今回の調査後も承認待ちで停止する。次のいずれも自動では行わない。

1. この設計に基づくpreflight workflow/scriptの登録と`workflow_dispatch`。
2. どのref（現行remote HEAD `a3bb53b...`またはRun対象の`f444054...`）をpreflight入力にするかの決定。
3. restore-onlyを越えたActions cache save、cache path、保存期間、容量予算。
4. 候補small targetの選択と、短時間compileを実行する承認。
5. full Chromium build、unsigned bundle生成、U0/U1、artifact transfer。
6. self-hosted Intel Mac登録、RBE/remote cache credential、GitHub Team以上のlarger runner契約。

commit、push、force-push、merge、rebase、Actions dispatch、artifact download/upload、既存source/evidence/artifact/profileの変更は、この調査では行わない。
