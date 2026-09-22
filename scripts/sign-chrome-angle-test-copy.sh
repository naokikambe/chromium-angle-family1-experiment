#!/usr/bin/env bash
set -euo pipefail

PHASE3_SCRIPT_NAME='sign-chrome-angle-test-copy'
readonly PHASE3_SCRIPT_NAME
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/phase3-test-copy-common.sh"

usage() {
  printf 'usage: %s TEST_CHROME_APP RESULTS_DIRECTORY [--dry-run] [--confirm-ad-hoc-signing]\n' "$0" >&2
  exit 64
}

phase3_sign_capture_signature() {
  local executable=$1 destination_prefix=$2 target=$3
  phase3_run_codesign "$executable" -dvvv "$target" > "${destination_prefix}-details.txt" 2>&1 || true
  phase3_run_codesign "$executable" -d --entitlements :- "$target" > "${destination_prefix}-entitlements.txt" 2>&1 || true
  phase3_run_codesign "$executable" --verify --deep --strict "$target" > "${destination_prefix}-strict-verify.txt" 2>&1 || true
}

phase3_sign_target() {
  local codesign_executable=$1
  local target=$2
  local target_kind=${3:-code}
  local preserve_metadata=false

  case "$target_kind" in
    code)
      ;;
    *)
      phase3_fail "unsupported signing target kind: $target_kind"
      ;;
  esac

  if "$codesign_executable" -d --entitlements :- "$target" >/dev/null 2>&1; then
    preserve_metadata=true
  fi
  if [[ "$preserve_metadata" == true ]]; then
    "$codesign_executable" --force --sign - --timestamp=none \
      --preserve-metadata=entitlements,flags "$target"
  else
    "$codesign_executable" --force --sign - --timestamp=none "$target"
  fi
}

phase3_sign_framework_bundle_version() {
  local codesign_executable=$1
  local framework=$2
  local version_name=$3

  # Additional versions of a versioned framework must be selected through the
  # Framework bundle. Signing Versions/<name> directly does not create the
  # version signature that an embedding app verifies.
  "$codesign_executable" --force --sign - --timestamp=none \
    "--bundle-version=$version_name" "$framework"
}

phase3_sign_framework_version() {
  local codesign_executable=$1
  local framework=$2
  local version_dir=$3
  local version_name
  local target

  version_name=$(basename "$version_dir")

  # Sign nested code inside one concrete Framework version from the inside out.
  while IFS= read -r -d '' target; do
    if file -b "$target" | grep -F 'Mach-O' >/dev/null; then
      phase3_sign_target "$codesign_executable" "$target"
    fi
  done < <(find -P "$version_dir" -type f -print0)

  # find -depth emits a child bundle before its parent bundle.
  while IFS= read -r -d '' target; do
    phase3_sign_target "$codesign_executable" "$target"
  done < <(find -P "$version_dir" -depth -type d \
    \( -name '*.app' -o -name '*.bundle' \) -print0)

  phase3_sign_framework_bundle_version "$codesign_executable" "$framework" "$version_name"
}

phase3_sign_versioned_framework() {
  local codesign_executable=$1
  local framework=$2
  local results_dir=$3
  local versions_dir="$framework/Versions"
  local version_dir
  local version_count=0

  [[ -d "$versions_dir" && ! -L "$versions_dir" ]] ||
    phase3_fail "Framework Versions directory is missing or symlinked: $versions_dir"
  : > "$results_dir/framework-versions.txt"
  while IFS= read -r -d '' version_dir; do
    version_count=$((version_count + 1))
    printf '%s\n' "$version_dir" >> "$results_dir/framework-versions.txt"
    phase3_sign_framework_version "$codesign_executable" "$framework" "$version_dir"
    if ! phase3_run_codesign "$codesign_executable" --verify --deep --strict "$version_dir" \
      > "$results_dir/framework-version-${version_count}-strict-verify.txt" 2>&1; then
      cat "$results_dir/framework-version-${version_count}-strict-verify.txt" >&2 || true
      phase3_fail "ad-hoc signed Framework version failed strict verification: $version_dir"
    fi
  done < <(find -P "$versions_dir" -mindepth 1 -maxdepth 1 -type d -print0)
  (( version_count > 0 )) || phase3_fail "Framework contains no concrete versions: $framework"
}

phase3_sign_nested_components() {
  local codesign_executable=$1
  local test_app_real=$2
  local framework=$3
  local main_executable=$4
  local results_dir=$5

  # Sign every concrete version through the Framework bundle, then sign its
  # Current version once more through the Framework root before signing app.
  phase3_sign_versioned_framework "$codesign_executable" "$framework" "$results_dir"
  phase3_sign_target "$codesign_executable" "$framework"
  phase3_sign_target "$codesign_executable" "$main_executable"
  phase3_sign_target "$codesign_executable" "$test_app_real"
}
phase3_sign_main() {
local codesign_executable=$1
shift
[[ -x "$codesign_executable" ]] || phase3_fail "required codesign executable is unavailable: $codesign_executable"
dry_run=false
confirmed=false
[[ $# -ge 2 ]] || usage
test_app=$1
results_dir=$2
shift 2
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) dry_run=true ;;
    --confirm-ad-hoc-signing) confirmed=true ;;
    *) phase3_fail "unknown option: $1" ;;
  esac
  shift
done

phase3_reject_root
[[ -d "$test_app" ]] || phase3_fail "test app does not exist: $test_app"
[[ ! -e "$results_dir" && ! -L "$results_dir" ]] || phase3_fail "refusing existing results directory: $results_dir"
test_app_real=$(phase3_real_directory "$test_app")
phase3_reject_applications_path "$test_app_real"
results_parent_real=$(phase3_real_directory "$(dirname "$results_dir")")
phase3_require_user_owned_directory "$results_parent_real"
results_real="$results_parent_real/$(basename "$results_dir")"
phase3_reject_symlink_components "$results_real"

# This verifies the separate manifest and checksum, then verifies the two
# pinned dylibs and rejects every additional external dylib in Libraries.
phase3_validate_manifest "$test_app_real"
manifest=$(phase3_manifest_path "$test_app_real")
manifest_hash=$(phase3_manifest_hash_path "$test_app_real")
receipt=$(phase3_receipt_path "$test_app_real")
receipt_hash=$(phase3_receipt_hash_path "$test_app_real")

if [[ "$dry_run" == true ]]; then
  printf 'dry-run: would clear xattrs and ad-hoc sign only this prepared test copy:\n'
  printf '  xattr -cr %q\n' "$test_app_real"
  printf '  codesign nested Mach-O files and .app/.bundle containers inside each concrete Framework version\n'
  printf '  then codesign each Framework version via --bundle-version, the Current Framework, the main executable, and the app\n'
  printf 'no xattr or codesign command was executed.\n'
  exit 0
fi

[[ "$confirmed" == true ]] || phase3_fail 'refusing ad-hoc signing without --confirm-ad-hoc-signing'
for command in xattr shasum find file; do
  command -v "$command" >/dev/null 2>&1 || phase3_fail "required command is unavailable: $command"
done
[[ -x "$codesign_executable" ]] || phase3_fail "required codesign executable is unavailable: $codesign_executable"
[[ ! -e "$receipt" && ! -e "$receipt_hash" ]] || phase3_fail 'refusing to replace an existing signing receipt'

printf '%s\n' 'WARNING: this will remove extended attributes and replace Google Developer ID/notarized signatures with ad-hoc signatures on the test copy only.' >&2
printf '%s\n' 'Do not use this copy for normal browsing, existing profiles, or ordinary Chrome use.' >&2
mkdir "$results_real"

source_app=$(phase3_manifest_value "$manifest" 'SOURCE_APP')
source_version=$(phase3_manifest_value "$manifest" 'SOURCE_CHROME_VERSION')
{
  printf 'test_app=%s\n' "$test_app_real"
  printf 'source_app=%s\n' "$source_app"
  printf 'source_version=%s\n' "$source_version"
  printf 'manifest=%s\n' "$manifest"
  printf 'manifest_sha256=%s\n' "$(phase3_hash "$manifest")"
  printf 'timestamp_utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
} > "$results_real/signing-metadata.txt"

phase3_sign_capture_signature "$codesign_executable" "$results_real/test-app-before" "$test_app_real"
if [[ -d "$source_app" && ! -L "$source_app" ]]; then
  phase3_sign_capture_signature "$codesign_executable" "$results_real/source-app-read-only" "$source_app"
fi
framework="$test_app_real/Contents/Frameworks/Google Chrome Framework.framework"
executable_name=$(phase3_plist_value CFBundleExecutable "$test_app_real/Contents/Info.plist") || phase3_fail 'cannot read test app executable name'
main_executable="$test_app_real/Contents/MacOS/$executable_name"
gpu_helper=$(find "$framework" -type f -path '*/Google Chrome Helper (GPU).app/Contents/MacOS/Google Chrome Helper (GPU)' -print -quit)
[[ -x "$main_executable" && -n "$gpu_helper" ]] || phase3_fail 'test app signing targets are missing'
phase3_sign_capture_signature "$codesign_executable" "$results_real/main-before" "$main_executable"
phase3_sign_capture_signature "$codesign_executable" "$results_real/framework-before" "$framework"
phase3_sign_capture_signature "$codesign_executable" "$results_real/gpu-helper-before" "$gpu_helper"
phase3_sign_capture_signature "$codesign_executable" "$results_real/libEGL-before" "$framework/Libraries/libEGL.dylib"
phase3_sign_capture_signature "$codesign_executable" "$results_real/libGLESv2-before" "$framework/Libraries/libGLESv2.dylib"

# Sign every concrete Framework version through its Framework bundle. App-level
# --deep signing is not used; the final Framework-root signing covers Current.
xattr -cr "$test_app_real"
phase3_sign_nested_components "$codesign_executable" "$test_app_real" "$framework" "$main_executable" "$results_real"
phase3_run_codesign "$codesign_executable" --verify --deep --strict "$test_app_real" || phase3_fail 'ad-hoc signed test copy failed strict verification'

phase3_sign_capture_signature "$codesign_executable" "$results_real/test-app-after" "$test_app_real"
phase3_sign_capture_signature "$codesign_executable" "$results_real/main-after" "$main_executable"
phase3_sign_capture_signature "$codesign_executable" "$results_real/framework-after" "$framework"
phase3_sign_capture_signature "$codesign_executable" "$results_real/gpu-helper-after" "$gpu_helper"
phase3_sign_capture_signature "$codesign_executable" "$results_real/libEGL-after" "$framework/Libraries/libEGL.dylib"
phase3_sign_capture_signature "$codesign_executable" "$results_real/libGLESv2-after" "$framework/Libraries/libGLESv2.dylib"
for component in test-app main framework gpu-helper libEGL libGLESv2; do
  diff -u "$results_real/${component}-before-details.txt" "$results_real/${component}-after-details.txt" > "$results_real/${component}-details.diff" || true
  diff -u "$results_real/${component}-before-entitlements.txt" "$results_real/${component}-after-entitlements.txt" > "$results_real/${component}-entitlements.diff" || true
done
grep -F 'Signature=adhoc' "$results_real/test-app-after-details.txt" >/dev/null ||
  phase3_fail 'test app is not reported as ad-hoc signed after signing'

{
  printf 'SCHEMA=phase3-angle-signing-receipt-v1\n'
  printf 'TEST_APP=%s\n' "$test_app_real"
  printf 'PREPARE_MANIFEST_SHA256=%s\n' "$(phase3_hash "$manifest")"
  printf 'SIGNING_METHOD=ad-hoc-versioned-framework\n'
  printf 'SIGNED_AT_UTC=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf 'STRICT_VERIFICATION=passed\n'
  printf 'RESULTS_DIRECTORY=%s\n' "$results_real"
} > "$receipt"
phase3_write_hash_file "$receipt" "$receipt_hash"
printf 'ad-hoc signing completed only for test copy: %s\n' "$test_app_real"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  phase3_sign_main /usr/bin/codesign "$@"
fi
