#!/usr/bin/env bash
set -euo pipefail

readonly EXPECTED_CHROME_VERSION='154.0.8037.17'
readonly LIBEGL_SHA256='f4a8a7575183a41373404f7c25b4f56e1a1540c5b1578d11437c180b1f698db8'
readonly LIBGLESV2_SHA256='2e0aadc21e76b0bb1adcfb3b908e757906995b75abb9e90edb3dfb5c1d1adef0'

fail() {
  printf 'run-dynamic-angle-test: %s\n' "$1" >&2
  exit 1
}

plist_value() {
  /usr/libexec/PlistBuddy -c "Print :$1" "$2"
}

verify_hash() {
  local path=$1
  local expected=$2
  local actual
  actual=$(shasum -a 256 "$path" | awk '{print $1}')
  [[ "$actual" == "$expected" ]] || fail "SHA-256 mismatch for $path"
}

if [[ $# -ne 3 ]]; then
  printf 'usage: %s CASE_B|CASE_C TEST_CHROME_APP RESULTS_DIRECTORY\n' "$0" >&2
  exit 64
fi

test_case=$1
test_app=$2
results_dir=$3
case "$test_case" in
  CASE_B|CASE_C) ;;
  *) fail 'case must be CASE_B or CASE_C' ;;
esac

for command in lipo codesign shasum pgrep; do
  command -v "$command" >/dev/null 2>&1 || fail "required command is unavailable: $command"
done
[[ -d "$test_app" ]] || fail "test Chrome app does not exist: $test_app"
[[ ! -e "$results_dir" ]] || fail "refusing to overwrite existing results: $results_dir"

repo_root=$(git rev-parse --show-toplevel 2>/dev/null || true)
results_parent=$(dirname "$results_dir")
[[ -d "$results_parent" ]] || fail "results parent does not exist: $results_parent"
results_parent_real=$(cd "$results_parent" && pwd -P)
results_real="$results_parent_real/$(basename "$results_dir")"
if [[ -n "$repo_root" ]]; then
  repo_root=$(cd "$repo_root" && pwd -P)
  if [[ "$results_real" == "$repo_root" || "$results_real" == "$repo_root/"* ]]; then
    git check-ignore -q --no-index "$results_real" ||
      fail 'results inside the repository must be covered by .gitignore'
  fi
fi

test_app_real=$(cd "$test_app" && pwd -P)
case "$test_app_real" in
  /Applications/*) fail 'refusing to launch an app under /Applications' ;;
esac
[[ "$(basename "$test_app_real")" == *'ANGLE Test.app' ]] ||
  fail 'test app name must end with "ANGLE Test.app"'

info_plist="$test_app_real/Contents/Info.plist"
[[ -f "$info_plist" ]] || fail 'test app has no Info.plist'
chrome_version=$(plist_value CFBundleShortVersionString "$info_plist") || fail 'cannot read Chrome version'
[[ "$chrome_version" == "$EXPECTED_CHROME_VERSION" ]] ||
  fail "expected Chrome $EXPECTED_CHROME_VERSION, found $chrome_version"
executable_name=$(plist_value CFBundleExecutable "$info_plist") || fail 'cannot read Chrome executable name'
chrome_executable="$test_app_real/Contents/MacOS/$executable_name"
[[ -x "$chrome_executable" ]] || fail 'test app main executable is missing'
lipo -info "$chrome_executable" | grep -Eq '(^|[[:space:]])x86_64($|[[:space:]])' ||
  fail 'test app main executable is not x86_64'
codesign --verify --deep --strict "$test_app_real" ||
  fail 'test app signature is invalid; do not bypass Library Validation or re-sign automatically'

framework="$test_app_real/Contents/Frameworks/Google Chrome Framework.framework"
[[ -d "$framework" ]] || fail 'test app framework is missing'
libraries_dir="$(cd "$framework" && pwd -P)/Libraries"
verify_hash "$libraries_dir/libEGL.dylib" "$LIBEGL_SHA256"
verify_hash "$libraries_dir/libGLESv2.dylib" "$LIBGLESV2_SHA256"

if pgrep -fl 'Google Chrome' >/dev/null 2>&1; then
  printf 'existing Chrome processes detected; stop before using a separate test profile:\n' >&2
  pgrep -fl 'Google Chrome' >&2 || true
  exit 1
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
  printf 'test_app=%s\n' "$test_app_real"
  printf 'libEGL_sha256=%s\n' "$LIBEGL_SHA256"
  printf 'libGLESv2_sha256=%s\n' "$LIBGLESV2_SHA256"
  printf 'user_data_dir=%s\n' "$profile_dir"
  printf 'command='
  printf '%q ' "${command[@]}"
  printf '\n'
} > "$results_real/run-metadata.txt"

"${command[@]}" > "$results_real/stdout.log" 2> "$results_real/stderr.log" &
browser_pid=$!
printf '%s\n' "$browser_pid" > "$results_real/browser.pid"
printf 'Chrome launched as PID %s. Independent profile retained at: %s\n' "$browser_pid" "$profile_dir"
printf 'Run evidence collection only after observing the test app; no profile cleanup is automatic.\n'
