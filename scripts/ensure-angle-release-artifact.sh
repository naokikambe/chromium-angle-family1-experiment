#!/usr/bin/env bash
set -euo pipefail

readonly PHASE3_REPOSITORY='naokikambe/chromium-angle-family1-experiment'
readonly PHASE3_BUILD_WORKFLOW='build-angle-macos-x64.yml'
readonly PHASE3_BUILD_REF='phase3-dynamic-angle-prep'
PHASE3_SCRIPT_NAME='ensure-angle-release-artifact'
readonly PHASE3_SCRIPT_NAME
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/phase3-test-copy-common.sh"

usage() {
  printf 'usage: %s --source-app APP --artifact-cache-root DIRECTORY\n' "$0" >&2
  exit 64
}

source_app=''
artifact_cache_root=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    --source-app)
      [[ $# -ge 2 ]] || usage
      source_app=$2
      shift 2
      ;;
    --artifact-cache-root)
      [[ $# -ge 2 ]] || usage
      artifact_cache_root=$2
      shift 2
      ;;
    *) usage ;;
  esac
done

phase3_reject_root
[[ -n "$source_app" && -n "$artifact_cache_root" ]] || usage
[[ "$source_app" == /* && "$artifact_cache_root" == /* ]] ||
  phase3_fail 'source app and artifact cache root must be absolute paths'
for command in gh git find shasum awk grep date sleep; do
  command -v "$command" >/dev/null 2>&1 || phase3_fail "required command is unavailable: $command"
done

source_real=$(phase3_real_directory "$source_app")
[[ -f "$source_real/Contents/Info.plist" && ! -L "$source_real/Contents/Info.plist" ]] ||
  phase3_fail 'source Chrome Info.plist is missing or symlinked'
source_version=$(phase3_plist_value CFBundleShortVersionString "$source_real/Contents/Info.plist") ||
  phase3_fail 'cannot read source Chrome version'
[[ "$source_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] ||
  phase3_fail 'source Chrome version is not a four-part numeric version'

cache_real=$(phase3_real_directory "$artifact_cache_root")
phase3_require_user_owned_directory "$cache_real"
phase3_reject_applications_path "$cache_real"
case "$cache_real/" in
  "$source_real/"*|"$source_real/") phase3_fail 'artifact cache root may not be inside source Chrome' ;;
esac
repo_root=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [[ -n "$repo_root" ]]; then
  repo_root=$(cd "$repo_root" && pwd -P)
  case "$cache_real/" in
    "$repo_root/"*) phase3_fail 'artifact cache root may not be inside the Git repository' ;;
  esac
fi

matching_artifacts=()
while IFS= read -r -d '' manifest; do
  candidate=$(dirname "$manifest")
  candidate_real=$(phase3_real_directory "$candidate")
  case "$candidate_real/" in
    "$cache_real/"*) ;;
    *) phase3_fail "artifact candidate resolves outside cache root: $candidate" ;;
  esac
  if (phase3_validate_release_manifest "$candidate_real" >/dev/null 2>&1); then
    candidate_version=$(phase3_manifest_value "$manifest" CHROME_VERSION)
    if [[ "$candidate_version" == "$source_version" ]]; then
      matching_artifacts+=("$candidate_real")
    fi
  else
    printf 'ignoring invalid release artifact candidate: %s\n' "$candidate_real" >&2
  fi
done < <(find -P "$cache_real" -mindepth 2 -maxdepth 2 -type f -name ANGLE_RELEASE_MANIFEST -print0 | LC_ALL=C sort -z)

if [[ ${#matching_artifacts[@]} -eq 1 ]]; then
  phase3_validate_release_manifest "${matching_artifacts[0]}"
  printf '%s\n' "${matching_artifacts[0]}"
  exit 0
fi
[[ ${#matching_artifacts[@]} -eq 0 ]] ||
  phase3_fail "multiple verified artifacts match Chrome $source_version"

printf 'no verified artifact matches Chrome %s; dispatching %s\n' \
  "$source_version" "$PHASE3_BUILD_WORKFLOW" >&2
runs_before=$(gh run list \
  --repo "$PHASE3_REPOSITORY" \
  --workflow "$PHASE3_BUILD_WORKFLOW" \
  --branch "$PHASE3_BUILD_REF" \
  --event workflow_dispatch \
  --limit 30 \
  --json databaseId \
  --jq '.[].databaseId') || phase3_fail 'cannot record existing ANGLE build runs'

gh workflow run "$PHASE3_BUILD_WORKFLOW" \
  --repo "$PHASE3_REPOSITORY" \
  --ref "$PHASE3_BUILD_REF" \
  -f "chrome_version=$source_version" >&2 || phase3_fail 'ANGLE build dispatch failed'

run_id=''
for ((poll_attempt = 0; poll_attempt < 30; poll_attempt++)); do
  while IFS= read -r candidate_run; do
    [[ "$candidate_run" =~ ^[0-9]+$ ]] || continue
    if ! grep -Fx "$candidate_run" <<< "$runs_before" >/dev/null; then
      run_id=$candidate_run
      break
    fi
  done < <(gh run list \
    --repo "$PHASE3_REPOSITORY" \
    --workflow "$PHASE3_BUILD_WORKFLOW" \
    --branch "$PHASE3_BUILD_REF" \
    --event workflow_dispatch \
    --limit 30 \
    --json databaseId \
    --jq '.[].databaseId')
  [[ -z "$run_id" ]] || break
  sleep 2
done
[[ "$run_id" =~ ^[0-9]+$ ]] || phase3_fail 'could not identify the dispatched ANGLE build run'

printf 'waiting for ANGLE build run %s\n' "$run_id" >&2
gh run watch "$run_id" --repo "$PHASE3_REPOSITORY" --exit-status >&2 ||
  phase3_fail "ANGLE build run failed: $run_id"

output_dir="$cache_real/run-${run_id}-artifact"
[[ ! -e "$output_dir" && ! -L "$output_dir" ]] ||
  phase3_fail "refusing existing artifact output: $output_dir"
"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/download-angle-artifact.sh" \
  "$run_id" "$output_dir" >&2
output_real=$(phase3_real_directory "$output_dir")
phase3_validate_release_manifest "$output_real"
[[ "$PHASE3_RELEASE_CHROME_VERSION" == "$source_version" ]] ||
  phase3_fail "downloaded artifact targets Chrome $PHASE3_RELEASE_CHROME_VERSION, expected $source_version"
printf '%s\n' "$output_real"
