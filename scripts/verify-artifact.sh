#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'usage: %s ARTIFACT_DIRECTORY\n' "$0" >&2
  exit 64
fi

artifact_dir=$1
if [[ ! -d "$artifact_dir" ]]; then
  printf 'artifact directory does not exist: %s\n' "$artifact_dir" >&2
  exit 66
fi

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'required command is unavailable: %s\n' "$1" >&2
    exit 69
  fi
}

fail() {
  printf 'verification failed: %s\n' "$1" >&2
  exit 1
}

check_forbidden_path() {
  local result_file=$1
  local forbidden_path

  for forbidden_path in "${RUNNER_TEMP:-}" "${GITHUB_WORKSPACE:-}"; do
    if [[ -n "$forbidden_path" ]] && grep -F -- "$forbidden_path" "$result_file" >/dev/null; then
      fail "CI work directory appears in ${result_file##*/}"
    fi
  done
}

require_command file
require_command lipo
require_command otool
require_command codesign
require_command shasum
require_command awk

cd "$artifact_dir"

required_libraries=(libEGL.dylib libGLESv2.dylib)
for library in "${required_libraries[@]}"; do
  [[ -f "$library" ]] || fail "required library is missing: $library"
done

export LC_ALL=C
shopt -s nullglob
libraries=(*.dylib)
(( ${#libraries[@]} > 0 )) || fail 'artifact contains no dylibs'

: > file-results.txt
: > lipo-results.txt
: > otool-results.txt
: > codesign-results.txt
signature_invalid=0

for library in "${libraries[@]}"; do
  printf '== %s ==\n' "$library" >> file-results.txt
  file "$library" >> file-results.txt

  printf '== %s ==\n' "$library" >> lipo-results.txt
  lipo -info "$library" >> lipo-results.txt
  if ! lipo -info "$library" | grep -Eq '(^|[[:space:]])x86_64($|[[:space:]])'; then
    fail "$library does not contain x86_64"
  fi

  printf '== %s: install name ==\n' "$library" >> otool-results.txt
  if ! install_name_report=$(otool -D "$library"); then
    fail "$library install name report failed"
  fi
  printf '%s\n' "$install_name_report" >> otool-results.txt
  if ! install_name_output=$(otool -arch x86_64 -D "$library"); then
    fail "$library install name lookup failed"
  fi
  install_name=''
  install_name_count=0
  while IFS= read -r install_name_line; do
    [[ -n "$install_name_line" ]] || continue
    install_name=$install_name_line
    ((install_name_count += 1))
  done < <(printf '%s\n' "$install_name_output" | awk 'NR > 1 && NF { print }')
  (( install_name_count == 1 )) ||
    fail "$library has an ambiguous or missing x86_64 install name"
  printf 'x86_64 install name: %s\n' "$install_name" >> otool-results.txt

  printf '== %s: dependencies ==\n' "$library" >> otool-results.txt
  if ! dependency_report=$(otool -L "$library"); then
    fail "$library dependency report failed"
  fi
  printf '%s\n' "$dependency_report" >> otool-results.txt
  printf '== %s: load commands ==\n' "$library" >> otool-results.txt
  otool -l "$library" >> otool-results.txt

  if ! dependency_output=$(otool -arch x86_64 -L "$library"); then
    fail "$library dependency lookup failed"
  fi
  dependencies=()
  while IFS= read -r dependency; do
    [[ -n "$dependency" ]] || continue
    dependencies+=("$dependency")
  done < <(printf '%s\n' "$dependency_output" | awk 'NR > 1 && NF { print $1 }')
  (( ${#dependencies[@]} > 0 )) || fail "$library has no x86_64 otool -L entries"

  for dependency_index in "${!dependencies[@]}"; do
    dependency=${dependencies[dependency_index]}
    if (( dependency_index == 0 )); then
      [[ "$dependency" == "$install_name" ]] ||
        fail "$library x86_64 self install name does not match its first otool -L entry"
      continue
    fi
    case "$dependency" in
      /System/Library/*|/usr/lib/*)
        ;;
      @rpath/*|@loader_path/*|@executable_path/*)
        dependency_name=${dependency##*/}
        [[ -f "$dependency_name" ]] ||
          fail "$library requires non-system dylib absent from artifact: $dependency"
        ;;
      *)
        fail "$library has an unexpected non-system dependency: $dependency"
        ;;
    esac
  done

  {
    printf '== %s ==\n' "$library"
    if codesign_details=$(codesign -dvvv "$library" 2>&1); then
      codesign_details_status=0
    else
      codesign_details_status=$?
    fi
    if codesign_verify=$(codesign --verify --verbose=4 "$library" 2>&1); then
      codesign_verify_status=0
    else
      codesign_verify_status=$?
    fi
    printf '%s\n' "$codesign_details"
    printf '%s\n' "$codesign_verify"
    if (( codesign_details_status == 0 && codesign_verify_status == 0 )); then
      printf 'codesign verification status: signed and valid\n'
    elif [[ "$codesign_details" == *'not signed'* || "$codesign_verify" == *'not signed'* ]]; then
      printf 'codesign verification status: unsigned (allowed in Phase 2)\n'
    else
      printf 'codesign verification status: signed but invalid\n'
      signature_invalid=1
    fi
  } >> codesign-results.txt
done

check_forbidden_path otool-results.txt

shasum -a 256 -- "${libraries[@]}" > checksums.sha256

release_manifest=ANGLE_RELEASE_MANIFEST
release_sidecar=ANGLE_RELEASE_MANIFEST.sha256
[[ -f "$release_manifest" && ! -L "$release_manifest" ]] || fail 'ANGLE release manifest is missing or symlinked'
[[ -f "$release_sidecar" && ! -L "$release_sidecar" ]] || fail 'ANGLE release manifest checksum is missing or symlinked'
shasum -a 256 -c "$release_sidecar" >/dev/null || fail 'ANGLE release manifest checksum mismatch'
manifest_value() {
  local key=$1 matches
  matches=$(grep -E "^${key}=" "$release_manifest" || true)
  [[ $(printf '%s\n' "$matches" | sed '/^$/d' | wc -l | tr -d ' ') == 1 ]] || fail "invalid release manifest key: $key"
  printf '%s\n' "${matches#*=}"
}
[[ "$(manifest_value SCHEMA)" == angle-release-v1 ]] || fail 'unsupported release manifest schema'
[[ "$(manifest_value ARTIFACT_SCHEMA)" == angle-artifact-v1 ]] || fail 'unsupported artifact schema'
chrome_version=$(manifest_value CHROME_VERSION)
chromium_revision=$(manifest_value CHROMIUM_REVISION)
angle_revision=$(manifest_value ANGLE_REVISION)
depot_revision=$(manifest_value DEPOT_TOOLS_REVISION)
libegl_sha=$(manifest_value LIBEGL_SHA256)
gles_sha=$(manifest_value LIBGLESV2_SHA256)
artifact_name=$(manifest_value ARTIFACT_NAME)
run_id=$(manifest_value BUILD_RUN_ID)
gn_args_sha=$(manifest_value GN_ARGS_SHA256)
[[ "$chrome_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail 'invalid Chrome version in release manifest'
for revision in "$chromium_revision" "$angle_revision" "$depot_revision"; do [[ "$revision" =~ ^[0-9a-f]{40}$ ]] || fail 'invalid source revision in release manifest'; done
for checksum in "$libegl_sha" "$gles_sha" "$gn_args_sha"; do [[ "$checksum" =~ ^[0-9a-f]{64}$ ]] || fail 'invalid SHA-256 in release manifest'; done
[[ "$run_id" =~ ^[0-9]+$ ]] || fail 'invalid build run ID in release manifest'
[[ "$artifact_name" == "angle-macos-x86_64-chrome-${chrome_version}-angle-${angle_revision:0:8}-${run_id}" ]] || fail 'artifact name does not match release manifest fields'
[[ "$(shasum -a 256 libEGL.dylib | awk '{print $1}')" == "$libegl_sha" ]] || fail 'libEGL SHA-256 does not match release manifest'
[[ "$(shasum -a 256 libGLESv2.dylib | awk '{print $1}')" == "$gles_sha" ]] || fail 'libGLESv2 SHA-256 does not match release manifest'
[[ "$(shasum -a 256 args.gn | awk '{print $1}')" == "$gn_args_sha" ]] || fail 'args.gn SHA-256 does not match release manifest'
grep -Fx "CHROME_VERSION=$chrome_version" build-environment.txt >/dev/null || fail 'build environment Chrome version differs from release manifest'
grep -Fx "CHROMIUM_REVISION=$chromium_revision" build-environment.txt >/dev/null || fail 'build environment Chromium revision differs from release manifest'
grep -Fx "ANGLE_EXPECTED_REVISION=$angle_revision" build-environment.txt >/dev/null || fail 'build environment ANGLE revision differs from release manifest'
grep -Fx "DEPOT_TOOLS_EXPECTED_REVISION=$depot_revision" build-environment.txt >/dev/null || fail 'build environment depot_tools revision differs from release manifest'

if (( signature_invalid != 0 )); then
  fail 'one or more dylibs have an invalid code signature'
fi

printf 'artifact verification passed\n'
