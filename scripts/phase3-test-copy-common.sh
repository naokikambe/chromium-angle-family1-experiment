#!/usr/bin/env bash

readonly PHASE3_CHROME_VERSION='154.0.8037.45'
readonly PHASE3_CHROMIUM_REVISION='731082f0a26ce4b3976c3d82943092f5d13daf13'
readonly PHASE3_ANGLE_REVISION='72b8f72a7587ec776d7d2a57d275a6e9b1781b1d'
readonly PHASE3_ARTIFACT_NAME='angle-macos-x86_64-chrome-154.0.8037.45-angle-72b8f72a-35515036255'
readonly PHASE3_LIBEGL_SHA256='f4a8a7575183a41373404f7c25b4f56e1a1540c5b1578d11437c180b1f698db8'
readonly PHASE3_LIBGLESV2_SHA256='8d3d188d3d4f23cf3f96ecea209b084c6db9c6192244f879cfb6bf0fb2e02cf0'
readonly PHASE3_TEST_COPY_MANIFEST_SCHEMA='phase3-angle-test-copy-v3'
readonly PHASE3_COPY_POLICY='norsrc,noextattr,noacl,noqtn'
readonly PHASE3_LIBRARIES_SYMLINK_TARGET='Versions/Current/Libraries'

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

phase3_validate_libraries_directory() {
  local libraries_dir=$1
  local framework_dir=$2
  local link_target
  local libraries_real
  local framework_real

  [[ -d "$libraries_dir" ]] || phase3_fail "Libraries directory is missing: $libraries_dir"
  framework_real=$(cd "$framework_dir" 2>/dev/null && pwd -P) ||
    phase3_fail "Framework directory cannot be resolved: $framework_dir"
  if [[ -L "$libraries_dir" ]]; then
    link_target=$(readlink "$libraries_dir") || phase3_fail "Libraries symlink cannot be read: $libraries_dir"
    [[ "$link_target" == "$PHASE3_LIBRARIES_SYMLINK_TARGET" ]] ||
      phase3_fail "Libraries symlink target is not the canonical target: $libraries_dir"
  elif [[ ! -d "$libraries_dir" ]]; then
    phase3_fail "Libraries path is not a directory: $libraries_dir"
  fi
  libraries_real=$(cd "$libraries_dir" 2>/dev/null && pwd -P) ||
    phase3_fail "Libraries symlink is broken: $libraries_dir"
  case "$libraries_real/" in
    "$framework_real/"*) ;;
    *) phase3_fail "Libraries symlink resolves outside the test Framework: $libraries_dir" ;;
  esac
  printf '%s\n' "$libraries_real"
}

phase3_validate_new_libraries_path() {
  local libraries_dir=$1
  local framework_dir=$2
  local parent_dir
  local framework_real
  local parent_real

  [[ ! -e "$libraries_dir" && ! -L "$libraries_dir" ]] ||
    phase3_fail "Libraries path is not new: $libraries_dir"
  parent_dir=$(dirname "$libraries_dir")
  [[ -d "$parent_dir" && ! -L "$parent_dir" ]] ||
    phase3_fail "Libraries parent is not a regular directory: $parent_dir"
  framework_real=$(cd "$framework_dir" 2>/dev/null && pwd -P) ||
    phase3_fail "Framework directory cannot be resolved: $framework_dir"
  parent_real=$(cd "$parent_dir" 2>/dev/null && pwd -P) ||
    phase3_fail "Libraries parent cannot be resolved: $parent_dir"
  case "$parent_real/" in
    "$framework_real/"*) ;;
    *) phase3_fail "New Libraries path is outside the test Framework: $libraries_dir" ;;
  esac
}

phase3_validate_inventory_field() {
  local value=$1
  local description=$2
  if printf '%s' "$value" | LC_ALL=C grep '[[:cntrl:]]' >/dev/null; then
    phase3_fail "Libraries inventory ${description} contains a control character"
  fi
}

phase3_validate_inventory_file() {
  local inventory=$1
  local line remainder name type value
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" == *$'\t'*$'\t'* ]] || phase3_fail "invalid Libraries inventory record: $inventory"
    name=${line%%$'\t'*}
    remainder=${line#*$'\t'}
    type=${remainder%%$'\t'*}
    value=${remainder#*$'\t'}
    phase3_validate_inventory_field "$name" 'entry name'
    case "$type" in
      file)
        [[ "$value" =~ ^[0-9a-f]{64}$ ]] || phase3_fail "invalid Libraries file inventory record: $name"
        ;;
      symlink)
        phase3_validate_inventory_field "$value" 'symlink target'
        ;;
      *) phase3_fail "invalid Libraries inventory entry type: $type" ;;
    esac
    line=''
  done < "$inventory"
}

phase3_inventory_libraries() {
  local libraries_real=$1
  local inventory=$2
  local entry name link_target hash
  : > "$inventory"
  while IFS= read -r -d '' entry; do
    name=${entry##*/}
    phase3_validate_inventory_field "$name" 'entry name'
    if [[ -L "$entry" ]]; then
      link_target=$({ readlink -n "$entry"; printf '\001'; }) || phase3_fail "cannot read Libraries entry: $entry"
      link_target=${link_target%$'\001'}
      phase3_validate_inventory_field "$link_target" 'symlink target'
      printf '%s\tsymlink\t%s\n' "$name" "$link_target" >> "$inventory"
    elif [[ -f "$entry" ]]; then
      hash=$(phase3_hash "$entry")
      printf '%s\tfile\t%s\n' "$name" "$hash" >> "$inventory"
    else
      phase3_fail "unsupported Libraries entry type: $entry"
    fi
  done < <(find "$libraries_real" -mindepth 1 -maxdepth 1 -print0 | LC_ALL=C sort -z)
}

phase3_validate_post_inventory() {
  local baseline=$1
  local actual=$2
  local name type value actual_line
  phase3_validate_inventory_file "$baseline"
  phase3_validate_inventory_file "$actual"
  while IFS=$'\t' read -r name type value; do
    actual_line=$(awk -F '\t' -v n="$name" '$1 == n {print; found=1} END {if (!found) exit 1}' "$actual") ||
      phase3_fail "baseline Libraries entry is missing: $name"
    [[ "$actual_line" == "$name	$type	$value" ]] || phase3_fail "baseline Libraries entry changed: $name"
  done < "$baseline"
  for name in libEGL.dylib libGLESv2.dylib; do
    actual_line=$(awk -F '\t' -v n="$name" '$1 == n {print; found=1} END {if (!found) exit 1}' "$actual") ||
      phase3_fail "ANGLE Libraries entry is missing: $name"
    [[ "$actual_line" == "$name	file	${name/libEGL.dylib/$PHASE3_LIBEGL_SHA256}" || "$actual_line" == "$name	file	${name/libGLESv2.dylib/$PHASE3_LIBGLESV2_SHA256}" ]] ||
      phase3_fail "ANGLE Libraries entry has unexpected content: $name"
  done
  [[ $(wc -l < "$actual" | tr -d ' ') == $(($(wc -l < "$baseline") + 2)) ]] ||
    phase3_fail 'unexpected additional or missing Libraries entries'
}

phase3_require_only_angle_dylibs() {
  local libraries_dir=$1
  local framework_dir=$2
  local library
  local libraries_real
  local -a actual=()
  local -a expected=(libEGL.dylib libGLESv2.dylib)

  libraries_real=$(phase3_validate_libraries_directory "$libraries_dir" "$framework_dir")
  while IFS= read -r library; do
    actual+=("$(basename "$library")")
    [[ ! -L "$library" ]] || phase3_fail "dylib is symlinked: $library"
  done < <(find "$libraries_real" -maxdepth 1 -type f -name '*.dylib' -print | LC_ALL=C sort)
  [[ "${actual[*]}" == "${expected[*]}" ]] ||
    phase3_fail 'Libraries directory must contain exactly libEGL.dylib and libGLESv2.dylib'
}

phase3_validate_manifest() {
  local app=$1
  local manifest
  local manifest_hash
  local framework
  local libraries_dir
  local evidence_dir
  local current_inventory

  manifest=$(phase3_manifest_path "$app")
  manifest_hash=$(phase3_manifest_hash_path "$app")
  phase3_verify_sidecar_hash "$manifest" "$manifest_hash"
  [[ "$(phase3_manifest_value "$manifest" 'SCHEMA')" == "$PHASE3_TEST_COPY_MANIFEST_SCHEMA" ]] ||
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
  [[ "$(phase3_manifest_value "$manifest" 'COPY_POLICY')" == "$PHASE3_COPY_POLICY" ]] ||
    phase3_fail 'manifest copy policy does not match'

  framework="$app/Contents/Frameworks/Google Chrome Framework.framework"
  [[ -d "$framework" && ! -L "$framework" ]] || phase3_fail 'test app framework is missing or symlinked'
  libraries_dir="$(cd "$framework" && pwd -P)/Libraries"
  evidence_dir="$(phase3_manifest_path "$app").evidence"
  phase3_verify_sidecar_hash "$evidence_dir/libraries-baseline-inventory.txt" "$evidence_dir/libraries-baseline-inventory.sha256"
  phase3_verify_sidecar_hash "$evidence_dir/libraries-final-inventory.txt" "$evidence_dir/libraries-final-inventory.sha256"
  [[ "$(phase3_manifest_value "$(phase3_manifest_path "$app")" 'LIBRARIES_BASELINE_INVENTORY_SHA256')" == "$(phase3_hash "$evidence_dir/libraries-baseline-inventory.txt")" ]] ||
    phase3_fail 'manifest Libraries baseline inventory hash does not match'
  phase3_validate_post_inventory "$evidence_dir/libraries-baseline-inventory.txt" "$evidence_dir/libraries-final-inventory.txt"
  current_inventory=$(mktemp "${TMPDIR:-/tmp}/phase3-current-inventory.XXXXXX")
  phase3_inventory_libraries "$(phase3_validate_libraries_directory "$libraries_dir" "$framework")" "$current_inventory"
  cmp "$evidence_dir/libraries-final-inventory.txt" "$current_inventory" || phase3_fail 'current Libraries inventory differs from prepared inventory'
  rm -f "$current_inventory"
  phase3_verify_hash "$libraries_dir/libEGL.dylib" "$PHASE3_LIBEGL_SHA256"
  phase3_verify_hash "$libraries_dir/libGLESv2.dylib" "$PHASE3_LIBGLESV2_SHA256"
}

phase3_validate_signed_test_copy() {
  local app=$1
  local manifest
  local receipt
  local manifest_sha256

  phase3_validate_manifest "$app"
  manifest=$(phase3_manifest_path "$app")
  receipt=$(phase3_receipt_path "$app")
  phase3_verify_sidecar_hash "$receipt" "$(phase3_receipt_hash_path "$app")"
  [[ "$(phase3_manifest_value "$receipt" 'SCHEMA')" == 'phase3-angle-signing-receipt-v1' ]] ||
    phase3_fail 'unsupported signing receipt schema'
  [[ "$(phase3_manifest_value "$receipt" 'TEST_APP')" == "$app" ]] ||
    phase3_fail 'signing receipt app path does not match'
  [[ "$(phase3_manifest_value "$receipt" 'SIGNING_METHOD')" == 'ad-hoc-deep' ]] ||
    phase3_fail 'test copy was not ad-hoc signed'
  [[ "$(phase3_manifest_value "$receipt" 'STRICT_VERIFICATION')" == 'passed' ]] ||
    phase3_fail 'signing receipt does not record strict verification'
  manifest_sha256=$(phase3_hash "$manifest")
  [[ "$(phase3_manifest_value "$receipt" 'PREPARE_MANIFEST_SHA256')" == "$manifest_sha256" ]] ||
    phase3_fail 'signing receipt does not match the current preparation manifest'
  codesign --verify --deep --strict "$app" || phase3_fail 'test copy strict signature verification failed'
  codesign -dvvv "$app" 2>&1 | grep -F 'Signature=adhoc' >/dev/null ||
    phase3_fail 'test copy is not currently ad-hoc signed'
}

phase3_capture_process_snapshot() {
  local destination=$1
  ps -wwaxo pid=,command= > "$destination"
}

phase3_snapshot_matching_processes() {
  local snapshot=$1
  local first_required=$2
  local second_required=${3:-}

  awk -v first_required="$first_required" -v second_required="$second_required" '
    {
      process_id = $1
      command = $0
      sub(/^[[:space:]]*[0-9]+[[:space:]]+/, "", command)
      if (process_id ~ /^[0-9]+$/ && index(command, first_required) &&
          (second_required == "" || index(command, second_required))) {
        print process_id " " command
      }
    }
  ' "$snapshot"
}

phase3_capture_signature() {
  local destination_prefix=$1
  local target=$2
  codesign -dvvv "$target" > "${destination_prefix}-details.txt" 2>&1 || true
  codesign -d --entitlements :- "$target" > "${destination_prefix}-entitlements.txt" 2>&1 || true
  codesign --verify --deep --strict "$target" > "${destination_prefix}-strict-verify.txt" 2>&1 || true
}
