#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd -P)
workflow="$repo_root/.github/workflows/phase5-chromium-url-diagnostic.yml"
runner="$repo_root/scripts/run-phase5-unsigned-chromium-u0u1.sh"
diagnostic_patch="$repo_root/patches/phase5-chromium-url-loader-diagnostics.patch"

for path in "$workflow" "$runner" "$diagnostic_patch"; do
  test -f "$path"
done
bash -n "$runner"
ruby -e 'require "yaml"; YAML.parse_file(ARGV.fetch(0))' "$workflow"

grep -F 'workflow_dispatch:' "$workflow" >/dev/null
grep -F 'workflow_call:' "$workflow" >/dev/null
grep -F 'chromium_revision:' "$workflow" >/dev/null
grep -F 'angle_revision:' "$workflow" >/dev/null
grep -F 'angle_build_run_id:' "$workflow" >/dev/null
grep -F 'diagnostic_patch_sha256:' "$workflow" >/dev/null
grep -F 'runs-on: macos-15-intel' "$workflow" >/dev/null
grep -F 'actions: read' "$workflow" >/dev/null
grep -F 'contents: read' "$workflow" >/dev/null
grep -F 'gclient sync --no-history' "$workflow" >/dev/null
grep -F 'git apply --unidiff-zero --check' "$workflow" >/dev/null
grep -F 'gn gen out/Phase5URLDiagnostic' "$workflow" >/dev/null
grep -F 'autoninja -C out/Phase5URLDiagnostic chrome' "$workflow" >/dev/null
grep -F -- '--local-source-app' "$workflow" "$runner" >/dev/null
grep -F -- '--local-revisions' "$workflow" "$runner" >/dev/null
grep -F 'phase5-chromium-url-diagnostic-' "$workflow" >/dev/null
grep -F 'actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02' "$workflow" >/dev/null

grep -F 'diff --git a/content/browser/storage_partition_impl.cc' "$diagnostic_patch" >/dev/null
grep -F 'diff --git a/services/network/url_loader_factory.cc' "$diagnostic_patch" >/dev/null
grep -F 'diff --git a/services/network/url_loader.cc' "$diagnostic_patch" >/dev/null
for marker in browser_factory_create factory_request factory_loader_created schedule_start schedule_decision response_started completed mojo_disconnect; do
  grep -F "[PHASE5_URL_DIAG] $marker" "$diagnostic_patch" >/dev/null
done

test "$(shasum -a 256 "$diagnostic_patch" | awk '{print $1}')" = \
  646c6b5a166b2054f664c97e373dd2760292d447c84cb8266ed36e32d599dc22
grep -F 'SIGNING_OPERATION=none' "$runner" >/dev/null
grep -F 'XATTR_OPERATION=none' "$runner" >/dev/null
grep -F 'RUNTIME_DEVICE_READY' "$runner" >/dev/null
! grep -E '(^|[[:space:]])(push|pull_request|pull_request_target):' "$workflow" >/dev/null
! grep -E '(^|[^A-Za-z])(sudo|git[[:space:]]+push|force-push|contents:[[:space:]]+write|id-token:|secrets\.)' "$workflow" >/dev/null
! grep -E 'codesign[^\n]*(--sign|--force|--options|--entitlements)|xattr[^\n]*(-c|-w|-d|-r)' "$runner" "$workflow" >/dev/null
! grep -E '/Applications|Google Chrome' "$runner" "$workflow" >/dev/null

git diff --check
printf '%s\n' 'phase5 Chromium URL diagnostic static audit passed'
