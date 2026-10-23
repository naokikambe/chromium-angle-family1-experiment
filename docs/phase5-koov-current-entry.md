# 現行KOOVの起動入力と受入準備

この文書は [実機作業の一括引き継ぎ](phase5-device-completion-handoff.md) の工程Aで調査する起動入力と、工程Cの実施条件を補足する。旧実験計画のprofile複製手順や「結果の記録だけで完了」という条件を、今回の受入へ適用しない。

## 現行の起動方式

[公式の移行告知](https://www.koov.io/notices/487) は、旧Windows/macOS/ChromeOS版のアクセス終了を2026年3月31日としている。旧App IDやランチャーを、そのまま現行版の起動入力とみなさない。

[公式ダウンロードページ](https://www.koov.io/downloads) はPC版について最新版Chrome/Edgeでの利用を案内し、macOSでは「アプリをインストール」後にFinderでLogic LabのアイコンをDockまたはApplicationsへ移す手順を示している。[現在の公式要件](https://koov-support.sonyged.com/hc/ja/articles/115000925707) はmacOS 14以降と最新版Chrome/Edgeである。古い移行告知のmacOS 13要件を現行要件として使わない。実験Chromiumが公式ページに認識され、インストール導線を利用できるかは別途実測し、browserやOSの判定を偽装しない。

KOOV公式PC版のOS要件はmacOS 14以降である。公式ページのインストール結果がPWA形式かFinder配置型のアプリかを事前に断定せず、対象版の実際の登録・起動方式を確認する。ANGLE受入後に実験Chromiumで試す場合、その結果はこの実験での探索的確認であり、ベンダーサポートや公式要件への適合を意味しない。

以前の調査では、公式ページがChrome向けに公開PWA manifestを参照し、`/app/welcome`を起動先とするstandalone表示を指定していた。現行ダウンロードページはMac上のFinder配置手順も案内するため、この記録だけで現在の起動方式やApp IDを確定しない。通常タブの`/app`を開いただけでは、正しいKOOV起動方式の成否を判定できない。

工程Cでは、実験Chromiumの新しい専用profileから公式ダウンロードページを開き、対象版で表示されるインストール導線を確認する。インストールできた場合だけ、Finderまたはprofileに登録された実際のアプリ名・ID・起動方法を私的証跡へ記録し、同じprofileから起動する。歴史的な`kpmcfooelenggiklfmbljpognolignpg`と一致するとは仮定しない。対象Chromiumソースの`--app-id`処理や過去のmanifestだけから、登録済みアプリの存在や現行アプリの起動成功を推測しない。ページが対象browserを拒否した場合は、UA偽装やOS要件回避をせず、その互換境界を記録する。

[固定版の起動処理](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/chrome/browser/ui/startup/startup_browser_creator.cc) を、実際にインストールされたアプリ方式と照合する。開発・旧検証用の別ホストを本番入力へ転用せず、HTTP認証の要求を埋め込み値で回避しない。

## 工程Cへ進む前の条件

独自ANGLE版の署名・正常Keychain・ページ描画・暗号化cookie再起動、同じGPU PIDでの独自ANGLE/Metalロード、WebGL1 context・draw・readbackを成立させる。stockの通常GPU・独立profile3件の受入は別の未完了項目として追跡し、KOOV試験で置き換えない。インストール入力を確認したことも、KOOVの実画面や操作の受入へ数えない。

オーナーの認証入力と実画面の観察時間を用意する。既存profile・作品・資格情報は複製せず、新規の非機密テスト作品だけを使う。アカウントに既存作品が表示されても編集や移行の対象としない。新しいGUIユーザーやKeychainが必要なら、対象・影響・復帰方法への個別同意を得る。

## 埋め込み動画の優先診断

動画プレイヤーが黒いまま、または再生しない場合は、KOOVの長時間安定性試験より先に切り分ける。黒い表示だけでANGLE/WebGL障害やcodec障害と決めず、オーナーがプレイヤーの再生操作を行った同一試行を観測する。

同じ試行で、動画要素の`readyState`・`networkState`・`error.code`・`paused`・`currentTime`・`videoWidth`／`videoHeight`、リソース応答のstatus・`Content-Type`・`Content-Range`・`Accept-Ranges`・`Content-Disposition`、Chromium media pipelineのdecoder初期化・エラー・frame出力を対応付ける。`canPlayType()`の宣言結果だけで再生対応や実際のdecode成功を判定しない。URLパス・query、cookie、動画本文、ページ本文、未加工のmedia logは保存せず、必要な状態と許可したheaderだけを残す。

判定では、resource request／range応答、container・codec認識、decoder初期化、decoded frameの生成、動画面の合成・表示を順に分ける。受信・metadata・frameのいずれかが進まない場合と、frameは生成されるが画面が黒い場合を別の故障境界として扱う。KOOVのWebGL描画や3D操作の結果は動画再生の受入に流用しない。

### 2026-10-24 fixture A/Bの結果

提示されたMP4を埋め込んだloopback配信ページを、既存のstock版とFamily 1 ANGLE版の試験profileで確認した。両版とも再生を要求した後、30秒間`readyState=0`、`networkState=2`、動画寸法0、buffered range 0のままだった。動画要素は`loadstart`、`waiting`、`stalled`を出し、要素のエラーはなかった。CDP NetworkとResource Timingには動画のmedia request／responseやresource entryが記録されなかった。各ページから別途送ったHEAD-only要求はHTTP 200、`Content-Type: application/mp4`となり、CDPにも記録された。この診断では動画本文を保存していない。

両版とも`canPlayType("video/mp4")`は`maybe`、H.264 baseline／highとAACのqueryは空だった。`MediaSource.isTypeSupported()`もMP4/H.264/AACをfalse、WebM VP8/VP9をtrueと返した。Media domainにはdecoderやdecoded frameのpropertyが現れず、player error eventのerrors一覧も空だった。MP4の実codecは未確認だが、試験した両appはH.264/AAC対応を示さないため、提供MP4がそのcodecなら再生不能を説明できる。stock版とANGLE版に観測上の差はなかった。ただしdecoder初期化やframe合成より前で止まっているため、ANGLEが原因とも、ANGLE動画描画が正常とも判定できない。次は実際のmedia GET／range応答、container／codec、decoder初期化を確認してから動画面の合成経路を調べる。

## 一続きの確認と記録

1. 実験appの実パス・version・署名・profile・全引数と環境変数、登録されたPWA ID、起動したBrowser/GPU PIDを固定する。
2. 実KOOVのdocument・JS・fetch・必要な描画とオーナーの実画面を対応付ける。nonce付きfixture結果は別の証跡として保持する。
3. 黒画面または再生しない動画があれば、上記の優先診断を実施し、再生開始後の同一試行からmedia/network状態を対応付ける。
4. 非機密の新規テスト作品で画面遷移、ブロック編集、保存、再読込、必要な3D描画、resizeを確認する。WebGL2を要求する境界に達したら、ES2/WebGL1限定の実験能力との差として調べる。
5. 約30分の連続操作中にクラッシュ・context loss・白黒画面・表示破損・CPU/メモリ傾向を記録する。開始終了時刻だけで連続操作済みと判断しない。
6. 正常終了後に同じ専用profileで再起動し、テスト作品、基本操作、画面とKeychainアクセスを再確認する。毎回手動のKeychain応答が必要な条件は継続利用の受入としない。
7. USB/Bluetoothと機器転送は対象機器・操作への明示同意がある場合だけ行う。機器未試験でもソフトウェア確認の各項目は個別に報告し、機器連携へ拡張しない。

失敗時は起動方式、認証、HTTP、JS、要求されるWebGL機能、保存、再起動の最初の未完了境界を区別する。生ログ、画面、アカウント識別子、profileと機器識別子はローカル証跡に保持し、公開文書には再現可能な一般手順と入力revisionだけを記載する。
