#!/usr/bin/env bash
set -euo pipefail

PHASE3_SCRIPT_NAME='run-phase3c-preflight'
readonly PHASE3_SCRIPT_NAME
script_dir=$(cd "$(dirname "$0")" && pwd -P)
repo_root=$(cd "$script_dir/.." && pwd -P)
source "$script_dir/phase3-test-copy-common.sh"

usage() {
  cat <<'EOF'
usage: run-phase3c-preflight.sh --source-app APP --artifact-dir DIR --output-app APP --results-dir DIR

Runs Phase 3C gates, prepares one new test copy, and performs only a sign dry-run.
It never signs, launches, deletes, or replaces an existing retry/evidence directory.
EOF
}

source_app=''; artifact_dir=''; output_app=''; results_dir=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --source-app|--artifact-dir|--output-app|--results-dir)
      [[ $# -ge 2 ]] || { usage >&2; exit 64; }
      case "$1" in
        --source-app) source_app=$2 ;;
        --artifact-dir) artifact_dir=$2 ;;
        --output-app) output_app=$2 ;;
        --results-dir) results_dir=$2 ;;
      esac
      shift 2 ;;
    *) phase3_fail "unknown option: $1" ;;
  esac
done
[[ -n "$source_app" && -n "$artifact_dir" && -n "$output_app" && -n "$results_dir" ]] || { usage >&2; exit 64; }

phase3_reject_root
for command in git ps shasum awk grep lipo find file codesign xattr ditto stat install cmp; do
  command -v "$command" >/dev/null 2>&1 || phase3_fail "required command is unavailable: $command"
done
for path in "$source_app" "$artifact_dir" "$output_app" "$results_dir"; do
  [[ "$path" != *$'\n'* && "$path" != *$'\r'* ]] || phase3_fail 'paths may not contain newline or carriage return'
  case "$path" in
    */retry0|*/retry0/*|*/retry1|*/retry1/*|*/retry2|*/retry2/*|*/retry3|*/retry3/*)
      phase3_fail 'retry0-retry3 paths are reserved; choose a new user-owned path (retry4 is next)' ;;
  esac
done

source_real=$(phase3_real_directory "$source_app")
artifact_real=$(phase3_real_directory "$artifact_dir")
[[ -f "$source_real/Contents/Info.plist" ]] || phase3_fail 'source Info.plist is missing'
phase3_reject_applications_path "$source_real"
phase3_reject_applications_path "$artifact_real"
[[ ! -e "$output_app" && ! -L "$output_app" ]] || phase3_fail 'output app already exists'
[[ ! -e "$results_dir" && ! -L "$results_dir" ]] || phase3_fail 'results directory already exists'
output_parent_real=$(phase3_real_directory "$(dirname "$output_app")")
results_parent_real=$(phase3_real_directory "$(dirname "$results_dir")")
phase3_require_user_owned_directory "$output_parent_real"
phase3_require_user_owned_directory "$results_parent_real"
phase3_reject_applications_path "$output_parent_real"
phase3_reject_applications_path "$results_parent_real"
output_real="$output_parent_real/$(basename "$output_app")"
results_real="$results_parent_real/$(basename "$results_dir")"
phase3_reject_symlink_components "$output_real"
phase3_reject_symlink_components "$results_real"
[[ "$output_real" != "$results_real" ]] || phase3_fail 'output and results paths collide'
[[ "$source_real" != "$output_real" && "$artifact_real" != "$output_real" ]] || phase3_fail 'output collides with an input'
case "$results_real/" in
  "$source_real/"*|"$artifact_real/"*) phase3_fail 'results path is inside a protected input' ;;
esac

branch=$(git -C "$repo_root" branch --show-current)
[[ "$branch" == 'phase3-dynamic-angle-prep' ]] || phase3_fail "unexpected branch: $branch"
[[ -z "$(git -C "$repo_root" status --porcelain)" ]] || phase3_fail 'repository is not clean'
source_version=$(phase3_plist_value CFBundleShortVersionString "$source_real/Contents/Info.plist") || phase3_fail 'cannot read source Chrome version'
[[ "$source_version" == "$PHASE3_CHROME_VERSION" ]] || phase3_fail "expected Chrome $PHASE3_CHROME_VERSION, found $source_version"
source_executable_name=$(phase3_plist_value CFBundleExecutable "$source_real/Contents/Info.plist") || phase3_fail 'cannot read source executable name'
source_executable="$source_real/Contents/MacOS/$source_executable_name"
[[ -x "$source_executable" ]] || phase3_fail 'source executable is missing or not executable'
lipo -info "$source_executable" | grep -Eq '(^|[[:space:]])x86_64($|[[:space:]])' || phase3_fail 'source executable has no x86_64 slice'
phase3_verify_hash "$artifact_real/libEGL.dylib" "$PHASE3_LIBEGL_SHA256"
phase3_verify_hash "$artifact_real/libGLESv2.dylib" "$PHASE3_LIBGLESV2_SHA256"
[[ -f "$artifact_real/ANGLE_REVISION" && ! -L "$artifact_real/ANGLE_REVISION" ]] || phase3_fail 'artifact ANGLE_REVISION is missing'
[[ "$(<"$artifact_real/ANGLE_REVISION")" == "$PHASE3_ANGLE_REVISION" ]] || phase3_fail 'artifact ANGLE revision does not match'

process_snapshot=$(mktemp "${TMPDIR:-/tmp}/phase3c-process.XXXXXX")
trap 'rm -f "$process_snapshot"' EXIT
phase3_capture_process_snapshot "$process_snapshot"
source_process=$(phase3_snapshot_matching_processes "$process_snapshot" "$source_real/Contents/MacOS/$source_executable_name")
[[ -z "$source_process" ]] || phase3_fail 'source Chrome process is already running'

mkdir "$results_real"
printf 'PHASE3C_STATE=preflight-started\nBRANCH=%s\nSOURCE_VERSION=%s\n' "$branch" "$source_version" > "$results_real/preflight-state.txt"
cp "$process_snapshot" "$results_real/process-snapshot.txt"
"$script_dir/inspect-chrome-for-dynamic-angle.sh" "$source_real" > "$results_real/source-inspection.txt" 2>&1
"$script_dir/prepare-chrome-angle-test-copy.sh" "$source_real" "$artifact_real" "$output_real" > "$results_real/prepare.txt" 2>&1
phase3_validate_manifest "$output_real"
phase3_capture_signature "$results_real/output-read-only" "$output_real"
sign_dry_run_dir="$results_real/sign-dry-run"
"$script_dir/sign-chrome-angle-test-copy.sh" "$output_real" "$sign_dry_run_dir" --dry-run > "$results_real/sign-dry-run.txt" 2>&1
printf 'PHASE3C_STATE=prepared-unsigned-sign-dry-run\n' > "$results_real/preflight-state.txt"
printf 'NEXT_APPROVED_COMMAND=sign-chrome-angle-test-copy.sh %q %q --confirm-ad-hoc-signing\n' "$output_real" "$results_real/sign-results" > "$results_real/next-step.txt"
printf 'Phase 3C preflight passed gates; no signing, launch, deletion, retry operation, or xattr mutation was performed.\n'
