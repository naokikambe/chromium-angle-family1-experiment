#!/usr/bin/env bash
set -euo pipefail

workflow=${1:?workflow path}
base_patch=${2:?base runtime patch path}
experiment_patch=${3:?family1 experiment patch path}

test -f "$workflow"
test -f "$base_patch"
test -f "$experiment_patch"
experiment_patch_sha256=$(shasum -a 256 "$experiment_patch" | awk '{print $1}')
test "$experiment_patch_sha256" = b364519e8067d2f0dcb0ad3e41cb26ffc63cd40b70f53a8b37fb2a7cc4fab857
experiment_patch_paths=$(git apply --numstat "$experiment_patch" | awk '{print $3}' | LC_ALL=C sort)
test "$experiment_patch_paths" = src/common/apple_platform_utils.mm

grep -F 'family1_experiment:' "$workflow" >/dev/null
grep -F 'family1_experiment_patch_sha256:' "$workflow" >/dev/null
grep -F 'FAMILY1_EXPERIMENT_PATCH_PATH: patches/phase5-metal-family1-family1-experiment.patch' "$workflow" >/dev/null
grep -F 'FAMILY1_EXPERIMENT_PATCH_SHA256:' "$workflow" >/dev/null
grep -F 'if [[ "$FAMILY1_EXPERIMENT" == true ]]; then' "$workflow" >/dev/null
grep -F 'git apply --unidiff-zero --check -- "$GITHUB_WORKSPACE/$FAMILY1_EXPERIMENT_PATCH_PATH"' "$workflow" >/dev/null
grep -F 'git apply --unidiff-zero -- "$GITHUB_WORKSPACE/$FAMILY1_EXPERIMENT_PATCH_PATH"' "$workflow" >/dev/null
grep -F 'FAMILY1_EXPERIMENT=true' "$workflow" >/dev/null
grep -F 'FAMILY1_EXPERIMENT_PATCH_PATH=%s' "$workflow" >/dev/null
grep -F 'FAMILY1_EXPERIMENT_COMPILE_TIME_DEFINE=ANGLE_PHASE5_METAL_FAMILY1_EXPERIMENT' "$workflow" >/dev/null
grep -F 'UNSUPPORTED_HARDWARE_OVERRIDE=true' "$workflow" >/dev/null
grep -F 'phase5-metal-family1-family1-experiment-v1' "$workflow" >/dev/null
grep -F 'phase5-metal-family1-family1-experiment-' "$workflow" >/dev/null
grep -F 'family1-experiment-patch.diff' "$workflow" >/dev/null
grep -F 'scripts/verify-phase5-runtime-artifact.sh' "$workflow" >/dev/null
! grep -E '(^|[^A-Za-z])(codesign|xattr|security|sudo|git push|force-push|KOOV|--user-data-dir|Google Chrome|open -a)' "$workflow" >/dev/null

grep -F '#define ANGLE_PHASE5_METAL_FAMILY1_EXPERIMENT 1' "$experiment_patch" >/dev/null
grep -F 'family1_experiment_availability=bypass' "$experiment_patch" >/dev/null
grep -F 'return true;' "$experiment_patch" >/dev/null
! grep -E 'getenv[[:space:]]*\(|setenv[[:space:]]*\(|unsetenv[[:space:]]*\(|argv\[|argc|DYLD_' "$experiment_patch" >/dev/null
! grep -E 'ANGLE_ENABLE_METAL_FAMILY1_TEST_STUB|DisplayMtlFamily1Test|ANGLE_MetalFamily1Test' "$experiment_patch" >/dev/null

printf '%s\n' 'phase5-metal-family1-family1-experiment-static: success'
