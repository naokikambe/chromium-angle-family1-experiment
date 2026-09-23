#!/usr/bin/env bash
set -euo pipefail

PHASE3_SCRIPT_NAME='sign-chrome-angle-test-copy'
readonly PHASE3_SCRIPT_NAME
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/phase3-test-copy-common.sh"

usage() {
  printf 'usage: %s TEST_CHROME_APP RESULTS_DIRECTORY --identity APPLE_DEVELOPMENT_IDENTITY_SHA1 [--dry-run] [--confirm-apple-development-signing]\n' "$0" >&2
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
  local identity=$2
  local target=$3
  local entitlements=${4:-}
  local options=${5:-}
  local -a command

  command=("$codesign_executable" --force --sign "$identity" --timestamp=none)
  if [[ -n "$options" ]]; then
    command+=(--options "$options")
  else
    command+=(--preserve-metadata=flags)
  fi
  if [[ -n "$entitlements" ]]; then
    [[ -f "$entitlements" && ! -L "$entitlements" ]] ||
      phase3_fail "signing entitlements template is missing or symlinked: $entitlements"
    command+=(--entitlements "$entitlements")
  fi
  command+=("$target")
  "${command[@]}"
}

phase3_validate_apple_development_identity() {
  local security_executable=$1
  local identity=$2
  local matching_line

  [[ "$identity" =~ ^[0-9A-Fa-f]{40}$ ]] ||
    phase3_fail 'Apple Development identity must be a 40-character SHA-1 fingerprint'
  identity=$(printf '%s' "$identity" | tr '[:lower:]' '[:upper:]')
  matching_line=$("$security_executable" find-identity -v -p codesigning 2>/dev/null |
    awk -v expected="$identity" '$2 == expected { print; found = 1 } END { exit !found }') ||
    phase3_fail 'requested Apple Development identity is not currently valid'
  [[ "$matching_line" == *'"Apple Development:'* ]] ||
    phase3_fail 'requested signing identity is not an Apple Development identity'
  printf '%s\n' "$identity"
}

phase3_assert_development_app_entitlements() {
  local entitlements_file=$1
  local required forbidden

  for required in \
    com.apple.security.device.audio-input \
    com.apple.security.device.bluetooth \
    com.apple.security.device.camera \
    com.apple.security.device.print \
    com.apple.security.device.usb \
    com.apple.security.personal-information.location \
    com.apple.security.personal-information.photos-library; do
    grep -F "<key>$required</key>" "$entitlements_file" >/dev/null ||
      phase3_fail "Apple Development app signature is missing required entitlement: $required"
  done
  for forbidden in \
    com.apple.application-identifier \
    keychain-access-groups \
    com.apple.developer.associated-domains.applinks.read-write \
    com.apple.developer.web-browser.public-key-credential; do
    ! grep -F "<key>$forbidden</key>" "$entitlements_file" >/dev/null ||
      phase3_fail "Apple Development app signature retains Google-bound entitlement: $forbidden"
  done
}

phase3_sign_current_framework() {
  local codesign_executable=$1
  local identity=$2
  local framework=$3
  local results_dir=$4
  local jit_entitlements=$5
  local version_dir="$framework/Versions/$PHASE3_FRAMEWORK_CURRENT_VERSION"
  local target

  phase3_validate_current_only_framework "$framework" "$PHASE3_FRAMEWORK_CURRENT_VERSION"
  printf '%s\n' "$version_dir" > "$results_dir/framework-versions.txt"

  # The test copy contains exactly one concrete Framework version. Sign its
  # nested code from the inside out, then seal the Framework through its root.
  while IFS= read -r -d '' target; do
    if file -b "$target" | grep -F 'Mach-O' >/dev/null; then
      phase3_sign_target "$codesign_executable" "$identity" "$target"
    fi
  done < <(find -P "$version_dir" -type f -print0)

  # find -depth emits a child bundle before its parent bundle.
  while IFS= read -r -d '' target; do
    case "$target" in
      *'Google Chrome Helper (Renderer).app'|*'Google Chrome Helper (Aperitif Renderer).app'|*'Google Chrome Helper (GPU).app'|*'Google Chrome Helper (Aperitif GPU).app')
        # Chromium deliberately omits Library Validation for JIT-capable GPU
        # and renderer helpers. Keep their hardened runtime, kill, and restrict
        # flags without inheriting the outer app's library-validation flag.
        phase3_sign_target "$codesign_executable" "$identity" "$target" "$jit_entitlements" 'runtime,kill,restrict'
        ;;
      *) phase3_sign_target "$codesign_executable" "$identity" "$target" ;;
    esac
  done < <(find -P "$version_dir" -depth -type d \
    \( -name '*.app' -o -name '*.bundle' \) -print0)

  phase3_sign_target "$codesign_executable" "$identity" "$framework"
}

phase3_sign_nested_components() {
  local codesign_executable=$1
  local identity=$2
  local test_app_real=$3
  local framework=$4
  local main_executable=$5
  local results_dir=$6
  local app_entitlements=$7
  local jit_entitlements=$8

  phase3_sign_current_framework "$codesign_executable" "$identity" "$framework" "$results_dir" "$jit_entitlements"
  phase3_sign_target "$codesign_executable" "$identity" "$main_executable"
  phase3_sign_target "$codesign_executable" "$identity" "$test_app_real" "$app_entitlements"
}
phase3_sign_main() {
local codesign_executable=$1
local security_executable=$2
shift 2
[[ -x "$codesign_executable" ]] || phase3_fail "required codesign executable is unavailable: $codesign_executable"
[[ -x "$security_executable" ]] || phase3_fail "required security executable is unavailable: $security_executable"
dry_run=false
confirmed=false
identity=''
[[ $# -ge 2 ]] || usage
test_app=$1
results_dir=$2
shift 2
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) dry_run=true ;;
    --identity)
      [[ $# -ge 2 ]] || usage
      identity=$2
      shift
      ;;
    --confirm-apple-development-signing) confirmed=true ;;
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
signed_evidence_dir=$(phase3_receipt_evidence_dir "$test_app_real")
signed_inventory=$(phase3_signed_libraries_inventory_path "$test_app_real")
signed_inventory_hash=$(phase3_signed_libraries_inventory_hash_path "$test_app_real")
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
app_entitlements="$script_dir/entitlements/phase3-chromium-base-app-entitlements.plist"
jit_entitlements="$script_dir/entitlements/phase3-chromium-jit-helper-entitlements.plist"
[[ -n "$identity" ]] || phase3_fail 'Apple Development signing requires --identity'
identity=$(phase3_validate_apple_development_identity "$security_executable" "$identity")

if [[ "$dry_run" == true ]]; then
  printf 'dry-run: would clear xattrs and Apple Development sign only this prepared test copy:\n'
  printf '  xattr -cr %q\n' "$test_app_real"
  printf '  codesign --sign %s nested Mach-O files and .app/.bundle containers inside the sole current Framework version\n' "$identity"
  printf '  then codesign the current-only Framework, the main executable, and the app with Chromium development entitlements\n'
  printf 'no xattr or codesign command was executed.\n'
  exit 0
fi

[[ "$confirmed" == true ]] || phase3_fail 'refusing Apple Development signing without --confirm-apple-development-signing'
for command in xattr shasum find file; do
  command -v "$command" >/dev/null 2>&1 || phase3_fail "required command is unavailable: $command"
done
[[ -x "$codesign_executable" ]] || phase3_fail "required codesign executable is unavailable: $codesign_executable"
[[ ! -e "$receipt" && ! -e "$receipt_hash" && ! -e "$signed_evidence_dir" && ! -L "$signed_evidence_dir" ]] ||
  phase3_fail 'refusing to replace existing signing evidence or receipt'

printf '%s\n' 'WARNING: this will remove extended attributes and replace Google Developer ID/notarized signatures with an Apple Development signature on the test copy only.' >&2
printf '%s\n' 'Do not use this copy for normal browsing, existing profiles, or ordinary Chrome use.' >&2
mkdir "$results_real"

source_app=$(phase3_manifest_value "$manifest" 'SOURCE_APP')
source_version=$(phase3_manifest_value "$manifest" 'SOURCE_CHROME_VERSION')
{
  printf 'test_app=%s\n' "$test_app_real"
  printf 'source_app=%s\n' "$source_app"
  printf 'source_version=%s\n' "$source_version"
  printf 'signing_identity_sha1=%s\n' "$identity"
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

# Sign the sole current Framework version. App-level --deep signing is not used.
xattr -cr "$test_app_real"
phase3_sign_nested_components "$codesign_executable" "$identity" "$test_app_real" "$framework" "$main_executable" "$results_real" "$app_entitlements" "$jit_entitlements"
phase3_run_codesign "$codesign_executable" --verify --deep --strict "$test_app_real" || phase3_fail 'Apple Development signed test copy failed strict verification'

mkdir "$signed_evidence_dir"
libraries_real=$(phase3_validate_libraries_directory "$framework/Libraries" "$framework")
phase3_inventory_libraries "$libraries_real" "$signed_inventory"
phase3_validate_signed_inventory \
  "$(phase3_manifest_path "$test_app_real").evidence/libraries-post-install.txt" \
  "$signed_inventory" "$signed_inventory"
phase3_write_hash_file "$signed_inventory" "$signed_inventory_hash"

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
grep -F 'Authority=Apple Development:' "$results_real/test-app-after-details.txt" >/dev/null ||
  phase3_fail 'test app is not reported as Apple Development signed after signing'
grep -E '^TeamIdentifier=.+$' "$results_real/test-app-after-details.txt" | grep -Fv 'TeamIdentifier=not set' >/dev/null ||
  phase3_fail 'test app has no Apple Development team identifier after signing'
phase3_assert_development_app_entitlements "$results_real/test-app-after-entitlements.txt"

{
  printf 'SCHEMA=phase3-angle-signing-receipt-v3\n'
  printf 'TEST_APP=%s\n' "$test_app_real"
  printf 'PREPARE_MANIFEST_SHA256=%s\n' "$(phase3_hash "$manifest")"
  printf 'SIGNING_METHOD=apple-development-current-framework\n'
  printf 'SIGNING_IDENTITY_SHA1=%s\n' "$identity"
  printf 'ENTITLEMENTS_PROFILE=chromium-base-device-v1\n'
  printf 'SIGNED_LIBRARIES_INVENTORY_SHA256=%s\n' "$(phase3_hash "$signed_inventory")"
  printf 'SIGNED_AT_UTC=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf 'STRICT_VERIFICATION=passed\n'
  printf 'RESULTS_DIRECTORY=%s\n' "$results_real"
} > "$receipt"
phase3_write_hash_file "$receipt" "$receipt_hash"
printf 'Apple Development signing completed only for test copy: %s\n' "$test_app_real"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  phase3_sign_main /usr/bin/codesign /usr/bin/security "$@"
fi
