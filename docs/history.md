# History and migration scope

## Repository migration

The former repository combined Chrome/Chromium experiments, CI probes, and browser recovery work. The maintenance migration narrowed the maintained role to exact Chrome-to-Chromium-to-ANGLE source mappings, reviewed Family 1 patches, fixed build recipes, unsigned library candidates, and owner-run local tools.

The maintenance tree was introduced in commit `37bd6d9d3dd122b2373a8573f5c4646c88f43d4a` and merged by PR #2 at `84594c238ae9e55285caf153f5af9772a1067a26`. It moved the retained CDP and media/WebGL probes under `src/probes`, preserved the Chrome 156 source pins and ANGLE patch, and removed phase-specific workflows and handoff material that were no longer part of the maintenance path. Those removals affected the current tree; they did not rewrite Git history or delete old workflow runs, artifacts, or branches.

PR #3 added the Chrome 158 candidate and corrected artifact redirect handling. It was merged at `5ba61b9f043905cf0f67ef0449a4781f1bf22055`. It also updated pull request validation to run synthetic, privacy, and safe-push fixture checks before full 156 and 158 builds for same-repository PRs; fork PRs remained synthetic-only. The monitor schedule stayed guarded to `main`. See [automation operations](automation-operations.md) for the current workflow description.

## License and provenance repair

The migration did not carry forward the project-authored root `LICENSE` from commit `6fc46f29131fbbf623986908c500622824350c47`. The migration's published documentation later described that absence as intentional. That conclusion was incorrect. This repair restores the exact source license and the README's original bounded scope for repository-authored workflow files, scripts, and documentation.

The ANGLE license and the retained Chromium reference license remain at their existing paths. Their source revisions and applicability are documented separately; neither notice grants a blanket license for unrelated files, Chrome or KOOV binaries, or generated media.
