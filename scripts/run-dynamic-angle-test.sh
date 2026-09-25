#!/usr/bin/env bash
set -euo pipefail

PHASE3_SCRIPT_NAME='run-dynamic-angle-test'
readonly PHASE3_SCRIPT_NAME
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/phase3-test-copy-common.sh"

phase3_run_main() {
local codesign_executable=$1
shift
[[ -x "$codesign_executable" ]] || phase3_fail "required codesign executable is unavailable: $codesign_executable"
[[ $# -ge 3 && $# -le 4 ]] || { printf 'usage: %s CASE_B|CASE_C TEST_CHROME_APP RESULTS_DIRECTORY [--diagnostic-gpu-startup]\n' "$0" >&2; exit 64; }
phase3_reject_root
test_case=$1
test_app=$2
results_dir=$3
diagnostic_gpu_startup=false
if [[ $# -eq 4 ]]; then
  [[ "$4" == '--diagnostic-gpu-startup' ]] || phase3_fail "unsupported option: $4"
  diagnostic_gpu_startup=true
fi
case "$test_case" in CASE_B|CASE_C) ;; *) phase3_fail 'case must be CASE_B or CASE_C' ;; esac
for command in lipo shasum ps awk; do command -v "$command" >/dev/null 2>&1 || phase3_fail "required command is unavailable: $command"; done
[[ -d "$test_app" ]] || phase3_fail "test app does not exist: $test_app"
[[ ! -e "$results_dir" && ! -L "$results_dir" ]] || phase3_fail "refusing existing results: $results_dir"
test_app_real=$(phase3_real_directory "$test_app")
phase3_reject_applications_path "$test_app_real"
results_parent_real=$(phase3_real_directory "$(dirname "$results_dir")")
phase3_require_user_owned_directory "$results_parent_real"
results_real="$results_parent_real/$(basename "$results_dir")"
phase3_reject_symlink_components "$results_real"
phase3_validate_signed_test_copy "$test_app_real" "$codesign_executable"

info_plist="$test_app_real/Contents/Info.plist"
chrome_version=$(phase3_plist_value CFBundleShortVersionString "$info_plist") || phase3_fail 'cannot read Chrome version'
[[ "$chrome_version" == "$PHASE3_RELEASE_CHROME_VERSION" ]] || phase3_fail "manifest expects Chrome $PHASE3_RELEASE_CHROME_VERSION, found $chrome_version"
executable_name=$(phase3_plist_value CFBundleExecutable "$info_plist") || phase3_fail 'cannot read Chrome executable name'
chrome_executable="$test_app_real/Contents/MacOS/$executable_name"
[[ -x "$chrome_executable" ]] || phase3_fail 'test app main executable is missing'
lipo -info "$chrome_executable" | grep -Eq '(^|[[:space:]])x86_64($|[[:space:]])' || phase3_fail 'test app main executable has no x86_64 slice'

mkdir "$results_real"
process_snapshot="$results_real/process-table-before-launch.txt"
phase3_capture_process_snapshot "$process_snapshot"
source_app=$(phase3_manifest_value "$(phase3_manifest_path "$test_app_real")" 'SOURCE_APP')
source_executable="$source_app/Contents/MacOS/$executable_name"
if source_matches=$(phase3_snapshot_matching_processes "$process_snapshot" "$source_executable") && [[ -n "$source_matches" ]]; then
  printf 'source Chrome process detected; do not mix it with the test copy:\n%s\n' "$source_matches" >&2
  exit 1
fi
if test_copy_matches=$(phase3_snapshot_matching_processes "$process_snapshot" "$chrome_executable") && [[ -n "$test_copy_matches" ]]; then
  printf 'the test copy is already running:\n%s\n' "$test_copy_matches" >&2
  exit 1
fi
profile_dir=$(mktemp -d "${TMPDIR:-/tmp}/chrome-angle-${test_case}.XXXXXX")
command=(
  "$chrome_executable"
  --use-gl=angle
  --use-angle=metal
  --use-dynamic-angle
  --no-first-run
  --no-default-browser-check
  --disable-sync
  --enable-logging=stderr
  "--user-data-dir=$profile_dir"
)
if [[ "$diagnostic_gpu_startup" == true ]]; then
  # Use Chrome's own trace and VLOG facilities rather than DYLD_* variables.
  # Hardened Runtime can ignore DYLD_* unless a separately granted entitlement
  # allows them, whereas these flags leave the signed code unchanged.
  startup_trace="$results_real/chrome-gpu-startup-trace.json"
  command+=(
    '--vmodule=gl_display=2,gl_initializer_mac=2'
    '--trace-startup=gpu,disabled-by-default-gpu.angle'
    "--trace-startup-file=$startup_trace"
    '--trace-startup-duration=15'
  )
fi
if [[ "$test_case" == 'CASE_C' ]]; then
  command+=(--disable-angle-features=requireGpuFamily2)
fi
{
  printf 'timestamp_utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf 'case=%s\n' "$test_case"
  printf 'chrome_version=%s\n' "$chrome_version"
  printf 'angle_revision=%s\n' "$PHASE3_RELEASE_ANGLE_REVISION"
  printf 'artifact_name=%s\n' "$PHASE3_RELEASE_ARTIFACT_NAME"
  printf 'release_manifest_sha256=%s\n' "$(phase3_manifest_value "$(phase3_manifest_path "$test_app_real")" 'RELEASE_MANIFEST_SHA256')"
  printf 'libEGL_sha256=%s\n' "$PHASE3_RELEASE_LIBEGL_SHA256"
  printf 'libGLESv2_sha256=%s\n' "$PHASE3_RELEASE_LIBGLESV2_SHA256"
  printf 'user_data_dir=%s\n' "$profile_dir"
  printf 'diagnostic_gpu_startup=%s\n' "$diagnostic_gpu_startup"
  if [[ "$diagnostic_gpu_startup" == true ]]; then
    printf 'chrome_gpu_startup_trace=%s\n' "$startup_trace"
  fi
  printf 'command='
  printf '%q ' "${command[@]}"
  printf '\n'
} > "$results_real/run-metadata.txt"
printf '%s\n' 'This test copy is Apple Development signed and is not for normal browsing or existing profiles.' >&2
"${command[@]}" > "$results_real/stdout.log" 2> "$results_real/stderr.log" &
browser_pid=$!
printf '%s\n' "$browser_pid" > "$results_real/browser.pid"
printf 'Chrome launched as PID %s. Independent profile retained at: %s\n' "$browser_pid" "$profile_dir"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  phase3_run_main /usr/bin/codesign "$@"
fi
