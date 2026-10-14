# 古い履歴を誤って push しないための手順

この手順は、履歴整理後に `phase5-page-recovery` の作業を続けるための
推奨 runbook です。コマンドは手順の例であり、この文書作成時には実行して
いません。`CLEAN_REPO`、`OLD_REPO`、`PRIVATE_STATE`、`CLEAN_HOOKS`、
`ARCHIVE_HOOKS`、`EXPECTED_REMOTE_TIP`、`CLEAN_ANCHOR`、`CANDIDATE`、
`REMOTE_NAME`、`OLD_COMMITS_COUNT`、`OLD_COMMITS_SHA256` には Owner がレビューした
値を引用符付きで設定してください。`REMOTE_NAME` は inventory から選び、空欄に
しません。
履歴対応表、旧 SHA 一覧、設定バックアップ、作業データは公開リポジトリの
外にある private state とし、公開文書に記載しません。各コマンドが失敗したら
直ちに停止し、後続コマンドを実行しません。シェル全体への `set -e` や `exit`
は設定せず、各 step の結果を確認します。Code block 内のコマンドは一つずつ
実行し、成功を確認してから次へ進みます。まとめて shell script として流しません。

## 1. 事前条件と中止条件

- Owner がレビュー済みの old-to-new 対応表と、残す履歴・公開先 tip を確定
  していること。公開する対応表は作らず、private state 内で照合します。
- `PRIVATE_STATE` は新規の owner-only directory とし、既存の退避 data を
  上書きしないこと。`CLEAN_HOOKS` と `ARCHIVE_HOOKS` は分離した private
  directory とし、既存の shared hook directory を上書きしません。
- 作業中の Git 操作を止め、元 checkout と active worktree の場所、状態、
  共通 Git directory を確認できること。両者が同じ common directory を使う
  場合、repository-local config や hooks の変更が両方に作用します。
- 共有 Git directory、両 checkout の tracked/unstaged/untracked data、index、
  stash、refs、reflogs、設定、hook 配置を、復元可能な形で private state に
  別途保全します。bundle は参照先 refs の補助バックアップです。dirty file、
  untracked file、index、stash の復元状態、全 reflog/config/hook を単独で
  保証するものではありません。
- backup が読めない、元と active worktree の関係が不明、old-to-new 対応表が
  不足、公開先が想定と違う、clean clone に既知の旧履歴が混在、または
  validation に失敗したら停止します。停止時は元 checkout や refs を直さず、
  private backup と記録を保ったまま Parent に戻します。

Owner が値を設定した後、以下の inventory は private state にだけ保存します。
出力を issue、chat、public log に貼りません。

```sh
: "${CLEAN_REPO:?Owner must set CLEAN_REPO}"
: "${OLD_REPO:?Owner must set OLD_REPO}"
: "${PRIVATE_STATE:?Owner must set PRIVATE_STATE}"
: "${CLEAN_HOOKS:?Owner must set CLEAN_HOOKS}"
: "${ARCHIVE_HOOKS:?Owner must set ARCHIVE_HOOKS}"
: "${EXPECTED_REMOTE_TIP:?Owner must set EXPECTED_REMOTE_TIP}"
: "${CLEAN_ANCHOR:?Owner must set CLEAN_ANCHOR}"
: "${CANDIDATE:?Owner must set CANDIDATE}"
: "${REMOTE_NAME:?Owner must set REMOTE_NAME}"
: "${OLD_COMMITS_COUNT:?Owner must set OLD_COMMITS_COUNT}"
: "${OLD_COMMITS_SHA256:?Owner must set OLD_COMMITS_SHA256}"

test ! -e "$PRIVATE_STATE"
```

上の existence check が成功した後にだけ、新規 private directory を作ります。

```sh
(umask 077 && mkdir -m 700 "$PRIVATE_STATE")
```

以降のコマンドは一つずつ実行し、その都度 status を確認します。

```sh

git -C "$OLD_REPO" status --porcelain=v2 --branch --untracked-files=all \
  > "$PRIVATE_STATE/status.txt"
git -C "$OLD_REPO" worktree list --porcelain \
  > "$PRIVATE_STATE/worktrees.txt"
git -C "$OLD_REPO" show-ref --head \
  > "$PRIVATE_STATE/refs.txt"
git -C "$OLD_REPO" reflog show --all --date=iso \
  > "$PRIVATE_STATE/reflogs.txt"
git -C "$OLD_REPO" stash list --date=iso \
  > "$PRIVATE_STATE/stashes.txt"
git -C "$OLD_REPO" config --local --show-origin --list \
  > "$PRIVATE_STATE/local-config.txt"
git -C "$OLD_REPO" config --show-origin --show-scope --list \
  > "$PRIVATE_STATE/effective-config.txt"
git -C "$OLD_REPO" remote -v \
  > "$PRIVATE_STATE/remotes-and-urls.txt"
git -C "$OLD_REPO" remote \
  > "$PRIVATE_STATE/remotes.txt"
git -C "$OLD_REPO" rev-parse --path-format=absolute --git-common-dir \
  > "$PRIVATE_STATE/common-dir.txt"
git -C "$OLD_REPO" bundle create "$PRIVATE_STATE/all-refs.bundle" --all \
  > "$PRIVATE_STATE/bundle.stdout" 2> "$PRIVATE_STATE/bundle.stderr"
```

`local-config.txt` や remote URL に秘密が含まれていないか private 側で確認
します。bundle に加えて、Owner が inventory した両 worktree と common Git
directory を、ACL/permission を保った private backup に保存し、読み戻し可能
か確かめます。Tracked changes、index changes、untracked file の内容は、bundle
には含まれません。これらを捨てたり stash/pop したりせずに保全できない場合は
停止します。

`PRIVATE_STATE` は空であることを確認した新規 directory として準備します。
Inventory/config 出力は元 checkout と active worktree のそれぞれで取り、
private に保管します。全 config scope と include、common config、worktree
override、すべての hook path/contents、全 remote と effective push URL/refspec/
mirror/URL rewrite を含めます。人が読める inventory だけでなく、actual common
config、worktree config、system/global config、参照された各 hook directory の
contents も private backup に保存します。秘密を含む可能性があるため、backup
は public repository 外に置き、permission を制限します。

## 2. 独立した clean clone を作る

新しい network clone は public remote から直接作ります。古い checkout、local
path、reference clone、shared objects、alternates、shallow clone を使いません。
作成時から origin push URL を無効にし、restrictive hook の実装・レビュー・
synthetic validation が終わるまで disabled のままにします。

```sh
test ! -e "$CLEAN_REPO"
git clone -c push.default=nothing \
  -c remote.origin.pushurl=file:///dev/null \
  --single-branch --branch phase5-page-recovery --no-tags \
  https://github.com/naokikambe/chromium-angle-family1-experiment.git \
  "$CLEAN_REPO"
git -C "$CLEAN_REPO" fetch --no-tags origin phase5-page-recovery
```

Owner は clone 後に、origin URL がこの GitHub repository の fetch URL と一致
すること、clone が shallow でないこと、objects alternates が無いこと、common
Git directory が `OLD_REPO` と独立していることを確認します。`--single-branch`
は取得対象を絞りますが、後から明示的な refspec を指定する push まで禁止する
ものではありません。Git の [`clone` option reference](https://git-scm.com/docs/git-clone)
を参照してください。

全 effective config scope (system/global/local/worktree/includes)、すべての remote,
push URL/refspec、mirror、default push remote と URL rewrite を private 側で照合
します。想定外の値や inherited push 設定が見つかったら停止します。Local
`remote.origin.push` を消すだけでは inherited refspec を消せません。

Clone の remote-tracking tip が、事前に Owner がレビューして private に記録した
`EXPECTED_REMOTE_TIP` と完全一致することを確認します。Clone 時点の remote tip
を自動的に受け入れてはいけません。不一致なら停止します。Private 対応表にある
旧 commit が accepted history や push 候補の祖先でないことを検査します。
確認結果だけを残し、旧 SHA や対応表は private に保ちます。Reviewed
`CLEAN_ANCHOR` が push candidate の祖先であることを確認します。これは旧履歴の
混入検査の代わりにはなりません。古い履歴を含む merge も anchor の子孫になり
得るため、anchor lineage と旧履歴非混入の両方を検証します。検査対象は tip だけ
でなく、push で新たに到達可能になる全 commit です。

Private old-commit list は parent-reviewed 対応表から作成し、一行一つの lowercase
40-character SHA とします。Expected count と checksum は同じ private 対応表から
記録します。空、形式不正、期待 count/checksum 不一致なら fail closed で停止します。
Accepted tip と candidate の双方について reachability
intersection を private に計算します。どちらか一方でも intersection が空で
なければ停止し、ID は public に出しません。

```sh
test "$(git -C "$CLEAN_REPO" rev-parse refs/remotes/origin/phase5-page-recovery)" \
  = "$EXPECTED_REMOTE_TIP"
git -C "$CLEAN_REPO" merge-base --is-ancestor \
  "$CLEAN_ANCHOR" "$CANDIDATE"
test -s "$PRIVATE_STATE/old-commits.txt"
awk 'NF != 1 || length($0) != 40 || $0 !~ /^[0-9a-f]+$/ { bad=1 } END { exit (bad || NR == 0) }' \
  "$PRIVATE_STATE/old-commits.txt"
wc -l "$PRIVATE_STATE/old-commits.txt" > "$PRIVATE_STATE/old-commits.count"
test "$(awk '{print $1}' "$PRIVATE_STATE/old-commits.count")" = "$OLD_COMMITS_COUNT"
shasum -a 256 "$PRIVATE_STATE/old-commits.txt" > "$PRIVATE_STATE/old-commits.sha256"
test "$(cut -d ' ' -f 1 "$PRIVATE_STATE/old-commits.sha256")" = "$OLD_COMMITS_SHA256"
git -C "$CLEAN_REPO" rev-list refs/remotes/origin/phase5-page-recovery \
  > "$PRIVATE_STATE/accepted-reachable-raw.txt"
sort -u "$PRIVATE_STATE/accepted-reachable-raw.txt" \
  > "$PRIVATE_STATE/accepted-reachable.txt"
git -C "$CLEAN_REPO" rev-list "$CANDIDATE" \
  > "$PRIVATE_STATE/candidate-reachable-raw.txt"
sort -u "$PRIVATE_STATE/candidate-reachable-raw.txt" \
  > "$PRIVATE_STATE/candidate-reachable.txt"
sort -u "$PRIVATE_STATE/old-commits.txt" > "$PRIVATE_STATE/old-commits-sorted.txt"
comm -12 "$PRIVATE_STATE/old-commits-sorted.txt" \
  "$PRIVATE_STATE/accepted-reachable.txt" \
  > "$PRIVATE_STATE/accepted-old-intersection.txt"
comm -12 "$PRIVATE_STATE/old-commits-sorted.txt" \
  "$PRIVATE_STATE/candidate-reachable.txt" \
  > "$PRIVATE_STATE/candidate-old-intersection.txt"
test ! -s "$PRIVATE_STATE/accepted-old-intersection.txt"
test ! -s "$PRIVATE_STATE/candidate-old-intersection.txt"
```

## 3. 新 clone の push 設定を制限する

Public account alias と GitHub noreply email を設定します。Hook は別々の private
directory に置く計画にし、clean clone と archive clone の間で共有しません。
Tracked `.githooks` や既存 hook directory を上書きせず、pre-commit と
commit-msg の privacy scanner を維持する reviewed wrappers を用意します。これら
の wrapper と restrictive pre-push hook が未実装/未検証の間は push URL を
無効のままにします。

```sh
git -C "$CLEAN_REPO" config --local user.name "$PUBLIC_ACCOUNT_ALIAS"
git -C "$CLEAN_REPO" config --local user.email "$GITHUB_NOREPLY"
git -C "$CLEAN_REPO" config --local push.default nothing
git -C "$CLEAN_REPO" config --local push.followTags false
git -C "$CLEAN_REPO" config --local push.autoSetupRemote false
git -C "$CLEAN_REPO" config --local remote.origin.mirror false
if git -C "$CLEAN_REPO" config --local --get-all remote.origin.push >/dev/null; then
  git -C "$CLEAN_REPO" config --local --unset-all remote.origin.push
fi
```

Restrictive hook が別途実装・レビュー・synthetic validation 済みになった後に
限り、privacy hooks と restrictive policy を連鎖実行する private `CLEAN_HOOKS`
を設定します。既存 tracked hook directory は上書きしません。

```sh
git -C "$CLEAN_REPO" config --local core.hooksPath "$CLEAN_HOOKS"
```

確認項目:

- `origin` の fetch URL は指定 repository のみで、effective push URL は
  `file:///dev/null` だけです。mirror 設定や default push refspec はなく、全 scope
  で unexpected inherited config が残っていません。
- `push.default=nothing` により、refspec を省略した通常 push は失敗します。
  それでも明示的な push は可能なので、これは単独の安全策ではありません。
- `core.hooksPath` は clean clone 専用の `CLEAN_HOOKS` を指し、pre-commit と
  commit-msg privacy scans が維持されることを確認します。
- restrictive hook が実装・レビュー・synthetic validation 済みになるまで
  `remote.origin.pushurl=file:///dev/null` を解除しません。
- workflow/status の各 SHA は public run provenance を保つための記録です。
  old-to-new 対応表や private denial values を public config、hook、文書に複製
  しません。

### Restrictive pre-push implementation

`scripts/check-safe-push.py` は制限の実装です。`scripts/test_safe_push.py` は
独立した架空 repository で検証します。実装があることだけで、ある clone の
hook が導入・受入済みになったとは扱いません。Parent が diff と focused tests
をレビューし、private wrapper と情報を設定し、実際の hook と dry-run を検証
する必要があります。Git の push 設定は
[`git-config`](https://git-scm.com/docs/git-config) の system/global/local
precedence に従うため、effective configuration 全体を確認します。Hook は
既存 privacy scan を維持し、以下を fail closed で拒否します。

- destination が指定 GitHub repository 以外、または remote ref が既存の
  `refs/heads/phase5-page-recovery` 以外。
- branch creation/deletion、tag 更新、他 branch、non-fast-forward 更新。Hook は
  pre-push の old/new object IDs から non-fast-forward を判定します。実際の FF
  update に付けた `--force` option 自体は hook から判定できないため、force 系
  option の使用は常に禁止します。
- private old-SHA 対応表や履歴検査用 metadata が読めない、壊れている、または
  判定できない場合。
- 更新後 history のどこかに対応表上の旧 commit が含まれる場合。

許可条件には「reviewed clean anchor lineage」と「旧履歴の祖先が無い」の両方が
必要です。Anchor だけを許可リストにしてはなりません。Pre-push hook は標準
入力から更新対象 ref を得られ、拒否時は push を中止できますが、`--no-verify`
で skip できます。Destination URL を直接指定すると named remote の push URL 制限
を迂回するため、直接 URL を使いません。Git の
[`githooks` pre-push specification](https://git-scm.com/docs/githooks#_pre_push)
を参照してください。Client hook は強制境界ではないため、必要なら remote-side
branch protection を別途レビュー・承認します。

## 4. Push 前 validation と clean clone の有効化

Real remote を変更せず、local-only synthetic repositories で restrictive hook を
検証します。Allowed の fast-forward 以外はすべて拒否されることを確認します。

- clean history の既存 branch への fast-forward: 許可候補。
- no-refspec push: `push.default=nothing` による config/integration check で拒否
  されること。これは hook の stdin だけでは検出できません。
- branch creation/deletion、tag push、別 branch: hook で拒否。
- old commit を含む intermediate commit を merge した履歴: tip が clean でも拒否。
- non-fast-forward update、間違った remote URL、壊れた/欠落した private map: 拒否。
  `--force` と `--force-with-lease` は常に使用しません。
- 対応表上の旧 history を除いた clean synthetic history: その他の条件も満たす
  場合だけ許可候補。

Synthetic tests が通った後、clean clone の private `CLEAN_HOOKS` を有効にし、
origin push URL を canonical URL に戻します。全 effective config が意図どおり
であることを確認し、許可された existing branch への明示 refspec で dry-run
します。

```sh
git -C "$CLEAN_REPO" config --local core.hooksPath "$CLEAN_HOOKS"
git -C "$CLEAN_REPO" config --local --replace-all remote.origin.pushurl \
  https://github.com/naokikambe/chromium-angle-family1-experiment.git
git -C "$CLEAN_REPO" push --dry-run origin \
  refs/heads/phase5-page-recovery:refs/heads/phase5-page-recovery
```

Dry-run に想定外 refs、旧履歴、non-fast-forward が現れる、effective URL が
canonical URL と一致しない、hook/lineage check が不明、またはいずれかの
command が失敗した場合は停止します。この runbook は real remote update を行い
ません。実際の publishing は既存の Owner-authorized scope に従い、dry-run 後に
通常作業を始める clone は `CLEAN_REPO` とします。Archive clone から push しません。

## 5. 旧 shared clone を archive-only にする

Clean clone が独立性・tip・lineage・privacy hook の確認を通過した後、元 checkout
と active worktree が共有している旧 repository に対してのみ行います。共通
config に触るため両 worktree に作用することを確認し、事前に全 config scopes と
hook 状態を保全してください。旧 checkout だけでなく、known audit mirror が
あれば各 repository を別々に扱います。すべての configured remote を private
inventory から列挙して push URL を無効化し、effective push URL が
`file:///dev/null` のみであることを検証します。Inherited push URL が残るなど
明確に無効化できない場合は global/system config を勝手に変更せず停止します。

Reviewed privacy checks を保つ wrappers と、毎回拒否する `pre-push` hook を
`ARCHIVE_HOOKS` に別途配置し、hook ごとの repository-local config を設定します。
shared hook directory は変更せず、各 archive repository の配置と effective URLs
を確認します。

```sh
git -C "$OLD_REPO" config --local --replace-all \
  "remote.${REMOTE_NAME}.pushurl" file:///dev/null
git -C "$OLD_REPO" config --local core.hooksPath "$ARCHIVE_HOOKS"
```

Run the pushurl command separately for each inventoried remote and validate that its
effective push URL is only `file:///dev/null`. If inherited push URLs remain, stop; do not
alter global/system config to mask the problem. No existing `pre-commit` or `commit-msg`
scanner is overwritten or weakened. The archive pre-push hook keeps any existing privacy
scan and then unconditionally rejects. Fetch URLs, refs, stash, dirty/untracked files,
apps, and evidence remain untouched. “Archive-only” describes operating policy; do not
chmod or otherwise mutate retained files.

元 clone は「正しい push 先」として再利用しません。古い履歴を clean clone に
戻す、branch を merge/cherry-pick する、remote push URL を再有効化するのは、別の
明示的なレビュー・承認なしに行いません。

## 6. Rollback と GC の扱い

誤設定があれば、レビュー済み private backup から該当する config/hook だけを
復元します。Clean clone に旧 refs や old history を戻さず、復元後に origin URL、
push 設定、hooks と履歴 lineage を再検査します。元 clone に切り替えれば保存済み
作業ファイルを維持できますが、push を再度有効にするには意図的な別手順が必要
です。

誤 push 防止に GC は不要です。推奨は古い repository と private backup を archive
のまま残すことです。通常の `git gc` も、全 Git process が停止し、backup と
read-only reachability inventory を確認した後に限り、別の保守作業として判断
します。Reflog expiration と unreachable object の prune は復元余地を狭めます。
`--expire=now`、`--prune=now`、`--expire=all` は日常手順として実行しません。
古い履歴の完全削除は、削除対象 ref と reflog 保持期間を明記した別の Owner
承認なしには行いません。Git は一般に直接の `prune` より `gc` を使うよう案内し、
reflog には既定の保持期間があります ([`git gc`](https://git-scm.com/docs/git-gc),
[`git reflog`](https://git-scm.com/docs/git-reflog))。

この文書は推奨手順です。Clone、config/hook 更新、push、GC、または private
evidence の操作を実施した記録ではありません。

## Private metadata and wrapper contract

The restrictive checker accepts `--metadata PRIVATE_METADATA --mapping PRIVATE_MAP`
and the two pre-push arguments supplied by Git. Keep both files outside public Git.
Metadata has exactly `clean_anchor`, `old_commits`, `old_commits_count`,
`old_commits_sha256`, and `mapping_sha256`. The old list is nonempty, unique,
lowercase SHA-40 strings; its checksum covers each entry plus LF in array order.
The mapping is ASCII TSV with two SHA-40 fields per line and unique old-side keys.
The denial set must equal every mapping key whose new value differs. An unchanged
reviewed baseline is not a rewritten old commit. Validate the original reviewed
map and reachability audit before deriving this representation; do not accept an
intermediate preparation map as the final publication map.

Use a dedicated private directory for reviewed checker/scanner copies and wrappers.
The pre-push wrapper calls the checker with fixed private metadata/map paths and
forwards Git's remote arguments and stdin. The checker invokes the existing privacy
scanner for all introduced commits, including messages and author/committer data.
Pre-commit and commit-msg wrappers retain the same scanner with an explicit repo
root. Preserve their previous configuration before changing `core.hooksPath`.
A missing dependency or unreadable private information must reject the operation.

An up-to-date Git dry-run may supply no ref updates to a hook. The checker rejects
empty input; separately exercise it with the reviewed existing ref's old/new IDs
before interpreting a network dry-run. Tests and dry-run do not publish a ref.
Client hooks can still be bypassed deliberately and do not replace server controls.

When correcting obsolete workflow inputs, use verified current public counterparts
and distinguish them from the revision actually used by historical runs. Do not
copy the private mapping into workflow files or dispatch historical workflows as
part of reference maintenance. Reference maintenance alone does not restore missing
support scripts or establish workflow readiness. The scope of old-repository configuration changes
and GC remains subject to the current Owner instruction.
