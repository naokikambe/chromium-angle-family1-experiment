#!/usr/bin/env bash
set -euo pipefail

PHASE3_SCRIPT_NAME='run-phase3c-preflight'
readonly PHASE3_SCRIPT_NAME
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
repo_root=$(cd "$script_dir/.." && pwd -P)
source "$script_dir/phase3-test-copy-common.sh"
source "$script_dir/prepare-chrome-angle-test-copy.sh"

usage() {
  cat <<'EOF'
usage: run-phase3c-preflight.sh --source-app APP --artifact-dir DIR --output-app APP --results-dir DIR --signing-identity APPLE_DEVELOPMENT_IDENTITY_SHA1

Runs Phase 3C gates, prepares one new test copy, and performs only a sign dry-run.
It never signs, launches, deletes, or replaces an existing retry/evidence directory.
EOF
}

phase3_preflight_main() {
local codesign_executable=$1
local sign_dry_run_script=$2
local inspect_script=$3
shift 3
[[ -x "$codesign_executable" ]] || phase3_fail "required codesign executable is unavailable: $codesign_executable"
[[ -x "$sign_dry_run_script" ]] || phase3_fail "required sign dry-run script is unavailable: $sign_dry_run_script"
[[ -x "$inspect_script" ]] || phase3_fail "required inspect script is unavailable: $inspect_script"
source_app=''; artifact_dir=''; output_app=''; results_dir=''; signing_identity=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --source-app|--artifact-dir|--output-app|--results-dir|--signing-identity)
      [[ $# -ge 2 ]] || { usage >&2; exit 64; }
      case "$1" in
        --source-app) source_app=$2 ;;
        --artifact-dir) artifact_dir=$2 ;;
        --output-app) output_app=$2 ;;
        --results-dir) results_dir=$2 ;;
        --signing-identity) signing_identity=$2 ;;
      esac
      shift 2 ;;
    *) phase3_fail "unknown option: $1" ;;
  esac
done
[[ -n "$source_app" && -n "$artifact_dir" && -n "$output_app" && -n "$results_dir" ]] || { usage >&2; exit 64; }
if [[ "$sign_dry_run_script" == "$script_dir/sign-chrome-angle-test-copy.sh" ]]; then
  [[ "$signing_identity" =~ ^[0-9A-Fa-f]{40}$ ]] ||
    phase3_fail 'production preflight requires --signing-identity with an Apple Development identity SHA-1'
fi

results_real=''
journal_path=''
result_path=''
last_completed_step='none'
failed_step=''
phase3_journal() {
  local step=$1 state=$2 status=$3
  [[ -n "$journal_path" ]] || return 0
  printf '%s\t%s\t%s\t%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$step" "$state" "$status" >> "$journal_path" || true
  [[ "$state" == pass ]] && last_completed_step=$step
  [[ "$state" == fail ]] && failed_step=$step
  return 0
}
phase3_finalize() {
  local status=$1
  if [[ -n "$result_path" && ! -e "$result_path" && ! -L "$result_path" ]]; then
    [[ "$status" -eq 0 ]] && final_state=completed-dry-run || final_state=failed
    [[ -n "$failed_step" || "$status" -eq 0 ]] || failed_step=${current_step:-unknown}
    {
      printf 'PHASE3C_PREFLIGHT_SCHEMA=1\nFINAL_STATE=%s\nFINAL_EXIT_STATUS=%s\nLAST_COMPLETED_STEP=%s\n' "$final_state" "$status" "$last_completed_step"
      [[ -n "$failed_step" ]] && printf 'FAILED_STEP=%s\n' "$failed_step"
      printf 'REAL_SIGNING_PERFORMED=false\nCHROME_LAUNCHED=false\nKOOV_LAUNCHED=false\n'
    } > "$result_path" || true
  fi
  if [[ "$status" -ne 0 && -n "$journal_path" ]]; then
    phase3_journal "${current_step:-unknown}" fail "$status"
  fi
  [[ -n "$journal_path" ]] && phase3_journal final-result "$([[ "$status" -eq 0 ]] && printf pass || printf fail)" "$status"
  return "$status"
}
trap 'phase3_finalize "$?"' EXIT

phase3_reject_root
PHASE3_CODESIGN_EXECUTABLE="$codesign_executable"
current_step=readonly-gates
for command in git ps shasum awk grep lipo find file xattr ditto stat install cmp date; do
  command -v "$command" >/dev/null 2>&1 || phase3_fail "required command is unavailable: $command"
done
[[ -x /usr/bin/codesign ]] || phase3_fail 'required production codesign executable is unavailable: /usr/bin/codesign'
for path in "$source_app" "$artifact_dir" "$output_app" "$results_dir"; do
  [[ "$path" != *$'\n'* && "$path" != *$'\r'* ]] || phase3_fail 'paths may not contain newline or carriage return'
  [[ ! "$path" =~ (^|/)([^/]+-)?retry(0|[1-9]|1[0-2])(/|$) ]] || phase3_fail 'legacy retry0-retry12 paths are immutable and reserved'
done

[[ "$source_app" == /* && "$artifact_dir" == /* && "$output_app" == /* && "$results_dir" == /* ]] ||
  phase3_fail 'all preflight paths must be absolute'
for path in "$output_app" "$results_dir"; do
  [[ "$path" != *'//'* ]] || phase3_fail 'paths may not contain empty components'
  [[ "$path" != *'/../'* && "$path" != */.. && "$path" != *'/./'* && "$path" != */. ]] ||
    phase3_fail 'prospective retry paths may not contain dot components'
done
[[ "$output_app" != "$results_dir" ]] || phase3_fail 'output and results paths are identical'
source_real=$(phase3_real_directory "$source_app")
artifact_real=$(phase3_real_directory "$artifact_dir")
[[ -f "$source_real/Contents/Info.plist" ]] || phase3_fail 'source Info.plist is missing'
phase3_reject_applications_path "$artifact_real"
retry_root=$(dirname "$output_app")
results_root=$(dirname "$results_dir")
[[ "$retry_root" == "$results_root" ]] || phase3_fail 'output and results must be direct children of one retry root'
retry_root_name=$(basename "$retry_root")
[[ "$retry_root_name" =~ ^attempt-[0-9]{8}-[0-9]{6}$ ]] ||
  phase3_fail 'prospective root must use attempt-YYYYMMDD-HHMMSS naming'
[[ -n "$(basename "$output_app")" && -n "$(basename "$results_dir")" ]] || phase3_fail 'output and results must have non-empty child names'
[[ ! -e "$retry_root" && ! -L "$retry_root" ]] || phase3_fail 'prospective retry root already exists'
[[ ! -e "$output_app" && ! -L "$output_app" ]] || phase3_fail 'output app already exists'
[[ ! -e "$results_dir" && ! -L "$results_dir" ]] || phase3_fail 'results directory already exists'
retry_parent_real=$(phase3_real_directory "$(dirname "$retry_root")")
phase3_require_user_owned_directory "$retry_parent_real"
phase3_reject_applications_path "$retry_parent_real"
phase3_reject_applications_path "$retry_root"
phase3_reject_symlink_components "$retry_root"
[[ "$source_real" != "$retry_root" && "$artifact_real" != "$retry_root" ]] || phase3_fail 'retry root collides with an input'
case "$retry_root/" in
  "$source_real/"*|"$artifact_real/"*) phase3_fail 'retry root is inside a protected input' ;;
esac

branch=$(git -C "$repo_root" branch --show-current)
[[ "$branch" == 'phase3-dynamic-angle-prep' ]] || phase3_fail "unexpected branch: $branch"
[[ -z "$(git -C "$repo_root" status --porcelain)" ]] || phase3_fail 'repository is not clean'
phase3_validate_release_manifest "$artifact_real"
source_version=$(phase3_plist_value CFBundleShortVersionString "$source_real/Contents/Info.plist") || phase3_fail 'cannot read source Chrome version'
[[ "$source_version" == "$PHASE3_RELEASE_CHROME_VERSION" ]] || phase3_fail "release expects Chrome $PHASE3_RELEASE_CHROME_VERSION, found $source_version"
source_executable_name=$(phase3_plist_value CFBundleExecutable "$source_real/Contents/Info.plist") || phase3_fail 'cannot read source executable name'
source_executable="$source_real/Contents/MacOS/$source_executable_name"
[[ -x "$source_executable" ]] || phase3_fail 'source executable is missing or not executable'
lipo -info "$source_executable" | grep -Eq '(^|[[:space:]])x86_64($|[[:space:]])' || phase3_fail 'source executable has no x86_64 slice'
phase3_journal readonly-gates pass 0

process_snapshot=$(mktemp "${TMPDIR:-/tmp}/phase3c-process.XXXXXX")
inspection=$(mktemp "${TMPDIR:-/tmp}/phase3c-inspection.XXXXXX")
trap 'status=$?; rm -f "$process_snapshot" "$inspection"; phase3_finalize "$status"' EXIT
phase3_capture_process_snapshot "$process_snapshot"
source_process=$(phase3_snapshot_matching_processes "$process_snapshot" "$source_real/Contents/MacOS/$source_executable_name" |
  awk -v self_pid="$$" '$1 != self_pid')
[[ -z "$source_process" ]] || phase3_fail 'source Chrome process is already running'
current_step=source-inspection
"$inspect_script" "$source_real" > "$inspection" 2>&1
phase3_journal source-inspection pass 0

current_step=retry-root-created
mkdir "$retry_root"
phase3_journal retry-root-created pass 0
retry_root_real=$(phase3_real_directory "$retry_root")
[[ "$retry_root_real" == "$retry_parent_real/$retry_root_name" ]] || phase3_fail 'retry root canonical path changed'
[[ ! -L "$retry_root" ]] || phase3_fail 'retry root became a symlink'
phase3_require_user_owned_directory "$retry_root_real"
phase3_reject_applications_path "$retry_root_real"
output_real="$retry_root_real/$(basename "$output_app")"
results_real="$retry_root_real/$(basename "$results_dir")"
[[ "$output_real" == "$retry_root_real/$(basename "$output_app")" && "$results_real" == "$retry_root_real/$(basename "$results_dir")" ]] ||
  phase3_fail 'post-create child paths are not direct children'
[[ ! -e "$output_real" && ! -L "$output_real" && ! -e "$results_real" && ! -L "$results_real" ]] ||
  phase3_fail 'post-create output or results path is not new'
phase3_reject_symlink_components "$output_real"
phase3_reject_symlink_components "$results_real"
mkdir "$results_real"
results_real=$(phase3_real_directory "$results_real")
journal_path="$results_real/preflight-step-journal.tsv"
result_path="$results_real/preflight-final-result.txt"
phase3_journal readonly-gates pass 0
phase3_journal source-inspection pass 0
phase3_journal retry-root-created pass 0
phase3_journal preflight-start start 0
current_step=results-create
phase3_journal results-create pass 0
printf 'PHASE3C_STATE=preflight-started\nBRANCH=%s\nSOURCE_VERSION=%s\n' "$branch" "$source_version" > "$results_real/preflight-state.txt"
cp "$process_snapshot" "$results_real/process-snapshot.txt"
cp "$inspection" "$results_real/source-inspection.txt"
current_step=prepare
phase3_journal prepare start 0
phase3_prepare_main "$source_real" "$artifact_real" "$output_real" "$codesign_executable" > "$results_real/prepare.txt" 2>&1
phase3_journal prepare pass 0
current_step=manifest-validation
phase3_validate_manifest "$output_real"
phase3_journal manifest-validation pass 0
phase3_capture_signature "$results_real/output-read-only" "$output_real"
sign_dry_run_dir="$results_real/sign-dry-run"
current_step=sign-dry-run
sign_dry_run_command=("$sign_dry_run_script" "$output_real" "$sign_dry_run_dir" --dry-run)
if [[ -n "$signing_identity" ]]; then
  sign_dry_run_command+=(--identity "$signing_identity")
fi
"${sign_dry_run_command[@]}" > "$results_real/sign-dry-run-stdout.txt" 2> "$results_real/sign-dry-run-stderr.txt"
cat "$results_real/sign-dry-run-stdout.txt" "$results_real/sign-dry-run-stderr.txt" > "$results_real/sign-dry-run.txt"
phase3_journal sign-dry-run pass 0
printf 'PHASE3C_STATE=prepared-unsigned-sign-dry-run\n' > "$results_real/preflight-state.txt"
printf 'NEXT_APPROVED_COMMAND=sign-chrome-angle-test-copy.sh %q %q --identity %q --confirm-apple-development-signing\n' "$output_real" "$results_real/sign-results" "$signing_identity" > "$results_real/next-step.txt"
printf 'Phase 3C preflight passed gates; no signing, launch, deletion, retry operation, or xattr mutation was performed.\n'
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  phase3_preflight_main /usr/bin/codesign "$script_dir/sign-chrome-angle-test-copy.sh" "$script_dir/inspect-chrome-for-dynamic-angle.sh" "$@"
fi
