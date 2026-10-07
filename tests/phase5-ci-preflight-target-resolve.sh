#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd -P)
script="$repo_root/scripts/phase5-ci-preflight.sh"
tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/phase5-preflight-target.XXXXXX")
trap 'rm -rf -- "$tmp_dir"' EXIT

targets_file="$tmp_dir/ninja-targets.txt"
cat > "$targets_file" <<'EOF'
services_unittests: phony
base_unittests: phony
EOF

resolved_output=$(
  PREFLIGHT_DIAG_DIR="$tmp_dir/auto" \
  PREFLIGHT_NINJA_TARGETS_FILE="$targets_file" \
  SMALL_TARGET_LABEL=//services:services_unittests \
  SMALL_TARGET_NINJA=auto \
  bash "$script" --resolve-target
)
grep -F 'small_target_ninja=services_unittests' <<< "$resolved_output" >/dev/null
grep -F 'small_target_resolution=label-derived' <<< "$resolved_output" >/dev/null
test "$(<"$tmp_dir/auto/resolved-small-target")" = services_unittests

explicit_output=$(
  PREFLIGHT_DIAG_DIR="$tmp_dir/explicit" \
  PREFLIGHT_NINJA_TARGETS_FILE="$targets_file" \
  SMALL_TARGET_LABEL=//services:services_unittests \
  SMALL_TARGET_NINJA=services_unittests \
  bash "$script" --resolve-target
)
grep -F 'small_target_resolution=explicit' <<< "$explicit_output" >/dev/null

if PREFLIGHT_DIAG_DIR="$tmp_dir/missing" \
  PREFLIGHT_NINJA_TARGETS_FILE="$targets_file" \
  SMALL_TARGET_LABEL=//services:services_unittests \
  SMALL_TARGET_NINJA=network_service_unittests \
  bash "$script" --resolve-target > "$tmp_dir/missing.out" 2>&1; then
  printf '%s\n' 'missing explicit target was incorrectly accepted' >&2
  exit 1
fi
grep -F 'small_target_status=not-found' "$tmp_dir/missing.out" >/dev/null

printf '%s\n' 'phase5 preflight target resolution tests passed'
