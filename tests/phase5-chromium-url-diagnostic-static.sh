#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd -P)
workflow="$repo_root/.github/workflows/phase5-chromium-url-diagnostic.yml"
runner="$repo_root/scripts/run-phase5-unsigned-chromium-u0u1.sh"
diagnostic_patch="$repo_root/patches/phase5-chromium-url-loader-diagnostics.patch"
compat_patch="$repo_root/patches/phase5-chromium-xcode16-compat.patch"

for path in "$workflow" "$runner" "$diagnostic_patch" "$compat_patch"; do
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
grep -F 'timeout-minutes: 360' "$workflow" >/dev/null
grep -F 'timeout-minutes: 330' "$workflow" >/dev/null
grep -F 'timeout-minutes: 150' "$workflow" >/dev/null
grep -F 'timeout-minutes: 45' "$workflow" >/dev/null
! grep -F 'timeout-minutes: 240' "$workflow" >/dev/null
grep -F 'actions: read' "$workflow" >/dev/null
grep -F 'contents: read' "$workflow" >/dev/null
grep -F 'prepare-angle:' "$workflow" >/dev/null
grep -F 'build-chromium:' "$workflow" >/dev/null
grep -F 'diagnose-u0-u1:' "$workflow" >/dev/null
grep -F 'needs: [prepare-angle, build-chromium]' "$workflow" >/dev/null
grep -F 'phase5-chromium-angle-input-' "$workflow" >/dev/null
grep -F 'phase5-chromium-url-build-' "$workflow" >/dev/null
grep -F 'actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093' "$workflow" >/dev/null
grep -F 'compression-level: 0' "$workflow" >/dev/null
grep -F 'gclient sync --no-history' "$workflow" >/dev/null
grep -F 'git merge-base --is-ancestor "$APPROVED_BASE_REVISION" HEAD' "$workflow" >/dev/null
grep -F 'git apply --unidiff-zero --check' "$workflow" >/dev/null
grep -F 'gn gen out/Phase5URLDiagnostic' "$workflow" >/dev/null
grep -F 'autoninja -C out/Phase5URLDiagnostic chrome' "$workflow" >/dev/null
grep -F "steps.build_chromium.outcome" "$workflow" >/dev/null
grep -F 'clang_use_chrome_plugins = false' "$workflow" >/dev/null
grep -F 'use_clang_modules = false' "$workflow" >/dev/null
grep -F 'use_unified_system_module = false' "$workflow" >/dev/null
grep -F 'enable_precompiled_headers = false' "$workflow" >/dev/null
grep -F 'Apply Xcode 16 SDK compatibility patch' "$workflow" >/dev/null
grep -F 'XCODE16_COMPAT_PATCH_SHA256' "$workflow" >/dev/null
grep -F 'skia/ext/skia_utils_mac.mm' "$workflow" >/dev/null
grep -F 'mac_deployment_target = "13.0"' "$workflow" >/dev/null
grep -F 'mac_min_system_version = "13.0"' "$workflow" >/dev/null
grep -F -- '--local-source-app' "$workflow" "$runner" >/dev/null
grep -F -- '--local-revisions' "$workflow" "$runner" >/dev/null
grep -F -- '--local-angle-artifact' "$workflow" "$runner" >/dev/null
grep -F 'phase5-chromium-url-diagnostic-' "$workflow" >/dev/null
grep -F 'actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02' "$workflow" >/dev/null

grep -F 'diff --git a/content/browser/storage_partition_impl.cc' "$diagnostic_patch" >/dev/null
grep -F 'diff --git a/services/network/url_loader_factory.cc' "$diagnostic_patch" >/dev/null
grep -F 'diff --git a/services/network/url_loader.cc' "$diagnostic_patch" >/dev/null
for marker in browser_factory_create factory_request factory_loader_created schedule_start schedule_decision response_started completed mojo_disconnect; do
  grep -F "[PHASE5_URL_DIAG] $marker" "$diagnostic_patch" >/dev/null
done

test "$(shasum -a 256 "$diagnostic_patch" | awk '{print $1}')" = \
  1be36abf18ac58b94ff1421607be18152c0373a9f92b0aeeb14ad8e352a250c1
test "$(shasum -a 256 "$compat_patch" | awk '{print $1}')" = \
  59b2cf4e7b5e963d6416d3eb02ab37292f50fbd43854debac313b13297b0eaaa
grep -F 'SIGNING_OPERATION=none' "$runner" >/dev/null
grep -F 'XATTR_OPERATION=none' "$runner" >/dev/null
grep -F 'RUNTIME_DEVICE_READY' "$runner" >/dev/null
! grep -E '(^|[[:space:]])(push|pull_request|pull_request_target):' "$workflow" >/dev/null
! grep -E '(^|[^A-Za-z])(sudo|git[[:space:]]+push|force-push|contents:[[:space:]]+write|id-token:|secrets\.)' "$workflow" >/dev/null
! grep -E 'codesign[^\n]*(--sign|--force|--options|--entitlements)|xattr[^\n]*(-c|-w|-d|-r)' "$runner" "$workflow" >/dev/null
! grep -E '/Applications|Google Chrome' "$runner" "$workflow" >/dev/null

git diff --check
printf '%s\n' 'phase5 Chromium URL diagnostic static audit passed'
