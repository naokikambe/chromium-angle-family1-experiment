#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd -P)
workflow="$repo_root/.github/workflows/phase5-unsigned-chromium-u0u1.yml"
runner="$repo_root/scripts/run-phase5-unsigned-chromium-u0u1.sh"
cdp_probe="$repo_root/scripts/phase5-unsigned-cdp-probe.py"
loopback_server="$repo_root/scripts/phase5-unsigned-loopback-server.py"
fixture="$repo_root/tests/fixtures/phase5-unsigned-loopback.html"

for path in "$workflow" "$runner" "$cdp_probe" "$loopback_server" "$fixture"; do
  test -f "$path"
done
bash -n "$runner"
python3 -m py_compile "$cdp_probe" "$loopback_server"

grep -F 'workflow_dispatch:' "$workflow" >/dev/null
grep -F 'snapshot_position:' "$workflow" >/dev/null
grep -F 'snapshot_sha256:' "$workflow" >/dev/null
grep -F 'angle_build_run_id:' "$workflow" >/dev/null
grep -F 'runs-on: macos-15-intel' "$workflow" >/dev/null
grep -F 'permissions:' "$workflow" >/dev/null
grep -F 'actions: read' "$workflow" >/dev/null
grep -F 'contents: read' "$workflow" >/dev/null
grep -F 'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683' "$workflow" >/dev/null
grep -F 'actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02' "$workflow" >/dev/null
grep -F 'persist-credentials: false' "$workflow" >/dev/null
grep -F 'if: always()' "$workflow" >/dev/null
grep -F 'commondatastorage.googleapis.com/chromium-browser-snapshots/Mac' "$runner" >/dev/null
grep -F 'chrome-mac.zip' "$runner" >/dev/null
grep -F 'REVISIONS' "$runner" >/dev/null
grep -F '.got_revision' "$runner" >/dev/null
grep -F '.got_angle_revision' "$runner" >/dev/null
! grep -F "grep -Eo '[0-9a-f]{40}'" "$runner" >/dev/null
grep -F 'codesign -dvvv --strict' "$runner" >/dev/null
grep -F 'code object is not signed at all' "$runner" >/dev/null
grep -F 'download-angle-artifact.sh' "$runner" >/dev/null
grep -F 'verify-phase5-runtime-artifact.sh' "$runner" >/dev/null
grep -F -- '--disable-gpu' "$runner" >/dev/null
grep -F -- '--use-gl=angle' "$runner" >/dev/null
grep -F -- '--use-angle=metal' "$runner" >/dev/null
grep -F -- '--use-dynamic-angle' "$runner" >/dev/null
grep -F -- '--browser-arg=' "$runner" >/dev/null
grep -F 'DYLD_PRINT_LIBRARIES' "$workflow" "$runner" >/dev/null
grep -F 'loopback-server.stderr' "$runner" >/dev/null
grep -F 'python3-preflight.txt' "$runner" >/dev/null
grep -F 'loopback_server_port=0' "$runner" >/dev/null
grep -F 'socketserver.TCPServer.server_bind' "$loopback_server" >/dev/null
grep -F 'phase3d-webgl-smoke.html' "$runner" >/dev/null
grep -F 'RUNTIME_DEVICE_READY' "$runner" >/dev/null
grep -F 'APPROVED_BASE_REVISION: eb21b3b30fe0d062d5bf500d46d74a7a57ad56f5' "$workflow" >/dev/null
grep -F 'git merge-base --is-ancestor "$APPROVED_BASE_REVISION" "$GITHUB_SHA"' "$workflow" >/dev/null
grep -F 'U0' "$workflow" >/dev/null
grep -F 'U1' "$workflow" >/dev/null
! grep -E '(^|[[:space:]])(push|pull_request|pull_request_target):' "$workflow" >/dev/null
! grep -E '(^|[^A-Za-z])(sudo|git[[:space:]]+push|force-push|contents:[[:space:]]+write|id-token:|secrets\.)' "$workflow" >/dev/null
! grep -E 'codesign[^\n]*(--sign|--force|--options|--entitlements)|xattr[^\n]*(-c|-w|-d|-r)' "$runner" "$workflow" >/dev/null
! grep -E '/Applications|Chrome\.app|Google Chrome' "$runner" "$workflow" >/dev/null
grep -F 'SIGNING_OPERATION=none' "$runner" >/dev/null
grep -F 'XATTR_OPERATION=none' "$runner" >/dev/null

printf '%s\n' 'phase5 unsigned Chromium U0/U1 static audit passed'
