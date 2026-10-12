# Keychain対策を裏付ける公開資料

確認日：2026-10-12。これまでの固定版Chromiumソース調査に、Appleの公式資料の照合を追加した。以下はAPI・信頼条件・対策の仕様上の根拠であり、対象Macでの原因確定や修正成功を示す実測結果ではない。

## Apple公式資料と計画への対応

| 資料・確認箇所 | 裏付ける内容 | 対象Macで別途確認すること |
| --- | --- | --- |
| [SecItemCopyMatching](https://developer.apple.com/documentation/security/secitemcopymatching%28_%3A_%3A%29) — Performance considerations | APIは呼出しthreadをブロックする。Appleはbackground実行を推奨する | 待っている要求・PID、応答後のAPI返却と後続処理。Chromiumは既にworker実行しており、単にworkerへ移す案は新しい修正にはならない |
| [Access Control Lists](https://developer.apple.com/documentation/security/access-control-lists) — Overview | 従来型KeychainのACLは操作とtrusted appを照合し、未信頼の要求には確認を求める。恒久許可は対象entryのtrusted app一覧に反映される | 実際の対象item・操作・stored requirement・要求元と決定結果。静的metadataだけで実行時の拒否を確定しない |
| [TN2206](https://developer.apple.com/library/archive/technotes/tn2206/) — Trust and Code Signing | コードの妥当性とリソースを許可するpolicyは別である。既定のKeychain policyは作成appを信頼し、DRで追跡する | 現在のitemが既定policyかcustom ACLか、保存された条件と試験appが対応するか。archived資料なので実OSでの挙動も確認する |
| [TN3127](https://developer.apple.com/documentation/technotes/tn3127-inside-code-signing-requirements) — Designated requirement／Default designated requirement | DRがアプリの識別を担う。Apple DevelopmentとDeveloper IDの既定DRは異なり、配布経路の変更でKeychain確認が現れることがある | 同じTeam ID・bundle IDだけで同一条件と判断せず、実際のDRとitem条件を比較する |
| [Apple Support：アクセス確認](https://support.apple.com/guide/keychain-access/if-youre-asked-for-access-to-your-keychain-kyca1243/mac) | 一度だけの許可、恒久許可、拒否は異なる応答である | 選んだ操作・対象・時刻・実際の応答結果。一度の許可を継続利用の修正とみなさない |
| [Apple Support：アプリごとの許可](https://support.apple.com/guide/mac-help/allow-apps-to-access-your-keychain-kychn002/mac) — Access Control | 対象password itemへ個別appを許可する操作が公式に説明されている | 採用するapp・item・要件・変更差分と既存データへの影響。現在の原因調査で自動適用する許可は与えない |
| [TN3137](https://developer.apple.com/documentation/technotes/tn3137-on-mac-keychains) — Implementation differences | macOSのfile-based Keychainとdata protection Keychainは、選択方法・アクセス制御が異なる。検索一覧にはユーザーloginと共有Systemが含まれる | 使用している方式、対象itemの実所属Keychainと検索順。別ユーザーのloginを用意してもSystemまで分離されるとは考えない |

Always Allowや個別appの許可は、Appleが説明する通常の機能である。現在の原因調査でこれらを使わないのは、比較する承認状態を保ち、未承認の権限変更を避けるための実験範囲である。恒久復旧への採用は対象を限定した別の変更案として扱う。

## 固定版Chromiumとの接続

対象ソースは `82303c21a18acdc256c6264cd2ed0e1588df99d4`。実行した別revisionに適用する場合は対応ソースを確認する。

- [KeychainV2](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/crypto/apple/keychain_v2.mm)の`MakeGenericPasswordQuery`はservice/accountで検索し、data protectionや同期の指定、検索Keychainの明示限定を行っていない。TN3137の既定動作と照合するとfile-based経路として調べる根拠になる。実機の所属itemの確認は別途必要である。
- [KeychainPassword](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/components/os_crypt/common/keychain_password_mac.mm)はbrandingに応じた既定Safe Storage名を使い、itemがない場合に鍵を作成する経路を持つ。新規profileや表示名の変更だけで名前が分離されるとはしない。
- [KeychainKeyProvider](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/components/os_crypt/async/browser/keychain_key_provider.mm)はblocking処理をworkerで実行し、`--use-mock-keychain`ではfake providerを選択する。空の取得結果は一時利用不能として返す。
- [OSCryptAsync](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/components/os_crypt/async/browser/os_crypt_async.cc)、[CookieOSCryptAsyncDelegate](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/services/network/network_context.cc)、[SQLitePersistentCookieStore](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/net/extras/sqlite/sqlite_persistent_cookie_store.cc)、[URLRequestHttpJob](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/net/url_request/url_request_http_job.cc)を通して、初期化・cookie取得・HTTP開始のcallback依存を追える。

APIがblockingであることはApple資料で、待機の影響がHTTPへ伝わる構造はChromiumソースで裏付ける。対象requestで実際にこの依存が停止したことは、同一試行の応答・API・network・描画の実測で確認する。

## 類似する公開報告と限界

[browser-use issue #5415](https://github.com/browser-use/browser-use/issues/5415)には、OS Keychainへのアクセス確認と起動待ち、mock条件での改善を報告した利用者の一次報告がある。既存profileのcookie復号を維持する必要性も述べられている。

これはAppleやChromiumによる対象問題の修正保証ではない。報告環境・ブラウザ版が異なり、対照では二つの引数を変更している。今回の一引数対照やHTTP開始前の停止と同じ機構を証明する資料としては使わない。

## 計画に加える確認

1. Safe Storageの実所属Keychain・検索順・重複するservice/account itemを秘密値を読まずに確認する。
2. file-basedのtrusted-app ACLとdata protectionのaccess groupを混同しない。access-group entitlement追加をfile-based itemへの対策として直ちに採用しない。
3. 独立ユーザー比較ではlogin項目の分離と共有Systemを区別し、同じ署名済みappで実測する。
4. 個別appの恒久許可は、原因調査を終えた後の承認された変更として試し、再起動・鍵の再利用・通常Keychainでのページ表示を確認する。
5. 以上の公開資料は対策を検討する根拠であり、現在のS0の完了条件や10月5日の証跡不足を代替しない。
