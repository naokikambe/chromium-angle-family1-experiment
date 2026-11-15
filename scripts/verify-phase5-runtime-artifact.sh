#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'usage: %s ARTIFACT_DIRECTORY\n' "$0" >&2
  exit 64
fi

artifact_dir=$1
[[ -d "$artifact_dir" ]] || {
  printf 'runtime artifact directory does not exist: %s\n' "$artifact_dir" >&2
  exit 66
}

fail() {
  printf 'Phase 5 runtime artifact verification failed: %s\n' "$1" >&2
  exit 1
}

manifest="$artifact_dir/ANGLE_RELEASE_MANIFEST"
[[ -f "$manifest" && ! -L "$manifest" ]] || fail 'ANGLE_RELEASE_MANIFEST is missing or symlinked'

manifest_value() {
  local key=$1 matches
  matches=$(grep -E "^${key}=" "$manifest" || true)
  [[ $(printf '%s\n' "$matches" | sed '/^$/d' | wc -l | tr -d ' ') == 1 ]] ||
    fail "invalid or duplicate manifest key: $key"
  printf '%s\n' "${matches#*=}"
}

check_sha256() {
  local path=$1 expected=$2 label=$3 actual
  [[ -f "$path" && ! -L "$path" ]] || fail "$label is missing or symlinked"
  actual=$(shasum -a 256 "$path" | awk '{print $1}')
  [[ "$actual" == "$expected" ]] || fail "$label SHA-256 mismatch"
}

[[ "$(manifest_value SCHEMA)" == angle-release-v1 ]] || fail 'unexpected release manifest schema'
[[ "$(manifest_value ARTIFACT_SCHEMA)" == angle-artifact-v1 ]] || fail 'unexpected artifact schema'
[[ "$(manifest_value RUNTIME_ARTIFACT_SCHEMA)" == phase5-metal-family1-runtime-v1 ]] ||
  fail 'unexpected runtime artifact schema'
[[ "$(manifest_value RUNTIME_PROFILE)" == phase5-metal-family1-control-v1 ]] ||
  fail 'unexpected runtime profile'
[[ "$(manifest_value CHROME_VERSION)" == 156.0.8078.48 ]] || fail 'artifact is not for Chrome Stable 156.0.8078.48'
[[ "$(manifest_value CHROMIUM_REVISION)" == d0c02bfad08ec92a6ffcf989e53cd995e6381a4c ]] ||
  fail 'Chromium source revision does not match the Chrome Stable tag'
[[ "$(manifest_value ANGLE_REVISION)" == 3b89d84e9d59f75675ac4e2bef58fc068a9f0577 ]] ||
  fail 'ANGLE revision does not match the tagged Chrome Stable DEPS entry'
[[ "$(manifest_value ANGLE_EXPECTED_REVISION)" == "$(manifest_value ANGLE_REVISION)" ]] ||
  fail 'ANGLE expected and recorded revisions differ'
[[ "$(manifest_value ANGLE_ACTUAL_REVISION)" == "$(manifest_value ANGLE_REVISION)" ]] ||
  fail 'built ANGLE source revision differs from the Chromium DEPS pin'
[[ "$(manifest_value DEPOT_TOOLS_EXPECTED_REVISION)" == "$(manifest_value DEPOT_TOOLS_REVISION)" ]] ||
  fail 'depot_tools expected and recorded revisions differ'
[[ "$(manifest_value DEPOT_TOOLS_ACTUAL_REVISION)" == "$(manifest_value DEPOT_TOOLS_REVISION)" ]] ||
  fail 'built dependency checkout differs from its pinned revision'

patch_path=$(manifest_value RUNTIME_PATCH_PATH)
[[ "$patch_path" == patches/phase5-metal-family1-runtime.patch ]] || fail 'unexpected runtime patch path'
[[ "$patch_path" != /* && "$patch_path" != *..* ]] || fail 'runtime patch path is not repository-relative'
patch_sha=$(manifest_value RUNTIME_PATCH_SHA256)
[[ "$patch_sha" =~ ^[0-9a-f]{64}$ ]] || fail 'invalid runtime patch SHA-256'
[[ "$patch_sha" == dedac2c57daa69b72fe78bbde443f45d5a6cdfe128d4022049a35c0dbbf501b0 ]] ||
  fail 'runtime patch hash does not match the reviewed source patch'
check_sha256 "$artifact_dir/runtime-patch.diff" "$patch_sha" 'runtime patch provenance'
[[ "$(manifest_value RUNTIME_PATCH_APPLIED)" == true ]] || fail 'runtime patch was not recorded as applied'
[[ "$(manifest_value RUNTIME_PATCH_MODE)" == source-patch ]] || fail 'unexpected runtime patch mode'
grep -F 'ANGLE_PHASE5_ENABLE_METAL_FAMILY1' "$artifact_dir/runtime-patch.diff" >/dev/null ||
  fail 'explicit Family 1 runtime opt-in is missing from patch provenance'
[[ "$(manifest_value RUNTIME_OPT_IN)" == 'ANGLE_PHASE5_ENABLE_METAL_FAMILY1=1 --disable-angle-features=requireGpuFamily2' ]] ||
  fail 'runtime opt-in does not match the pinned source capabilities'
[[ "$(manifest_value TEST_ONLY_STUB)" == absent ]] || fail 'test-only stub presence was not rejected'
[[ "$(manifest_value RUNTIME_DEVICE_READY)" == false ]] || fail 'artifact is incorrectly marked device-ready'
[[ "$(manifest_value UNSIGNED_ARTIFACT)" == true ]] || fail 'artifact is not marked unsigned'

gn_args="$artifact_dir/args.gn"
[[ -f "$gn_args" && ! -L "$gn_args" ]] || fail 'GN args are missing or symlinked'
gn_args_sha=$(manifest_value GN_ARGS_SHA256)
[[ "$gn_args_sha" =~ ^[0-9a-f]{64}$ ]] || fail 'invalid GN args SHA-256'
check_sha256 "$gn_args" "$gn_args_sha" 'GN args'
grep -Fx 'target_cpu = "x64"' "$gn_args" >/dev/null || fail 'GN target is not x86_64'
grep -Fx 'mac_deployment_target = "13.0"' "$gn_args" >/dev/null ||
  fail 'GN deployment target does not match the build workflow'
grep -Fx 'mac_min_system_version = "13.0"' "$gn_args" >/dev/null ||
  fail 'GN minimum system version does not match its deployment target'
! grep -E 'angle_enable_metal_family1_test_stub|angle_build_tests[[:space:]]*=[[:space:]]*true|build_angle_deqp_tests[[:space:]]*=[[:space:]]*true' \
  "$gn_args" >/dev/null || fail 'GN args enable test-only build settings'

environment="$artifact_dir/build-environment.txt"
[[ -f "$environment" && ! -L "$environment" ]] || fail 'build environment record is missing or symlinked'
grep -Fx 'TARGET_ARCH=x86_64' "$environment" >/dev/null || fail 'build environment target is not x86_64'
grep -Fx 'MACOS_DEPLOYMENT_TARGET=13.0' "$environment" >/dev/null ||
  fail 'build environment deployment target is missing'
manifest_sha=$(shasum -a 256 "$manifest" | awk '{print $1}')
[[ "$(awk 'NR == 1 {print $1}' "$artifact_dir/ANGLE_RELEASE_MANIFEST.sha256")" == "$manifest_sha" ]] ||
  fail 'release manifest checksum mismatch'

for library in libEGL.dylib libGLESv2.dylib; do
  library_path="$artifact_dir/$library"
  [[ -f "$library_path" && ! -L "$library_path" ]] || fail "runtime library is missing or symlinked: $library"
  actual_architectures=$(lipo -archs "$library_path") || fail "$library architecture lookup failed"
  [[ "$actual_architectures" == x86_64 ]] ||
    fail "$library architectures are not exactly x86_64: $actual_architectures"

  load_commands=$(otool -l "$library_path") || fail "$library load command lookup failed"
  deployment_target=$(printf '%s\n' "$load_commands" | awk '
    /^[[:space:]]*cmd / {
      command = $2
      platform = ""
      next
    }
    command == "LC_BUILD_VERSION" && $1 == "platform" { platform = $2; next }
    command == "LC_BUILD_VERSION" && (platform == "MACOS" || platform == "1") && $1 == "minos" { print $2; exit }
    command == "LC_VERSION_MIN_MACOSX" && $1 == "version" { print $2; exit }
  ')
  [[ "$deployment_target" == 13.0 ]] ||
    fail "$library minimum macOS version is not 13.0: ${deployment_target:-missing}"

  key=LIBEGL_SHA256
  [[ "$library" == libGLESv2.dylib ]] && key=LIBGLESV2_SHA256
  expected_sha=$(manifest_value "$key")
  [[ "$expected_sha" =~ ^[0-9a-f]{64}$ ]] || fail "invalid $key"
  check_sha256 "$library_path" "$expected_sha" "$library"

  symbols=$(nm -gU "$library_path") || fail "$library exported symbol lookup failed"
  if [[ "$library" == libEGL.dylib ]]; then
    required_symbols=(eglGetProcAddress eglInitialize eglCreateContext)
  else
    required_symbols=(glDrawArrays glReadPixels)
  fi
  for symbol in "${required_symbols[@]}"; do
    grep -Eq "[[:space:]]_?${symbol}$" <<< "$symbols" ||
      fail "$library is missing required exported symbol: $symbol"
  done

  if details=$(codesign -dvvv "$library_path" 2>&1); then
    fail "$library is signed; Phase 5 runtime dylibs must remain unsigned"
  fi
  [[ "$details" == *'not signed'* ]] || fail "$library signature state could not be confirmed unsigned"
done

[[ "$(manifest_value ARTIFACT_NAME)" =~ ^angle-macos-x86_64-chrome-156\.0\.8078\.48-angle-3b89d84e-[0-9]+$ ]] ||
  fail 'unexpected artifact name'

printf '%s\n' 'phase5 runtime artifact verification passed'
