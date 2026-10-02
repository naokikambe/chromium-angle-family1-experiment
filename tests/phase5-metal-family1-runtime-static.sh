#!/usr/bin/env bash
set -euo pipefail

workflow=${1:?workflow path}
patch=${2:?patch path}

test -f "$workflow"
test -f "$patch"
patch_sha256=$(shasum -a 256 "$patch" | awk '{print $1}')
test "$patch_sha256" = 6abc915e79513ceae887ef4e2a91ae65d40878edc87b0bf77c053adfd5a13e5f
patch_paths=$(git apply --numstat "$patch" | awk '{print $3}' | LC_ALL=C sort)
expected_patch_paths=$(printf '%s\n' \
  src/common/apple_platform_utils.mm \
  src/libANGLE/Context.cpp \
  src/libANGLE/Display.cpp \
  src/libANGLE/renderer/metal/DisplayMtl.mm \
  src/libANGLE/validationEGL.cpp \
  src/libEGL/libEGL_autogen.cpp \
  src/libGLESv2/entry_points_egl_autogen.cpp)
test "$patch_paths" = "$expected_patch_paths"
grep -F 'phase5-metal-family1-runtime.patch' "$workflow" >/dev/null
grep -F "$patch_sha256" "$workflow" >/dev/null
grep -F 'e12217f3e133cb1029b050d893b1806d141483be' "$workflow" >/dev/null
grep -F '154.0.8037.97' "$workflow" >/dev/null
grep -F '802a8704ca940b633b731493ee192e0661eb8cdd' "$workflow" >/dev/null
grep -F '154.0.8037.92' "$workflow" >/dev/null
grep -F 'cft_compatibility:' "$workflow" >/dev/null
grep -F 'CFT_COMPATIBILITY:' "$workflow" >/dev/null
grep -F 'unsupported Chrome/ANGLE input pair' "$workflow" >/dev/null
grep -F 'gitiles_base=' "$workflow" >/dev/null
grep -F 'base64 -D' "$workflow" >/dev/null
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
test "$(grep -Fc 'src/libANGLE/Context.cpp' "$workflow")" -eq 1
test "$(grep -Fc 'src/libANGLE/Display.cpp' "$workflow")" -eq 1
test "$(grep -Fc 'src/libANGLE/validationEGL.cpp' "$workflow")" -eq 1
test "$(grep -Fc 'src/libEGL/libEGL_autogen.cpp' "$workflow")" -eq 1
test "$(grep -Fc 'src/libGLESv2/entry_points_egl_autogen.cpp' "$workflow")" -eq 1
test "$(grep -Fc 'src/libANGLE/renderer/metal/DisplayMtl.mm' "$workflow")" -eq 1
grep -F 'expected_source_paths=$(printf' "$workflow" >/dev/null
grep -F "'src/common/apple_platform_utils.mm'" "$workflow" >/dev/null
grep -F "'src/libANGLE/Context.cpp'" "$workflow" >/dev/null
grep -F "'src/libANGLE/renderer/metal/DisplayMtl.mm'" "$workflow" >/dev/null
grep -F '"$expected_source_paths"' "$workflow" >/dev/null
! grep -F 'angle_enable_metal_family1_test_stub' "$workflow" >/dev/null
! grep -E '(^|[^A-Za-z])(codesign|xattr|security|sudo|git push|force-push|KOOV|--user-data-dir|Google Chrome|open -a)([^A-Za-z]|$)' "$workflow" >/dev/null
! grep -E 'ANGLE_MetalFamily1Test|DisplayMtlFamily1Test|ANGLE_ENABLE_METAL_FAMILY1_TEST_STUB' "$patch" >/dev/null
grep -F '[ANGLE_PHASE5_LOAD] libGLESv2_loaded' "$patch" >/dev/null
grep -F '[ANGLE_PHASE5_LOAD] libEGL_loaded' "$patch" >/dev/null
grep -F 'eglInitialize_return_failure' "$patch" >/dev/null
grep -F 'eglGetError_return=0x%04x' "$patch" >/dev/null
grep -F 'pragma clang diagnostic ignored "-Wglobal-constructors"' "$patch" >/dev/null
grep -F 'display_initialize_backend_failure id=' "$patch" >/dev/null
grep -F 'display_initialize_backend_success' "$patch" >/dev/null
grep -F 'display_initialize_begin' "$patch" >/dev/null
grep -F 'eglChooseConfig_return success=%s num_config=%d' "$patch" >/dev/null
grep -F 'eglGetConfigAttrib attribute=0x%04x success=%s value=%d' "$patch" >/dev/null
grep -F 'eglCreateContext_config=no_config' "$patch" >/dev/null
grep -F 'eglCreateContext_attribute key=0x%04x value=%d' "$patch" >/dev/null
grep -F 'context_version_check requested=%u.%u max_supported=%u.%u' "$patch" >/dev/null
grep -F 'context_version_rejected reason=max_supported_version' "$patch" >/dev/null
grep -F 'context_error code=EGL_BAD_ATTRIBUTE attribute=0x3098 value=%u' "$patch" >/dev/null
grep -F 'context_initialize_error code=0x%04x id=%d message=%s' "$patch" >/dev/null
grep -F 'context_initialize_success' "$patch" >/dev/null
grep -F 'eglCreateContext_validation_enabled=%s' "$patch" >/dev/null
grep -F 'context_attribute_validation key=0x%04x result=%s' "$patch" >/dev/null
grep -F 'context_attribute_value_validation key=0x%04x value=%d result=%s' "$patch" >/dev/null
grep -F 'max_es_version_gpu_family4_or1=' "$patch" >/dev/null
grep -F 'max_es_version=2.0' "$patch" >/dev/null
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
