#!/usr/bin/env bash
set -euo pipefail

workflow=${1:?workflow path}
patch=${2:?patch path}

test -f "$workflow"
test -f "$patch"
patch_sha256=$(shasum -a 256 "$patch" | awk '{print $1}')
test "$patch_sha256" = 728c6bc8acc1009f583b5739a9d5058e7707e81cc90d8d2a4ecda6a3958ceb20
patch_paths=$(git apply --numstat "$patch" | awk '{print $3}' | LC_ALL=C sort)
expected_patch_paths=$(printf '%s\n' \
  src/common/apple_platform_utils.mm \
  src/libANGLE/renderer/metal/DisplayMtl.mm)
test "$patch_paths" = "$expected_patch_paths"
grep -F 'phase5-metal-family1-runtime.patch' "$workflow" >/dev/null
grep -F "$patch_sha256" "$workflow" >/dev/null
grep -F '1ff8799c596d4fc9acea28343610b1f33650a6fa' "$workflow" >/dev/null
grep -F '154.0.8037.59' "$workflow" >/dev/null
grep -F 'workflow_dispatch:' "$workflow" >/dev/null
! grep -E '^[[:space:]]*(push|pull_request|pull_request_target):' "$workflow" >/dev/null
grep -F 'runs-on: macos-15-intel' "$workflow" >/dev/null
grep -F 'timeout-minutes: 120' "$workflow" >/dev/null
grep -A4 -F -- '- name: Build libEGL' "$workflow" | grep -F 'timeout-minutes: 40' >/dev/null
grep -A2 -F -- '- name: Build libGLESv2' "$workflow" | grep -F 'timeout-minutes: 25' >/dev/null
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
test "$(grep -Fc 'src/common/apple_platform_utils.mm' "$workflow")" -eq 1
test "$(grep -Fc 'src/libANGLE/renderer/metal/DisplayMtl.mm' "$workflow")" -eq 1
grep -F 'expected_source_paths=$(printf' "$workflow" >/dev/null
grep -F "'src/common/apple_platform_utils.mm'" "$workflow" >/dev/null
grep -F "'src/libANGLE/renderer/metal/DisplayMtl.mm'" "$workflow" >/dev/null
grep -F '"$expected_source_paths"' "$workflow" >/dev/null
! grep -F 'angle_enable_metal_family1_test_stub' "$workflow" >/dev/null
! grep -E '(^|[^A-Za-z])(codesign|xattr|security|sudo|git push|force-push|KOOV|--user-data-dir|Google Chrome|open -a)([^A-Za-z]|$)' "$workflow" >/dev/null
! grep -E 'ANGLE_MetalFamily1Test|DisplayMtlFamily1Test|ANGLE_ENABLE_METAL_FAMILY1_TEST_STUB' "$patch" >/dev/null
grep -F '[ANGLE_PHASE5_LOAD] libGLESv2_loaded' "$patch" >/dev/null
grep -F '+__attribute__((constructor)) static void Phase5LogMetalLibraryLoaded()' "$patch" >/dev/null
! grep -E '^\+.*INFO\(\)' "$patch" >/dev/null
grep -E '^\+.*ERR\(\)' "$patch" >/dev/null

for marker in \
  'machine_model_gate=pass' \
  'machine_model_gate=reject' \
  'default_metal_device=present' \
  'default_metal_device=missing' \
  'mac_gpu_family2_supported=' \
  'mac_catalyst_gpu_family2_supported=' \
  'gpu_family_requirement=not_applicable' \
  'renderer_availability=' \
  'display_renderer_availability=' \
  'metal_device_selection=success' \
  'metal_device_selection=failure' \
  'require_gpu_family2 enabled=' \
  'require_gpu_family2 family_check=checked supported=' \
  'require_gpu_family2 family_check=skipped' \
  'nvidia_gate enabled=' \
  'command_queue=' \
  'format_table=begin' \
  'format_table=success' \
  'shader_library=begin' \
  'shader_library=success' \
  'render_utils=begin' \
  'render_utils=success' \
  'display_initialize_result='; do
  grep -F "[ANGLE_PHASE5_METAL_INIT] $marker" "$patch" >/dev/null
done

test "$(grep -Ec '^\+.*supportsEitherGPUFamily\(1, 2\)' "$patch")" -eq 1
test "$(grep -Ec '^\+.*supportsFamily:MTLGPUFamily(Mac2|MacCatalyst2)' "$patch")" -eq 2
grep -F '+            supportsRequiredGpuFamily = supportsEitherGPUFamily(1, 2);' "$patch" >/dev/null
grep -F '+        if (requireGpuFamily2Enabled && !supportsRequiredGpuFamily)' "$patch" >/dev/null
grep -F '+        if (disableMetalOnNvidiaEnabled && isNvidiaDevice)' "$patch" >/dev/null
grep -F '         ANGLE_TRY(mFormatTable.initialize(this));' "$patch" >/dev/null
grep -F '         ANGLE_TRY(initializeShaderLibrary());' "$patch" >/dev/null
awk '
  /^         mCmdQueue = angle::adoptObjCPtr\(\[mMetalDevice newCommandQueue\]\);$/ { assignment = NR }
  /^\+        if \(!mCmdQueue\)$/ { guard = NR }
  /^\+            return angle::Result::Stop;$/ && guard { stop = NR }
  /^         ANGLE_TRY\(mFormatTable\.initialize\(this\)\);$/ { format = NR }
  END { exit !(assignment && guard > assignment && stop > guard && format > stop) }
' "$patch"
! grep -E '^\+.*(ANGLE_ENABLE_METAL_FAMILY1_TEST_STUB|DisplayMtlFamily1Test|ANGLE_MetalFamily1Test|--[[:alnum:]-]+|getenv[[:space:]]*\(|setenv[[:space:]]*\(|unsetenv[[:space:]]*\(|argv\[|argc|family.?bypass|force.?family)' "$patch" >/dev/null
! grep -E '^\+.*return (true|angle::Result::Continue);' "$patch" >/dev/null

printf '%s\n' 'phase5-metal-family1-runtime-static: success'
