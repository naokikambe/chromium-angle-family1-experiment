#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd -P)
workflow="$repo_root/.github/workflows/phase3d-chrome-launch-probe.yml"
probe="$repo_root/scripts/run-phase3d-chrome-launch-probe.sh"

grep -F 'workflow_dispatch:' "$workflow" >/dev/null
grep -F 'required: true' "$workflow" >/dev/null
grep -F 'loader_trace:' "$workflow" >/dev/null
grep -F 'default: true' "$workflow" >/dev/null
grep -F 'runs-on: macos-15-intel' "$workflow" >/dev/null
grep -F 'permissions:' "$workflow" >/dev/null
grep -F 'contents: read' "$workflow" >/dev/null
grep -F '11bd71901bbe5b1630ceea73d27597364c9af683' "$workflow" >/dev/null
grep -F 'ea165f8d65b6e75b540449e92b4886f43607fa02' "$workflow" >/dev/null
grep -F 'persist-credentials: false' "$workflow" >/dev/null
grep -F 'if: always()' "$workflow" >/dev/null
grep -F 'probe_results="$RUNNER_TEMP/phase3d-cft-launch-probe-results"' "$workflow" >/dev/null
grep -F 'path: ${{ runner.temp }}/phase3d-cft-launch-probe-results' "$workflow" >/dev/null
! grep -F 'PROBE_RESULTS: ${{ runner.temp }}' "$workflow" >/dev/null
! grep -E 'pull_request(_target)?|^[[:space:]]+push:|secrets\.|id-token:|contents:[[:space:]]+write|continue-on-error' "$workflow" >/dev/null
grep -F 'known-good-versions-with-downloads.json' "$probe" >/dev/null
grep -F 'mac-x64' "$probe" >/dev/null
grep -F 'gpu-pid-first-last.tsv' "$probe" >/dev/null
grep -F 'gpu-pid-all-sources.tsv' "$probe" >/dev/null
grep -F 'gpu-pid-events.tsv' "$probe" >/dev/null
grep -F 'GPU_PID_COUNT_STDERR=%s' "$probe" >/dev/null
grep -F 'start_stderr_observer' "$probe" >/dev/null
grep -F 'watch_gpu_stderr' "$probe" >/dev/null
grep -F 'DYLD_PRINT_LIBRARIES=1' "$probe" >/dev/null
grep -F 'dyld-library-loads.txt' "$probe" >/dev/null
grep -F 'authoritative-result.txt' "$probe" >/dev/null
grep -F 'BROWSER_OBSERVED=%s' "$probe" >/dev/null
grep -F 'BROWSER_ALIVE_AT_DEADLINE=%s' "$probe" >/dev/null
grep -F 'safe_test_bundle_helper' "$probe" >/dev/null
grep -F 'browser_started=true' "$probe" >/dev/null
grep -F 'browser_app/' "$probe" >/dev/null
grep -F -- '--type=gpu-process' "$probe" >/dev/null
grep -F 'wait "$collector_pid"' "$probe" >/dev/null
grep -F 'xattr -lr' "$probe" >/dev/null
grep -F '/Library/Logs/DiagnosticReports' "$probe" >/dev/null
grep -F 'crash-report-snapshot-errors.txt' "$probe" >/dev/null
grep -F "record_failure 'process sampler or GPU evidence collector failed during exit cleanup'" "$probe" >/dev/null
grep -F 'cp "$crash_report" "$results_dir/new-crash-reports/" || true' "$probe" >/dev/null
grep -F 'lsof -nP -p' "$probe" >/dev/null
grep -F 'vmmap "$pid"' "$probe" >/dev/null
! grep -E '(^|[[:space:]])sudo([[:space:]]|$)|fs_usage|dtruss|xattr[[:space:]]+-c|codesign[^\n]*--sign' "$probe" >/dev/null
! grep -E -- '--use-dynamic-angle|--use-angle|--use-gl' "$probe" >/dev/null
printf '%s\n' 'phase3d Chrome launch probe static audit passed'
