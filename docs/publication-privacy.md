# Publication privacy boundary

Public Git content and workflow artifacts must not contain personal or
actual-device evidence. The target hardware model and public upstream revision
pins are technical inputs and may remain public. Do not publish usernames,
home paths, hostnames, non-loopback IP or MAC addresses, email addresses,
serials, UDIDs, signing team or certificate identities, Keychain ACL or item
results, raw device logs, profiles, cookies, authentication material,
passwords or passphrases, access/refresh/session tokens, API keys or client
secrets, private keys, recovery codes, screenshots, recordings, or device
receipts. Apply this rule to code, configuration, documentation, fixtures,
commit messages, and CI artifacts, logs, and summaries. Keep that evidence
outside Git and do not copy it into CI.

Use clearly synthetic placeholders in source fixtures. Never use real local
values in tests, even when a test is intended to verify the privacy scanner.
The target model and fixed public source revisions are not private evidence.

Review the selected diff before staging. Then run
`python3 scripts/check-publication-privacy.py` after staging and before commit. The default scan reads the Git index rather than the working
tree, so it checks what a commit would contain. It also checks the configured
Git author and committer identities: use the public account alias as the name
and a GitHub noreply address as the email, never a personal real name. To
inspect a committed snapshot, pass `--tree <ref>`. Findings reveal only a file
path, line, and category; the matched value is never printed. Supply additional
private values with repeated `--deny-value` options when the owner provides
them. Do not put those values in command logs or public files.

The commit-message hook checks the proposed message; the pre-commit hook checks
staged blobs. The pre-push hook checks every commit
introduced by the requested ref update, including old commits whose sensitive
file was later removed from the branch tip. Do not merge or repush a
pre-cleanup history just because its current tree looks clean. If history needs
to be replaced, the parent must prepare and review a fresh clean checkout while
preserving the old work and evidence separately; never rewrite history or
discard retained data without explicit owner approval. For a new remote branch,
the hook fails closed by scanning the local branch's full reachable history.

The checker is a focused guard, not proof that every possible personal datum
has been recognized. A parent must review the staged diff and artifact paths
before publication. Do not add broad file, directory, or test exclusions to
make a scan pass. It recognizes selected token and private-key formats and
owner-supplied deny values, but cannot guarantee detection of arbitrary
passwords, tokens, or other secrets. Manual review of staged content remains
required.

When a reviewed old-to-new map is available after an approved history rewrite,
audit maintained documentation links and repository SHA references against it.
Use current source-tree counterparts where appropriate, but preserve historical CI
provenance through run IDs and run records; explicitly distinguish a current
counterpart from the ref actually executed by an old run. Keep the full mapping
private. The privacy scanner does not detect obsolete SHA references.

One exact labeled team-identifier exception covers the public Google signing
identity used by Chromium's upstream code-signing fixture. It does not exempt
team identifiers in other contexts, certificate identities, or any owner
identity. The source and tests keep this exception exact; never add a private
team identifier to it.

For this branch, the Owner-approved replacement policy in
[safe-push-and-gc-procedure.md](safe-push-and-gc-procedure.md) additionally
requires a fixed approved anchor, single-parent history after that anchor,
and rejection of all post-anchor merges. The private old-SHA list/map is no
longer a publication prerequisite. This does not repeat the old-SHA audit.
New remote branches are forbidden by the restrictive checker even though the
privacy scanner can inspect their full reachable history.

The tracked `.githooks` provide privacy scans only. Install dedicated reviewed
copies and wrappers in a durable owner-only directory outside public Git,
separate from old checkouts' hooks. Keep origin pushes disabled and use the
integrity-checked launcher for publication. Missing hooks or guard data must
stop that launcher before push. Never store required guard files in a
temporary directory or share them with preserved old repositories.
