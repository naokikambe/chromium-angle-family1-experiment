#!/usr/bin/env bash
set -euo pipefail

PHASE3_SCRIPT_NAME='run-dynamic-angle-test'
readonly PHASE3_SCRIPT_NAME
source "$(cd "$(dirname "$0")" && pwd -P)/phase3-test-copy-common.sh"

[[ $# -eq 3 ]] || { printf 'usage: %s CASE_B|CASE_C TEST_CHROME_APP RESULTS_DIRECTORY\n' "$0" >&2; exit 64; }
phase3_reject_root
test_case=$1
test_app=$2
results_dir=$3
case "$test_case" in CASE_B|CASE_C) ;; *) phase3_fail 'case must be CASE_B or CASE_C' ;; esac
for command in lipo codesign shasum pgrep; do command -v "$command" >/dev/null 2>&1 || phase3_fail "required command is unavailable: $command"; done
[[ -d "$test_app" ]] || phase3_fail "test app does not exist: $test_app"
[[ ! -e "$results_dir" && ! -L "$results_dir" ]] || phase3_fail "refusing existing results: $results_dir"
test_app_real=$(phase3_real_directory "$test_app")
phase3_reject_applications_path "$test_app_real"
results_parent_real=$(phase3_real_directory "$(dirname "$results_dir")")
phase3_require_user_owned_directory "$results_parent_real"
results_real="$results_parent_real/$(basename "$results_dir")"
phase3_reject_symlink_components "$results_real"
phase3_validate_manifest "$test_app_real"

receipt=$(phase3_receipt_path "$test_app_real")
receipt_hash=$(phase3_receipt_hash_path "$test_app_real")
phase3_verify_sidecar_hash "$receipt" "$receipt_hash"
[[ "$(phase3_manifest_value "$receipt" 'SCHEMA')" == 'phase3-angle-signing-receipt-v1' ]] || phase3_fail 'unsupported signing receipt schema'
[[ "$(phase3_manifest_value "$receipt" 'TEST_APP')" == "$test_app_real" ]] || phase3_fail 'signing receipt app path does not match'
[[ "$(phase3_manifest_value "$receipt" 'SIGNING_METHOD')" == 'ad-hoc-deep' ]] || phase3_fail 'test copy was not ad-hoc signed'
[[ "$(phase3_manifest_value "$receipt" 'STRICT_VERIFICATION')" == 'passed' ]] || phase3_fail 'signing receipt does not record strict verification'
codesign --verify --deep --strict "$test_app_real" || phase3_fail 'test copy strict signature verification failed'
codesign -dvvv "$test_app_real" 2>&1 | grep -F 'Signature=adhoc' >/dev/null || phase3_fail 'test copy is not currently ad-hoc signed'

info_plist="$test_app_real/Contents/Info.plist"
chrome_version=$(phase3_plist_value CFBundleShortVersionString "$info_plist") || phase3_fail 'cannot read Chrome version'
[[ "$chrome_version" == "$PHASE3_CHROME_VERSION" ]] || phase3_fail "expected Chrome $PHASE3_CHROME_VERSION, found $chrome_version"
executable_name=$(phase3_plist_value CFBundleExecutable "$info_plist") || phase3_fail 'cannot read Chrome executable name'
chrome_executable="$test_app_real/Contents/MacOS/$executable_name"
[[ -x "$chrome_executable" ]] || phase3_fail 'test app main executable is missing'
lipo -info "$chrome_executable" | grep -Eq '(^|[[:space:]])x86_64($|[[:space:]])' || phase3_fail 'test app main executable has no x86_64 slice'

if pgrep -fl 'Google Chrome' >/dev/null 2>&1; then
  printf 'existing Chrome process detected; do not mix the test app with an existing Chrome/profile:\n' >&2
  pgrep -fl 'Google Chrome' >&2 || true
  exit 1
fi
if pgrep -af "$test_app_real" >/dev/null 2>&1; then
  phase3_fail 'the test copy is already running'
fi

mkdir "$results_real"
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
if [[ "$test_case" == 'CASE_C' ]]; then
  command+=(--disable-angle-features=requireGpuFamily2)
fi
{
  printf 'timestamp_utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf 'case=%s\n' "$test_case"
  printf 'chrome_version=%s\n' "$chrome_version"
  printf 'angle_revision=%s\n' "$PHASE3_ANGLE_REVISION"
  printf 'artifact_name=%s\n' "$PHASE3_ARTIFACT_NAME"
  printf 'libEGL_sha256=%s\n' "$PHASE3_LIBEGL_SHA256"
  printf 'libGLESv2_sha256=%s\n' "$PHASE3_LIBGLESV2_SHA256"
  printf 'user_data_dir=%s\n' "$profile_dir"
  printf 'command='
  printf '%q ' "${command[@]}"
  printf '\n'
} > "$results_real/run-metadata.txt"
printf '%s\n' 'This test copy is ad-hoc signed and is not for normal browsing or existing profiles.' >&2
"${command[@]}" > "$results_real/stdout.log" 2> "$results_real/stderr.log" &
browser_pid=$!
printf '%s\n' "$browser_pid" > "$results_real/browser.pid"
printf 'Chrome launched as PID %s. Independent profile retained at: %s\n' "$browser_pid" "$profile_dir"
