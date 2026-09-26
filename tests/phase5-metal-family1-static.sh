#!/usr/bin/env bash
set -euo pipefail

workflow=${1:?workflow path}
patch=${2:?patch path}

test -f "$workflow"
test -f "$patch"
test "$(shasum -a 256 "$patch" | awk '{print $1}')" = \
  deb591ecd2dd2e897815dfd2c3b13982eaa212e08a9382bc7d65bb493b4e7d76
grep -F 'angle_enable_metal_family1_test_stub = false' "$patch" >/dev/null
grep -F 'ANGLE_ENABLE_METAL_FAMILY1_TEST_STUB' "$patch" >/dev/null
grep -F 'thread_local Family1TestState' "$patch" >/dev/null
grep -F 'if (!mCmdQueue)' "$patch" >/dev/null
grep -F 'DisplayMtlFamily1Test' "$patch" >/dev/null
! grep -Ei 'getenv|command.line|--use-angle|--use-gl' "$patch" >/dev/null

grep -F 'workflow_dispatch:' "$workflow" >/dev/null
! grep -E '^[[:space:]]*(push|pull_request|pull_request_target):' "$workflow" >/dev/null
grep -F 'runs-on: macos-15-intel' "$workflow" >/dev/null
grep -F 'timeout-minutes: 60' "$workflow" >/dev/null
grep -F 'timeout-minutes: 45' "$workflow" >/dev/null
grep -F 'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683' "$workflow" >/dev/null
grep -F 'actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02' "$workflow" >/dev/null
grep -F 'persist-credentials: false' "$workflow" >/dev/null
grep -F 'permissions:' "$workflow" >/dev/null
grep -F 'contents: read' "$workflow" >/dev/null
grep -F 'phase5-metal-family1-test-stub.patch' "$workflow" >/dev/null
grep -F 'deb591ecd2dd2e897815dfd2c3b13982eaa212e08a9382bc7d65bb493b4e7d76' "$workflow" >/dev/null
grep -F '1ff8799c596d4fc9acea28343610b1f33650a6fa' "$workflow" >/dev/null
grep -F 'phase5-metal-family1-test-stub-v1' "$workflow" >/dev/null
grep -F 'angle-metal-family1-test-stub-' "$workflow" >/dev/null
grep -F 'angle_enable_metal_family1_test_stub = true' "$workflow" >/dev/null
grep -F 'angle_build_tests = true' "$workflow" >/dev/null
grep -F 'ninja -C out/Phase5 angle_unittests' "$workflow" >/dev/null
grep -F -- '--gtest_filter=DisplayMtlFamily1Test.*' "$workflow" >/dev/null
grep -F 'test-result.txt' "$workflow" >/dev/null
grep -F 'manifest.sha256' "$workflow" >/dev/null
grep -F 'artifact.sha256' "$workflow" >/dev/null
grep -F 'GN_ARGS_SHA256=' "$workflow" >/dev/null
! grep -E 'Chrome|chrome|angle-artifact-v1|libEGL\.dylib|libGLESv2\.dylib' "$workflow" >/dev/null
! grep -E '(^|[^A-Za-z])(sudo|codesign|xattr|security|gh |git push|force-push|secrets\.|id-token|contents: write)([^A-Za-z]|$)' "$workflow" >/dev/null

for path in \
  gni/angle.gni \
  src/libANGLE/renderer/metal/BUILD.gn \
  src/libANGLE/renderer/metal/DisplayMtl.h \
  src/libANGLE/renderer/metal/DisplayMtl.mm \
  src/tests/angle_unittests.gni \
  src/libANGLE/renderer/metal/DisplayMtlFamily1Test.mm; do
  grep -F "$path" "$workflow" >/dev/null
done

printf '%s\n' 'phase5-metal-family1-static: success'
