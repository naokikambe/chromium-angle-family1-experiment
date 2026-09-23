#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf 'inspect-chrome-for-dynamic-angle: %s\n' "$1" >&2
  exit 1
}

report_command() {
  local label=$1
  shift
  printf '\n== %s ==\n' "$label"
  if "$@"; then
    printf 'status: success\n'
  else
    printf 'status: failed (%s)\n' "$?"
  fi
}

plist_value() {
  /usr/libexec/PlistBuddy -c "Print :$1" "$2"
}

summarize_signature() {
  local label=$1
  local target=$2
  local details
  local entitlements
  local team_identifier

  details=$(/usr/bin/codesign -dvvv "$target" 2>&1 || true)
  entitlements=$(/usr/bin/codesign -d --entitlements :- "$target" 2>&1 || true)
  team_identifier=$(printf '%s\n' "$details" | sed -n 's/^TeamIdentifier=//p' | head -n 1)
  printf '%s TeamIdentifier: %s\n' "$label" "${team_identifier:-unavailable}"
  if printf '%s\n' "$details" | grep -Eq 'flags=.*runtime'; then
    printf '%s Hardened Runtime: present\n' "$label"
  else
    printf '%s Hardened Runtime: absent or unconfirmed\n' "$label"
  fi
  if printf '%s\n' "$entitlements" | grep -F 'com.apple.security.cs.disable-library-validation' >/dev/null; then
    printf '%s disable-library-validation entitlement: present\n' "$label"
  else
    printf '%s disable-library-validation entitlement: absent or unconfirmed\n' "$label"
  fi
}

if [[ $# -ne 1 ]]; then
  printf 'usage: %s CHROME_APP\n' "$0" >&2
  exit 64
fi

for command in file lipo; do
  command -v "$command" >/dev/null 2>&1 || fail "required command is unavailable: $command"
done
[[ -x /usr/bin/codesign ]] || fail 'required production codesign executable is unavailable: /usr/bin/codesign'

chrome_app=$1
[[ -d "$chrome_app" ]] || fail "Chrome app does not exist: $chrome_app"
info_plist="$chrome_app/Contents/Info.plist"
[[ -f "$info_plist" ]] || fail "missing app Info.plist: $info_plist"

chrome_version=$(plist_value CFBundleShortVersionString "$info_plist") ||
  fail 'cannot read CFBundleShortVersionString'
chrome_build=$(plist_value CFBundleVersion "$info_plist") || fail 'cannot read CFBundleVersion'
executable_name=$(plist_value CFBundleExecutable "$info_plist") || fail 'cannot read CFBundleExecutable'
main_executable="$chrome_app/Contents/MacOS/$executable_name"
framework="$chrome_app/Contents/Frameworks/Google Chrome Framework.framework"

[[ -x "$main_executable" ]] || fail "missing main executable: $main_executable"
[[ -d "$framework" ]] || fail "missing Chrome framework: $framework"
framework_real=$(cd "$framework" && pwd -P)
libraries_dir="$framework_real/Libraries"

printf 'Chrome app: %s\n' "$chrome_app"
printf 'CFBundleShortVersionString: %s\n' "$chrome_version"
printf 'CFBundleVersion: %s\n' "$chrome_build"
printf 'Main executable: %s\n' "$main_executable"
printf 'Framework real path: %s\n' "$framework_real"
printf 'dynamic ANGLE Libraries candidate: %s\n' "$libraries_dir"

[[ "$chrome_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail 'Chrome version is not a four-part numeric version'

printf '\n== Main executable architecture ==\n'
lipo -info "$main_executable"
if ! lipo -info "$main_executable" 2>&1 | grep -Eq '(^|[[:space:]])x86_64($|[[:space:]])'; then
  printf 'warning: main executable does not report x86_64\n' >&2
fi
file "$main_executable"

report_command 'App signature verification' /usr/bin/codesign --verify --deep --strict "$chrome_app"
report_command 'App signature details' /usr/bin/codesign -dvvv "$chrome_app"
report_command 'App entitlements' /usr/bin/codesign -d --entitlements :- "$chrome_app"
report_command 'Main executable signature details' /usr/bin/codesign -dvvv "$main_executable"
report_command 'Framework signature details' /usr/bin/codesign -dvvv "$framework_real"
summarize_signature 'App' "$chrome_app"
summarize_signature 'Main executable' "$main_executable"
summarize_signature 'Framework' "$framework_real"

gpu_helper=$(find "$framework_real" -type f -path '*/Google Chrome Helper (GPU).app/Contents/MacOS/Google Chrome Helper (GPU)' -print -quit)
if [[ -n "$gpu_helper" ]]; then
  printf 'GPU Helper: %s\n' "$gpu_helper"
  report_command 'GPU Helper signature details' /usr/bin/codesign -dvvv "$gpu_helper"
  report_command 'GPU Helper entitlements' /usr/bin/codesign -d --entitlements :- "$gpu_helper"
  summarize_signature 'GPU Helper' "$gpu_helper"
else
  printf 'warning: GPU Helper executable was not found under the framework\n' >&2
fi

for library in libEGL.dylib libGLESv2.dylib; do
  library_path="$libraries_dir/$library"
  if [[ -e "$library_path" ]]; then
    printf 'existing %s: %s\n' "$library" "$library_path"
    report_command "$library signature details" /usr/bin/codesign -dvvv "$library_path"
  else
    printf 'existing %s: absent\n' "$library"
  fi
done
