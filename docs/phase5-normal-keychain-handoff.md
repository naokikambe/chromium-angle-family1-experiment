# 通常Keychainでのstock復旧：実機エージェントへの一括指示

後工程も委任する場合は[stock復旧からANGLE・KOOVまでの一括プロンプト](phase5-device-completion-handoff.md)を使用してください。この文書は同プロンプトの工程Aの詳細として適用します。

対象Macで、正しく初回署名したstock Chromiumの正常なKeychainアクセスとページ描画を検証してください。この指示を次工程として受け取った場合、準備、結果別の追加調査、受入検査、文書化、必要な変更の検証・commit／pushまでを一括で進めます。Keychainの許可操作やシステム変更への同意は、作業委任と区別してください。公開記録には実機固有の機種名を含めません。

## 出発点と目的

リポジトリは `naokikambe/chromium-angle-family1-experiment`、ブランチは `phase5-page-recovery`。最新の公開手順と固定source pinを読み、既存変更を保全して試験HEADを記録します。`71d5bb1`以降のキットは `--startup-timeout 45`を指定できます。上限は60秒で、HTTP navigationのtimeoutとは別です。

現行S0・GPU無効化の測定範囲では、未応答時のKeychain待機とHTTP stream開始前の停止が対応しました。拒否応答後はKeychain error返却後のページ要求と描画が進みました。これは拒否後に開始した要求の成功であり、未応答中の同じ要求の再開を測定したとは扱いません。mockの独立profile3件は自動検査と実GUI確認が通過しました。通常Keychainによる正常な鍵取得は別途検証します。

拒否後の表示成功は暗号化不可の状態であり、正常アクセスの復旧ではありません。次の目的は、mockや拒否に頼らず、通常Keychainで鍵を正常に取得して、通常GPUでstockのページを表示し、再起動後も暗号化データを利用できる条件を確立することです。対象はstockまでとし、独自ANGLE・KOOVは受入後の工程です。

読む資料：

- [現在の再計画](phase5-page-recovery-replan.md)
- [Apple公開資料と固定版ソースの対応](phase5-keychain-public-evidence.md)
- [原因調査の手順・完了条件](phase5-keychain-investigation-handoff.md)
- [計測キット](../scripts/page-recovery/README.md)

## 操作範囲とオーナー入力

既存の拒否一回の同意は「許可」、追加の拒否、Always Allow、ACL変更、ユーザー作成へ拡張しません。読み取り専用の調査、既存試験環境の確認、非機密fixtureと受入runnerの準備、文書化は進められます。対象環境の実行制限は守ってください。

オーナー操作が必要なら、先に候補を調査して具体的な試験を準備し、対象appの完全hash・署名要件・対象itemと所属Keychain・操作・回数または必要となる条件・表示観察の時間・既存データへの影響をまとめて依頼します。保留中の回答を確認し、新しい必要事項だけを依頼してください。秘密値や入力パスワードを記録しません。

「一度だけの許可」はその対象と操作への明示的な同意がある場合に限ります。追加の応答が必要になったら同意の範囲を確認します。既存の検証用GUIユーザーを優先し、新しいユーザー・Keychain環境の作成が必要なら差分と復元方法を用意して承認後に実施します。既存itemのACL編集・Always Allow・削除はこの指示では実施せず、必要性を示す案として残します。

## 一括で進める手順

### 現在の阻害要因を先に切り分ける

通常KeychainのAllow試行ではHTTP streamへ進まず、同じ試行のAPI返却は未観測でした。後続の未応答試行にはKeychain待機stackがありますが、先のAllow試行の測定値へ転用しません。署名検査は実行経路を固定して確認し、Keychain accessとは別の判定にします。通常GUIユーザーでのSafe Storage API返却、暗号化利用、通常GPUでの独立profile試験は別途成立が必要です。以下はその未完了境界から進めます。

1. **署名とidentityを読み取り専用で診断する。** 正確な検証コマンド・stderr・検証時刻・macOS時刻、appの署名情報・DR・封印した内容の整合性、署名証明書の公開情報（期限・issuer・chain）、ユーザーのKeychain検索一覧とlock状態、実行ユーザー・起動経路、identity検索の範囲を対応付けます。`CSSMERR_TP_NOT_TRUSTED`から、再署名やファイル改変を原因と断定しません。identity 0件だけで秘密鍵が存在しないとも断定しません。証明書期限、chainの不足、信頼設定、検索範囲、実行権限のどれが確認できたかを区別し、失敗した部品も特定します。秘密鍵は取得・出力しません。

   署名時と同じGUIユーザーでも、sandbox内とホストの通常実行経路ではKeychain・証明書の可視性が異なる場合があります。読み取り専用で同じapp hash・検証コマンド・検索範囲を比較し、実行経路を証跡に明記してください。許容されたホスト経路で厳密な署名検証と有効identityが成立するなら、sandbox側の信頼エラーや0件だけを理由に証明書・信頼設定・署名を修復しません。署名検証の成功と、既存Safe StorageのACLによるアクセス許可は別の判定です。

2. **修復案を具体化する。** 既存の信頼設定変更や証明書操作は実施せず、必要な変更・根拠・影響・復元方法を用意します。新しい署名identityが必要なら、正規の有効なidentityを用意する工程と、完全未署名原本から別コピーを初回署名する工程を提案します。既存S0を再署名しません。無条件に信頼する設定、検証を省く操作、保護機能を無効にする操作で受入を通しません。
3. **追加Allowは一回の測定で境界を絞る。** 使用済みのAllowを再利用可能な同意として扱いません。保留中の追加Allow一回への回答を確認し、回答があればその範囲で測定します。対象app・完全hash・GUIユーザー・item・全引数・新規profileを固定し、GPU無効化・mockなしで、prompt前から応答後までの収集を準備します。署名状態が未解決のappで行う場合は既存条件の診断試行と位置付け、stock受入へ数えません。署名や環境を変えたappへ同意を自動移転しません。
4. **同じ試行のAPI境界を測る。** Browser／Network service／要求元のPIDと親子関係、prompt対象、オーナー操作時刻、workerの応答前後stack、取得可能なsecurityd／Chromiumの成功・エラー記録、request sourceとnonce、server受信を採取します。取得できないsampleをsudoで強行せず、通常権限で使える観測方法を準備します。API返却の成功・エラーが確認できたか、wait stackが残るか、観測できなかったかを分けます。ページターゲットの作成とfixture navigation開始も時刻を記録し、後続試行のsampleやオーナーのクリック報告だけでAPI成功を断定しません。

Allow Onceは現在のアクセスへの応答であり、後続の別プロセスでpromptが再発すること自体は先のAllowが反映されなかった証拠ではありません。継続利用の受入では無promptの正常アクセスを別途必要とするため、反復promptを避ける条件の比較へ進みます。繰り返しAllowを依頼するだけの探索は行いません。

署名診断、追加Allowの収集準備、既存の検証ユーザーの確認、非機密fixture／再起動runnerの検証は、依存関係に従って進められます。追加応答の回答待ちだけを理由に全作業を止めません。署名修復や環境作成が必須となった場合は、まとめた具体案をオーナーへ提示し、必要な変更への同意を得てから実施します。

1. **入力と対象itemを固定する。** 同じsnapshotから正しいrole policyで初回署名したstockコピーを優先し、実パス・出所・完全hash・署名identity・DR・role設定を記録します。既存S0と正常アクセス候補の関係を明示します。秘密値を出力せず、Safe Storage itemの所属Keychain・検索順・同名item・信頼条件との関係を調べます。新規profileやbundle名の変更だけでKeychainが分離されると想定しません。

2. **正常アクセスの試験を準備する。** 同じapp・GUIユーザー・fixtureでGPU無効化を一旦固定し、mockなしの新規profileで測定します。対象の一度だけの許可について同意がある場合はオーナーの正常応答後を観測し、鍵取得・暗号化利用可能・HTTP・DOM・JS・fetch・描画を対応付けます。待機解除やページ表示だけで鍵取得成功とは判定しません。直接の成功記録と非機密データの暗号化利用の証拠を示します。必要な同意がなければ準備と独立環境の調査を続けます。

3. **独立環境を比較する。** 既存の検証用GUIユーザーが使える場合は、同じ署名済みappを変更せず比較します。対象itemが共有Systemにある場合は別ユーザーだけでは隔離できないため、実際の検索結果と項目所属を確認します。実ユーザーのprofile・Keychain・秘密鍵は移しません。新しいSafe Storage itemを作る条件を使う場合、その環境変更の同意範囲も確認します。別ユーザーの成功だけでACLが唯一の差だと断定しません。

4. **通常GPUへ戻す。** 正常Keychainアクセスの条件を確立してから、GPU引数だけを変える比較を行います。mock、GPU無効化、保護機能の無効化を使わず、HTTP・本文・JS・fetch・canvas・描画・実GUIを確認します。stockの既定ANGLE/GPU状態も記録し、2D成功を独自ANGLEやWebGL成功へ読み替えません。

5. **独立profileと再起動を検証する。** 成立した通常Keychain・通常GPU条件で新規profile3件を実施し、各試験IDにオーナー観察を対応付けます。さらに専用の検証profileを正常終了して再起動し、非機密のpersistent cookieの保存・送信・復号と暗号化保存形式を確認します。鍵や実ユーザーのcookieは出力しません。テストprofileのみ保持・再利用します。再起動ごとに承認が必要なら、その条件を明示し、継続利用の受入完了とはしません。

   現行probeは毎回新規profileを作るため、再起動検査は小さな専用runnerまたは限定した拡張を準備してください。署名済みappや既存profileは変更しません。正常終了前後、cookie期限、nonce、保存形式、再起動後のserver受信を対応付ける意味のある検証を行い、関連文書と一緒にcommit／pushします。

   `scripts/page-recovery/persistent_cookie_runner.py`は、一つの新規profileでsynthetic persistent cookieを設定し、正常終了、SQLiteの暗号化metadata確認、同じprofileでの再起動とcookie再送信を測る実装です。cookie値は記録しません。最初の起動に必要な一回のAllowが明示承認されている場合だけ応答し、再起動後にpromptが再び出たら追加の同意を推定せず未受入として記録します。runnerは通常GPUを使い、Keychain ACL、Always Allow、既存profileは変更しません。

### 同じ見た目のpromptを別のauthorization境界として診断する

同じプロセス内で見た目が同じKeychain promptが続けて現れても、一つの承認が繰り返されたとは限りません。Apple公開Securityソースの例では、`SecurityServerAcl::validate`が通常のACL検証を実行してから、その外側でpartition検証を行います。Decrypt authorization（action 24）の後、client partitionが登録リストにない場合は、partitionを追加する検証（`CSSM_ACL_AUTHORIZATION_PARTITION_ID`、action 65538）へ進む構造です。どちらもKeychain promptを表示し得るため、同一PIDと同じprompt外観だけでは、どの境界で止まったか判定できません。[`acls.cpp`の`validate`、`validatePartition`、`extendPartition`](https://github.com/apple-oss-distributions/Security/blob/main/securityd/src/acls.cpp)

同じ公開ソースの`KeychainPromptAclSubject::validateExplicitly`では、ACL／partition更新callbackはremember応答があり、かつ検証状態が条件を満たす場合にだけ呼び出されます。通常のAllow応答そのものを、恒久ACL追加やpartition追加と同一視しないでください。[`acl_keychain.cpp`の`validateExplicitly`](https://github.com/apple-oss-distributions/Security/blob/main/securityd/src/acl_keychain.cpp) これらは公開ソース上の仕組みを示す参照であり、対象OSが同じ実装・経路を使うという証明ではありません。

診断では同一PIDについて、prompt前後のpermission event、action値、partition情報、API返却を一つの時系列へ対応付けます。action 24の試行に対するAllowが観測されてもAPI成功とは限りません。次にaction 65538相当のpromptが現れた場合は、未応答・回答済み・観測不能を分けて記録し、誤ったパスワードだったと推定しません。最初の応答から二つ目への応答、Always Allow、ACLまたはpartitionの編集への同意は推定せず、それぞれの対象と変更について別の明示的なオーナー承認を得ます。

観測時間にも上限があります。CDP navigationが短いtimeoutで終了し、その後runnerが`Browser.close`を呼ぶと、ページ要求と観測がそこで打ち切られることがあります。準備した観測待ち時間は、runnerがその終了経路へ入った場合の実測時間を保証しません。アプリ終了時のwatchdogによるexitは正常終了ではなく、鍵やcookieの成功も証明しません。観測中にserver HTTP eventがなかった場合に言えるのは、その観測範囲で記録されなかったことだけです。

## 結果別に次へ進む

| 結果 | 同じ委任内で行うこと |
| --- | --- |
| 署名検証が信頼エラーで失敗、または有効identityが見つからない | 期限・chain・信頼評価・検索範囲・実行経路を切り分ける。受入は未達とし、診断試行と分離する。修復が必要なら具体的な差分と復元方法をまとめる |
| Allowの所有者報告があるが同じ試行のAPI境界を観測できない | 成功・待機継続のどちらとも断定せず、同意範囲内の一回の追加測定の収集方法を整える。別の未応答試行のsampleで補ったことにしない |
| 一度の許可で正常に鍵を取得し、ページが表示する | 正常アクセス候補として保存し、独立環境・通常GPU・再起動の検査へ進む。反復promptの有無も確認する |
| 許可したのにKeychainが待つ、またはエラーになる | 対象PID・item・応答と追加要求を照合し、最初の未完了境界を確認する。追加応答の同意は推定しない |
| 独立環境で正常アクセス・再起動が成功する | その環境でstock受入を進め、既存ユーザーとの差と恒久運用候補を整理する。既存ユーザーが復旧したとは扱わない |
| 正常な鍵取得後もHTTPが止まる | 暗号化初期化・cookie callback・HTTP開始の最初の未完了境界へ観測を限定する |
| GPUを戻すと描画だけ失敗する | Keychainと分けてGPU process・compositor・stock ANGLE・対応Metal機能を調べる。一条件ずつ比較し、独自ANGLE追加を先行させない |
| 保存後のcookieが再起動で復号できない | 同じ鍵・item・profileの再利用、cookie期限、終了時flush、保存形式を照合する。既存データ削除や暗号化の無効化で通過させない |

全体ビルドは、必要なコード差分と停止境界を絞ってから費用・実行環境を具体化します。10月5日の試行条件への適用範囲の確認は並行し、現在のstock検査を停止しません。

## 完了条件

次を満たして「通常Keychainでのstock復旧完了」としてください。

- 対象app、署名、GUIユーザー、Keychain環境、全引数、再現手順が固定されている。
- 対象appの署名検証が成功し、証明書の信頼エラーを残していない。検証環境と初回署名の記録が対応している。
- mock・拒否・暗号化不可へのfallbackに頼らず、Safe Storage鍵の正常な取得・利用を実証している。
- 通常GPUと保護機能を有効にした状態で、独立した新規profile3件がHTTP・DOM・JS・fetch・canvas・描画と実GUI確認に合格している。
- 専用profileの正常終了と再起動で、テストcookieの暗号化保存と復号・再送信を実証している。
- 再起動ごとに手動の承認応答へ依存せず、対象の正常アクセスが継続する。
- 適用ユーザー・対象item・既存環境との差・恒久運用候補・残る制約を説明している。独立環境での完了と既存ユーザーでの復旧を区別している。
- 変更と関連文書が検証され、作業ブランチへpushされている。公開手順・固定入力・再現条件・限界が文書にそろっている。

現行S0の原因特定完了は保持します。次工程の未完了を、原因不明への後戻りとは表現しません。

## Read-only OSCrypt histogram observation

The persistent cookie runner records a read-only observation of Chromium's
`OSCrypt.Mac.FindGenericPasswordResult` histogram once during each launch,
before it requests `Browser.close`. It queries only that exact histogram from
the browser-root CDP endpoint and records the endpoint's browser PID alongside
the launched PID. A mismatch, missing histogram, malformed buckets, or CDP
failure is recorded as `unavailable` with a diagnostic. Such a measurement
cannot support a pass.

The mapping is pinned to Chromium revision
[`82303c21a18acdc256c6264cd2ed0e1588df99d4`'s Keychain lookup](https://github.com/chromium/chromium/blob/82303c21a18acdc256c6264cd2ed0e1588df99d4/components/os_crypt/common/keychain_password_mac.mm): enum value `0` means
`PasswordFound`, `1` means `PasswordNotFound`, and `2` means `Error`. The
capture labels an observation `verified_found` only when the validated
histogram contains samples exclusively in the bucket `[0, 1)`, and its reported
sample sum is zero. The total count and sample sum must agree with the bucket
counts. Only the three pinned enum bucket ranges are accepted. Samples in
other enum buckets are `verified_other`; they do not establish that an existing
password was found. Empty, overlapping, malformed, or mixed found/other
bucket results remain unavailable.

Each phase writes `keychain-histogram.json` and embeds the same summary in its
phase result. The record includes the source revision, observation timestamp,
profile binding, and PID binding. It does not collect Keychain item values,
passwords, cookies, or unrelated histograms. The histogram is emitted during
Chromium's deferred cleanup after the generic-password lookup returns, so this
observation measures the process-wide histogram at capture time; it does not
identify a particular item or prove that any later cookie decryption used that
lookup result. The capture is supplemental evidence and does not change the
runner's persistent-cookie classification. The overall result separately
reports whether both phases have verified-found observations, so a missing or
other observation cannot satisfy the normal-Keychain acceptance requirement.

The fixture tests use synthetic CDP replies and temporary synthetic
`DevToolsActivePort` files only. They do not connect to Chromium or access
macOS Keychain.

有効な既存結果は再利用し、一試験ごとに次の指示を求めず分岐に従って続行してください。中間報告を行っても作業は続けます。必須のオーナー入力・実行資源がなく、他に進められる作業も尽きた場合は、満たした条件・残条件・阻害要因・必要な操作とその後の続行手順を一つの報告にまとめてください。時間切れや回答待ちは完了としません。
