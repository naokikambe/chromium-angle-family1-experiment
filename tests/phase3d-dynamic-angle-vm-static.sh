#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd -P)
workflow="$repo_root/.github/workflows/phase3d-dynamic-angle-vm.yml"
probe="$repo_root/scripts/run-phase3d-chrome-launch-probe.sh"
context_analyzer="$repo_root/scripts/analyze-phase5-context-trace.sh"
evidence_helper="$repo_root/scripts/phase3-gpu-evidence.sh"

grep -F 'workflow_dispatch:' "$workflow" >/dev/null
grep -F 'angle_build_run_id:' "$workflow" >/dev/null
grep -F 'actions: read' "$workflow" >/dev/null
grep -F 'contents: read' "$workflow" >/dev/null
grep -F 'runs-on: macos-15-intel' "$workflow" >/dev/null
grep -F 'timeout-minutes: 30' "$workflow" >/dev/null
grep -F 'persist-credentials: false' "$workflow" >/dev/null
grep -F '11bd71901bbe5b1630ceea73d27597364c9af683' "$workflow" >/dev/null
grep -F 'ea165f8d65b6e75b540449e92b4886f43607fa02' "$workflow" >/dev/null
grep -F 'scripts/download-angle-artifact.sh "$ANGLE_BUILD_RUN_ID" "$artifact_dir"' "$workflow" >/dev/null
grep -F 'bash scripts/verify-artifact.sh "$artifact_dir"' "$workflow" >/dev/null
grep -F 'phase3_validate_release_manifest "$artifact_dir"' "$workflow" >/dev/null
grep -F -- '--angle-artifact "$ANGLE_ARTIFACT_DIR"' "$workflow" >/dev/null
grep -F 'if: always()' "$workflow" >/dev/null
grep -F -- '--dynamic-angle-flags' "$workflow" >/dev/null
grep -F 'stock-control-comparison.txt' "$workflow" >/dev/null
grep -F 'path: ${{ runner.temp }}/phase3d-dynamic-angle-results' "$workflow" >/dev/null
! grep -E 'pull_request(_target)?|^[[:space:]]+push:|id-token:|contents:[[:space:]]+write|actions:[[:space:]]+write|continue-on-error' "$workflow" >/dev/null

grep -F 'phase3_validate_release_manifest "$angle_artifact_dir"' "$probe" >/dev/null
grep -F 'bash -n scripts/analyze-phase5-context-trace.sh' "$workflow" >/dev/null
grep -F 'scripts/analyze-phase5-context-trace.sh' "$workflow" >/dev/null
grep -F 'phase5-context-trace-analysis-v1' "$context_analyzer" >/dev/null
grep -F 'NON_VERSION_ATTRIBUTES_IDENTICAL' "$context_analyzer" >/dev/null
grep -F 'egl-bad-attribute-from-context-version-rejection' "$context_analyzer" >/dev/null
grep -F 'PHASE3_APPROVED_RUNTIME_OPT_IN' "$repo_root/scripts/phase3-test-copy-common.sh" >/dev/null
grep -F 'PHASE3_RELEASE_RUNTIME_OPT_IN' "$repo_root/scripts/phase3-test-copy-common.sh" >/dev/null
grep -F 'runtime_opt_in_applied' "$probe" >/dev/null
grep -F 'launch_args+=("$runtime_opt_in")' "$probe" >/dev/null
grep -F 'RUNTIME_OPT_IN_APPLIED=%s' "$probe" >/dev/null
grep -F 'RUNTIME_OPT_IN=%s' "$probe" >/dev/null
grep -F 'PHASE3_RELEASE_CHROME_VERSION' "$probe" >/dev/null
grep -F 'refusing existing CfT replacement target' "$probe" >/dev/null
grep -F 'phase3_verify_hash "$destination_file"' "$probe" >/dev/null
grep -F -- '--use-gl=angle' "$probe" >/dev/null
grep -F -- '--use-angle=metal' "$probe" >/dev/null
grep -F -- '--use-dynamic-angle' "$probe" >/dev/null
grep -F 'LIBEGL_DYLD_LOAD_OBSERVED=%s' "$probe" >/dev/null
grep -F 'LIBGLESV2_DYLD_LOAD_OBSERVED=%s' "$probe" >/dev/null
grep -F 'LIBEGL_GPU_DYLD_LOAD_OBSERVED=%s' "$probe" >/dev/null
grep -F 'LIBGLESV2_GPU_DYLD_LOAD_OBSERVED=%s' "$probe" >/dev/null
grep -F 'gpu_dyld_has_path' "$probe" >/dev/null
grep -F 'DYNAMIC_ANGLE_OUTCOME=%s' "$probe" >/dev/null
grep -F 'replacement-library-post-run.sha256' "$probe" >/dev/null
grep -F 'ANGLE_FLAGS_REQUESTED=%s' "$probe" >/dev/null
grep -F 'dynamic-angle-evidence.txt' "$probe" >/dev/null
grep -F 'same_gpu_pid_process_map=' "$probe" >/dev/null
grep -F 'phase3-gpu-evidence.sh' "$probe" >/dev/null
grep -F 'Initialization of all \([0-9]+\) EGL display types failed' "$evidence_helper" >/dev/null
grep -F 'GLDisplayEGL::Initialize' "$evidence_helper" >/dev/null
! grep -E '(^|[[:space:]])sudo([[:space:]]|$)|xattr[[:space:]]+-c|codesign[^[:cntrl:]]*--sign|/Applications/Google Chrome\.app' "$workflow" "$probe" >/dev/null

printf '%s\n' 'phase3d dynamic ANGLE VM static audit passed'
