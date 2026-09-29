#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd -P)
workflow="$repo_root/.github/workflows/phase3d-dynamic-angle-vm.yml"
probe="$repo_root/scripts/run-phase3d-chrome-launch-probe.sh"
page="$repo_root/tests/fixtures/phase3d-webgl-smoke.html"

test -f "$page"
grep -F -- '--webgl-smoke-page' "$workflow" >/dev/null
grep -F 'tests/fixtures/phase3d-webgl-smoke.html' "$workflow" >/dev/null
grep -F 'webgl-smoke-comparison.txt' "$workflow" >/dev/null
grep -F 'WEBGL_SMOKE_RESULT_OBSERVED' "$workflow" >/dev/null
grep -F -- '--webgl-smoke-page' "$probe" >/dev/null
grep -F -- '--remote-debugging-address=127.0.0.1' "$probe" >/dev/null
grep -F -- '--remote-debugging-port=' "$probe" >/dev/null
grep -F 'webgl-devtools-json.txt' "$probe" >/dev/null
grep -F 'file://$webgl_smoke_page' "$probe" >/dev/null
grep -F "sed 's/&quot;/\"/g'" "$probe" >/dev/null
grep -F 'WEBGL2_CONTEXT_CREATED=%s' "$probe" >/dev/null
grep -F 'WEBGL1_CONTEXT_CREATED=%s' "$probe" >/dev/null
grep -F 'WEBGL_DRAW_OPERATION_COMPLETED=%s' "$probe" >/dev/null
grep -F 'webgl-smoke-summary.txt' "$probe" >/dev/null
grep -F 'phase3d-webgl-smoke-v1' "$page" >/dev/null
grep -F "inspectContext('webgl2'" "$page" >/dev/null
grep -F "inspectContext('webgl'" "$page" >/dev/null
grep -F 'document.title = `phase3d-webgl-smoke:' "$page" >/dev/null
! grep -E '(^|[[:space:]])sudo([[:space:]]|$)|/Applications/Google Chrome\.app|codesign[^\n]*--sign|xattr[[:space:]]+-c' \
  "$workflow" "$probe" "$page" >/dev/null

printf '%s\n' 'phase3d WebGL smoke static audit passed'
