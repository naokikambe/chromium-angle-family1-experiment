#!/usr/bin/env bash
set -euo pipefail

PHASE3_SCRIPT_NAME='collect-phase3-evidence'
readonly PHASE3_SCRIPT_NAME
source "$(cd "$(dirname "$0")" && pwd -P)/phase3-test-copy-common.sh"

capture() {
  local destination=$1
  shift
  if "$@" > "$destination" 2>&1; then printf 'status: success\n' >> "$destination"; else printf 'status: failed (%s)\n' "$?" >> "$destination"; fi
}

[[ $# -eq 2 ]] || { printf 'usage: %s TEST_CHROME_APP RESULTS_DIRECTORY\n' "$0" >&2; exit 64; }
phase3_reject_root
test_app=$1
results_dir=$2
for command in codesign file otool shasum pgrep ps find; do command -v "$command" >/dev/null 2>&1 || phase3_fail "required command is unavailable: $command"; done
[[ -d "$test_app" ]] || phase3_fail "test app does not exist: $test_app"
[[ -d "$results_dir" && ! -L "$results_dir" ]] || phase3_fail "results directory does not exist: $results_dir"
test_app_real=$(phase3_real_directory "$test_app")
phase3_reject_applications_path "$test_app_real"
results_real=$(phase3_real_directory "$results_dir")
phase3_validate_manifest "$test_app_real"
receipt=$(phase3_receipt_path "$test_app_real")
phase3_verify_sidecar_hash "$receipt" "$(phase3_receipt_hash_path "$test_app_real")"
[[ "$(phase3_manifest_value "$receipt" 'SIGNING_METHOD')" == 'ad-hoc-deep' ]] || phase3_fail 'test copy signing receipt is not ad-hoc'

manifest=$(phase3_manifest_path "$test_app_real")
source_app=$(phase3_manifest_value "$manifest" 'SOURCE_APP')
framework="$test_app_real/Contents/Frameworks/Google Chrome Framework.framework"
libraries_dir="$(cd "$framework" && pwd -P)/Libraries"
executable_name=$(phase3_plist_value CFBundleExecutable "$test_app_real/Contents/Info.plist") || phase3_fail 'cannot read Chrome executable name'
main_executable="$test_app_real/Contents/MacOS/$executable_name"
gpu_helper=$(find "$framework" -type f -path '*/Google Chrome Helper (GPU).app/Contents/MacOS/Google Chrome Helper (GPU)' -print -quit)
[[ -n "$gpu_helper" ]] || phase3_fail 'GPU Helper is missing'

phase3_capture_signature "$results_real/test-copy-current" "$test_app_real"
phase3_capture_signature "$results_real/main-current" "$main_executable"
phase3_capture_signature "$results_real/framework-current" "$framework"
phase3_capture_signature "$results_real/gpu-helper-current" "$gpu_helper"
if [[ -d "$source_app" && ! -L "$source_app" ]]; then phase3_capture_signature "$results_real/source-current-read-only" "$source_app"; fi
for library in libEGL.dylib libGLESv2.dylib; do
  library_path="$libraries_dir/$library"
  capture "$results_real/${library}.file.txt" file "$library_path"
  capture "$results_real/${library}.otool-D.txt" otool -D "$library_path"
  capture "$results_real/${library}.otool-L.txt" otool -L "$library_path"
  phase3_capture_signature "$results_real/${library}" "$library_path"
done
shasum -a 256 "$libraries_dir/libEGL.dylib" "$libraries_dir/libGLESv2.dylib" > "$results_real/dylib-sha256.txt"

sign_results=$(phase3_manifest_value "$receipt" 'RESULTS_DIRECTORY')
if [[ -d "$sign_results" && ! -L "$sign_results" ]]; then
  find "$sign_results" -maxdepth 1 -type f \( -name '*-details.diff' -o -name '*-entitlements.diff' -o -name 'signing-metadata.txt' \) -exec cp {} "$results_real" \;
fi

gpu_pids_file="$results_real/gpu-processes.txt"
: > "$gpu_pids_file"
pgrep -af "$framework" 2>/dev/null | grep 'Google Chrome Helper (GPU)' >> "$gpu_pids_file" || true
if [[ ! -s "$gpu_pids_file" ]]; then
  printf 'No matching GPU process was observed; dynamic ANGLE load is unconfirmed.\n' >> "$gpu_pids_file"
else
  while IFS= read -r gpu_line; do
    gpu_pid=${gpu_line%% *}
    [[ "$gpu_pid" =~ ^[0-9]+$ ]] || continue
    capture "$results_real/gpu-${gpu_pid}-command.txt" ps -ww -p "$gpu_pid" -o pid=,command=
    if command -v lsof >/dev/null 2>&1; then
      capture "$results_real/gpu-${gpu_pid}-lsof.txt" lsof -p "$gpu_pid"
      if grep -F -- "$libraries_dir/libEGL.dylib" "$results_real/gpu-${gpu_pid}-lsof.txt" >/dev/null && grep -F -- "$libraries_dir/libGLESv2.dylib" "$results_real/gpu-${gpu_pid}-lsof.txt" >/dev/null; then
        printf 'direct dynamic ANGLE load evidence: lsof confirmed both test-copy dylib absolute paths for GPU PID %s\n' "$gpu_pid" >> "$results_real/load-evidence.txt"
      fi
    fi
    if command -v vmmap >/dev/null 2>&1; then
      capture "$results_real/gpu-${gpu_pid}-vmmap.txt" vmmap "$gpu_pid"
      if grep -F -- "$libraries_dir/libEGL.dylib" "$results_real/gpu-${gpu_pid}-vmmap.txt" >/dev/null && grep -F -- "$libraries_dir/libGLESv2.dylib" "$results_real/gpu-${gpu_pid}-vmmap.txt" >/dev/null; then
        printf 'direct dynamic ANGLE load evidence: vmmap confirmed both test-copy dylib absolute paths for GPU PID %s\n' "$gpu_pid" >> "$results_real/load-evidence.txt"
      fi
    fi
  done < "$gpu_pids_file"
fi
[[ -f "$results_real/load-evidence.txt" ]] || printf 'No direct dylib load evidence was collected; do not report dynamic ANGLE as loaded.\n' > "$results_real/load-evidence.txt"
if [[ -f "$results_real/stderr.log" ]]; then
  grep -Ei 'EGL|Metal|requireGpuFamily2|GL implementation|Display type|GL_VENDOR|GL_RENDERER|WebGL|Compositing|Rasterization|GPU process|crash' "$results_real/stderr.log" > "$results_real/chrome-log-extract.txt" || true
fi
cat > "$results_real/chrome-gpu-manual.txt" <<'EOF'
Save chrome://gpu from the isolated test app after the run. Record GPU process crash count, GL implementation parts, Display type, GL_VENDOR, GL_RENDERER, WebGL, Compositing, Rasterization, and EGL/Metal errors. Command-line switches are not load proof: report external ANGLE as loaded only when lsof, vmmap, or equivalent direct evidence names both test-copy dylib absolute paths.
EOF
printf 'evidence collection complete: %s\n' "$results_real"
