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
  otool -D "$library" >> otool-results.txt
  install_name=$(otool -D "$library" | sed -n '2p')
  [[ -n "$install_name" ]] || fail "$library has no install name"

  printf '== %s: dependencies ==\n' "$library" >> otool-results.txt
  otool -L "$library" >> otool-results.txt
  printf '== %s: load commands ==\n' "$library" >> otool-results.txt
  otool -l "$library" >> otool-results.txt

  while IFS= read -r dependency; do
    [[ -n "$dependency" ]] || continue
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
  done < <(otool -L "$library" | awk 'NR > 1 { print $1 }')

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

if (( signature_invalid != 0 )); then
  fail 'one or more dylibs have an invalid code signature'
fi

printf 'artifact verification passed\n'
