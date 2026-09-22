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
  local recursive=${3:-false}

  if [[ "$recursive" == true ]]; then
    xattr -lr "$target" > "$destination" 2>&1 || true
  else
    xattr -l "$target" > "$destination" 2>&1 || true
  fi
}

readonly SOURCE_METADATA_DETRITUS='resource fork, Finder information, or similar detritus not allowed'
readonly EXPECTED_TEAM_IDENTIFIER='EQHXZ8M8AV'
readonly EXPECTED_GOOGLE_AUTHORITY='Authority=Developer ID Application: Google LLC (EQHXZ8M8AV)'

capture_component_evidence() {
  local prefix=$1
  local target=$2
  local executable

  codesign -dvvv "$target" > "${prefix}-details.txt" 2>&1 || true
  codesign -d --entitlements :- "$target" > "${prefix}-entitlements.txt" 2>&1 || true
  capture_xattrs "${prefix}-xattrs.txt" "$target"
  executable=$(awk -F= '/^Executable=/{print substr($0, index($0, "=") + 1); exit}' "${prefix}-details.txt")
  [[ -f "$executable" && ! -L "$executable" ]] || phase3_fail "cannot identify a regular executable for evidence: $target"
  shasum -a 256 "$executable" | awk '{print $1}' > "${prefix}-sha256.txt"
  printf '%s\n' "$executable" > "${prefix}-executable-path.txt"
}

strict_output_is_metadata_detritus_only() {
  local output=$1
  awk -v message="$SOURCE_METADATA_DETRITUS" '
    NF { seen = 1; if (index($0, message) == 0) invalid = 1 }
    END { exit(seen && !invalid ? 0 : 1) }
  ' "$output"
}

verify_source_component() {
  local prefix=$1
  local target=$2
  local status

  capture_component_evidence "$prefix" "$target"
  set +e
  codesign --verify --strict "$target" > "${prefix}-strict-verify.txt" 2>&1
  status=$?
  set -e
  printf '%s\n' "$status" > "${prefix}-strict-verify-status.txt"
  if [[ "$status" -eq 0 ]]; then
    printf 'passed\n' > "${prefix}-strict-classification.txt"
    return
  fi
  if strict_output_is_metadata_detritus_only "${prefix}-strict-verify.txt"; then
    printf 'warning: source-side metadata detritus only\n' > "${prefix}-strict-classification.txt"
    return
  fi
  printf 'fatal: unexpected source strict verification failure\n' > "${prefix}-strict-classification.txt"
  phase3_fail "source strict verification failed for $target"
}

verify_source_components() {
  local app=$1 evidence_dir=$2 label=$3 executable_name main_executable framework gpu_helper
  executable_name=$(phase3_plist_value CFBundleExecutable "$app/Contents/Info.plist") || phase3_fail 'cannot read source executable name'
  main_executable="$app/Contents/MacOS/$executable_name"
  framework="$app/Contents/Frameworks/Google Chrome Framework.framework"
  gpu_helper=$(find "$framework" -type f -path '*/Google Chrome Helper (GPU).app/Contents/MacOS/Google Chrome Helper (GPU)' -print -quit)
  [[ -x "$main_executable" && -d "$framework" && -n "$gpu_helper" ]] || phase3_fail 'source Chrome components are missing'
  verify_source_component "$evidence_dir/${label}-app" "$app"
  verify_source_component "$evidence_dir/${label}-main" "$main_executable"
  verify_source_component "$evidence_dir/${label}-framework" "$framework"
  verify_source_component "$evidence_dir/${label}-gpu-helper" "$gpu_helper"
}

verify_copy_component() {
  local prefix=$1
  local target=$2
  shift 2

  capture_component_evidence "$prefix" "$target"
  "$@" > "${prefix}-strict-verify.txt" 2>&1 || phase3_fail "test copy strict verification failed for $target"
  printf '0\n' > "${prefix}-strict-verify-status.txt"
  grep -F "TeamIdentifier=$EXPECTED_TEAM_IDENTIFIER" "${prefix}-details.txt" >/dev/null ||
    phase3_fail "test copy TeamIdentifier mismatch for $target"
  grep -F "$EXPECTED_GOOGLE_AUTHORITY" "${prefix}-details.txt" >/dev/null ||
    phase3_fail "test copy is not Google Developer ID signed: $target"
}

compare_component_identity_and_hash() {
  local left_prefix=$1
  local right_prefix=$2
  local left_identity="${left_prefix}-identity.txt"
  local right_identity="${right_prefix}-identity.txt"

  grep -E '^(Authority|TeamIdentifier|CodeDirectory)' "${left_prefix}-details.txt" > "$left_identity" || true
  grep -E '^(Authority|TeamIdentifier|CodeDirectory)' "${right_prefix}-details.txt" > "$right_identity" || true
  cmp "${left_prefix}-sha256.txt" "${right_prefix}-sha256.txt" || phase3_fail "component SHA-256 differs: $left_prefix"
  cmp "$left_identity" "$right_identity" || phase3_fail "component signing identity differs: $left_prefix"
}

verify_clean_copy_components() {
  local app=$1 evidence_dir=$2 framework framework_executable main_executable gpu_helper executable_name
  executable_name=$(phase3_plist_value CFBundleExecutable "$app/Contents/Info.plist") || phase3_fail 'cannot read test copy executable name'
  main_executable="$app/Contents/MacOS/$executable_name"
  framework="$app/Contents/Frameworks/Google Chrome Framework.framework"
  [[ -d "$framework" && ! -L "$framework" ]] || phase3_fail 'test copy framework is missing or symlinked'
  framework_executable=$(find "$framework" -type f -name 'Google Chrome Framework' -print -quit)
  gpu_helper=$(find "$framework" -type f -path '*/Google Chrome Helper (GPU).app/Contents/MacOS/Google Chrome Helper (GPU)' -print -quit)
  [[ -f "$app/Contents/Info.plist" && -d "$app/Contents/Resources" && -x "$main_executable" && -f "$framework_executable" && -x "$gpu_helper" ]] ||
    phase3_fail 'test copy required files, directories, or executable attributes are missing'
  verify_copy_component "$evidence_dir/copy-before-dylibs-app" "$app" codesign --verify --deep --strict "$app"
  verify_copy_component "$evidence_dir/copy-before-dylibs-main" "$main_executable" codesign --verify --strict "$main_executable"
  verify_copy_component "$evidence_dir/copy-before-dylibs-framework" "$framework" codesign --verify --strict "$framework"
  verify_copy_component "$evidence_dir/copy-before-dylibs-gpu-helper" "$gpu_helper" codesign --verify --strict "$gpu_helper"
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
capture_xattrs "$evidence_dir/source-xattrs-before-recursive.txt" "$source_real" true

# Stage 2: --norsrc excludes resource forks and HFS metadata; the explicit
# no* options document that extended attributes, ACLs, and quarantine are not copied.
printf 'COPY_POLICY=%s\n' "$PHASE3_COPY_POLICY" > "$evidence_dir/copy-policy.txt"
printf '%s\n' 'ditto --norsrc --noextattr --noacl --noqtn SOURCE_APP OUTPUT_APP' > "$evidence_dir/copy-command.txt"
ditto --norsrc --noextattr --noacl --noqtn "$source_real" "$output_real"
[[ -d "$output_real/Contents" && ! -L "$output_real" ]] || phase3_fail 'ditto did not create a regular app bundle'
capture_xattrs "$evidence_dir/copy-xattrs-before-dylibs-recursive.txt" "$output_real" true
if grep -F 'com.apple.FinderInfo' "$evidence_dir/copy-xattrs-before-dylibs-recursive.txt" >/dev/null; then
  phase3_fail 'copied test app retained FinderInfo or ResourceFork; no dylib was placed'
fi
if grep -F 'com.apple.ResourceFork' "$evidence_dir/copy-xattrs-before-dylibs-recursive.txt" >/dev/null; then
  phase3_fail 'copied test app retained FinderInfo or ResourceFork; no dylib was placed'
fi
verify_clean_copy_components "$output_real" "$evidence_dir"
for component in app main framework gpu-helper; do
  compare_component_identity_and_hash "$evidence_dir/source-before-${component}" "$evidence_dir/copy-before-dylibs-${component}"
done
verify_source_components "$source_real" "$evidence_dir" source-after-copy
for component in app main framework gpu-helper; do
  compare_component_identity_and_hash "$evidence_dir/source-before-${component}" "$evidence_dir/source-after-copy-${component}"
done

# Stage 3: only two verified non-component dylibs. This intentionally invalidates
# the copied Google signature; ad-hoc signing is a separate explicit script.
framework="$output_real/Contents/Frameworks/Google Chrome Framework.framework"
[[ -d "$framework" && ! -L "$framework" ]] || phase3_fail 'test copy framework is missing or symlinked'
libraries_dir="$(cd "$framework" && pwd -P)/Libraries"
source_libraries_real=$(phase3_validate_libraries_directory "$(cd "$source_real/Contents/Frameworks/Google Chrome Framework.framework" && pwd -P)/Libraries" "$source_real/Contents/Frameworks/Google Chrome Framework.framework")
phase3_inventory_libraries "$source_libraries_real" "$evidence_dir/libraries-source-baseline.txt"
phase3_write_hash_file "$evidence_dir/libraries-source-baseline.txt" "$evidence_dir/libraries-source-baseline.sha256"
for angle_name in libEGL.dylib libGLESv2.dylib; do
  if awk -F '\t' -v n="$angle_name" '$1 == n {found=1} END {exit !found}' "$evidence_dir/libraries-source-baseline.txt"; then
    phase3_fail "ANGLE library already exists in source baseline: $angle_name"
  fi
done
if [[ -L "$libraries_dir" ]]; then
  phase3_validate_libraries_directory "$libraries_dir" "$framework" >/dev/null
elif [[ -e "$libraries_dir" ]]; then
  [[ -d "$libraries_dir" ]] || phase3_fail 'Libraries path is not a regular directory'
  phase3_validate_libraries_directory "$libraries_dir" "$framework" >/dev/null
else
  phase3_validate_new_libraries_path "$libraries_dir" "$framework"
  mkdir "$libraries_dir"
  phase3_validate_libraries_directory "$libraries_dir" "$framework" >/dev/null
fi
phase3_inventory_libraries "$(phase3_validate_libraries_directory "$libraries_dir" "$framework")" "$evidence_dir/libraries-copy-baseline.txt"
phase3_write_hash_file "$evidence_dir/libraries-copy-baseline.txt" "$evidence_dir/libraries-copy-baseline.sha256"
cmp "$evidence_dir/libraries-source-baseline.txt" "$evidence_dir/libraries-copy-baseline.txt" || phase3_fail 'source and copy Libraries baseline differs'
for angle_name in libEGL.dylib libGLESv2.dylib; do
  if awk -F '\t' -v n="$angle_name" '$1 == n {found=1} END {exit !found}' "$evidence_dir/libraries-copy-baseline.txt"; then
    phase3_fail "ANGLE library collision in copy baseline: $angle_name"
  fi
done
install -m 0755 "$artifact_real/libEGL.dylib" "$libraries_dir/libEGL.dylib"
install -m 0755 "$artifact_real/libGLESv2.dylib" "$libraries_dir/libGLESv2.dylib"
phase3_inventory_libraries "$(phase3_validate_libraries_directory "$libraries_dir" "$framework")" "$evidence_dir/libraries-post-install.txt"
phase3_write_hash_file "$evidence_dir/libraries-post-install.txt" "$evidence_dir/libraries-post-install.sha256"
phase3_validate_post_inventory "$evidence_dir/libraries-copy-baseline.txt" "$evidence_dir/libraries-post-install.txt"
phase3_verify_hash "$libraries_dir/libEGL.dylib" "$PHASE3_LIBEGL_SHA256"
phase3_verify_hash "$libraries_dir/libGLESv2.dylib" "$PHASE3_LIBGLESV2_SHA256"
phase3_capture_signature "$evidence_dir/copy-after-dylibs" "$output_real"
if codesign --verify --deep --strict "$output_real" > "$evidence_dir/copy-after-dylibs-strict-required.txt" 2>&1; then
  printf 'warning: copied app remained strictly signed after unsigned dylib placement; review before signing.\n' >&2
else
  printf 'expected: unsigned ANGLE dylibs invalidated the copied Google signature; no signing was performed.\n' >&2
fi
verify_source_components "$source_real" "$evidence_dir" source-after-dylibs
for component in app main framework gpu-helper; do
  compare_component_identity_and_hash "$evidence_dir/source-before-${component}" "$evidence_dir/source-after-dylibs-${component}"
done

{
  printf 'SCHEMA=%s\n' "$PHASE3_TEST_COPY_MANIFEST_SCHEMA"
  printf 'TEST_APP=%s\n' "$output_real"
  printf 'SOURCE_APP=%s\n' "$source_real"
  printf 'SOURCE_CHROME_VERSION=%s\n' "$source_version"
  printf 'CHROME_VERSION=%s\n' "$PHASE3_CHROME_VERSION"
  printf 'CHROMIUM_REVISION=%s\n' "$PHASE3_CHROMIUM_REVISION"
  printf 'ANGLE_REVISION=%s\n' "$PHASE3_ANGLE_REVISION"
  printf 'ARTIFACT_NAME=%s\n' "$PHASE3_ARTIFACT_NAME"
  printf 'LIBEGL_SHA256=%s\n' "$PHASE3_LIBEGL_SHA256"
  printf 'LIBGLESV2_SHA256=%s\n' "$PHASE3_LIBGLESV2_SHA256"
  printf 'LIBRARIES_SOURCE_BASELINE_SHA256=%s\n' "$(phase3_hash "$evidence_dir/libraries-source-baseline.txt")"
  printf 'LIBRARIES_COPY_BASELINE_SHA256=%s\n' "$(phase3_hash "$evidence_dir/libraries-copy-baseline.txt")"
  printf 'LIBRARIES_POST_INSTALL_SHA256=%s\n' "$(phase3_hash "$evidence_dir/libraries-post-install.txt")"
  printf 'COPY_POLICY=%s\n' "$PHASE3_COPY_POLICY"
  printf 'CREATED_AT_UTC=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf 'PREPARATION_STATE=unsigned-angle-libraries\n'
} > "$manifest"
phase3_write_hash_file "$manifest" "$manifest_hash"

printf 'prepared unsigned test copy: %s\n' "$output_real"
printf 'manifest: %s\n' "$manifest"
printf 'source extended attributes, ACLs, and HFS metadata were not changed; the test copy used %s.\n' "$PHASE3_COPY_POLICY"
printf 'the test copy is not for normal use or distribution.\n'
printf 'no xattr -cr or re-signing was performed on the copy; post-dylib signing remains a separate reviewed step.\n'
