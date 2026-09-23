#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${PHASE3_SCRIPT_NAME+x}" ]]; then
  PHASE3_SCRIPT_NAME='prepare-chrome-angle-test-copy'
  readonly PHASE3_SCRIPT_NAME
fi
if ! declare -F phase3_hash >/dev/null 2>&1; then
  source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/phase3-test-copy-common.sh"
fi

phase3_prepare_usage() {
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
PHASE3_CODESIGN_EXECUTABLE='/usr/bin/codesign'

capture_component_evidence() {
  local prefix=$1
  local target=$2
  local executable

  phase3_run_codesign "$PHASE3_CODESIGN_EXECUTABLE" -dvvv "$target" > "${prefix}-details.txt" 2>&1 || true
  phase3_run_codesign "$PHASE3_CODESIGN_EXECUTABLE" -d --entitlements :- "$target" > "${prefix}-entitlements.txt" 2>&1 || true
  capture_xattrs "${prefix}-xattrs.txt" "$target"
  executable=$(awk -F= '/^Executable=/{print substr($0, index($0, "=") + 1); exit}' "${prefix}-details.txt")
  [[ -f "$executable" && ! -L "$executable" ]] || phase3_fail "cannot identify a regular executable for evidence: $target"
  shasum -a 256 "$executable" | awk '{print $1}' > "${prefix}-sha256.txt"
  printf '%s\n' "$executable" > "${prefix}-executable-path.txt"
}

strict_output_is_metadata_detritus_only() {
  local output
  local seen=0
  local invalid=0
  for output in "$@"; do
    while IFS= read -r line; do
      [[ -n "$line" ]] || continue
      seen=1
      [[ "$line" == *"$SOURCE_METADATA_DETRITUS"* ]] || invalid=1
    done < "$output"
  done
  [[ "$seen" -eq 1 && "$invalid" -eq 0 ]]
}

render_codesign_command() {
  local executable=$1
  shift
  local rendered arg
  printf -v rendered '%q' "$executable"
  for arg in "$@"; do
    printf -v arg '%q' "$arg"
    rendered+=" $arg"
  done
  printf '%s' "$rendered"
}

verify_source_component() {
  local prefix=$1
  local target=$2
  local label=$3
  local status started ended command_rendered phase line

  capture_component_evidence "$prefix" "$target"
  case "$label" in
    source-before) phase=source-before-copy ;;
    source-after-copy) phase=source-after-copy ;;
    source-after-dylibs) phase=source-after-dylibs ;;
    *) phase=$label ;;
  esac
  started=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
  command_rendered=$(render_codesign_command "$PHASE3_CODESIGN_EXECUTABLE" --verify --strict "$target")
  set +e
  phase3_run_codesign "$PHASE3_CODESIGN_EXECUTABLE" --verify --strict "$target" > "${prefix}-strict-verify-stdout.txt" 2> "${prefix}-strict-verify-stderr.txt"
  status=$?
  set -e
  ended=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
  printf '%s\n' "$status" > "${prefix}-strict-verify-status.txt"
    printf 'schema=phase3-component-verification-v1\ncomponent=%s\ntarget=%s\ncommand=%s\ncodesign_executable=%s\nstart_utc=%s\nend_utc=%s\nraw_exit_status=%s\ncwd=%s\nPATH=%s\nphase=%s\n' \
      "${prefix##*/}" "$target" "$command_rendered" "$PHASE3_CODESIGN_EXECUTABLE" "$started" "$ended" "$status" "$PWD" "$PATH" "$phase" > "${prefix}-strict-verify-metadata.txt"
  if [[ "$status" -eq 0 ]]; then
    printf 'passed\n' > "${prefix}-strict-classification.txt"
    return
  fi
  if strict_output_is_metadata_detritus_only "${prefix}-strict-verify-stdout.txt" "${prefix}-strict-verify-stderr.txt"; then
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
  verify_source_component "$evidence_dir/${label}-app" "$app" "$label"
  verify_source_component "$evidence_dir/${label}-main" "$main_executable" "$label"
  verify_source_component "$evidence_dir/${label}-framework" "$framework" "$label"
  verify_source_component "$evidence_dir/${label}-gpu-helper" "$gpu_helper" "$label"
}

verify_copy_component() {
  local prefix=$1
  local target=$2
  local status started ended command_rendered
  local -a command=("$PHASE3_CODESIGN_EXECUTABLE" --verify --strict "$target")
  [[ "${prefix##*/}" == *-app ]] && command=("$PHASE3_CODESIGN_EXECUTABLE" --verify --deep --strict "$target")

  capture_component_evidence "$prefix" "$target"
  started=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
  command_rendered=$(render_codesign_command "${command[@]}")
  set +e
  phase3_run_codesign "${command[@]}" > "${prefix}-strict-verify-stdout.txt" 2> "${prefix}-strict-verify-stderr.txt"
  status=$?
  set -e
  ended=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
  printf '%s\n' "$status" > "${prefix}-strict-verify-status.txt"
  printf 'schema=phase3-component-verification-v1\ncomponent=%s\ntarget=%s\ncommand=%s\ncodesign_executable=%s\nstart_utc=%s\nend_utc=%s\nraw_exit_status=%s\ncwd=%s\nPATH=%s\nphase=copy-before-dylibs\n' \
    "${prefix##*/}" "$target" "$command_rendered" "$PHASE3_CODESIGN_EXECUTABLE" "$started" "$ended" "$status" "$PWD" "$PATH" > "${prefix}-strict-verify-metadata.txt"
  [[ "$status" -eq 0 ]] || phase3_fail "test copy strict verification failed for $target"
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
  verify_copy_component "$evidence_dir/copy-before-dylibs-app" "$app"
  verify_copy_component "$evidence_dir/copy-before-dylibs-main" "$main_executable"
  verify_copy_component "$evidence_dir/copy-before-dylibs-framework" "$framework"
  verify_copy_component "$evidence_dir/copy-before-dylibs-gpu-helper" "$gpu_helper"
}

prepare_current_only_framework() {
  local framework=$1
  local evidence_dir=$2
  local versions="$framework/Versions"
  local current="$versions/Current"
  local entry name current_target current_real entry_real temp_inventory
  local before="$evidence_dir/framework-versions-before.txt"
  local removed_inventory="$evidence_dir/framework-removed-version-inventory.txt"
  local after="$evidence_dir/framework-versions-after.txt"
  local status

  [[ -d "$framework" && ! -L "$framework" ]] || phase3_fail 'test copy framework is missing or symlinked'
  [[ -d "$versions" && ! -L "$versions" ]] || phase3_fail 'test copy Framework Versions directory is missing or symlinked'
  [[ -L "$current" ]] || phase3_fail 'test copy Framework Current is not a symlink'
  current_target=$(readlink "$current") || phase3_fail 'test copy Framework Current symlink cannot be read'
  [[ "$current_target" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || phase3_fail 'Framework Current target is not a numeric version'
  current_real=$(cd "$versions/$current_target" 2>/dev/null && pwd -P) || phase3_fail 'current Framework version is missing'
  [[ -d "$versions/$current_target" && ! -L "$versions/$current_target" ]] || phase3_fail 'current Framework version is symlinked'
  phase3_inventory_framework_versions_layout "$framework" "$before"
  grep -Fx "$current_target"$'\tdir\t-' "$before" >/dev/null ||
    phase3_fail 'Framework versions-before evidence lacks the current version'
  grep -Fx 'Current'$'\tsymlink\t'"$current_target" "$before" >/dev/null ||
    phase3_fail 'Framework versions-before evidence lacks the canonical Current symlink'
  phase3_write_hash_file "$before" "$evidence_dir/framework-versions-before.sha256"

  : > "$removed_inventory"
  : > "$evidence_dir/framework-removed-version-names.txt"
  while IFS= read -r -d '' entry; do
    name=$(basename "$entry")
    [[ "$name" == Current || "$name" == "$current_target" ]] && continue
    [[ "$name" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || phase3_fail "unexpected Framework Versions entry: $name"
    [[ -d "$entry" && ! -L "$entry" ]] || phase3_fail "non-directory obsolete Framework version entry: $name"
    entry_real=$(cd "$entry" && pwd -P)
    [[ "$entry_real" == "$framework/Versions/$name" ]] || phase3_fail 'obsolete Framework version resolves outside the test copy'
    temp_inventory=$(mktemp "${TMPDIR:-/tmp}/phase3-version-inventory.XXXXXX")
    phase3_inventory_tree "$entry_real" "$temp_inventory"
    awk -F '\t' -v prefix="$name/" '{print prefix $1 "\t" $2 "\t" $3}' "$temp_inventory" >> "$removed_inventory"
    rm -f "$temp_inventory"
    printf '%s\n' "$name" >> "$evidence_dir/framework-removed-version-names.txt"
  done < <(find -P "$versions" -mindepth 1 -maxdepth 1 -print0 | LC_ALL=C sort -z)
  phase3_write_hash_file "$removed_inventory" "$evidence_dir/framework-removed-version-inventory.sha256"
  phase3_write_hash_file "$evidence_dir/framework-removed-version-names.txt" "$evidence_dir/framework-removed-version-names.sha256"
  while IFS= read -r name; do
    [[ -n "$name" ]] || continue
    entry="$versions/$name"
    entry_real=$(cd "$entry" && pwd -P)
    phase3_run_codesign "$PHASE3_CODESIGN_EXECUTABLE" -dvvv "$entry_real/Google Chrome Framework" \
      > "$evidence_dir/framework-removed-$name-signature-details.txt" 2>&1 || true
    phase3_run_codesign "$PHASE3_CODESIGN_EXECUTABLE" --verify --strict "$entry_real/Google Chrome Framework" \
      > "$evidence_dir/framework-removed-$name-strict-verify.txt" 2>&1 || true
    [[ "$entry_real" == "$framework/Versions/$name" ]] || phase3_fail 'refusing to remove an uncanonical Framework version path'
    rm -rf -- "$entry_real"
  done < "$evidence_dir/framework-removed-version-names.txt"
  phase3_validate_current_only_framework "$framework" "$current_target"
  phase3_inventory_framework_versions_layout "$framework" "$after"
  phase3_write_hash_file "$after" "$evidence_dir/framework-versions-after.sha256"

  set +e
  phase3_run_codesign "$PHASE3_CODESIGN_EXECUTABLE" --verify --deep --strict "$framework" \
    > "$evidence_dir/framework-after-normalization-strict-verify-stdout.txt" \
    2> "$evidence_dir/framework-after-normalization-strict-verify-stderr.txt"
  status=$?
  set -e
  printf '%s\n' "$status" > "$evidence_dir/framework-after-normalization-strict-verify-status.txt"
  {
    printf 'POLICY=%s\n' "$PHASE3_FRAMEWORK_VERSION_POLICY"
    printf 'CURRENT_VERSION=%s\n' "$current_target"
    printf 'REMOVED_VERSIONS_SHA256=%s\n' "$(phase3_hash "$evidence_dir/framework-removed-version-names.txt")"
    printf 'REMOVED_FROM_TEST_COPY_ONLY=true\n'
    printf 'SOURCE_APP_WRITTEN=false\n'
    printf 'NORMALIZED_AT_UTC=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  } > "$evidence_dir/framework-version-normalization.txt"
}

phase3_prepare_main() {
  local codesign_executable=$4
  [[ $# -eq 4 ]] || phase3_prepare_usage
  [[ -x "$codesign_executable" ]] || phase3_fail "required codesign executable is unavailable: $codesign_executable"
  PHASE3_CODESIGN_EXECUTABLE="$codesign_executable"
phase3_reject_root

for command in ditto shasum lipo xattr stat find install cmp date rm; do
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
phase3_validate_release_manifest "$artifact_real"
[[ "$source_version" == "$PHASE3_RELEASE_CHROME_VERSION" ]] || phase3_fail "release expects Chrome $PHASE3_RELEASE_CHROME_VERSION, found $source_version"
source_executable_name=$(phase3_plist_value CFBundleExecutable "$source_real/Contents/Info.plist") || phase3_fail 'cannot read source executable name'
source_executable="$source_real/Contents/MacOS/$source_executable_name"
[[ -x "$source_executable" ]] || phase3_fail 'source main executable is missing'
lipo -info "$source_executable" | grep -Eq '(^|[[:space:]])x86_64($|[[:space:]])' || phase3_fail 'source main executable has no x86_64 slice'

[[ -L "$source_real/Contents/Frameworks/Google Chrome Framework.framework/Versions/Current" ]] || phase3_fail 'source Framework Current is not a symlink'
source_framework_version=$(readlink "$source_real/Contents/Frameworks/Google Chrome Framework.framework/Versions/Current")
[[ "$source_framework_version" == "$source_version" ]] || phase3_fail 'source Framework Current version differs from Chrome bundle version'

manifest=$(phase3_manifest_path "$output_real")
manifest_hash=$(phase3_manifest_hash_path "$output_real")
evidence_dir="${manifest}.evidence"
[[ ! -e "$manifest" && ! -e "$manifest_hash" && ! -e "$evidence_dir" ]] || phase3_fail 'refusing existing test-copy sidecar files'
mkdir "$evidence_dir"
cp "$(phase3_release_manifest_path "$artifact_real")" "$evidence_dir/ANGLE_RELEASE_MANIFEST"
cp "$(phase3_release_manifest_hash_path "$artifact_real")" "$evidence_dir/ANGLE_RELEASE_MANIFEST.sha256"

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

# Stage 2.5: normalize only the new test copy to the clean-install-equivalent
# current Framework layout. Preserve a hashed inventory before removing the
# retained legacy version. The source app is read-only throughout.
framework="$output_real/Contents/Frameworks/Google Chrome Framework.framework"
prepare_current_only_framework "$framework" "$evidence_dir"

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
phase3_verify_hash "$libraries_dir/libEGL.dylib" "$PHASE3_RELEASE_LIBEGL_SHA256"
phase3_verify_hash "$libraries_dir/libGLESv2.dylib" "$PHASE3_RELEASE_LIBGLESV2_SHA256"
phase3_capture_signature "$evidence_dir/copy-after-dylibs" "$output_real"
post_started=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
if phase3_run_codesign "$PHASE3_CODESIGN_EXECUTABLE" --verify --deep --strict "$output_real" > "$evidence_dir/copy-after-dylibs-strict-verify-stdout.txt" 2> "$evidence_dir/copy-after-dylibs-strict-verify-stderr.txt"; then
  post_status=0
  printf 'warning: copied app remained strictly signed after unsigned dylib placement; review before signing.\n' >&2
else
  post_status=$?
  post_output="$evidence_dir/copy-after-dylibs-strict-verify-stderr.txt"
  post_framework="$output_real/Contents/Frameworks/Google Chrome Framework.framework"
  if awk -v app="$output_real" -v framework="$post_framework" '
    NR == 1 && $0 == app ": a sealed resource is missing or invalid" { first=1; next }
    NR == 2 && $0 == "In subcomponent: " framework { second=1; next }
    NF { invalid=1 }
    END { exit !(first && second && !invalid) }
  ' "$post_output"; then
    post_expected=1
    printf 'expected: unsigned ANGLE dylibs invalidated the copied Google signature; no signing was performed.\n' >&2
  else
    post_expected=0
  fi
fi
post_ended=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
printf '%s\n' "$post_status" > "$evidence_dir/copy-after-dylibs-strict-verify-status.txt"
printf 'schema=phase3-component-verification-v1\ncomponent=app\ntarget=%s\ncommand=%s --verify --deep --strict %s\ncodesign_executable=%s\nstart_utc=%s\nend_utc=%s\nraw_exit_status=%s\ncwd=%s\nPATH=%s\nphase=copy-after-dylibs-before-resigning\n' \
  "$output_real" "$PHASE3_CODESIGN_EXECUTABLE" "$output_real" "$PHASE3_CODESIGN_EXECUTABLE" "$post_started" "$post_ended" "$post_status" "$PWD" "$PATH" > "$evidence_dir/copy-after-dylibs-strict-required-metadata.txt"
[[ "${post_expected:-1}" -eq 1 ]] || phase3_fail 'unexpected post-dylib strict verification failure'
verify_source_components "$source_real" "$evidence_dir" source-after-dylibs
for component in app main framework gpu-helper; do
  compare_component_identity_and_hash "$evidence_dir/source-before-${component}" "$evidence_dir/source-after-dylibs-${component}"
done

{
  printf 'SCHEMA=%s\n' "$PHASE3_TEST_COPY_MANIFEST_SCHEMA"
  printf 'TEST_APP=%s\n' "$output_real"
  printf 'SOURCE_APP=%s\n' "$source_real"
  printf 'SOURCE_CHROME_VERSION=%s\n' "$source_version"
  printf 'RELEASE_MANIFEST_SHA256=%s\n' "$PHASE3_RELEASE_MANIFEST_SHA256"
  printf 'CHROME_VERSION=%s\n' "$PHASE3_RELEASE_CHROME_VERSION"
  printf 'CHROMIUM_REVISION=%s\n' "$PHASE3_RELEASE_CHROMIUM_REVISION"
  printf 'ANGLE_REVISION=%s\n' "$PHASE3_RELEASE_ANGLE_REVISION"
  printf 'ARTIFACT_NAME=%s\n' "$PHASE3_RELEASE_ARTIFACT_NAME"
  printf 'LIBEGL_SHA256=%s\n' "$PHASE3_RELEASE_LIBEGL_SHA256"
  printf 'LIBGLESV2_SHA256=%s\n' "$PHASE3_RELEASE_LIBGLESV2_SHA256"
  printf 'LIBRARIES_SOURCE_BASELINE_SHA256=%s\n' "$(phase3_hash "$evidence_dir/libraries-source-baseline.txt")"
  printf 'LIBRARIES_COPY_BASELINE_SHA256=%s\n' "$(phase3_hash "$evidence_dir/libraries-copy-baseline.txt")"
  printf 'LIBRARIES_POST_INSTALL_SHA256=%s\n' "$(phase3_hash "$evidence_dir/libraries-post-install.txt")"
  printf 'FRAMEWORK_VERSION_POLICY=%s\n' "$PHASE3_FRAMEWORK_VERSION_POLICY"
  printf 'FRAMEWORK_CURRENT_VERSION=%s\n' "$source_framework_version"
  printf 'FRAMEWORK_REMOVED_VERSION_NAMES_SHA256=%s\n' "$(phase3_hash "$evidence_dir/framework-removed-version-names.txt")"
  printf 'FRAMEWORK_VERSIONS_BEFORE_SHA256=%s\n' "$(phase3_hash "$evidence_dir/framework-versions-before.txt")"
  printf 'FRAMEWORK_REMOVED_VERSION_INVENTORY_SHA256=%s\n' "$(phase3_hash "$evidence_dir/framework-removed-version-inventory.txt")"
  printf 'FRAMEWORK_VERSIONS_AFTER_SHA256=%s\n' "$(phase3_hash "$evidence_dir/framework-versions-after.txt")"
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
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  [[ $# -eq 3 ]] || phase3_prepare_usage
  phase3_prepare_main "$@" /usr/bin/codesign
fi
