#!/usr/bin/env bash
set -euo pipefail

readonly EXPECTED_CHROME_VERSION='154.0.8037.17'
readonly LIBEGL_SHA256='f4a8a7575183a41373404f7c25b4f56e1a1540c5b1578d11437c180b1f698db8'
readonly LIBGLESV2_SHA256='2e0aadc21e76b0bb1adcfb3b908e757906995b75abb9e90edb3dfb5c1d1adef0'

fail() {
  printf 'prepare-chrome-angle-test-copy: %s\n' "$1" >&2
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

if [[ $# -lt 2 || $# -gt 4 ]]; then
  printf 'usage: %s SOURCE_CHROME_APP ARTIFACT_DIRECTORY [OUTPUT_CHROME_APP] [--allow-existing-empty-output]\n' "$0" >&2
  exit 64
fi

source_app=$1
artifact_dir=$2
output_app=${3:-"$HOME/Applications/Google Chrome 154 ANGLE Test.app"}
allow_existing_empty_output=false
if [[ $# -eq 4 ]]; then
  [[ "$4" == '--allow-existing-empty-output' ]] || fail "unknown option: $4"
  allow_existing_empty_output=true
fi

for command in ditto shasum lipo codesign; do
  command -v "$command" >/dev/null 2>&1 || fail "required command is unavailable: $command"
done
[[ -d "$source_app" ]] || fail "source Chrome app does not exist: $source_app"
[[ -d "$artifact_dir" ]] || fail "artifact directory does not exist: $artifact_dir"
[[ -f "$source_app/Contents/Info.plist" ]] || fail 'source app has no Info.plist'

source_real=$(cd "$source_app" && pwd -P)
output_parent=$(dirname "$output_app")
case "$output_app" in
  /Applications/*) fail 'refusing to write anywhere under /Applications' ;;
esac
[[ -d "$output_parent" ]] || fail "output parent does not exist: $output_parent"
output_parent_real=$(cd "$output_parent" && pwd -P)
output_real="$output_parent_real/$(basename "$output_app")"

[[ "$source_real" != "$output_real" ]] || fail 'source app and output app are the same path'
case "$output_real" in
  /Applications/*) fail 'refusing to write anywhere under /Applications' ;;
esac

if [[ -e "$output_real" ]]; then
  [[ "$allow_existing_empty_output" == true ]] ||
    fail "refusing to overwrite existing output: $output_real"
  [[ -d "$output_real" ]] || fail 'existing output is not a directory'
  [[ -z "$(find "$output_real" -mindepth 1 -maxdepth 1 -print -quit)" ]] ||
    fail 'existing output must be empty; this script never deletes or overwrites an app'
fi

source_version=$(plist_value CFBundleShortVersionString "$source_real/Contents/Info.plist") ||
  fail 'cannot read source Chrome version'
[[ "$source_version" == "$EXPECTED_CHROME_VERSION" ]] ||
  fail "expected Chrome $EXPECTED_CHROME_VERSION, found $source_version"
source_executable_name=$(plist_value CFBundleExecutable "$source_real/Contents/Info.plist") ||
  fail 'cannot read source executable name'
source_executable="$source_real/Contents/MacOS/$source_executable_name"
[[ -x "$source_executable" ]] || fail 'source main executable is missing'
lipo -info "$source_executable" | grep -Eq '(^|[[:space:]])x86_64($|[[:space:]])' ||
  fail 'source Chrome main executable is not x86_64'
codesign --verify --deep --strict "$source_real" || fail 'source Chrome signature is not valid before copying'

verify_hash "$artifact_dir/libEGL.dylib" "$LIBEGL_SHA256"
verify_hash "$artifact_dir/libGLESv2.dylib" "$LIBGLESV2_SHA256"

ditto "$source_real" "$output_real"
[[ -d "$output_real/Contents" ]] || fail 'ditto did not create a Chrome app bundle at the requested output'
codesign --verify --deep --strict "$output_real" || fail 'test copy signature failed before dylib placement'

framework="$output_real/Contents/Frameworks/Google Chrome Framework.framework"
[[ -d "$framework" ]] || fail 'test copy has no Google Chrome Framework.framework'
framework_real=$(cd "$framework" && pwd -P)
libraries_dir="$framework_real/Libraries"
mkdir -p "$libraries_dir"
install -m 0755 "$artifact_dir/libEGL.dylib" "$libraries_dir/libEGL.dylib"
install -m 0755 "$artifact_dir/libGLESv2.dylib" "$libraries_dir/libGLESv2.dylib"
verify_hash "$libraries_dir/libEGL.dylib" "$LIBEGL_SHA256"
verify_hash "$libraries_dir/libGLESv2.dylib" "$LIBGLESV2_SHA256"

codesign --verify --deep --strict "$source_real" ||
  fail 'source Chrome signature changed unexpectedly; stop and inspect manually'
if ! codesign --verify --deep --strict "$output_real"; then
  printf 'test copy signature is invalid after placing unsigned ANGLE dylibs; no signing was performed.\n' >&2
  printf 'stop here: Phase 3B requires an explicit Library Validation and signing decision.\n' >&2
  exit 1
fi

printf 'test copy prepared without re-signing: %s\n' "$output_real"
printf 'dynamic ANGLE Libraries directory: %s\n' "$libraries_dir"
