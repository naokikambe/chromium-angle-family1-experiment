# History and migration scope

This repository previously combined several Chrome/Chromium experiments, CI probes, and browser recovery work. The new default role is narrower: maintain Chrome Stable to Chromium to ANGLE source mappings, the reviewed Family 1 patch, a fixed ANGLE recipe, unsigned library candidates, and owner-run local integration tools.

This migration prepares a candidate on the existing `main` base and the dedicated `migration/angle-maintenance` branch. It does not commit or push directly to `main`, merge the feature branch, or import its experiment history. It preserves the Chrome 156 source pins, patch bytes and license; transfers the common CDP and media/WebGL synthetic probe code into `src/probes`; and keeps the privacy checks and Git hooks at their existing paths.

The existing Chromium BSD notice remains at `scripts/page-recovery/reference/LICENSE` with its original scope. The ANGLE notice remains in `licenses/ANGLE-LICENSE.txt`; neither notice grants a repository-wide license.

The five old main-branch phase documents are replaced by the focused docs linked from the README. The old full-Chromium, URL-diagnostic, preflight, test-stub, and page-recovery Actions workflows and their supporting files remain in the repository until a separate owner-reviewed cleanup. They are not the normal ANGLE build path. No old workflow was disabled, deleted, or manually run here.

The monitor, re-acquire and state-recovery flows, local tool, and new documents are implementation for review on a Draft PR. PR CI runs synthetic checks only. Main integration requires a separate approval and may activate the six-hour schedule; it is not included in branch-push approval. A CI artifact remains distinct from owner runtime acceptance and adoption.
