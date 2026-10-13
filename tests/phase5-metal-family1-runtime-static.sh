#!/usr/bin/env bash
set -euo pipefail

workflow=${1:?workflow path}
patch=${2:?runtime patch path}

test -f "$workflow"
test -f "$patch"
patch_sha256=$(shasum -a 256 "$patch" | awk '{print $1}')
test "$patch_sha256" = 8cf28ad02dd132b653e93e85535dd7f9fd26571ff4b2ee7c5a0c27f73a720dcb
python3 - "$workflow" "$patch" scripts/verify-phase5-runtime-artifact.sh <<'PY'
import hashlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

workflow_path, patch_path, verifier_path = map(Path, sys.argv[1:])
workflow = workflow_path.read_text()
verifier = verifier_path.read_text()
patch_sha = hashlib.sha256(patch_path.read_bytes()).hexdigest()
reviewed = re.search(r'\[\[ "\$patch_sha" == ([0-9a-f]{64}) \]\]', verifier)
input_blocks = re.finditer(
    r'(?m)^      runtime_patch_sha256:\n(?P<body>(?:^        .*\n)+)', workflow)
inputs = next((block for block in input_blocks
               if re.search(r'(?m)^        default: [0-9a-f]{64}$', block["body"])), None)
default = re.search(r'(?m)^        default: ([0-9a-f]{64})$', inputs["body"]) if inputs else None
if not reviewed or not default:
    raise SystemExit("could not extract verifier reviewed hash or workflow default")
if not (reviewed[1] == default[1] == patch_sha):
    raise SystemExit(
        "runtime patch hash pins diverge: "
        f"verifier={reviewed[1]} workflow={default[1]} patch={patch_sha}")

try:
    function_start = verifier.index("manifest_value() {")
    function_end = verifier.index("\n}\n\ncheck_sha256", function_start) + 2
    guard_start = verifier.index("patch_sha=$(manifest_value RUNTIME_PATCH_SHA256)")
    guard_end = verifier.index('check_sha256 "$artifact_dir/runtime-patch.diff"', guard_start)
except ValueError as error:
    raise SystemExit(f"could not extract verifier patch-hash guard: {error}")
manifest_function = verifier[function_start:function_end]
hash_guard = verifier[guard_start:guard_end]
shell = """set -euo pipefail
manifest=$1
fail() { printf 'Phase 5 runtime artifact verification failed: %s\\n' \"$1\" >&2; exit 1; }
""" + manifest_function + "\n" + hash_guard

with tempfile.TemporaryDirectory(prefix="phase5-patch-manifest-") as directory:
    manifest = Path(directory) / "ANGLE_RELEASE_MANIFEST"
    for label, value, expected_exit in (
            ("current hash accepted", patch_sha, 0),
            ("previous hash rejected", "816622e659a0a46c9c68dfbcf63af59d7d69a81c39632fa4aa2460de6f57f491", 1)):
        manifest.write_text(f"RUNTIME_PATCH_SHA256={value}\n")
        result = subprocess.run(["bash", "-c", shell, "--", str(manifest)],
                                text=True, capture_output=True, check=False)
        if result.returncode != expected_exit:
            raise SystemExit(
                f"synthetic manifest {label} returned {result.returncode}; "
                f"expected {expected_exit}: {result.stderr.strip()}")
        if expected_exit and "runtime patch hash does not match" not in result.stderr:
            raise SystemExit(f"synthetic manifest {label} missed the hash diagnostic")
print("runtime patch contract: verifier/workflow/file hashes agree; current accepted and stale rejected")
PY
patch_paths=$(git apply --numstat "$patch" | awk '{print $3}' | LC_ALL=C sort)
expected_patch_paths=$(printf '%s\n' \
  src/common/apple_platform_utils.mm \
  src/libANGLE/Context.cpp \
  src/libANGLE/Display.cpp \
  src/libANGLE/renderer/metal/DisplayMtl.mm \
  src/libANGLE/renderer/metal/mtl_utils.mm \
  src/libANGLE/validationEGL.cpp \
  src/libEGL/libEGL_autogen.cpp \
  src/libGLESv2/entry_points_egl_autogen.cpp | LC_ALL=C sort)
test "$patch_paths" = "$expected_patch_paths"

grep -F '82303c21a18acdc256c6264cd2ed0e1588df99d4' "$workflow" >/dev/null
grep -F '8efd15f71c27cd0bc2a9cf0074d77e899ca9c448' "$workflow" >/dev/null
grep -F '154.0.8037.0' "$workflow" >/dev/null
grep -F 'fetch --depth=1 origin "$CHROMIUM_REVISION"' "$workflow" >/dev/null
grep -F 'test "$chromium_revision" = "$CHROMIUM_REVISION"' "$workflow" >/dev/null
grep -F 'resolved_angle_revision' "$workflow" >/dev/null
! grep -E 'refs/tags|git fetch[^\n]*CHROME_VERSION' "$workflow" >/dev/null

grep -F 'group: phase5-metal-family1-runtime-${{ github.workflow }}-${{ github.run_id }}-${{ github.run_attempt }}' "$workflow" >/dev/null
grep -F 'cancel-in-progress: false' "$workflow" >/dev/null
! grep -F 'cancel-in-progress: true' "$workflow" >/dev/null
grep -F 'runs-on: macos-15-intel' "$workflow" >/dev/null
grep -F 'timeout-minutes: 120' "$workflow" >/dev/null
grep -F 'timeout-minutes: 40' "$workflow" >/dev/null
grep -F 'timeout-minutes: 25' "$workflow" >/dev/null
grep -F 'mac_deployment_target = "13.0"' "$workflow" >/dev/null
grep -F 'mac_min_system_version = "13.0"' "$workflow" >/dev/null
grep -F 'target_cpu = "x64"' "$workflow" >/dev/null
grep -F 'ninja -C out/Phase5 libEGL' "$workflow" >/dev/null
grep -F 'ninja -C out/Phase5 libGLESv2' "$workflow" >/dev/null

grep -F 'ANGLE_PHASE5_ENABLE_METAL_FAMILY1=1 --disable-angle-features=requireGpuFamily2' "$workflow" >/dev/null
! grep -F 'requireMsl21' "$workflow" >/dev/null
grep -F 'UNSIGNED_ARTIFACT=true' "$workflow" >/dev/null
grep -F 'RUNTIME_DEVICE_READY=false' "$workflow" >/dev/null
grep -F 'scripts/verify-artifact.sh' "$workflow" >/dev/null
grep -F 'scripts/verify-phase5-runtime-artifact.sh' "$workflow" >/dev/null
test -f scripts/verify-artifact.sh
test -f scripts/verify-phase5-runtime-artifact.sh
grep -F 'lipo -archs "$library_path"' scripts/verify-phase5-runtime-artifact.sh >/dev/null
grep -F 'LC_BUILD_VERSION' scripts/verify-phase5-runtime-artifact.sh >/dev/null
grep -F 'LC_VERSION_MIN_MACOSX' scripts/verify-phase5-runtime-artifact.sh >/dev/null
grep -F 'required_symbols=(eglGetProcAddress eglInitialize eglCreateContext)' \
  scripts/verify-phase5-runtime-artifact.sh >/dev/null
grep -F 'required_symbols=(glDrawArrays glReadPixels)' scripts/verify-phase5-runtime-artifact.sh >/dev/null
grep -F 'ANGLE_EXPECTED_REVISION=%s' "$workflow" >/dev/null
grep -F 'ANGLE_ACTUAL_REVISION=%s' "$workflow" >/dev/null
grep -F 'DEPOT_TOOLS_EXPECTED_REVISION=%s' "$workflow" >/dev/null
grep -F 'DEPOT_TOOLS_ACTUAL_REVISION=%s' "$workflow" >/dev/null

python3 - scripts/verify-phase5-runtime-artifact.sh <<'PY'
import subprocess
import sys
from pathlib import Path

verifier = Path(sys.argv[1]).read_text()
try:
    assignment_start = verifier.index("deployment_target=$(printf")
    parser_start = verifier.index("| awk '", assignment_start) + len("| awk '")
    parser_end = verifier.index("\n  ')", parser_start)
except ValueError:
    raise SystemExit("could not extract the verifier's deployment-target parser")
parser = verifier[parser_start:parser_end]
fixtures = {
    "numeric platform 1": ("cmd LC_BUILD_VERSION\n platform 1\n minos 13.0\n sdk 15.0\n", "13.0"),
    "named macOS platform": ("cmd LC_BUILD_VERSION\n platform MACOS\n minos 13.0\n sdk 15.0\n", "13.0"),
    "legacy macOS command": ("cmd LC_VERSION_MIN_MACOSX\n version 13.0\n sdk 15.0\n", "13.0"),
    "other platform rejected": ("cmd LC_BUILD_VERSION\n platform 2\n minos 13.0\n sdk 15.0\n", ""),
}
for label, (load_commands, expected) in fixtures.items():
    result = subprocess.run(["awk", parser], input=load_commands, text=True,
                            stdout=subprocess.PIPE, check=True).stdout.strip()
    if result != expected:
        raise SystemExit(f"deployment parser {label}: expected {expected!r}, got {result!r}")
print("deployment parser: numeric/named/legacy macOS accepted; other platform rejected")
PY
grep -F 'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683' "$workflow" >/dev/null
grep -F 'actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02' "$workflow" >/dev/null
grep -F 'persist-credentials: false' "$workflow" >/dev/null
grep -F 'permissions:' "$workflow" >/dev/null
grep -F 'contents: read' "$workflow" >/dev/null
grep -F 'DEPOT_TOOLS_UPDATE: "0"' "$workflow" >/dev/null
grep -F 'if: success()' "$workflow" >/dev/null
grep -F 'if: always()' "$workflow" >/dev/null
grep -F 'git apply --unidiff-zero --check' "$workflow" >/dev/null
grep -F 'RUNTIME_ARTIFACT_SCHEMA=phase5-metal-family1-runtime-v1' "$workflow" >/dev/null
grep -F 'RUNTIME_PATCH_APPLIED=true' "$workflow" >/dev/null
grep -F 'phase5-metal-family1-runtime-diagnostics-' "$workflow" >/dev/null

python3 - "$workflow" scripts/verify-phase5-runtime-artifact.sh <<'PY'
import re
import sys
from pathlib import Path

workflow = Path(sys.argv[1]).read_text()
verifier = Path(sys.argv[2]).read_text()
manifest_start = workflow.index("printf 'SCHEMA=angle-release-v1\\n'")
manifest_end = workflow.index('} > "$ARTIFACT_DIR/ANGLE_RELEASE_MANIFEST"', manifest_start)
manifest_producer = workflow[manifest_start:manifest_end]
produced = set(re.findall(r"printf '([A-Z][A-Z0-9_]*)=", manifest_producer))
required = set(re.findall(r"manifest_value ([A-Z][A-Z0-9_]*)", verifier))
# The verifier selects these two checksum keys dynamically in its library loop.
required.update(("LIBEGL_SHA256", "LIBGLESV2_SHA256"))

def missing_keys(keys, producer_keys):
    return sorted(keys - producer_keys)

missing = missing_keys(required, produced)
if missing:
    print("manifest producer is missing verifier keys: " + ", ".join(missing), file=sys.stderr)
    raise SystemExit(1)

# Exercise the failure diagnostic without creating an artifact or invoking codesign.
probe = next(iter(sorted(required)))
diagnostic = missing_keys(required, produced - {probe})
if diagnostic != [probe]:
    print(f"manifest contract negative check failed for {probe}: {diagnostic}", file=sys.stderr)
    raise SystemExit(1)
print(f"manifest contract: {len(required)} verifier keys produced; missing-key diagnostic verified")
PY

for source_path in $expected_patch_paths; do
  grep -F "'$source_path'" "$workflow" >/dev/null
done

grep -F 'ANGLE_PHASE5_ENABLE_METAL_FAMILY1' "$patch" >/dev/null
grep -F 'family1_runtime_opt_in=invalid_value' "$patch" >/dev/null
grep -F 'std::strcmp(value, "1") != 0' "$patch" >/dev/null
grep -F 'MTLGPUFamilyMac1' "$patch" >/dev/null
grep -F 'MTLGPUFamilyMac2' "$patch" >/dev/null
grep -F 'family1RuntimeOptIn && supportsFamily1' "$patch" >/dev/null
grep -F 'supportsMacFamily1 && !supportsMacFamily2' "$patch" >/dev/null
grep -F 'MTLGPUFamilyMacCatalyst1' "$patch" >/dev/null
grep -F 'MTLGPUFamilyMacCatalyst2' "$patch" >/dev/null
test "$(grep -Ec '#[[:space:]]*pragma clang diagnostic ignored "-Wdeprecated-declarations"' "$patch")" -eq 4
test "$(grep -Ec '#[[:space:]]*pragma clang diagnostic push' "$patch")" -ge 2
test "$(grep -Ec '#[[:space:]]*pragma clang diagnostic pop' "$patch")" -ge 2
grep -F '#if TARGET_OS_MACCATALYST || TARGET_OS_OSX' "$patch" >/dev/null
grep -F 'returnValue && num_config' "$patch" >/dev/null
grep -F 'returnValue && value' "$patch" >/dev/null
! grep -F 'max_es_version=2.0 family=mac1' "$patch" >/dev/null
grep -F 'max_es_version_gpu_family4_or1=' "$patch" >/dev/null
grep -F 'angle::GetEnvironmentVar("ANGLE_PHASE5_ENABLE_METAL_FAMILY1") == "1"' "$patch" >/dev/null
grep -F 'UseLegacyMathOptionsForPhase5Family1(metalDevice, options.get())' "$patch" >/dev/null
grep -F 'respondsToSelector:@selector(setMathMode:)' "$patch" >/dev/null
grep -F 'respondsToSelector:@selector(setMathFloatingPointFunctions:)' "$patch" >/dev/null
grep -F 'options.get().fastMathEnabled = !disableFastMath;' "$patch" >/dev/null
grep -F 'math_options=legacy_fastMathEnabled' "$patch" >/dev/null
grep -F 'math-options-policy.py' "$workflow" >/dev/null
grep -F 'native_mac_family=1 mac1=true mac2=false' "$patch" >/dev/null
grep -F 'src/libANGLE/renderer/metal/mtl_utils.mm' "$patch" >/dev/null
grep -F 'eglInitialize_return_failure' "$patch" >/dev/null
grep -F 'eglGetError_return=0x%04x' "$patch" >/dev/null
grep -F '+__attribute__((constructor)) static void Phase5LogMetalLibraryLoaded()' "$patch" >/dev/null
! grep -E 'ANGLE_MetalFamily1Test|DisplayMtlFamily1Test|ANGLE_ENABLE_METAL_FAMILY1_TEST_STUB|requireMsl21' "$patch" >/dev/null
! grep -E '^\+.*(codesign|xattr|security|sudo|git push|force-push|KOOV|--user-data-dir|Google Chrome|open -a)' "$workflow" >/dev/null
! grep -E '^\+.*(setenv|unsetenv|family.?bypass|force.?family)' "$patch" >/dev/null

printf '%s\n' 'phase5-metal-family1-runtime-static: success'
