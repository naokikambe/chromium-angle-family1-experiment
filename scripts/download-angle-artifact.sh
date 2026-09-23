#!/usr/bin/env bash
set -euo pipefail

readonly REPOSITORY='naokikambe/chromium-angle-family1-experiment'
PHASE3_SCRIPT_NAME='download-angle-artifact'
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/phase3-test-copy-common.sh"

if [[ $# -ne 2 || ! "$1" =~ ^[0-9]+$ ]]; then
  printf 'usage: %s WORKFLOW_RUN_ID OUTPUT_DIRECTORY\n' "$0" >&2
  exit 64
fi
run_id=$1
output_dir=$2
command -v gh >/dev/null 2>&1 || phase3_fail 'GitHub CLI (gh) is required'
[[ "$output_dir" == /* ]] || phase3_fail 'output directory must be an absolute path'
output_parent=$(dirname "$output_dir")
output_name=$(basename "$output_dir")
[[ -d "$output_parent" ]] || phase3_fail "output parent does not exist: $output_parent"
[[ ! -e "$output_dir" && ! -L "$output_dir" ]] || phase3_fail "refusing existing output: $output_dir"
output_parent_real=$(phase3_real_directory "$output_parent")
output_real="$output_parent_real/$output_name"
phase3_reject_symlink_components "$output_real"
repo_root=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [[ -n "$repo_root" ]]; then
  repo_root=$(cd "$repo_root" && pwd -P)
  case "$output_real/" in "$repo_root/"*) phase3_fail 'refusing to place downloaded artifact inside the Git repository' ;; esac
fi

mkdir "$output_dir"
artifact_listing=$(gh api "repos/$REPOSITORY/actions/runs/$run_id/artifacts" \
  --jq '.artifacts[] | select(.expired == false) | .name') ||
  phase3_fail "could not list artifacts for workflow run $run_id"
expected_prefix='angle-macos-x86_64-chrome-'
artifact_matches=()
while IFS= read -r artifact_name; do
  [[ "$artifact_name" == "$expected_prefix"*"-"*"-$run_id" ]] && artifact_matches+=("$artifact_name")
done <<< "$artifact_listing"
[[ ${#artifact_matches[@]} -eq 1 ]] || phase3_fail "expected exactly one ANGLE release artifact in run $run_id"
if ! gh run download "$run_id" --repo "$REPOSITORY" --name "${artifact_matches[0]}" --dir "$output_dir"; then
  phase3_fail "workflow artifact download failed for run $run_id"
fi
phase3_validate_release_manifest "$output_dir"
printf 'release artifact verified: %s\n' "$output_real"
printf 'Chrome: %s\nChromium: %s\nANGLE: %s\n' \
  "$PHASE3_RELEASE_CHROME_VERSION" "$PHASE3_RELEASE_CHROMIUM_REVISION" "$PHASE3_RELEASE_ANGLE_REVISION"
printf 'libEGL SHA-256: %s\nlibGLESv2 SHA-256: %s\n' \
  "$PHASE3_RELEASE_LIBEGL_SHA256" "$PHASE3_RELEASE_LIBGLESV2_SHA256"
