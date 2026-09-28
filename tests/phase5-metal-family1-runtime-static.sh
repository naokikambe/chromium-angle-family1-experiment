#!/usr/bin/env bash
set -euo pipefail

workflow=${1:?workflow path}
patch=${2:?patch path}

test -f "$workflow"
test -f "$patch"
test "$(shasum -a 256 "$patch" | awk '{print $1}')" = \
  07d7e80d8ce1099cb3d9d3ad5654eabd39b3d33776932ad28e3d76deaf6d4070
git apply --numstat "$patch" >/dev/null
grep -F 'phase5-metal-family1-runtime.patch' "$workflow" >/dev/null
grep -F '07d7e80d8ce1099cb3d9d3ad5654eabd39b3d33776932ad28e3d76deaf6d4070' "$workflow" >/dev/null
grep -F '1ff8799c596d4fc9acea28343610b1f33650a6fa' "$workflow" >/dev/null
grep -F '154.0.8037.57' "$workflow" >/dev/null
grep -F 'workflow_dispatch:' "$workflow" >/dev/null
! grep -E '^[[:space:]]*(push|pull_request|pull_request_target):' "$workflow" >/dev/null
grep -F 'runs-on: macos-15-intel' "$workflow" >/dev/null
grep -F 'timeout-minutes: 120' "$workflow" >/dev/null
grep -F 'timeout-minutes: 25' "$workflow" >/dev/null
grep -F 'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683' "$workflow" >/dev/null
grep -F 'actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02' "$workflow" >/dev/null
grep -F 'persist-credentials: false' "$workflow" >/dev/null
grep -F 'permissions:' "$workflow" >/dev/null
grep -F 'contents: read' "$workflow" >/dev/null
grep -F 'DEPOT_TOOLS_UPDATE: "0"' "$workflow" >/dev/null
grep -F 'git apply --unidiff-zero --check' "$workflow" >/dev/null
grep -F 'angle_build_tests = false' "$workflow" >/dev/null
grep -F 'build_angle_deqp_tests = false' "$workflow" >/dev/null
grep -F 'gn desc out/Phase5 //:libEGL sources' "$workflow" >/dev/null
grep -F 'gn desc out/Phase5 //:libGLESv2 sources' "$workflow" >/dev/null
grep -F 'ninja -C out/Phase5 libEGL' "$workflow" >/dev/null
grep -F 'ninja -C out/Phase5 libGLESv2' "$workflow" >/dev/null
grep -F 'scripts/verify-artifact.sh' "$workflow" >/dev/null
grep -F 'scripts/verify-phase5-runtime-artifact.sh' "$workflow" >/dev/null
grep -F 'RUNTIME_ARTIFACT_SCHEMA=phase5-metal-family1-runtime-v1' "$workflow" >/dev/null
grep -F 'RUNTIME_PATCH_APPLIED=true' "$workflow" >/dev/null
grep -F 'RUNTIME_DEVICE_READY=false' "$workflow" >/dev/null
grep -F 'if: success()' "$workflow" >/dev/null
grep -F 'if: always()' "$workflow" >/dev/null
grep -F 'phase5-metal-family1-runtime-diagnostics-' "$workflow" >/dev/null
! grep -F 'angle_enable_metal_family1_test_stub' "$workflow" >/dev/null
! grep -E '(^|[^A-Za-z])(codesign|xattr|security|sudo|git push|force-push|KOOV|--user-data-dir|Google Chrome|open -a)([^A-Za-z]|$)' "$workflow" >/dev/null
! grep -E 'ANGLE_MetalFamily1Test|DisplayMtlFamily1Test|ANGLE_ENABLE_METAL_FAMILY1_TEST_STUB' "$patch" >/dev/null

printf '%s\n' 'phase5-metal-family1-runtime-static: success'
