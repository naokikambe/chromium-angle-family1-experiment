# 現行KOOVの起動入力と受入準備

この文書は、Chrome for Testing 154.0.8037.0 + Family 1 ANGLE revision `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`を使うKOOV実験の起動入力と受入条件を補足する。Chromiumだけで行った動画・codec診断は過去の比較であり、現行KOOVの受入経路ではない。stock Chromium／Keychain復旧は別トラックとして扱う。

## 現行の起動方式

[公式の移行告知](https://www.koov.io/notices/487) は、旧Windows/macOS/ChromeOS版のアクセス終了を2026年3月31日としている。旧App IDやランチャーを、そのまま現行版の起動入力とみなさない。

[公式ダウンロードページ](https://www.koov.io/downloads) はPC版について最新版Chrome/Edgeでの利用を案内し、macOSでは「アプリをインストール」後にFinderでLogic LabのアイコンをDockまたはApplicationsへ移す手順を示している。[現在の公式要件](https://koov-support.sonyged.com/hc/ja/articles/115000925707) はmacOS 14以降と最新版Chrome/Edgeである。古い移行告知のmacOS 13要件を現行要件として使わない。今回のKOOV対象はChrome for Testing 154であり、公式要件への適合やベンダーサポートを意味しない。

KOOV公式PC版のOS要件はmacOS 14以降である。公式ページのインストール結果がPWA形式かFinder配置型のアプリかを事前に断定せず、Chrome for Testing 154で実際に登録された起動方式を確認する。今回のChrome + ANGLE実験結果は探索的確認であり、ベンダーサポートや公式要件への適合を意味しない。

以前の調査では、公式ページがChrome向けに公開PWA manifestを参照し、`/app/welcome`を起動先とするstandalone表示を指定していた。現行ダウンロードページはMac上のFinder配置手順も案内するため、この記録だけで現在の起動方式やApp IDを確定しない。通常タブの`/app`を開いただけでは、正しいKOOV起動方式の成否を判定できない。

KOOVの起動確認では、Chrome for Testing 154の専用profileから公式ダウンロードページを開き、表示されるインストール導線を確認する。インストールできた場合は、Finderまたはprofileに登録された実際の起動方式を同じprofileから起動する。過去のmanifestやApp IDだけから現在の起動方式や起動成功を推測しない。ページが対象browserを拒否した場合は、UA偽装やOS要件回避をせず、その互換境界を記録する。

Chrome for Testing 154の[固定source revision `e967b7961d80199276ce493904c95f5fbbc42fca`](https://chromium.googlesource.com/chromium/src/+/e967b7961d80199276ce493904c95f5fbbc42fca/chrome/browser/ui/startup/startup_browser_creator.cc)を、実際にインストールされたアプリ方式と照合する。開発用の別hostを入力へ転用せず、HTTP認証を埋め込み値で回避しない。

## KOOV受入の確認条件

Chrome for Testing 154 + Family 1 ANGLEの署名・正常Keychain・ページ描画・暗号化cookie再起動、同じGPU processでのANGLE/Metalロード、WebGL1 context・draw・readbackを確認する。stock Chromiumの通常GPU・独立profile3件の受入は別トラックとして追跡する。インストール入力を確認したことも、KOOVの実画面や操作の受入へ数えない。

オーナーの認証入力と実画面の観察時間を用意する。既存profile・作品・資格情報は複製せず、新規の非機密テスト作品だけを使う。アカウントに既存作品が表示されても編集や移行の対象としない。新しいGUIユーザーやKeychainが必要なら、対象・影響・復帰方法への個別同意を得る。

## 過去の合成動画・codec比較（現行KOOVの受入対象外）

以下はstock／Family 1 Chromiumでの動画診断とChrome for Testing単体の比較記録である。いずれも履歴資料で、KOOV用途でChromium診断を再開せず、成功・失敗をChrome for Testing 154 + Family 1 ANGLEの受入へ流用しない。

### 2026-10-24 Chromium fixture A/Bの結果

2026-10-24の合成素材による比較では、stock ChromiumとFamily 1 ANGLE版の両方がH.264 Constrained Baselineを`error.code=4`（`MEDIA_ERR_SRC_NOT_SUPPORTED`）で拒否し、`readyState=0`、動画寸法0、decoded frame 0となりました。両版の`canPlayType("video/mp4")`は`maybe`、明示的なH.264 baseline queryとMP4/H.264の`MediaSource.isTypeSupported()`はfalse、WebM VP8/VP9はtrueでした。一方、合成VP8は両版で`readyState=4`、`error.code=0`、320×180、buffered range 1となり、再生時間とdecoded frameが進みました。この比較はH.264の失敗がFamily 1固有でないことを示しますが、すべてのChromium buildや実KOOV素材のcodec／表示を結論しません。

### Chrome for Testing単体との過去の合成codec比較

追加の対照として、Chrome for Testing公式配布の154.0.8037.0 macOS x64 artifactを用い、同一の合成H.264 Constrained Baseline素材と合成VP8素材を試しました。専用profileのheadless試験で、プロジェクト固有のANGLE引数、Family 1 opt-in環境変数、DYLDライブラリ注入はありません。Chrome内蔵の標準描画スタックは使われており、ANGLE自体を無効にした比較ではありません。

Chrome for TestingはH.264素材で`canPlayType`を`probably`、MediaSource対応を`true`と報告し、`readyState=4`、`error.code=0`、320×180、decoded frame 8で再生を開始しました。VP8もdecoded frameを確認しました。対して同じH.264素材は前項のChromium stock版・Family 1 ANGLE版の両方で`error.code=4`、decoded frame 0となり、両版の明示的H.264判定とMediaSource対応はありませんでした。Chromium公式のcodec一覧もH.264/AVCをGoogle Chrome限定のproprietary video codecとして分類しています（[Audio/Video codec support](https://www.chromium.org/audio-video/)）。

今回の三者比較ではChromium stock版とFamily 1 ANGLE版が同じH.264失敗を示し、Chromeとの差はcodec構成・build brandingの違いに整合します。ただし差の原因をcodec構成やANGLEの単独要因に特定できません。Chrome for Testingの基準revisionは1689415、対象Chromium snapshotは1689422で、source revisionは一致しません。CfT試験はheadlessであり、画面合成、実KOOV内の動画再生、持続再生の受入を証明しません。合成fixtureの結果を実KOOV動画のcodecや再生状態へ外挿しません。公開記録にはURL・本文、個人情報、実機固有値、未加工の素材・通信データ、ローカルパスを含めません。

## 現行対象：2026-10-25 Chrome for Testing 154 + Family 1 ANGLEの動画・WebGL確認

画面ありの比較では、Chrome for Testing公式配布のmacOS x64 artifact（154.0.8037.0、revision position 1689415、source revision `e967b7961d80199276ce493904c95f5fbbc42fca`）に、Family 1 ANGLE public revision pin `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`を組み合わせて確認しました。合成8秒・無音のH.264 Constrained BaselineとVP8は、実際の再生ボタン操作後にどちらも再生が進み、再生promiseが解決し、media errorはありませんでした。合成fixtureの測定では、再生時間約5.01秒／80 decoded framesと約7.02秒／111 decoded framesを確認し、各採取でdropped frameは1でした。WebGL1 fixtureもshader compile/link、draw、readbackを通過し、期待pixel `[0,160,0,255]`を返しました。GPU processにはFamily 1向けアプリbundle内のANGLE EGL/GLESライブラリ名とMetalがmapされていました。これは合成素材での自動計測で、音声や実KOOV素材のcodec・frame数を測った結果ではありません。runtime mappingは確認しましたが、実行したANGLE libraryのsource revisionやhashを独立に証明するものではありません。

同じChrome + Family 1 ANGLE構成でオーナーがKOOVを操作し、動画再生と3D操作に目立った問題はなかったと報告しました。KOOV画面の再生は自動計測していないため、実素材のcodec、frame数、WebGL callや描画値は未確認です。オーナーの方針として、KOOV用途ではChromiumの動画問題の追究を止め、Chromeのcodec構成を使い、この実験ではFamily 1 ANGLEを保持します。この判断は今回の実験構成に限り、Chromium全般またはChrome全般についての互換性保証ではありません。

KOOVの登録済みPWAの通常起動、作品の保存・再読込、約30分の継続操作、正常終了後の再起動、音声、およびUSB／Bluetooth機器連携は未確認です。したがって動画と3Dの肯定的な実操作報告は大きな進展ですが、KOOV全体の正式な受入完了とは区別します。

上記は今回の構成で得た測定結果であり、第三者が公開入力から一連の確認を再現できる手順ではありません。再現に必要な最小の公開入力は、再配布可能な合成メディアfixtureまたは権利条件を明記した生成手順、CfT artifactの取得URLとSHA-256、ANGLE build revisionとartifact hash、組み込み手順、利用者自身のidentityで行う初回署名手順です。KOOV受入も未完了です。

合成media/WebGL計測runnerと実行方法は[Chrome for Testing probe](../scripts/chrome-media-webgl/README.md)に記録しました。runnerは利用者が権利確認済みと申告するfixtureを受け取り、入力hashを照合しますが、fixtureの来歴やlicense自体は検証しません。

## 現行対象での受入確認と記録

1. Chrome for Testing 154.0.8037.0とFamily 1 ANGLE revision `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`を対象とし、version、公開source revision、専用profile、登録方式を記録する。実機固有pathやPIDは公開記録へ含めない。
2. 実KOOVのdocument・JS・fetch・必要な描画とオーナーの実画面を対応付ける。nonce付きfixture結果とKOOVの実操作観察は別々に判定する。
3. 動画または3Dが現行のChrome + ANGLE構成で失敗した場合は、その構成と最初に確認できた失敗境界を記録する。Chromium-only media-pipeline診断は再開せず、過去のChromium比較を現行結果と混同しない。
4. 非機密の新規テスト作品で画面遷移、ブロック編集、保存、再読込、必要な3D描画、resizeを確認する。WebGL2を要求する境界に達したら、ES2/WebGL1限定の実験能力との差として調べる。
5. 約30分の連続操作中にクラッシュ・context loss・白黒画面・表示破損・CPU/メモリ傾向を記録する。開始終了時刻だけで連続操作済みと判断しない。
6. 正常終了後に同じ専用profileで再起動し、テスト作品、基本操作、画面とKeychainアクセスを再確認する。毎回手動のKeychain応答が必要な条件は継続利用の受入としない。
7. USB/Bluetoothと機器転送は対象機器・操作への明示同意がある場合だけ行う。機器未試験でもソフトウェア確認の各項目は個別に報告し、機器連携へ拡張しない。

失敗時は起動方式、認証、HTTP、JS、要求されるWebGL機能、保存、再起動の最初の未完了境界を区別する。公開記録には再現可能な一般手順、公開入力revision、期待結果と限界を記し、個人情報、実機固有値、未加工の素材・通信データ、ローカルパスを含めません。
