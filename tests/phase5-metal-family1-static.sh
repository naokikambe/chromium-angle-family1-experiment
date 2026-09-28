#!/usr/bin/env bash
set -euo pipefail

workflow=${1:?workflow path}
patch=${2:?patch path}

test -f "$workflow"
test -f "$patch"
test "$(shasum -a 256 "$patch" | awk '{print $1}')" = \
  f318c2a4f57a3012ec61ff992a974479ce136b441448019e1bff02e0872f2181
grep -F 'angle_enable_metal_family1_test_stub = false' "$patch" >/dev/null
grep -F 'ANGLE_ENABLE_METAL_FAMILY1_TEST_STUB' "$patch" >/dev/null
grep -F 'thread_local Family1TestState' "$patch" >/dev/null
grep -F 'if (!mCmdQueue)' "$patch" >/dev/null
grep -F 'if (mCmdQueue.valid())' "$patch" >/dev/null
grep -F 'DisplayMtlFamily1Test' "$patch" >/dev/null
grep -F '#define EGL_EGL_PROTOTYPES 1' "$patch" >/dev/null
grep -F 'angle_metal_family1_test_stub' "$patch" >/dev/null
grep -F '"$angle_root:libEGL"' "$patch" >/dev/null
grep -F 'data_deps = [' "$patch" >/dev/null
grep -F '"$angle_root:libEGL"' "$patch" >/dev/null
grep -F '"$angle_root:libGLESv2"' "$patch" >/dev/null
! grep -F 'data_deps = [ "$angle_root:angle" ]' "$patch" >/dev/null
grep -F 'ANGLE_MetalFamily1TestGetSnapshot' "$patch" >/dev/null
grep -F 'DisplayMtlFamily1TestBridge.mm' "$patch" >/dev/null
grep -F 'defines += [ "ANGLE_ENABLE_METAL_FAMILY1_TEST_STUB" ]' "$patch" >/dev/null
grep -F 'constexpr const char *kDisabledFeatures' "$patch" >/dev/null
! grep -F 'reinterpret_cast<EGLAttrib>(disabledFeatures)' "$patch" >/dev/null
! sed -n '/^+void ExpectForcedStop/,/^+}  \/\/ namespace/p' "$patch" | grep -F '+    eglTerminate(display);' >/dev/null
test "$(sed -n '/^diff --git a\/src\/libANGLE\/renderer\/metal\/DisplayMtlFamily1Test.mm/,/^diff --git /p' "$patch" | grep -F '+}  // namespace' | wc -l | tr -d ' ')" -eq 1
! grep -Ei 'getenv|command.line|--use-angle|--use-gl' "$patch" >/dev/null

grep -F 'workflow_dispatch:' "$workflow" >/dev/null
grep -F 'name: GN configuration preflight' "$workflow" >/dev/null
test "$(grep -c 'gn gen out/Phase5' "$workflow")" -eq 1
grep -F 'gn desc out/Phase5 //:libGLESv2 configs' "$workflow" >/dev/null
grep -F "grep -F '//:internal_config'" "$workflow" >/dev/null
grep -F 'libGLESv2 configs' "$workflow" >/dev/null
! grep -E '^[[:space:]]*(push|pull_request|pull_request_target):' "$workflow" >/dev/null
grep -F 'runs-on: macos-15-intel' "$workflow" >/dev/null
grep -F 'timeout-minutes: 60' "$workflow" >/dev/null
grep -F 'timeout-minutes: 45' "$workflow" >/dev/null
grep -F 'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683' "$workflow" >/dev/null
grep -F 'actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02' "$workflow" >/dev/null
grep -F 'persist-credentials: false' "$workflow" >/dev/null
grep -F 'permissions:' "$workflow" >/dev/null
grep -F 'contents: read' "$workflow" >/dev/null
grep -F 'DEPOT_TOOLS_UPDATE: "0"' "$workflow" >/dev/null
grep -F 'export PATH="$DEPOT_TOOLS_ROOT:$PATH"' "$workflow" >/dev/null
grep -F 'phase5-metal-family1-test-stub.patch' "$workflow" >/dev/null
grep -F 'f318c2a4f57a3012ec61ff992a974479ce136b441448019e1bff02e0872f2181' "$workflow" >/dev/null
grep -F 'apply --unidiff-zero --check' "$workflow" >/dev/null
grep -F '1ff8799c596d4fc9acea28343610b1f33650a6fa' "$workflow" >/dev/null
grep -F 'phase5-metal-family1-test-stub-v1' "$workflow" >/dev/null
grep -F 'angle-metal-family1-test-stub-' "$workflow" >/dev/null
grep -F 'angle_enable_metal_family1_test_stub = true' "$workflow" >/dev/null
grep -F 'angle_build_tests = true' "$workflow" >/dev/null
grep -F 'ninja -C out/Phase5 angle_metal_family1_test_stub' "$workflow" >/dev/null
grep -F '(cd out/Phase5 && ./angle_metal_family1_test_stub --gtest_filter=DisplayMtlFamily1Test.*)' "$workflow" >/dev/null
grep -F 'gn desc out/Phase5 //src/tests:angle_metal_family1_test_stub sources' "$workflow" >/dev/null
grep -F 'gn desc out/Phase5 //src/libANGLE/renderer/metal:angle_metal_backend sources' "$workflow" >/dev/null
grep -F 'gn desc out/Phase5 //src/libANGLE/renderer/metal:angle_metal_backend defines' "$workflow" >/dev/null
grep -F 'bridge-gn-desc.log' "$workflow" >/dev/null
grep -F 'DisplayMtlFamily1TestBridge.mm' "$workflow" >/dev/null
grep -F "sed -n '/--- stub target sources ---/,/--- metal backend sources ---/p'" "$workflow" >/dev/null
grep -F "sed -n '/--- metal backend sources ---/,/--- metal backend defines ---/p'" "$workflow" >/dev/null
grep -F "sed -n '/--- metal backend defines ---/,/--- libGLESv2 configs ---/p'" "$workflow" >/dev/null
grep -F 'bridge_object=obj/src/libANGLE/renderer/metal/angle_metal_backend/DisplayMtlFamily1TestBridge.o' "$workflow" >/dev/null
grep -F 'ninja -C out/Phase5 "$bridge_object"' "$workflow" >/dev/null
grep -F 'nm -gU' "$workflow" >/dev/null
grep -F 'ANGLE_METAL_FAMILY1_TEST_EXPORT' "$patch" >/dev/null
grep -F 'metal_family1_test_libglesv2_export_config' "$patch" >/dev/null
grep -F 'configs += [ ":metal_family1_test_libglesv2_export_config" ]' "$patch" >/dev/null
grep -F 'ninja -C out/Phase5 libEGL' "$workflow" >/dev/null
grep -F 'ninja -C out/Phase5 libGLESv2' "$workflow" >/dev/null
grep -F 'gn desc out/Phase5 //:libGLESv2 outputs' "$workflow" >/dev/null
grep -F 'libglesv2-outputs.log' "$workflow" >/dev/null
grep -F 'libglesv2-nm.log' "$workflow" >/dev/null
grep -F 'libglesv2-symbol-status.txt' "$workflow" >/dev/null
grep -F 'ANGLE_MetalFamily1TestGetSnapshot' "$workflow" >/dev/null
grep -F -- '--gtest_filter=DisplayMtlFamily1Test.*' "$workflow" >/dev/null
grep -F 'test-result.txt' "$workflow" >/dev/null
grep -F 'manifest.sha256' "$workflow" >/dev/null
grep -F 'artifact.sha256' "$workflow" >/dev/null
grep -F 'GN_ARGS_SHA256=' "$workflow" >/dev/null
! grep -E 'Chrome|chrome|angle-artifact-v1' "$workflow" >/dev/null
! grep -E '(^|[^A-Za-z])(sudo|codesign|xattr|security|gh |git push|force-push|secrets\.|id-token|contents: write)([^A-Za-z]|$)' "$workflow" >/dev/null

for path in \
  BUILD.gn \
  gni/angle.gni \
  src/libANGLE/renderer/metal/BUILD.gn \
  src/libANGLE/renderer/metal/DisplayMtl.h \
  src/libANGLE/renderer/metal/DisplayMtl.mm \
  src/libANGLE/renderer/metal/DisplayMtlFamily1Test.mm \
  src/libANGLE/renderer/metal/DisplayMtlFamily1TestBridge.h \
  src/libANGLE/renderer/metal/DisplayMtlFamily1TestBridge.mm \
  src/tests/BUILD.gn \
  src/tests/DisplayMtlFamily1TestMain.cpp; do
  grep -F "$path" "$workflow" >/dev/null
done

printf '%s\n' 'phase5-metal-family1-static: success'
