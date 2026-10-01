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

manifest_value_optional() {
  local key=$1 matches count
  matches=$(grep -E "^${key}=" "$manifest" || true)
  count=$(printf '%s\n' "$matches" | sed '/^$/d' | wc -l | tr -d ' ')
  case "$count" in
    0) return 0 ;;
    1) printf '%s\n' "${matches#*=}" ;;
    *) fail "invalid or duplicate optional manifest key: $key" ;;
  esac
}

runtime_schema=$(manifest_value RUNTIME_ARTIFACT_SCHEMA)
runtime_profile=$(manifest_value RUNTIME_PROFILE)
family1_experiment=$(manifest_value_optional FAMILY1_EXPERIMENT)
family1_experiment=${family1_experiment:-false}
if [[ "$family1_experiment" == true ]]; then
  [[ "$runtime_schema" == phase5-metal-family1-family1-experiment-v1 ]] ||
    fail "unexpected Family 1 experiment artifact schema: $runtime_schema"
  [[ "$runtime_profile" == phase5-metal-family1-family1-experiment-v1 ]] ||
    fail "unexpected Family 1 experiment runtime profile: $runtime_profile"
else
  [[ "$family1_experiment" == false ]] || fail 'invalid FAMILY1_EXPERIMENT value'
  [[ "$runtime_schema" == phase5-metal-family1-runtime-v1 ]] ||
    fail "unexpected runtime artifact schema: $runtime_schema"
  [[ "$runtime_profile" == phase5-metal-family1-control-v1 ]] ||
    fail "unexpected runtime profile: $runtime_profile"
fi

patch_mode=$(manifest_value RUNTIME_PATCH_MODE)
[[ "$patch_mode" == source-patch ]] || fail "unexpected runtime patch mode: $patch_mode"

patch_path=$(manifest_value RUNTIME_PATCH_PATH)
[[ "$patch_path" == patches/phase5-metal-family1-runtime.patch ]] ||
  fail "unexpected runtime patch path: $patch_path"
[[ "$patch_path" != /* && "$patch_path" != *..* ]] || fail 'runtime patch path is not repository-relative'

patch_sha=$(manifest_value RUNTIME_PATCH_SHA256)
[[ "$patch_sha" =~ ^[0-9a-f]{64}$ ]] || fail 'invalid runtime patch SHA-256'
[[ -f "$artifact_dir/runtime-patch.diff" && ! -L "$artifact_dir/runtime-patch.diff" ]] ||
  fail 'runtime patch provenance file is missing or symlinked'
[[ "$(shasum -a 256 "$artifact_dir/runtime-patch.diff" | awk '{print $1}')" == "$patch_sha" ]] ||
  fail 'runtime patch provenance hash mismatch'

if [[ "$family1_experiment" == true ]]; then
  experiment_patch_path=$(manifest_value FAMILY1_EXPERIMENT_PATCH_PATH)
  [[ "$experiment_patch_path" == patches/phase5-metal-family1-family1-experiment.patch ]] ||
    fail "unexpected Family 1 experiment patch path: $experiment_patch_path"
  [[ "$experiment_patch_path" != /* && "$experiment_patch_path" != *..* ]] ||
    fail 'Family 1 experiment patch path is not repository-relative'
  experiment_patch_sha=$(manifest_value FAMILY1_EXPERIMENT_PATCH_SHA256)
  [[ "$experiment_patch_sha" =~ ^[0-9a-f]{64}$ ]] ||
    fail 'invalid Family 1 experiment patch SHA-256'
  [[ -f "$artifact_dir/family1-experiment-patch.diff" && ! -L "$artifact_dir/family1-experiment-patch.diff" ]] ||
    fail 'Family 1 experiment patch provenance file is missing or symlinked'
  [[ "$(shasum -a 256 "$artifact_dir/family1-experiment-patch.diff" | awk '{print $1}')" == "$experiment_patch_sha" ]] ||
    fail 'Family 1 experiment patch provenance hash mismatch'
  grep -F '#define ANGLE_PHASE5_METAL_FAMILY1_EXPERIMENT 1' \
    "$artifact_dir/family1-experiment-patch.diff" >/dev/null ||
    fail 'Family 1 experiment compile-time define is missing'
  [[ "$(manifest_value FAMILY1_EXPERIMENT_COMPILE_TIME_DEFINE)" == ANGLE_PHASE5_METAL_FAMILY1_EXPERIMENT ]] ||
    fail 'Family 1 experiment compile-time define provenance is missing'
  [[ "$(manifest_value UNSUPPORTED_HARDWARE_OVERRIDE)" == true ]] ||
    fail 'unsupported hardware override was not recorded'
else
  [[ "$(manifest_value_optional UNSUPPORTED_HARDWARE_OVERRIDE)" != true ]] ||
    fail 'base runtime artifact unexpectedly enables unsupported hardware override'
fi

runtime_opt_in=$(manifest_value RUNTIME_OPT_IN)
[[ "$runtime_opt_in" == '--disable-angle-features=requireGpuFamily2,requireMsl21' ]] ||
  fail 'runtime opt-in does not match the approved feature override'
[[ "$(manifest_value RUNTIME_PATCH_APPLIED)" == true ]] || fail 'runtime patch was not recorded as applied'
[[ "$(manifest_value TEST_ONLY_STUB)" == absent ]] || fail 'test-only stub presence was not rejected'
[[ "$(manifest_value RUNTIME_DEVICE_READY)" == false ]] || fail 'artifact is incorrectly marked device-ready'

for library in libEGL.dylib libGLESv2.dylib; do
  library_path="$artifact_dir/$library"
  [[ -f "$library_path" && ! -L "$library_path" ]] || fail "missing runtime library: $library"
  symbols_path="$artifact_dir/$library.phase5-symbols.txt"
  nm -gU "$library_path" > "$symbols_path"
  if grep -E 'ANGLE_MetalFamily1Test|DisplayMtlFamily1Test|ANGLE_ENABLE_METAL_FAMILY1_TEST_STUB' "$symbols_path" >/dev/null; then
    fail "$library contains test-only Family 1 symbols"
  fi
done

args_path="$artifact_dir/args.gn"
[[ -f "$args_path" && ! -L "$args_path" ]] || fail 'GN args are missing or symlinked'
! grep -E 'angle_enable_metal_family1_test_stub|angle_build_tests[[:space:]]*=[[:space:]]*true' "$args_path" >/dev/null ||
  fail 'runtime artifact GN args enable test-only build settings'

printf '%s\n' 'phase5 runtime artifact verification passed'
