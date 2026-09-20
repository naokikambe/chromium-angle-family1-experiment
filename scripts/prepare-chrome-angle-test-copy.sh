#!/usr/bin/env bash
set -euo pipefail

PHASE3_SCRIPT_NAME='prepare-chrome-angle-test-copy'
readonly PHASE3_SCRIPT_NAME
source "$(cd "$(dirname "$0")" && pwd -P)/phase3-test-copy-common.sh"

usage() {
  printf 'usage: %s SOURCE_CHROME_APP ARTIFACT_DIRECTORY OUTPUT_CHROME_APP\n' "$0" >&2
  exit 64
}

capture_xattrs() {
  local destination=$1
  local target=$2
  xattr -l "$target" > "$destination" 2>&1 || true
}

verify_source_components() {
  local app=$1 evidence_dir=$2 label=$3 executable_name main_executable framework gpu_helper
  executable_name=$(phase3_plist_value CFBundleExecutable "$app/Contents/Info.plist") || phase3_fail 'cannot read source executable name'
  main_executable="$app/Contents/MacOS/$executable_name"
  framework="$app/Contents/Frameworks/Google Chrome Framework.framework"
  [[ -x "$main_executable" && -d "$framework" ]] || phase3_fail 'source Chrome components are missing'
  codesign --verify --strict "$main_executable" || phase3_fail 'source main executable signature is invalid'
  codesign --verify --strict "$framework" || phase3_fail 'source framework signature is invalid'
  gpu_helper=$(find "$framework" -type f -path '*/Google Chrome Helper (GPU).app/Contents/MacOS/Google Chrome Helper (GPU)' -print -quit)
  [[ -n "$gpu_helper" ]] || phase3_fail 'source GPU Helper is missing'
  codesign --verify --strict "$gpu_helper" || phase3_fail 'source GPU Helper signature is invalid'
  phase3_capture_signature "$evidence_dir/${label}-app" "$app"
  phase3_capture_signature "$evidence_dir/${label}-main" "$main_executable"
  phase3_capture_signature "$evidence_dir/${label}-framework" "$framework"
  phase3_capture_signature "$evidence_dir/${label}-gpu-helper" "$gpu_helper"
}

[[ $# -eq 3 ]] || usage
phase3_reject_root

for command in ditto shasum lipo codesign xattr stat find install cmp; do
  command -v "$command" >/dev/null 2>&1 || phase3_fail "required command is unavailable: $command"
done

source_app=$1
artifact_dir=$2
output_app=$3
[[ -d "$source_app" ]] || phase3_fail "source Chrome app does not exist: $source_app"
[[ -d "$artifact_dir" ]] || phase3_fail "artifact directory does not exist: $artifact_dir"
[[ -f "$source_app/Contents/Info.plist" ]] || phase3_fail 'source app Info.plist is missing'
[[ ! -e "$output_app" && ! -L "$output_app" ]] || phase3_fail "refusing existing output: $output_app"

source_real=$(phase3_real_directory "$source_app")
artifact_real=$(phase3_real_directory "$artifact_dir")
output_parent=$(dirname "$output_app")
output_parent_real=$(phase3_real_directory "$output_parent")
phase3_require_user_owned_directory "$output_parent_real"
output_real="$output_parent_real/$(basename "$output_app")"
phase3_reject_symlink_components "$output_real"
phase3_reject_applications_path "$output_real"
[[ "$source_real" != "$output_real" ]] || phase3_fail 'source and output app paths are identical'

source_version=$(phase3_plist_value CFBundleShortVersionString "$source_real/Contents/Info.plist") || phase3_fail 'cannot read source Chrome version'
[[ "$source_version" == "$PHASE3_CHROME_VERSION" ]] || phase3_fail "expected Chrome $PHASE3_CHROME_VERSION, found $source_version"
source_executable_name=$(phase3_plist_value CFBundleExecutable "$source_real/Contents/Info.plist") || phase3_fail 'cannot read source executable name'
source_executable="$source_real/Contents/MacOS/$source_executable_name"
[[ -x "$source_executable" ]] || phase3_fail 'source main executable is missing'
lipo -info "$source_executable" | grep -Eq '(^|[[:space:]])x86_64($|[[:space:]])' || phase3_fail 'source main executable has no x86_64 slice'

phase3_verify_hash "$artifact_real/libEGL.dylib" "$PHASE3_LIBEGL_SHA256"
phase3_verify_hash "$artifact_real/libGLESv2.dylib" "$PHASE3_LIBGLESV2_SHA256"
[[ -f "$artifact_real/ANGLE_REVISION" && ! -L "$artifact_real/ANGLE_REVISION" ]] || phase3_fail 'artifact ANGLE_REVISION is missing'
[[ "$(<"$artifact_real/ANGLE_REVISION")" == "$PHASE3_ANGLE_REVISION" ]] || phase3_fail 'artifact ANGLE revision does not match'

manifest=$(phase3_manifest_path "$output_real")
manifest_hash=$(phase3_manifest_hash_path "$output_real")
evidence_dir="${manifest}.evidence"
[[ ! -e "$manifest" && ! -e "$manifest_hash" && ! -e "$evidence_dir" ]] || phase3_fail 'refusing existing test-copy sidecar files'
mkdir "$evidence_dir"

# Stage 1: source-only safety checks and evidence. No write targets source_app.
verify_source_components "$source_real" "$evidence_dir" source-before
capture_xattrs "$evidence_dir/source-xattrs-before.txt" "$source_real"

# Stage 2: ditto --help on the target macOS host documents --noextattr and
# --noqtn. Strict verification must pass before either unsigned dylib is placed.
ditto --noextattr --noqtn "$source_real" "$output_real"
[[ -d "$output_real/Contents" && ! -L "$output_real" ]] || phase3_fail 'ditto did not create a regular app bundle'
capture_xattrs "$evidence_dir/copy-xattrs-before-dylibs.txt" "$output_real"
if rg -F 'com.apple.FinderInfo' "$evidence_dir/copy-xattrs-before-dylibs.txt" >/dev/null || rg -F 'com.apple.ResourceFork' "$evidence_dir/copy-xattrs-before-dylibs.txt" >/dev/null; then
  phase3_fail 'copied test app retained FinderInfo or ResourceFork; no dylib was placed'
fi
phase3_capture_signature "$evidence_dir/copy-before-dylibs" "$output_real"
codesign --verify --deep --strict "$output_real" || phase3_fail 'test copy strict signature verification failed before dylib placement'
verify_source_components "$source_real" "$evidence_dir" source-after-copy
cmp "$evidence_dir/source-before-app-details.txt" "$evidence_dir/source-after-copy-app-details.txt" || phase3_fail 'source app signature details changed while preparing the copy'

# Stage 3: only two verified non-component dylibs. This intentionally invalidates
# the copied Google signature; ad-hoc signing is a separate explicit script.
framework="$output_real/Contents/Frameworks/Google Chrome Framework.framework"
[[ -d "$framework" && ! -L "$framework" ]] || phase3_fail 'test copy framework is missing or symlinked'
libraries_dir="$(cd "$framework" && pwd -P)/Libraries"
if [[ -d "$libraries_dir" ]]; then
  [[ -z "$(find "$libraries_dir" -maxdepth 1 -type f -name '*.dylib' -print -quit)" ]] || phase3_fail 'refusing to replace existing dylibs in the test copy'
else
  mkdir "$libraries_dir"
fi
install -m 0755 "$artifact_real/libEGL.dylib" "$libraries_dir/libEGL.dylib"
install -m 0755 "$artifact_real/libGLESv2.dylib" "$libraries_dir/libGLESv2.dylib"
phase3_require_only_angle_dylibs "$libraries_dir"
phase3_verify_hash "$libraries_dir/libEGL.dylib" "$PHASE3_LIBEGL_SHA256"
phase3_verify_hash "$libraries_dir/libGLESv2.dylib" "$PHASE3_LIBGLESV2_SHA256"
phase3_capture_signature "$evidence_dir/copy-after-dylibs" "$output_real"
if codesign --verify --deep --strict "$output_real" > "$evidence_dir/copy-after-dylibs-strict-required.txt" 2>&1; then
  printf 'warning: copied app remained strictly signed after unsigned dylib placement; review before signing.\n' >&2
else
  printf 'expected: unsigned ANGLE dylibs invalidated the copied Google signature; no signing was performed.\n' >&2
fi
verify_source_components "$source_real" "$evidence_dir" source-after-dylibs
cmp "$evidence_dir/source-before-app-details.txt" "$evidence_dir/source-after-dylibs-app-details.txt" || phase3_fail 'source app signature details changed while placing dylibs in the copy'

{
  printf 'SCHEMA=phase3-angle-test-copy-v1\n'
  printf 'TEST_APP=%s\n' "$output_real"
  printf 'SOURCE_APP=%s\n' "$source_real"
  printf 'SOURCE_CHROME_VERSION=%s\n' "$source_version"
  printf 'CHROME_VERSION=%s\n' "$PHASE3_CHROME_VERSION"
  printf 'CHROMIUM_REVISION=%s\n' "$PHASE3_CHROMIUM_REVISION"
  printf 'ANGLE_REVISION=%s\n' "$PHASE3_ANGLE_REVISION"
  printf 'ARTIFACT_NAME=%s\n' "$PHASE3_ARTIFACT_NAME"
  printf 'LIBEGL_SHA256=%s\n' "$PHASE3_LIBEGL_SHA256"
  printf 'LIBGLESV2_SHA256=%s\n' "$PHASE3_LIBGLESV2_SHA256"
  printf 'CREATED_AT_UTC=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf 'PREPARATION_STATE=unsigned-angle-libraries\n'
} > "$manifest"
phase3_write_hash_file "$manifest" "$manifest_hash"

printf 'prepared unsigned test copy: %s\n' "$output_real"
printf 'manifest: %s\n' "$manifest"
printf 'no xattr removal or signing was performed on the copy; use the separate signing script only after review.\n'
