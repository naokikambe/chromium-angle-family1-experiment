#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd -P)
script="$repo_root/scripts/phase5-ci-preflight.sh"
tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/phase5-preflight-classify.XXXXXX")
trap 'rm -rf -- "$tmp_dir"' EXIT

run_classify() {
  PREFLIGHT_DIAG_DIR="$tmp_dir" \
    PREFLIGHT_SOURCE_OUTCOME="$1" \
    PREFLIGHT_GRAPH_OUTCOME="$2" \
    PREFLIGHT_SMALL_TARGET_OUTCOME="$3" \
    RUN_SMALL_TARGET="$4" \
    bash "$script" --classify
}

graph_only_output=$(run_classify success success skipped false)
grep -F 'classification=success' <<< "$graph_only_output" >/dev/null

if run_classify success failure skipped false > "$tmp_dir/graph-failure.out" 2>&1; then
  printf '%s\n' 'graph failure was incorrectly accepted' >&2
  exit 1
fi
grep -F 'classification=environment_failure' "$tmp_dir/graph-failure.out" >/dev/null

touch "$tmp_dir/graph-inspection-timeout"
if run_classify success failure skipped false > "$tmp_dir/graph-timeout.out" 2>&1; then
  printf '%s\n' 'graph inspection timeout was incorrectly accepted' >&2
  exit 1
fi
grep -F 'classification=timeout' "$tmp_dir/graph-timeout.out" >/dev/null
rm -f "$tmp_dir/graph-inspection-timeout"

printf '%s\n' 'fatal error: intentional classifier test' > "$tmp_dir/small-target.log"
if run_classify success success failure true > "$tmp_dir/compiler-failure.out" 2>&1; then
  printf '%s\n' 'compiler failure was incorrectly accepted' >&2
  exit 1
fi
grep -F 'classification=compiler_failure' "$tmp_dir/compiler-failure.out" >/dev/null

printf '%s\n' 'phase5 preflight classification tests passed'
