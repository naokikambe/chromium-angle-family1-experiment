#!/usr/bin/env bash

readonly PHASE3_TEST_COPY_MANIFEST_SCHEMA='phase3-angle-test-copy-v6'
readonly PHASE3_RELEASE_MANIFEST_SCHEMA='angle-release-v1'
readonly PHASE3_ARTIFACT_SCHEMA='angle-artifact-v1'
readonly PHASE3_COPY_POLICY='norsrc,noextattr,noacl,noqtn'
readonly PHASE3_LIBRARIES_SYMLINK_TARGET='Versions/Current/Libraries'
readonly PHASE3_FRAMEWORK_VERSION_POLICY='current-only'

PHASE3_RELEASE_CHROME_VERSION=''
PHASE3_RELEASE_CHROMIUM_REVISION=''
PHASE3_RELEASE_ANGLE_REVISION=''
PHASE3_RELEASE_DEPOT_TOOLS_REVISION=''
PHASE3_RELEASE_LIBEGL_SHA256=''
PHASE3_RELEASE_LIBGLESV2_SHA256=''
PHASE3_RELEASE_ARTIFACT_NAME=''
PHASE3_RELEASE_BUILD_RUN_ID=''
PHASE3_RELEASE_BUILT_AT_UTC=''
PHASE3_RELEASE_GN_ARGS_SHA256=''
PHASE3_RELEASE_MANIFEST_SHA256=''

phase3_fail() {
  printf '%s: %s\n' "${PHASE3_SCRIPT_NAME:-phase3}" "$1" >&2
  exit 1
}

phase3_run_codesign() {
  local executable=$1
  shift
  "$executable" "$@"
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

phase3_release_manifest_path() {
  printf '%s/ANGLE_RELEASE_MANIFEST\n' "$1"
}

phase3_release_manifest_hash_path() {
  printf '%s/ANGLE_RELEASE_MANIFEST.sha256\n' "$1"
}

phase3_release_value() {
  phase3_manifest_value "$(phase3_release_manifest_path "$1")" "$2"
}

phase3_validate_release_manifest() {
  local artifact_dir=$1 metadata_only=${2:-false} manifest sidecar schema actual_gn_hash
  manifest=$(phase3_release_manifest_path "$artifact_dir")
  sidecar=$(phase3_release_manifest_hash_path "$artifact_dir")
  phase3_verify_sidecar_hash "$manifest" "$sidecar"
  schema=$(phase3_manifest_value "$manifest" SCHEMA)
  [[ "$schema" == "$PHASE3_RELEASE_MANIFEST_SCHEMA" ]] || phase3_fail 'unsupported ANGLE release manifest schema'
  [[ "$(phase3_manifest_value "$manifest" ARTIFACT_SCHEMA)" == "$PHASE3_ARTIFACT_SCHEMA" ]] ||
    phase3_fail 'unsupported ANGLE artifact schema'
  PHASE3_RELEASE_CHROME_VERSION=$(phase3_manifest_value "$manifest" CHROME_VERSION)
  [[ "$PHASE3_RELEASE_CHROME_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || phase3_fail 'invalid release Chrome version'
  PHASE3_RELEASE_CHROMIUM_REVISION=$(phase3_manifest_value "$manifest" CHROMIUM_REVISION)
  PHASE3_RELEASE_ANGLE_REVISION=$(phase3_manifest_value "$manifest" ANGLE_REVISION)
  PHASE3_RELEASE_DEPOT_TOOLS_REVISION=$(phase3_manifest_value "$manifest" DEPOT_TOOLS_REVISION)
  [[ "$PHASE3_RELEASE_CHROMIUM_REVISION" =~ ^[0-9a-f]{40}$ && "$PHASE3_RELEASE_ANGLE_REVISION" =~ ^[0-9a-f]{40}$ && "$PHASE3_RELEASE_DEPOT_TOOLS_REVISION" =~ ^[0-9a-f]{40}$ ]] || phase3_fail 'invalid source revision in release manifest'
  PHASE3_RELEASE_LIBEGL_SHA256=$(phase3_manifest_value "$manifest" LIBEGL_SHA256)
  PHASE3_RELEASE_LIBGLESV2_SHA256=$(phase3_manifest_value "$manifest" LIBGLESV2_SHA256)
  [[ "$PHASE3_RELEASE_LIBEGL_SHA256" =~ ^[0-9a-f]{64}$ && "$PHASE3_RELEASE_LIBGLESV2_SHA256" =~ ^[0-9a-f]{64}$ ]] || phase3_fail 'invalid dylib SHA-256 in release manifest'
  PHASE3_RELEASE_ARTIFACT_NAME=$(phase3_manifest_value "$manifest" ARTIFACT_NAME)
  PHASE3_RELEASE_BUILD_RUN_ID=$(phase3_manifest_value "$manifest" BUILD_RUN_ID)
  [[ "$PHASE3_RELEASE_BUILD_RUN_ID" =~ ^[0-9]+$ ]] || phase3_fail 'invalid release build run ID'
  [[ "$PHASE3_RELEASE_ARTIFACT_NAME" == "angle-macos-x86_64-chrome-${PHASE3_RELEASE_CHROME_VERSION}-angle-${PHASE3_RELEASE_ANGLE_REVISION:0:8}-${PHASE3_RELEASE_BUILD_RUN_ID}" ]] || phase3_fail 'release artifact name does not match manifest inputs'
  PHASE3_RELEASE_BUILT_AT_UTC=$(phase3_manifest_value "$manifest" BUILT_AT_UTC)
  [[ "$PHASE3_RELEASE_BUILT_AT_UTC" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] || phase3_fail 'invalid release build timestamp'
  PHASE3_RELEASE_GN_ARGS_SHA256=$(phase3_manifest_value "$manifest" GN_ARGS_SHA256)
  [[ "$PHASE3_RELEASE_GN_ARGS_SHA256" =~ ^[0-9a-f]{64}$ ]] || phase3_fail 'invalid GN args SHA-256'
  if [[ "$metadata_only" != true ]]; then
    [[ -f "$artifact_dir/libEGL.dylib" && ! -L "$artifact_dir/libEGL.dylib" ]] || phase3_fail 'release artifact lacks libEGL.dylib'
    [[ -f "$artifact_dir/libGLESv2.dylib" && ! -L "$artifact_dir/libGLESv2.dylib" ]] || phase3_fail 'release artifact lacks libGLESv2.dylib'
    phase3_verify_hash "$artifact_dir/libEGL.dylib" "$PHASE3_RELEASE_LIBEGL_SHA256"
    phase3_verify_hash "$artifact_dir/libGLESv2.dylib" "$PHASE3_RELEASE_LIBGLESV2_SHA256"
  fi
  if [[ -f "$artifact_dir/args.gn" ]]; then
    actual_gn_hash=$(phase3_hash "$artifact_dir/args.gn")
    [[ "$actual_gn_hash" == "$PHASE3_RELEASE_GN_ARGS_SHA256" ]] || phase3_fail 'release artifact GN args hash mismatch'
  fi
  PHASE3_RELEASE_MANIFEST_SHA256=$(phase3_hash "$manifest")
}

phase3_receipt_path() {
  printf '%s.phase3-angle-signing-receipt\n' "$1"
}

phase3_receipt_hash_path() {
  printf '%s.sha256\n' "$(phase3_receipt_path "$1")"
}

phase3_receipt_evidence_dir() {
  printf '%s.evidence\n' "$(phase3_receipt_path "$1")"
}

phase3_signed_libraries_inventory_path() {
  printf '%s/libraries-post-sign.txt\n' "$(phase3_receipt_evidence_dir "$1")"
}

phase3_signed_libraries_inventory_hash_path() {
  printf '%s.sha256\n' "$(phase3_signed_libraries_inventory_path "$1")"
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

phase3_validate_inventory_path() {
  local value=$1
  local description=$2
  local component
  phase3_validate_inventory_field "$value" "$description"
  [[ -n "$value" ]] || phase3_fail "Libraries inventory ${description} is empty"
  case "$value" in
    /*|*/|*//* ) phase3_fail "Libraries inventory ${description} is not root-relative: $value" ;;
  esac
  while IFS= read -r component; do
    case "$component" in
      ''|.|..) phase3_fail "Libraries inventory ${description} has an unsafe component: $value" ;;
    esac
  done < <(printf '%s\n' "$value" | tr '/' '\n')
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
    phase3_validate_inventory_path "$name" 'entry path'
    case "$type" in
      dir)
        [[ "$value" == '-' ]] || phase3_fail "invalid Libraries directory inventory record: $name"
        ;;
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
  awk -F '\t' '{ if (++seen[$1] > 1) exit 1 }' "$inventory" ||
    phase3_fail "duplicate Libraries inventory path: $inventory"
}

phase3_inventory_tree() {
  local tree_real=$1
  local inventory=$2
  local entry relpath link_target hash
  : > "$inventory"
  while IFS= read -r -d '' entry; do
    relpath=${entry#"$tree_real"/}
    phase3_validate_inventory_path "$relpath" 'entry path'
    if [[ -L "$entry" ]]; then
      link_target=$({ readlink -n "$entry"; printf '\001'; }) || phase3_fail "cannot read Libraries entry: $entry"
      link_target=${link_target%$'\001'}
      phase3_validate_inventory_field "$link_target" 'symlink target'
      printf '%s\tsymlink\t%s\n' "$relpath" "$link_target" >> "$inventory"
    elif [[ -d "$entry" ]]; then
      printf '%s\tdir\t-\n' "$relpath" >> "$inventory"
    elif [[ -f "$entry" ]]; then
      hash=$(phase3_hash "$entry")
      printf '%s\tfile\t%s\n' "$relpath" "$hash" >> "$inventory"
    else
      phase3_fail "unsupported Libraries entry type: $entry"
    fi
  done < <(find -P "$tree_real" -mindepth 1 -print0 | LC_ALL=C sort -z)
}

phase3_inventory_libraries() {
  phase3_inventory_tree "$@"
}

phase3_inventory_framework_versions_layout() {
  local framework=$1
  local inventory=$2
  local versions="$framework/Versions"
  local entry name target

  [[ -d "$versions" && ! -L "$versions" ]] ||
    phase3_fail "Framework Versions directory is missing or symlinked: $versions"
  : > "$inventory"
  while IFS= read -r -d '' entry; do
    name=$(basename "$entry")
    phase3_validate_inventory_path "$name" 'Framework version entry'
    if [[ -L "$entry" ]]; then
      target=$({ readlink -n "$entry"; printf '\001'; }) ||
        phase3_fail "cannot read Framework version symlink: $entry"
      target=${target%$'\001'}
      phase3_validate_inventory_field "$target" 'Framework version symlink target'
      printf '%s\tsymlink\t%s\n' "$name" "$target" >> "$inventory"
    elif [[ -d "$entry" ]]; then
      printf '%s\tdir\t-\n' "$name" >> "$inventory"
    else
      phase3_fail "unsupported Framework Versions entry: $entry"
    fi
  done < <(find -P "$versions" -mindepth 1 -maxdepth 1 -print0 | LC_ALL=C sort -z)
}

phase3_validate_current_only_framework() {
  local framework=$1
  local expected_version=${2:-}
  local versions="$framework/Versions"
  local current="$versions/Current"
  local current_target
  local entry name
  local current_seen=0
  local version_seen=0

  [[ -d "$framework" && ! -L "$framework" ]] ||
    phase3_fail "Framework is missing or symlinked: $framework"
  [[ -d "$versions" && ! -L "$versions" ]] ||
    phase3_fail "Framework Versions directory is missing or symlinked: $versions"
  [[ -L "$current" ]] || phase3_fail 'Framework Current is not a symlink'
  current_target=$(readlink "$current") || phase3_fail 'Framework Current symlink cannot be read'
  [[ "$current_target" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || phase3_fail 'Framework Current target is not a numeric version'
  [[ -z "$expected_version" || "$current_target" == "$expected_version" ]] || phase3_fail 'Framework Current target differs from the recorded release version'
  [[ -d "$versions/$current_target" && ! -L "$versions/$current_target" ]] ||
    phase3_fail 'current Framework version is missing or symlinked'

  while IFS= read -r -d '' entry; do
    name=$(basename "$entry")
    case "$name" in
      Current)
        [[ -L "$entry" ]] || phase3_fail 'Framework Current entry changed type'
        current_seen=$((current_seen + 1))
        ;;
      "$current_target")
        [[ -d "$entry" && ! -L "$entry" ]] || phase3_fail 'current Framework version changed type'
        version_seen=$((version_seen + 1))
        ;;
      *) phase3_fail "unexpected Framework version entry: $name" ;;
    esac
  done < <(find -P "$versions" -mindepth 1 -maxdepth 1 -print0)
  [[ "$current_seen" -eq 1 && "$version_seen" -eq 1 ]] ||
    phase3_fail 'Framework current-only layout is incomplete'
}

phase3_validate_post_inventory() {
  local baseline=$1
  local actual=$2
  local libegl_sha=${3:-$PHASE3_RELEASE_LIBEGL_SHA256}
  local gles_sha=${4:-$PHASE3_RELEASE_LIBGLESV2_SHA256}
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
    expected_sha=$libegl_sha
    [[ "$name" != libGLESv2.dylib ]] || expected_sha=$gles_sha
    [[ "$actual_line" == "$name	file	$expected_sha" ]] ||
      phase3_fail "ANGLE Libraries entry has unexpected content: $name"
  done
  while IFS=$'\t' read -r name type value; do
    case "$name" in
      libEGL.dylib|libGLESv2.dylib) ;;
      *)
        awk -F '\t' -v n="$name" -v t="$type" -v v="$value" \
          '$1 == n && $2 == t && $3 == v {found=1} END {exit !found}' "$baseline" ||
          phase3_fail "unexpected Libraries entry: $name"
        ;;
    esac
  done < "$actual"
  [[ $(wc -l < "$actual" | tr -d ' ') == $(($(wc -l < "$baseline") + 2)) ]] ||
    phase3_fail 'unexpected additional or missing Libraries entries'
}

phase3_validate_signed_inventory() {
  local prepared=$1
  local signed=$2
  local current=$3
  local name type value signed_line prepared_line signed_type signed_value prepared_type prepared_value

  phase3_validate_inventory_file "$prepared"
  phase3_validate_inventory_file "$signed"
  phase3_validate_inventory_file "$current"

  # Code signatures legitimately change the byte hashes of signed Mach-O
  # files. Preserve the prepared path/type/link layout, then pin the exact
  # post-sign inventory for later run/collect validation.
  while IFS=$'\t' read -r name type value; do
    signed_line=$(awk -F '\t' -v n="$name" '$1 == n {print; found=1} END {if (!found) exit 1}' "$signed") ||
      phase3_fail "signed Libraries entry is missing: $name"
    signed_type=${signed_line#*$'\t'}
    signed_type=${signed_type%%$'\t'*}
    signed_value=${signed_line#*$'\t'*$'\t'}
    case "$type" in
      file)
        [[ "$signed_type" == file && "$signed_value" =~ ^[0-9a-f]{64}$ ]] ||
          phase3_fail "signed Libraries file entry changed type: $name"
        ;;
      dir|symlink)
        [[ "$signed_line" == "$name"$'\t'"$type"$'\t'"$value" ]] ||
          phase3_fail "signed Libraries non-file entry changed: $name"
        ;;
    esac
  done < "$prepared"

  while IFS=$'\t' read -r name type value; do
    prepared_line=$(awk -F '\t' -v n="$name" '$1 == n {print; found=1} END {if (!found) exit 1}' "$prepared") ||
      phase3_fail "unexpected signed Libraries entry: $name"
    prepared_type=${prepared_line#*$'\t'}
    prepared_type=${prepared_type%%$'\t'*}
    prepared_value=${prepared_line#*$'\t'*$'\t'}
    case "$type" in
      file)
        [[ "$prepared_type" == file && "$prepared_value" =~ ^[0-9a-f]{64}$ ]] ||
          phase3_fail "signed Libraries file entry changed type: $name"
        ;;
      dir|symlink)
        [[ "$prepared_line" == "$name"$'\t'"$type"$'\t'"$value" ]] ||
          phase3_fail "signed Libraries non-file entry changed: $name"
        ;;
    esac
  done < "$signed"
  [[ $(wc -l < "$signed" | tr -d ' ') == $(wc -l < "$prepared" | tr -d ' ') ]] ||
    phase3_fail 'signed Libraries inventory has an unexpected entry count'
  cmp "$signed" "$current" || phase3_fail 'current Libraries inventory differs from signed inventory'
}

phase3_require_angle_dylibs_present() {
  local libraries_dir=$1 framework_dir=$2 libraries_real
  libraries_real=$(phase3_validate_libraries_directory "$libraries_dir" "$framework_dir")
  [[ -f "$libraries_real/libEGL.dylib" && ! -L "$libraries_real/libEGL.dylib" ]] || phase3_fail 'libEGL.dylib is missing or symlinked'
  [[ -f "$libraries_real/libGLESv2.dylib" && ! -L "$libraries_real/libGLESv2.dylib" ]] || phase3_fail 'libGLESv2.dylib is missing or symlinked'
}

phase3_validate_manifest() {
  local app=$1
  local validation_state=${2:-prepared}
  local signed_inventory=${3:-}
  local manifest
  local manifest_hash
  local framework
  local libraries_dir
  local evidence_dir
  local current_inventory
  local release_manifest_hash

  case "$validation_state" in
    prepared|signed) ;;
    *) phase3_fail "unsupported test-copy validation state: $validation_state" ;;
  esac

  manifest=$(phase3_manifest_path "$app")
  manifest_hash=$(phase3_manifest_hash_path "$app")
  phase3_verify_sidecar_hash "$manifest" "$manifest_hash"
  [[ "$(phase3_manifest_value "$manifest" 'SCHEMA')" == "$PHASE3_TEST_COPY_MANIFEST_SCHEMA" ]] ||
    phase3_fail 'unsupported test-copy manifest schema'
  [[ "$(phase3_manifest_value "$manifest" 'TEST_APP')" == "$app" ]] ||
    phase3_fail 'manifest test app path does not match the requested app'
  evidence_dir="$(phase3_manifest_path "$app").evidence"
  phase3_validate_release_manifest "$evidence_dir" true
  release_manifest_hash=$(phase3_hash "$(phase3_release_manifest_path "$evidence_dir")")
  [[ "$(phase3_manifest_value "$manifest" 'RELEASE_MANIFEST_SHA256')" == "$release_manifest_hash" ]] || phase3_fail 'test-copy manifest release-manifest hash mismatch'
  [[ "$(phase3_manifest_value "$manifest" 'CHROME_VERSION')" == "$PHASE3_RELEASE_CHROME_VERSION" ]] || phase3_fail 'test-copy Chrome version differs from release manifest'
  [[ "$(phase3_manifest_value "$manifest" 'CHROMIUM_REVISION')" == "$PHASE3_RELEASE_CHROMIUM_REVISION" ]] || phase3_fail 'test-copy Chromium revision differs from release manifest'
  [[ "$(phase3_manifest_value "$manifest" 'ANGLE_REVISION')" == "$PHASE3_RELEASE_ANGLE_REVISION" ]] || phase3_fail 'test-copy ANGLE revision differs from release manifest'
  [[ "$(phase3_manifest_value "$manifest" 'ARTIFACT_NAME')" == "$PHASE3_RELEASE_ARTIFACT_NAME" ]] || phase3_fail 'test-copy artifact name differs from release manifest'
  [[ "$(phase3_manifest_value "$manifest" 'LIBEGL_SHA256')" == "$PHASE3_RELEASE_LIBEGL_SHA256" ]] || phase3_fail 'test-copy libEGL SHA differs from release manifest'
  [[ "$(phase3_manifest_value "$manifest" 'LIBGLESV2_SHA256')" == "$PHASE3_RELEASE_LIBGLESV2_SHA256" ]] || phase3_fail 'test-copy libGLESv2 SHA differs from release manifest'
  [[ "$(phase3_manifest_value "$manifest" 'COPY_POLICY')" == "$PHASE3_COPY_POLICY" ]] ||
    phase3_fail 'manifest copy policy does not match'
  [[ "$(phase3_manifest_value "$manifest" 'FRAMEWORK_VERSION_POLICY')" == "$PHASE3_FRAMEWORK_VERSION_POLICY" ]] ||
    phase3_fail 'manifest Framework version policy does not match'
  PHASE3_FRAMEWORK_CURRENT_VERSION=$(phase3_manifest_value "$manifest" 'FRAMEWORK_CURRENT_VERSION')
  [[ "$PHASE3_FRAMEWORK_CURRENT_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || phase3_fail 'manifest current Framework version is invalid'

  framework="$app/Contents/Frameworks/Google Chrome Framework.framework"
  [[ -d "$framework" && ! -L "$framework" ]] || phase3_fail 'test app framework is missing or symlinked'
  phase3_validate_current_only_framework "$framework" "$PHASE3_FRAMEWORK_CURRENT_VERSION"
  libraries_dir="$(cd "$framework" && pwd -P)/Libraries"
  evidence_dir="$(phase3_manifest_path "$app").evidence"
  phase3_verify_sidecar_hash "$evidence_dir/libraries-source-baseline.txt" "$evidence_dir/libraries-source-baseline.sha256"
  phase3_verify_sidecar_hash "$evidence_dir/libraries-copy-baseline.txt" "$evidence_dir/libraries-copy-baseline.sha256"
  phase3_verify_sidecar_hash "$evidence_dir/libraries-post-install.txt" "$evidence_dir/libraries-post-install.sha256"
  phase3_verify_sidecar_hash "$evidence_dir/framework-versions-before.txt" "$evidence_dir/framework-versions-before.sha256"
  phase3_verify_sidecar_hash "$evidence_dir/framework-removed-version-inventory.txt" "$evidence_dir/framework-removed-version-inventory.sha256"
  phase3_verify_sidecar_hash "$evidence_dir/framework-removed-version-names.txt" "$evidence_dir/framework-removed-version-names.sha256"
  phase3_verify_sidecar_hash "$evidence_dir/framework-versions-after.txt" "$evidence_dir/framework-versions-after.sha256"
  local inventory_key inventory_file inventory_hash
  for inventory_key in SOURCE_BASELINE COPY_BASELINE POST_INSTALL; do
    case "$inventory_key" in
      SOURCE_BASELINE) inventory_file='libraries-source-baseline.txt' ;;
      COPY_BASELINE) inventory_file='libraries-copy-baseline.txt' ;;
      POST_INSTALL) inventory_file='libraries-post-install.txt' ;;
    esac
    inventory_hash="$(phase3_hash "$evidence_dir/$inventory_file")"
    [[ "$(phase3_manifest_value "$(phase3_manifest_path "$app")" "LIBRARIES_${inventory_key}_SHA256")" == "$inventory_hash" ]] ||
      phase3_fail "manifest Libraries ${inventory_key} inventory hash does not match"
  done
  local framework_inventory_key framework_inventory_file framework_inventory_hash
  for framework_inventory_key in VERSIONS_BEFORE REMOVED_VERSION_INVENTORY VERSIONS_AFTER; do
    case "$framework_inventory_key" in
      VERSIONS_BEFORE) framework_inventory_file='framework-versions-before.txt' ;;
      REMOVED_VERSION_INVENTORY) framework_inventory_file='framework-removed-version-inventory.txt' ;;
      VERSIONS_AFTER) framework_inventory_file='framework-versions-after.txt' ;;
    esac
    framework_inventory_hash=$(phase3_hash "$evidence_dir/$framework_inventory_file")
    [[ "$(phase3_manifest_value "$manifest" "FRAMEWORK_${framework_inventory_key}_SHA256")" == "$framework_inventory_hash" ]] ||
      phase3_fail "manifest Framework ${framework_inventory_key} inventory hash does not match"
  done
  phase3_validate_inventory_file "$evidence_dir/framework-versions-before.txt"
  phase3_validate_inventory_file "$evidence_dir/framework-removed-version-inventory.txt"
  phase3_validate_inventory_file "$evidence_dir/framework-versions-after.txt"
  grep -F $'Current\tsymlink\t'"$PHASE3_FRAMEWORK_CURRENT_VERSION" "$evidence_dir/framework-versions-before.txt" >/dev/null ||
    phase3_fail 'Framework versions-before evidence lacks the expected Current symlink'
  grep -F "$PHASE3_FRAMEWORK_CURRENT_VERSION"$'\tdir\t-' "$evidence_dir/framework-versions-before.txt" >/dev/null ||
    phase3_fail 'Framework versions-before evidence lacks the current version'
  grep -F $'Current\tsymlink\t'"$PHASE3_FRAMEWORK_CURRENT_VERSION" "$evidence_dir/framework-versions-after.txt" >/dev/null ||
    phase3_fail 'Framework versions-after evidence lacks the expected Current symlink'
  grep -F "$PHASE3_FRAMEWORK_CURRENT_VERSION"$'\tdir\t-' "$evidence_dir/framework-versions-after.txt" >/dev/null ||
    phase3_fail 'Framework versions-after evidence lacks the current version'
  [[ $(wc -l < "$evidence_dir/framework-versions-after.txt" | tr -d ' ') == 2 ]] ||
    phase3_fail 'Framework versions-after evidence is not current-only'
  [[ "$(phase3_manifest_value "$manifest" 'FRAMEWORK_REMOVED_VERSION_NAMES_SHA256')" == "$(phase3_hash "$evidence_dir/framework-removed-version-names.txt")" ]] || phase3_fail 'removed Framework version list hash mismatch'
  cmp "$evidence_dir/libraries-source-baseline.txt" "$evidence_dir/libraries-copy-baseline.txt" || phase3_fail 'source and copy Libraries baseline differs'
  phase3_validate_post_inventory "$evidence_dir/libraries-copy-baseline.txt" "$evidence_dir/libraries-post-install.txt"
  current_inventory=$(mktemp "${TMPDIR:-/tmp}/phase3-current-inventory.XXXXXX")
  phase3_inventory_libraries "$(phase3_validate_libraries_directory "$libraries_dir" "$framework")" "$current_inventory"
  if [[ "$validation_state" == prepared ]]; then
    cmp "$evidence_dir/libraries-post-install.txt" "$current_inventory" || phase3_fail 'current Libraries inventory differs from prepared inventory'
    phase3_verify_hash "$libraries_dir/libEGL.dylib" "$PHASE3_RELEASE_LIBEGL_SHA256"
    phase3_verify_hash "$libraries_dir/libGLESv2.dylib" "$PHASE3_RELEASE_LIBGLESV2_SHA256"
  else
    [[ -n "$signed_inventory" ]] || phase3_fail 'signed Libraries inventory path is missing'
    phase3_verify_sidecar_hash "$signed_inventory" "${signed_inventory}.sha256"
    phase3_validate_signed_inventory "$evidence_dir/libraries-post-install.txt" "$signed_inventory" "$current_inventory"
  fi
  rm -f "$current_inventory"
}

phase3_validate_signed_test_copy() {
  local app=$1
  local codesign_executable=${2:-/usr/bin/codesign}
  local manifest
  local receipt
  local manifest_sha256
  local signed_inventory
  local receipt_schema
  local signing_method
  local entitlements
  local required_entitlement
  local forbidden_entitlement

  manifest=$(phase3_manifest_path "$app")
  receipt=$(phase3_receipt_path "$app")
  phase3_verify_sidecar_hash "$receipt" "$(phase3_receipt_hash_path "$app")"
  receipt_schema=$(phase3_manifest_value "$receipt" 'SCHEMA')
  case "$receipt_schema" in
    phase3-angle-signing-receipt-v2|phase3-angle-signing-receipt-v3) ;;
    *) phase3_fail 'unsupported signing receipt schema' ;;
  esac
  [[ "$(phase3_manifest_value "$receipt" 'TEST_APP')" == "$app" ]] ||
    phase3_fail 'signing receipt app path does not match'
  signing_method=$(phase3_manifest_value "$receipt" 'SIGNING_METHOD')
  case "$signing_method" in
    ad-hoc-deep|ad-hoc-nested|ad-hoc-versioned-framework|ad-hoc-current-framework)
      [[ "$receipt_schema" == 'phase3-angle-signing-receipt-v2' ]] ||
        phase3_fail 'ad-hoc signing receipt has an unexpected schema'
      ;;
    apple-development-current-framework)
      [[ "$receipt_schema" == 'phase3-angle-signing-receipt-v3' ]] ||
        phase3_fail 'Apple Development signing receipt has an unexpected schema'
      [[ "$(phase3_manifest_value "$receipt" 'SIGNING_IDENTITY_SHA1')" =~ ^[0-9A-F]{40}$ ]] ||
        phase3_fail 'Apple Development signing receipt has an invalid identity fingerprint'
      [[ "$(phase3_manifest_value "$receipt" 'ENTITLEMENTS_PROFILE')" == 'chromium-base-device-v1' ]] ||
        phase3_fail 'Apple Development signing receipt has an unsupported entitlements profile'
      ;;
    *) phase3_fail 'unsupported signing method' ;;
  esac
  [[ "$(phase3_manifest_value "$receipt" 'STRICT_VERIFICATION')" == 'passed' ]] ||
    phase3_fail 'signing receipt does not record strict verification'
  manifest_sha256=$(phase3_hash "$manifest")
  [[ "$(phase3_manifest_value "$receipt" 'PREPARE_MANIFEST_SHA256')" == "$manifest_sha256" ]] ||
    phase3_fail 'signing receipt does not match the current preparation manifest'
  signed_inventory=$(phase3_signed_libraries_inventory_path "$app")
  phase3_verify_sidecar_hash "$signed_inventory" "$(phase3_signed_libraries_inventory_hash_path "$app")"
  [[ "$(phase3_manifest_value "$receipt" 'SIGNED_LIBRARIES_INVENTORY_SHA256')" == "$(phase3_hash "$signed_inventory")" ]] ||
    phase3_fail 'signing receipt does not match the signed Libraries inventory'
  phase3_validate_manifest "$app" signed "$signed_inventory"
  phase3_run_codesign "$codesign_executable" --verify --deep --strict "$app" || phase3_fail 'test copy strict signature verification failed'
  case "$signing_method" in
    ad-hoc-*)
      phase3_run_codesign "$codesign_executable" -dvvv "$app" 2>&1 | grep -F 'Signature=adhoc' >/dev/null ||
        phase3_fail 'test copy is not currently ad-hoc signed'
      ;;
    apple-development-current-framework)
      phase3_run_codesign "$codesign_executable" -dvvv "$app" 2>&1 | grep -F 'Authority=Apple Development:' >/dev/null ||
        phase3_fail 'test copy is not signed with an Apple Development identity'
      phase3_run_codesign "$codesign_executable" -dvvv "$app" 2>&1 | grep -E '^TeamIdentifier=.+$' | grep -Fv 'TeamIdentifier=not set' >/dev/null ||
        phase3_fail 'test copy has no Apple Development team identifier'
      entitlements=$(phase3_run_codesign "$codesign_executable" -d --entitlements :- "$app" 2>&1) ||
        phase3_fail 'cannot read Apple Development app entitlements'
      for required_entitlement in \
        com.apple.security.device.audio-input \
        com.apple.security.device.bluetooth \
        com.apple.security.device.camera \
        com.apple.security.device.print \
        com.apple.security.device.usb \
        com.apple.security.personal-information.location \
        com.apple.security.personal-information.photos-library; do
        [[ "$entitlements" == *"<key>$required_entitlement</key>"* ]] ||
          phase3_fail "test copy lacks required development entitlement: $required_entitlement"
      done
      for forbidden_entitlement in \
        com.apple.application-identifier \
        keychain-access-groups \
        com.apple.developer.associated-domains.applinks.read-write \
        com.apple.developer.web-browser.public-key-credential; do
        [[ "$entitlements" != *"<key>$forbidden_entitlement</key>"* ]] ||
          phase3_fail "test copy retains Google-bound entitlement: $forbidden_entitlement"
      done
      ;;
  esac
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
  local codesign_executable=${3:-/usr/bin/codesign}
  phase3_run_codesign "$codesign_executable" -dvvv "$target" > "${destination_prefix}-details.txt" 2>&1 || true
  phase3_run_codesign "$codesign_executable" -d --entitlements :- "$target" > "${destination_prefix}-entitlements.txt" 2>&1 || true
  phase3_run_codesign "$codesign_executable" --verify --deep --strict "$target" > "${destination_prefix}-strict-verify.txt" 2>&1 || true
}
