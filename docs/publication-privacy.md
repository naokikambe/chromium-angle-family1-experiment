# Publication privacy boundary

Public Git content and workflow artifacts must not contain personal data,
owner-environment details, or actual-device material. Do not publish usernames,
home paths, hostnames, non-loopback IP or MAC addresses, email addresses,
serials, UDIDs, signing team or certificate identities, Keychain ACL or item
results, raw device logs, profiles, cookies, authentication material,
passwords or passphrases, access/refresh/session tokens, API keys or client
secrets, private keys, recovery codes, screenshots, recordings, or device
receipts. Apply this rule to code, configuration, documentation, fixtures,
commit messages, and CI artifacts, logs, and summaries. Do not publish details
specific to the owner's environment, including the target device model. Public
upstream revision pins may be used as technical inputs. Exclude
owner-environment and actual-device data from Git and CI.

Public technical claims should be reproducible from tracked procedures, public
source pins, and synthetic inputs wherever feasible. Include the exact public
inputs, commands or procedure, and expected outcomes needed to repeat them. If
the tracked repository does not provide an end-to-end reproduction path, state
the technical gap neutrally and identify the smallest public input, procedure,
or artifact needed to close it, without pointing to non-public materials.
Public documentation must not state or imply that non-public information
exists, or disclose or imply where it is kept. Use reproducible summaries and
omit actual-device and personal data.

## Copyright and licensing boundary

Identify the author or source of every file considered for public release.
This includes source code and patches (including upstream context), documents
and quotations or translations, images, fonts, audio, video, fixtures,
generated outputs, binaries, and bundled dependencies. Public availability,
synthetic content, absent metadata, or generation by a tool does not establish
redistribution rights. The absence of a selected project-wide license is not
permission to reuse project material; do not add or change a project-wide
license without owner approval.

For third-party or derived material, record the source URL and immutable
revision or version, a content hash where practical, copyright holder, license
or other permission, modifications, required attribution, and any required
LICENSE or NOTICE files. Verify that the terms allow the intended public
redistribution and modifications. For generated assets, record source inputs
and generator/tool version and options, then verify rights to both. Record
relevant patent, codec, and trademark conditions separately from copyright
permission.
Do not include video files in a push unless their copyright and redistribution
license are confirmed; exclude files with unknown or incomplete rights.

Open-source material may be included when its applicable license permits the
intended use and redistribution and all license obligations are met. Include
required copyright notices, attribution, license texts, source code or source
offers, and other conditions for the distribution form. A license for one
component does not license unrelated files or the project as a whole.

Hold material with unknown or incomplete authorship, provenance, or
redistribution rights out of the public candidate until verified. Preserve
required notices.

Use clearly synthetic placeholders in source fixtures. Never use real local
values in tests, even when a test is intended to verify the privacy scanner.
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
to be replaced, prepare and review a fresh clean checkout; never rewrite
history or discard user data without explicit owner approval. For a new remote branch,
the hook fails closed by scanning the local branch's full reachable history.

The checker is a focused guard, not proof that every possible personal datum
has been recognized. A parent must review the staged diff and artifact paths
before publication. Do not add broad file, directory, or test exclusions to
make a scan pass. It recognizes selected token and private-key formats and
owner-supplied deny values, but cannot guarantee detection of arbitrary
passwords, tokens, or other secrets. Manual review of staged content remains
required.

Audit maintained documentation links and repository SHA references against
public source pins and run records. Use current source-tree counterparts where
appropriate, but distinguish them from the ref actually executed by an old
run. Do not publish owner-specific metadata. The privacy scanner does not
detect obsolete SHA references.

One exact labeled team-identifier exception covers the public Google signing
identity used by Chromium's upstream code-signing fixture. It does not exempt
team identifiers in other contexts, certificate identities, or any owner
identity. The source and tests keep this exception exact; never add a private
team identifier to it.

For this branch, the Owner-approved policy in
[safe-push-and-gc-procedure.md](safe-push-and-gc-procedure.md) additionally
requires a fixed approved anchor, single-parent history after that anchor,
and rejection of all post-anchor merges. Publication requires the approved
anchor and ancestry checks described in the procedure.
New remote branches are forbidden by the restrictive checker even though the
privacy scanner can inspect their full reachable history.

The tracked `.githooks` provide privacy scans only. Configure the reviewed
publication launcher and hook wrappers through the dedicated guard path
described in the safe-push procedure. Keep origin pushes disabled and use the
integrity-checked launcher for publication. Missing hooks or guard data must
stop that launcher before push. Do not include local paths or guard contents
in public output.
