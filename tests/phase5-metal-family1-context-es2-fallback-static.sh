#!/usr/bin/env bash
set -euo pipefail

workflow=${1:?workflow path}
patch=${2:?context fallback patch path}

test -f "$workflow"
test -f "$patch"
test "$(shasum -a 256 "$patch" | awk '{print $1}')" = \
  7bd8a40eaa6311c4ca37ebd68c19ab3d9822b936000e38dbadea70b92667a014
test "$(git apply --numstat "$patch" | awk '{print $3}')" = src/libANGLE/Context.cpp

grep -F 'context_es2_fallback_experiment:' "$workflow" >/dev/null
grep -F 'context_es2_fallback_patch_sha256:' "$workflow" >/dev/null
grep -F 'CONTEXT_ES2_FALLBACK_EXPERIMENT:' "$workflow" >/dev/null
grep -F 'CONTEXT_ES2_FALLBACK_PATCH_PATH: patches/phase5-metal-family1-context-es2-fallback.patch' \
  "$workflow" >/dev/null
grep -F 'CONTEXT_ES2_FALLBACK_PATCH_SHA256:' "$workflow" >/dev/null
grep -F 'context_es2_fallback_experiment: ${{ inputs.run_context_es2_fallback_experiment }}' \
  .github/workflows/phase5-metal-family1.yml >/dev/null
grep -F 'context_es2_fallback_patch_sha256: ${{ inputs.context_es2_fallback_patch_sha256 }}' \
  .github/workflows/phase5-metal-family1.yml >/dev/null
grep -F 'git apply --unidiff-zero --check -- "$GITHUB_WORKSPACE/$CONTEXT_ES2_FALLBACK_PATCH_PATH"' \
  "$workflow" >/dev/null
grep -F 'CONTEXT_ES2_FALLBACK_COMPILE_TIME_DEFINE=ANGLE_PHASE5_METAL_FAMILY1_ES2_FALLBACK_EXPERIMENT' \
  "$workflow" >/dev/null
grep -F 'context-es2-fallback-patch.diff' "$workflow" >/dev/null
grep -F 'family1_es3_to_es2_fallback' "$patch" >/dev/null
grep -F '#define ANGLE_PHASE5_METAL_FAMILY1_ES2_FALLBACK_EXPERIMENT 1' "$patch" >/dev/null
grep -F '!GetWebGLContext(attribs)' "$patch" >/dev/null
grep -F 'return maxSupportedVersion;' "$patch" >/dev/null
! grep -E '(^|[^A-Za-z])(codesign|xattr|security|sudo|git push|force-push|KOOV|Google Chrome|open -a)' \
  "$workflow" "$patch" >/dev/null

printf '%s\n' 'phase5-metal-family1-context-es2-fallback-static: success'
