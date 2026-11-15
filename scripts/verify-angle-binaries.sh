#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  printf 'usage: %s ARTIFACT_DIRECTORY ARCHITECTURE DEPLOYMENT_TARGET\n' "$0" >&2
  exit 64
fi
artifact_dir=$1
architecture=$2
deployment_target=$3
[[ -d "$artifact_dir" ]] || { printf 'artifact directory is missing\n' >&2; exit 66; }
[[ "$architecture" == x86_64 ]] || { printf 'unsupported build architecture\n' >&2; exit 64; }
[[ "$deployment_target" =~ ^[0-9]+\.[0-9]+$ ]] || { printf 'invalid deployment target\n' >&2; exit 64; }

for library in libEGL.dylib libGLESv2.dylib; do
  path="$artifact_dir/$library"
  [[ -f "$path" && ! -L "$path" ]] || { printf 'missing or symlinked library: %s\n' "$library" >&2; exit 1; }
  [[ "$(lipo -archs "$path")" == "$architecture" ]] || { printf 'unexpected library architecture: %s\n' "$library" >&2; exit 1; }
  load_commands=$(otool -l "$path")
  actual_target=$(printf '%s\n' "$load_commands" | awk '
    /^[[:space:]]*cmd / { command = $2; platform = ""; next }
    command == "LC_BUILD_VERSION" && $1 == "platform" { platform = $2; next }
    command == "LC_BUILD_VERSION" && (platform == "MACOS" || platform == "1") && $1 == "minos" { print $2; exit }
    command == "LC_VERSION_MIN_MACOSX" && $1 == "version" { print $2; exit }
  ')
  [[ "$actual_target" == "$deployment_target" ]] || { printf 'unexpected minimum OS target: %s\n' "$library" >&2; exit 1; }
  symbols=$(nm -gU "$path")
  ! grep -E 'ANGLE_MetalFamily1Test|DisplayMtlFamily1Test|ANGLE_ENABLE_METAL_FAMILY1_TEST_STUB' <<< "$symbols" >/dev/null || {
    printf 'test-only ANGLE symbol found: %s\n' "$library" >&2; exit 1;
  }
  if details=$(codesign -dvvv "$path" 2>&1); then
    printf 'library unexpectedly has a signature: %s\n' "$library" >&2; exit 1
  fi
  [[ "$details" == *'not signed'* ]] || { printf 'unsigned status was not confirmed: %s\n' "$library" >&2; exit 1; }
done
