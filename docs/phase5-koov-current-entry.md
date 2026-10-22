# 現行KOOVの起動入力と受入準備

この文書は [実機作業の一括引き継ぎ](phase5-device-completion-handoff.md) の工程Aで調査する起動入力と、工程Cの実施条件を補足する。旧実験計画のprofile複製手順や「結果の記録だけで完了」という条件を、今回の受入へ適用しない。

## 現行の起動方式

[公式の移行告知](https://www.koov.io/notices/487) は、旧Windows/macOS/ChromeOS版のアクセス終了を2026年3月31日としている。旧App IDやランチャーを、そのまま現行版の起動入力とみなさない。

[公式ダウンロードページ](https://www.koov.io/downloads) は現行PC版をChrome/Edgeからインストールする手順を案内している。[現在の公式要件](https://koov-support.sonyged.com/hc/ja/articles/115000925707) はmacOS 14以降と最新版Chrome/Edgeを示す。古い移行告知のmacOS 13要件よりも現在の要件を確認する。実験Chromiumでの動作は別途実測する。

KOOV公式PC版のOS要件はmacOS 14以降である。ANGLE受入後に実験ChromiumでPWAやソフトウェア動作を試す場合、その結果はこの実験での探索的確認であり、ベンダーサポートや公式要件への適合を意味しない。

調査時の公式ページは、対応するChrome UAに対して [公開PWA manifest](https://www.koov.io/manifests/add_home_screen_manifest.json) を参照した。その`id`と`start_url`は`/app/welcome`、`display`は`standalone`だった。公開ページのinstallボタンは`beforeinstallprompt`に応答し、インストールの承諾後に`/app/welcome`へ進む。サーバーが指定する条件では、通常タブの`/app`を制限する処理もある。このため、URLを通常タブで開いた結果だけでは、正しいKOOV起動方式の成否を判定できない。

工程Cでは、実験Chromiumの専用profileから公式ページでPWAを新規に準備し、そのprofileに登録された実際のWeb App IDを記録して起動する。歴史的な`kpmcfooelenggiklfmbljpognolignpg`と一致するとは仮定しない。対象Chromiumソースには`--app-id`処理があるが、登録済みアプリの存在やChrome Apps廃止の判定を伴う。引数の存在は、旧KOOVの起動成功を保証しない。

[固定版の起動処理](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/chrome/browser/ui/startup/startup_browser_creator.cc) を、実際にインストールされたアプリ方式と照合する。開発・旧検証用の別ホストを本番入力へ転用せず、HTTP認証の要求を埋め込み値で回避しない。

## 工程Cへ進む前の条件

stockの署名・通常Keychain・通常GPU・独立profile3件・暗号化cookie再起動と、独自ANGLE版の同じ受入、同じGPU PIDでの独自ANGLE/Metalロード、WebGL1 context・draw・readbackを成立させる。PWA入力を確認したことを、KOOVの実画面や操作の受入へ数えない。

オーナーの認証入力と実画面の観察時間を用意する。既存profile・作品・資格情報は複製せず、新規の非機密テスト作品だけを使う。アカウントに既存作品が表示されても編集や移行の対象としない。新しいGUIユーザーやKeychainが必要なら、対象・影響・復帰方法への個別同意を得る。

## 一続きの確認と記録

1. 実験appの実パス・version・署名・profile・全引数と環境変数、登録されたPWA ID、起動したBrowser/GPU PIDを固定する。
2. 実KOOVのdocument・JS・fetch・必要な描画とオーナーの実画面を対応付ける。nonce付きfixture結果は別の証跡として保持する。
3. 非機密の新規テスト作品で画面遷移、ブロック編集、保存、再読込、必要な3D描画、resizeを確認する。WebGL2を要求する境界に達したら、ES2/WebGL1限定の実験能力との差として調べる。
4. 約30分の連続操作中にクラッシュ・context loss・白黒画面・表示破損・CPU/メモリ傾向を記録する。開始終了時刻だけで連続操作済みと判断しない。
5. 正常終了後に同じ専用profileで再起動し、テスト作品、基本操作、画面とKeychainアクセスを再確認する。毎回手動のKeychain応答が必要な条件は継続利用の受入としない。
6. USB/Bluetoothと機器転送は対象機器・操作への明示同意がある場合だけ行う。機器未試験でもソフトウェア確認の各項目は個別に報告し、機器連携へ拡張しない。

失敗時は起動方式、認証、HTTP、JS、要求されるWebGL機能、保存、再起動の最初の未完了境界を区別する。生ログ、画面、アカウント識別子、profileと機器識別子はローカル証跡に保持し、公開文書には再現可能な一般手順と入力revisionだけを記載する。
