#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf 'collect-phase3-evidence: %s\n' "$1" >&2
  exit 1
}

plist_value() {
  /usr/libexec/PlistBuddy -c "Print :$1" "$2"
}

capture() {
  local destination=$1
  shift
  if "$@" > "$destination" 2>&1; then
    printf 'success\n' >> "$destination"
  else
    printf 'command failed: %s\n' "$?" >> "$destination"
  fi
}

if [[ $# -ne 2 ]]; then
  printf 'usage: %s TEST_CHROME_APP RESULTS_DIRECTORY\n' "$0" >&2
  exit 64
fi

for command in codesign file otool shasum pgrep ps; do
  command -v "$command" >/dev/null 2>&1 || fail "required command is unavailable: $command"
done

test_app=$1
results_dir=$2
[[ -d "$test_app" ]] || fail "test Chrome app does not exist: $test_app"
[[ -d "$results_dir" ]] || fail "results directory does not exist: $results_dir"
test_app_real=$(cd "$test_app" && pwd -P)
case "$test_app_real" in
  /Applications/*) fail 'refusing to collect evidence from an app under /Applications' ;;
esac
[[ "$(basename "$test_app_real")" == *'ANGLE Test.app' ]] ||
  fail 'test app name must end with "ANGLE Test.app"'

info_plist="$test_app_real/Contents/Info.plist"
[[ -f "$info_plist" ]] || fail 'test app has no Info.plist'
chrome_version=$(plist_value CFBundleShortVersionString "$info_plist") || fail 'cannot read Chrome version'
executable_name=$(plist_value CFBundleExecutable "$info_plist") || fail 'cannot read Chrome executable name'
main_executable="$test_app_real/Contents/MacOS/$executable_name"
framework="$test_app_real/Contents/Frameworks/Google Chrome Framework.framework"
[[ -d "$framework" ]] || fail 'test app framework is missing'
framework_real=$(cd "$framework" && pwd -P)
libraries_dir="$framework_real/Libraries"

gpu_helper=$(find "$framework_real" -type f -path '*/Google Chrome Helper (GPU).app/Contents/MacOS/Google Chrome Helper (GPU)' -print -quit)
{
  printf 'chrome_version=%s\n' "$chrome_version"
  printf 'test_app=%s\n' "$test_app_real"
  printf 'framework=%s\n' "$framework_real"
  printf 'libraries=%s\n' "$libraries_dir"
  [[ -f "$results_dir/run-metadata.txt" ]] && cat "$results_dir/run-metadata.txt"
} > "$results_dir/environment.txt"

for library in libEGL.dylib libGLESv2.dylib; do
  library_path="$libraries_dir/$library"
  [[ -f "$library_path" ]] || fail "required dynamic ANGLE library is missing: $library_path"
  capture "$results_dir/${library}.file.txt" file "$library_path"
  capture "$results_dir/${library}.otool-D.txt" otool -D "$library_path"
  capture "$results_dir/${library}.otool-L.txt" otool -L "$library_path"
  capture "$results_dir/${library}.codesign.txt" codesign -dvvv "$library_path"
done
shasum -a 256 "$libraries_dir/libEGL.dylib" "$libraries_dir/libGLESv2.dylib" > "$results_dir/dylib-sha256.txt"
capture "$results_dir/app-codesign.txt" codesign -dvvv "$test_app_real"
capture "$results_dir/app-entitlements.txt" codesign -d --entitlements :- "$test_app_real"
capture "$results_dir/gpu-helper-entitlements.txt" codesign -d --entitlements :- "$gpu_helper"

gpu_pids_file="$results_dir/gpu-processes.txt"
: > "$gpu_pids_file"
pgrep -af "$framework_real" 2>/dev/null | grep 'Google Chrome Helper (GPU)' >> "$gpu_pids_file" || true
if [[ ! -s "$gpu_pids_file" ]]; then
  printf 'No matching GPU process was observed; dynamic ANGLE load is unconfirmed.\n' >> "$gpu_pids_file"
else
  while IFS= read -r gpu_line; do
    gpu_pid=${gpu_line%% *}
    [[ "$gpu_pid" =~ ^[0-9]+$ ]] || continue
    capture "$results_dir/gpu-${gpu_pid}-command.txt" ps -ww -p "$gpu_pid" -o pid=,command=
    if command -v lsof >/dev/null 2>&1; then
      capture "$results_dir/gpu-${gpu_pid}-lsof.txt" lsof -p "$gpu_pid"
      if grep -F -- "$libraries_dir/libEGL.dylib" "$results_dir/gpu-${gpu_pid}-lsof.txt" >/dev/null && \
         grep -F -- "$libraries_dir/libGLESv2.dylib" "$results_dir/gpu-${gpu_pid}-lsof.txt" >/dev/null; then
        printf 'direct dynamic ANGLE load evidence: lsof confirmed both dylib absolute paths for GPU PID %s\n' "$gpu_pid" >> "$results_dir/load-evidence.txt"
      fi
    fi
    if command -v vmmap >/dev/null 2>&1; then
      capture "$results_dir/gpu-${gpu_pid}-vmmap.txt" vmmap "$gpu_pid"
      if grep -F -- "$libraries_dir/libEGL.dylib" "$results_dir/gpu-${gpu_pid}-vmmap.txt" >/dev/null && \
         grep -F -- "$libraries_dir/libGLESv2.dylib" "$results_dir/gpu-${gpu_pid}-vmmap.txt" >/dev/null; then
        printf 'direct dynamic ANGLE load evidence: vmmap confirmed both dylib absolute paths for GPU PID %s\n' "$gpu_pid" >> "$results_dir/load-evidence.txt"
      fi
    fi
  done < "$gpu_pids_file"
fi
[[ -f "$results_dir/load-evidence.txt" ]] ||
  printf 'No direct dylib load evidence was collected; do not report dynamic ANGLE as loaded.\n' > "$results_dir/load-evidence.txt"

if [[ -f "$results_dir/stderr.log" ]]; then
  grep -Ei 'EGL|Metal|requireGpuFamily2|GL implementation|Display type|GL_VENDOR|GL_RENDERER|WebGL|Compositing|Rasterization|GPU process|crash' \
    "$results_dir/stderr.log" > "$results_dir/chrome-log-extract.txt" || true
fi
cat > "$results_dir/chrome-gpu-manual.txt" <<'EOF'
Save chrome://gpu from the isolated test app after the run. Record GPU process crash count, GL implementation parts, Display type, GL_VENDOR, GL_RENDERER, WebGL, Compositing, Rasterization, and any EGL or Metal error. The command line only proves requested switches; require lsof, vmmap, or an equivalent dyld record before claiming external ANGLE was loaded.
EOF
printf 'evidence collection complete: %s\n' "$results_dir"
