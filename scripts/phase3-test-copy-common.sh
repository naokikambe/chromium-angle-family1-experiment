#!/usr/bin/env bash

readonly PHASE3_CHROME_VERSION='154.0.8037.45'
readonly PHASE3_CHROMIUM_REVISION='731082f0a26ce4b3976c3d82943092f5d13daf13'
readonly PHASE3_ANGLE_REVISION='72b8f72a7587ec776d7d2a57d275a6e9b1781b1d'
readonly PHASE3_ARTIFACT_NAME='angle-macos-x86_64-chrome-154.0.8037.45-angle-72b8f72a-35515036255'
readonly PHASE3_LIBEGL_SHA256='f4a8a7575183a41373404f7c25b4f56e1a1540c5b1578d11437c180b1f698db8'
readonly PHASE3_LIBGLESV2_SHA256='8d3d188d3d4f23cf3f96ecea209b084c6db9c6192244f879cfb6bf0fb2e02cf0'

phase3_fail() {
  printf '%s: %s\n' "${PHASE3_SCRIPT_NAME:-phase3}" "$1" >&2
  exit 1
}

phase3_reject_root() {
  [[ "$EUID" -ne 0 ]] || phase3_fail 'refusing to run as root'
  [[ "${PHASE3_FIXTURE_FORCE_ROOT:-0}" != '1' ]] || phase3_fail 'fixture: simulated root execution rejected'
}

phase3_reject_symlink_components() {
  local path=$1
  local absolute_path
  local current='/'
  local component
  local -a components

  if [[ "$path" == /* ]]; then
    absolute_path=$path
  else
    absolute_path="$PWD/$path"
  fi
  IFS='/' read -r -a components <<< "${absolute_path#/}"
  for component in "${components[@]}"; do
    [[ -n "$component" ]] || continue
    current="$current$component"
    [[ ! -L "$current" ]] || phase3_fail "refusing a path with a symlink component: $path"
    current="$current/"
  done
}

phase3_real_directory() {
  local path=$1
  [[ -d "$path" ]] || phase3_fail "directory does not exist: $path"
  phase3_reject_symlink_components "$path"
  (cd "$path" && pwd -P)
}

phase3_reject_applications_path() {
  local path=$1
  case "$path" in
    /Applications|/Applications/*) phase3_fail 'refusing a path under /Applications' ;;
  esac
}

phase3_require_user_owned_directory() {
  local path=$1
  local owner
  owner=$(stat -f '%u' "$path") || phase3_fail "cannot read directory owner: $path"
  [[ "$owner" == "$UID" ]] || phase3_fail "directory is not owned by the invoking user: $path"
}

phase3_plist_value() {
  /usr/libexec/PlistBuddy -c "Print :$1" "$2"
}

phase3_hash() {
  shasum -a 256 "$1" | awk '{print $1}'
}

phase3_verify_hash() {
  local path=$1
  local expected=$2
  local actual
  [[ -f "$path" && ! -L "$path" ]] || phase3_fail "required regular file is missing: $path"
  actual=$(phase3_hash "$path")
  [[ "$actual" == "$expected" ]] || phase3_fail "SHA-256 mismatch for $path"
}

phase3_manifest_path() {
  printf '%s.phase3-angle-manifest\n' "$1"
}

phase3_manifest_hash_path() {
  printf '%s.sha256\n' "$(phase3_manifest_path "$1")"
}

phase3_receipt_path() {
  printf '%s.phase3-angle-signing-receipt\n' "$1"
}

phase3_receipt_hash_path() {
  printf '%s.sha256\n' "$(phase3_receipt_path "$1")"
}

phase3_write_hash_file() {
  local input=$1
  local output=$2
  printf '%s  %s\n' "$(phase3_hash "$input")" "$(basename "$input")" > "$output"
  chmod 0444 "$input" "$output"
}

phase3_verify_sidecar_hash() {
  local input=$1
  local hash_file=$2
  local expected
  local actual
  [[ -f "$input" && ! -L "$input" ]] || phase3_fail "missing sidecar: $input"
  [[ -f "$hash_file" && ! -L "$hash_file" ]] || phase3_fail "missing sidecar checksum: $hash_file"
  expected=$(awk 'NR == 1 { print $1 }' "$hash_file")
  [[ "$expected" =~ ^[0-9a-f]{64}$ ]] || phase3_fail "invalid sidecar checksum: $hash_file"
  actual=$(phase3_hash "$input")
  [[ "$actual" == "$expected" ]] || phase3_fail "sidecar checksum mismatch: $input"
}

phase3_manifest_value() {
  local manifest=$1
  local key=$2
  local matches
  matches=$(grep -E "^${key}=" "$manifest" || true)
  [[ $(printf '%s\n' "$matches" | sed '/^$/d' | wc -l | tr -d ' ') == 1 ]] ||
    phase3_fail "invalid manifest key: $key"
  printf '%s\n' "${matches#*=}"
}

phase3_require_only_angle_dylibs() {
  local libraries_dir=$1
  local library
  local -a actual=()
  local -a expected=(libEGL.dylib libGLESv2.dylib)

  [[ -d "$libraries_dir" && ! -L "$libraries_dir" ]] ||
    phase3_fail "Libraries directory is missing or symlinked: $libraries_dir"
  while IFS= read -r library; do
    actual+=("$(basename "$library")")
    [[ ! -L "$library" ]] || phase3_fail "dylib is symlinked: $library"
  done < <(find "$libraries_dir" -maxdepth 1 -type f -name '*.dylib' -print | LC_ALL=C sort)
  [[ "${actual[*]}" == "${expected[*]}" ]] ||
    phase3_fail 'Libraries directory must contain exactly libEGL.dylib and libGLESv2.dylib'
}

phase3_validate_manifest() {
  local app=$1
  local manifest
  local manifest_hash
  local framework
  local libraries_dir

  manifest=$(phase3_manifest_path "$app")
  manifest_hash=$(phase3_manifest_hash_path "$app")
  phase3_verify_sidecar_hash "$manifest" "$manifest_hash"
  [[ "$(phase3_manifest_value "$manifest" 'SCHEMA')" == 'phase3-angle-test-copy-v1' ]] ||
    phase3_fail 'unsupported test-copy manifest schema'
  [[ "$(phase3_manifest_value "$manifest" 'TEST_APP')" == "$app" ]] ||
    phase3_fail 'manifest test app path does not match the requested app'
  [[ "$(phase3_manifest_value "$manifest" 'CHROME_VERSION')" == "$PHASE3_CHROME_VERSION" ]] ||
    phase3_fail 'manifest Chrome version does not match'
  [[ "$(phase3_manifest_value "$manifest" 'ANGLE_REVISION')" == "$PHASE3_ANGLE_REVISION" ]] ||
    phase3_fail 'manifest ANGLE revision does not match'
  [[ "$(phase3_manifest_value "$manifest" 'ARTIFACT_NAME')" == "$PHASE3_ARTIFACT_NAME" ]] ||
    phase3_fail 'manifest artifact name does not match'
  [[ "$(phase3_manifest_value "$manifest" 'LIBEGL_SHA256')" == "$PHASE3_LIBEGL_SHA256" ]] ||
    phase3_fail 'manifest libEGL SHA-256 does not match'
  [[ "$(phase3_manifest_value "$manifest" 'LIBGLESV2_SHA256')" == "$PHASE3_LIBGLESV2_SHA256" ]] ||
    phase3_fail 'manifest libGLESv2 SHA-256 does not match'

  framework="$app/Contents/Frameworks/Google Chrome Framework.framework"
  [[ -d "$framework" && ! -L "$framework" ]] || phase3_fail 'test app framework is missing or symlinked'
  libraries_dir="$(cd "$framework" && pwd -P)/Libraries"
  phase3_require_only_angle_dylibs "$libraries_dir"
  phase3_verify_hash "$libraries_dir/libEGL.dylib" "$PHASE3_LIBEGL_SHA256"
  phase3_verify_hash "$libraries_dir/libGLESv2.dylib" "$PHASE3_LIBGLESV2_SHA256"
}

phase3_capture_signature() {
  local destination_prefix=$1
  local target=$2
  codesign -dvvv "$target" > "${destination_prefix}-details.txt" 2>&1 || true
  codesign -d --entitlements :- "$target" > "${destination_prefix}-entitlements.txt" 2>&1 || true
  codesign --verify --deep --strict "$target" > "${destination_prefix}-strict-verify.txt" 2>&1 || true
}
