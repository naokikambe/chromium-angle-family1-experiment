# 作業ブランチの公開を制限する手順

## 現行ルールと承認範囲

2026-10-20、Ownerは`phase5-page-recovery`の公開条件から旧SHA一覧との照合を
外すことを明示的に承認しました。旧新SHA対応表・拒否一覧・そのchecksumは、
このブランチのpushの前提条件ではありません。過去の「欠落時は公開を停止する」
という条件を、この文書の固定起点・直線履歴の条件へ置き換えます。

承認済み公開HEAD `49b69c78861750b34ec533dfaa1fdbe3469fe9f2`を信頼の起点に固定します。
この起点自体の安全性を再証明したり、失われた一覧を復元・照合したりしたという
意味ではありません。旧SHA照合を取り除く承認と、起点以降の全mergeを拒否する
制限を区別してください。起点を自動的に現在のHEADへ更新してはいけません。

許可する更新は、公式repository
`https://github.com/naokikambe/chromium-angle-family1-experiment.git`の既存
`refs/heads/phase5-page-recovery`一件へのfast-forwardだけです。Main・他branch・
新規branch・tag・削除・force push・merge・release・PR・Issueは範囲外です。
通常の検証済みcommit/pushの委任は継続します。実機操作の個別承認条件は変えません。

## 1. 履歴・privacyの必須検査

`scripts/check-safe-push.py`は次の全条件を検査します。

- Gitから渡される更新行が一行で、更新元・更新先とも指定branchである。
- remote名は`origin`または専用経路が使うcanonical URLであり、URLは上記と完全一致する。
- old/new object IDが有効なcommitを指し、ゼロではない。新規作成・削除を拒否する。
- remote tipとcandidate双方が固定起点の子孫である。
- **起点から各tipまでの到達可能な全commitが、親をちょうど一つだけ持つ。**
  `--first-parent`だけの検査や、起点が祖先という条件だけでは許可しない。
  途中にあるmerge、treeがきれいなmerge、他の親も起点の子孫であるmergeも拒否する。
- remote tipがcandidateの祖先である。remote側にmergeが含まれていても拒否する。
- shallow、alternates、grafts、replacement refsや関連する履歴上書き環境変数がない。
- 追加される全commitの内容・メッセージ・author/committer情報について、既存の
  `check-publication-privacy.py --pre-push`を通す。途中で秘密情報を追加し、tipで
  消した履歴も検査する。Parentによる差分レビューも必要とする。

基準や必要objectが不在、入力不正、検査失敗なら拒否します。旧SHA一覧や対応表は
読み込みません。旧履歴のfetch/import、objectsのコピー、旧refの持込み、
alternates設定、旧branchの再公開を許可する変更ではありません。

## 2. 独立cloneと保全

既存の新cloneが独立していれば作り直しません。`pwd`、remote、HEAD、dirty状態、
適用`AGENTS.md`、common directory、shallow、alternates、grafts、replacement refsを
確認します。取得元は確認済みの公式GitHub remoteだけです。

新cloneの設定と既存hookは、変更前にrepository外のowner-only私的領域へ保全します。
未コミット変更・index・stash・refs・reflog・app・profile・証跡を保持し、
`reset --hard`、`checkout --`、`clean`で破棄しません。旧Gitのobjects・refs・reflog・
stash・bundleを新cloneへ持ち込みません。実機引継ぎ資料は必要ファイルだけ読み、
ディレクトリ全体を新cloneへコピーしません。

旧checkout・worktree・mirrorの設定変更やref整理は、この新cloneの担当範囲外です。
旧Gitのshared hookを上書きせず、新cloneとはhook配置を分離します。

## 3. 通常pushを常時無効にする

新cloneのeffective設定は次を満たす必要があります。全scope/include・URL rewrite・
複数値も確認し、不明な設定をglobal/system側で勝手に変更しません。

- remoteは`origin`のみで、fetch URLはcanonical URLのみ。
- originのpush URLは常に`disabled://phase5-safety-repair-required`のみ。
- `push.default=nothing`、`push.followTags=false`、`push.autoSetupRemote=false`、
  `remote.origin.mirror=false`。
- `remote.origin.push`の暗黙refspecとURL rewriteがない。

通常pushの失敗は意図した動作です。originのpush URLを恒久的にcanonical URLへ戻す
手順は廃止します。専用経路だけが検査後に固定URLと明示的refspecで公開します。
URL直指定や`--no-verify`を手動で使って専用経路を迂回してはいけません。

## 4. 永続的な専用公開経路

Gitはhookファイルが消失しているだけではpushを拒否しません。このため通常pushの
無効化を維持し、`scripts/safe-push.py`のレビュー済みコピーを、repository外の
永続的なowner-only `GUARD_DIR`へ配置します。一時領域に置きません。

同じdirectoryに次を置きます。新しいdirectoryを使い、既存の保管データは上書き
しません。新cloneの`core.hooksPath`もこの専用directoryに固定します。

- `safe-push.py`、`check-safe-push.py`、`check-publication-privacy.py`のレビュー済みコピー。
- `pre-push`、`pre-commit`、`commit-msg`のwrapper。全wrapperが新cloneの絶対pathを
  明示する。Pre-pushは同directoryのcheckerへremote引数とstdinを転送し、
  他の二つは既存privacy scannerを呼ぶ。新cloneのtracked `.githooks`だけでは
  restrictive policyにならない。
- `manifest.json`。Schemaは`schema`（整数1）、`repo`、`common_dir`、`anchor`、
  `files`だけ。前二つのpathは私的な絶対path、anchorは上記固定公開HEAD。
  `files`は六つのscript/wrapper名をキーにし、各ファイルのSHA-256を値にする。
  Manifest・全ファイル・directoryをowner-onlyにし、symlinkは使わない。

専用commandはmanifest・全ファイルの存在、型、所有者、権限、checksumを検査します。
新clone/common directoryのbinding、現在branch、clean状態、effective設定を検査し、
公式remoteの既存branch tipを読み取ります。履歴とprivacyを直接検査した後、
ファイル・設定・candidateを再確認します。必要なものが一つでも欠落・破損して
いればGit pushを呼びません。

```sh
python3 "$GUARD_DIR/safe-push.py" --dry-run
python3 "$GUARD_DIR/safe-push.py"
```

各commandは結果を確認してから次へ進みます。Wrapperは固定URL・固定refspecと
検証済みhook directoryでGitを呼び、force optionは使いません。検査中は同じcloneで
別のGit書込みを行いません。Remoteとの競合はhookと通常のFF検査で拒否します。
必要なremote commitがローカルに無ければ、公式originから取得して再検査します。
既に最新なら専用commandは検査後に更新なしで終了します。

Source変更でコピーの更新が必要になったら、parentが差分をレビューし、新しい
永続directoryへ全コピーとmanifestを組み立て、再検証してから切り替えます。
通常pushの無効化は維持します。欠落したguardを無視したり、checksumを自動的に
現在の内容へ更新したりしません。意図的なclient bypassを防ぐserver側制御の代替
ではありません。

## 5. 検証・公開

Phase 3B全fixtureはローカルで動かしません。ここでは公開guard専用の架空fixtureで、
直線FFの許可、全merge・non-FF・別起点・不正ref・新規作成/削除・tag・複数更新・
誤URL・履歴override・途中commitのprivacy違反を確認します。さらにmanifestや
hook/checkerの欠落・破損時に専用commandがpushを呼ばないことを確認します。

```sh
python3 scripts/test_safe_push.py
python3 scripts/test_safe_push_launcher.py
git diff --check
```

Parentのdiffレビュー後にstagingし、`python3 scripts/check-publication-privacy.py`を
実行してから通常commitします。設置済みguardの直接検査と専用commandのdry-runを
確認した後にだけ、同じ専用commandで指定branchへ公開します。検査結果、設定・
hookのバックアップ、実機証跡、私的pathはGitやCI出力へ転載しません。

## 6. 履歴資料とGC

旧SHA一覧や対応表が後で見つかっても私的資料として保持し、公開Gitへコピーしません。
歴史的workflowの実行refはrun記録で区別します。現在の文書内参照の確認に未復元の
対応表を必須条件とはしませんが、証拠がない対応関係を推測で書き換えません。

GC、参照削除、reflogの強制期限切れは今回実行しません。誤push防止のために履歴を
削除する必要はありません。旧Gitの設定変更、mirror保管専用化、GCも今回の担当
範囲外です。この文書は現行手順であり、個々の実機試験や設置検証の受入記録では
ありません。
