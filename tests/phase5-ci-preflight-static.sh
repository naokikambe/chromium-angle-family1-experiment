#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd -P)
workflow="$repo_root/.github/workflows/phase5-ci-preflight.yml"
script="$repo_root/scripts/phase5-ci-preflight.sh"

test -f "$workflow"
test -f "$script"
bash -n "$script"

grep -F 'workflow_dispatch:' "$workflow" >/dev/null
grep -F 'runs-on: macos-15-intel' "$workflow" >/dev/null
grep -F 'timeout-minutes: 120' "$workflow" >/dev/null
grep -F 'actions/cache/restore@5a3ec84eff668545956fd18022155c47e93e2684' "$workflow" >/dev/null
grep -F 'contents: read' "$workflow" >/dev/null
grep -F 'persist-credentials: false' "$workflow" >/dev/null
grep -F 'gclient sync --no-history' "$script" >/dev/null
grep -F 'gn gen out/Phase5Preflight' "$script" >/dev/null
grep -F 'autoninja -C out/Phase5Preflight' "$script" >/dev/null
grep -F 'PREFLIGHT_TARGET_REF_SHA' "$script" "$workflow" >/dev/null
grep -F 'DEPS_FILE_SHA256' "$script" >/dev/null
grep -F 'PREFLIGHT_CACHE_HIT' "$script" "$workflow" >/dev/null
grep -F 'localexec_parallelism' "$script" >/dev/null
grep -F 'estimated_remaining_seconds' "$script" >/dev/null
grep -F 'compiler_failure' "$script" >/dev/null
grep -F 'environment_failure' "$script" >/dev/null
grep -F 'timeout' "$script" >/dev/null

if grep -E 'upload-''artifact|download-''artifact|code''sign|x''attr|open[[:space:]]+-a|RUNTIME_DEVICE_READY[[:space:]]*=[[:space:]]*true' "$workflow" >/dev/null; then
  printf '%s\n' 'preflight static audit rejected unsafe operation' >&2
  exit 1
fi
if grep -E 'autoninja[[:space:]]+-C[^[:space:]]*[[:space:]]+chrome' "$script" >/dev/null; then
  printf '%s\n' 'preflight static audit rejected full chrome target' >&2
  exit 1
fi

git -C "$repo_root" diff --check
printf '%s\n' 'phase5 CI preflight static audit passed'
