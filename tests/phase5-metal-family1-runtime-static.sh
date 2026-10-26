#!/usr/bin/env bash
set -euo pipefail

workflow=${1:?workflow path}
patch=${2:?runtime patch path}
test -f "$workflow"
test -f "$patch"
test -f licenses/ANGLE-LICENSE.txt
python3 - "$workflow" <<'PY'
import re
import sys
from pathlib import Path

workflow = Path(sys.argv[1]).read_text()
triggers = re.search(r'(?ms)^on:\n(?P<body>.*?)(?=^\S|\Z)', workflow)
if not triggers:
    raise SystemExit("runtime workflow lacks an event block")
event_names = re.findall(r'(?m)^  ([A-Za-z_]+):', triggers["body"])
if event_names != ["workflow_call", "workflow_dispatch", "push"]:
    raise SystemExit("runtime workflow trigger set changed")
push = re.search(r'(?ms)^  push:\n(?P<body>.*?)(?=^(?:  \S|\S)|\Z)', workflow)
if not push:
    raise SystemExit("runtime workflow lacks a push trigger")
actual_scope = [line.strip() for line in push["body"].splitlines() if line.strip()]
expected_scope = [
    "branches:",
    "- phase5-page-recovery",
    "paths:",
    "- '.github/workflows/phase5-metal-family1-runtime.yml'",
    "- 'patches/phase5-metal-family1-runtime.patch'",
    "- 'scripts/verify-artifact.sh'",
    "- 'scripts/verify-phase5-runtime-artifact.sh'",
    "- 'tests/phase5-metal-family1-runtime-static.sh'",
    "- 'tests/phase5-metal-family1-native-query-policy.py'",
    "- 'tests/phase5-metal-family1-math-options-policy.py'",
    "- 'tests/phase5-metal-family1-vertex-unpack-policy.py'",
]
if actual_scope != expected_scope:
    raise SystemExit("push trigger branch/path scope changed")

defaults = {
    "ANGLE_REVISION": ("angle_revision", "3b89d84e9d59f75675ac4e2bef58fc068a9f0577"),
    "CHROME_VERSION": ("chrome_version", "156.0.8078.48"),
    "RUNTIME_PATCH_SHA256": (
        "runtime_patch_sha256",
        "dedac2c57daa69b72fe78bbde443f45d5a6cdfe128d4022049a35c0dbbf501b0",
    ),
}
for env_name, (input_name, pinned_value) in defaults.items():
    pattern = (
        rf"(?m)^      {env_name}: \$\{{\{{ inputs\.{input_name} \|\| "
        rf"'{re.escape(pinned_value)}' \}}\}}$"
    )
    if not re.search(pattern, workflow):
        raise SystemExit(f"{env_name} lacks the pinned no-input fallback")
print("push trigger: branch/path scope and pinned no-input defaults passed")
PY
license_sha256=$(shasum -a 256 licenses/ANGLE-LICENSE.txt | awk '{print $1}')
test "$license_sha256" = bf4da21bd20bcfb5b60b7ecc67fa864a79be049e21d6178076887f178dd6c71a
grep -F 'patches/phase5-metal-family1-runtime.patch whitespace=-blank-at-eol' .gitattributes >/dev/null
patch_sha256=$(shasum -a 256 "$patch" | awk '{print $1}')
test "$patch_sha256" = dedac2c57daa69b72fe78bbde443f45d5a6cdfe128d4022049a35c0dbbf501b0

# Bind the workflow, artifact verifier, and source patch to the same immutable
# Chrome/Chromium/ANGLE source set.
grep -F '156.0.8078.48' "$workflow" >/dev/null
grep -F 'd0c02bfad08ec92a6ffcf989e53cd995e6381a4c' "$workflow" >/dev/null
grep -F '3b89d84e9d59f75675ac4e2bef58fc068a9f0577' "$workflow" >/dev/null
grep -F 'dedac2c57daa69b72fe78bbde443f45d5a6cdfe128d4022049a35c0dbbf501b0' "$workflow" >/dev/null
grep -F '156.0.8078.48' scripts/verify-phase5-runtime-artifact.sh >/dev/null
grep -F 'd0c02bfad08ec92a6ffcf989e53cd995e6381a4c' scripts/verify-phase5-runtime-artifact.sh >/dev/null
grep -F '3b89d84e9d59f75675ac4e2bef58fc068a9f0577' scripts/verify-phase5-runtime-artifact.sh >/dev/null
grep -F 'dedac2c57daa69b72fe78bbde443f45d5a6cdfe128d4022049a35c0dbbf501b0' scripts/verify-phase5-runtime-artifact.sh >/dev/null
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
default = re.search(r'(?m)^        default: ([0-9a-f]{64})$', workflow)
reviewed = re.search(r'\[\[ "\$patch_sha" == ([0-9a-f]{64}) \]\]', verifier)
if not default or not reviewed or default[1] != reviewed[1] or reviewed[1] != patch_sha:
    raise SystemExit("workflow, verifier, and patch SHA-256 pins diverge")

start = verifier.index("manifest_value() {")
end = verifier.index("\n}\n\ncheck_sha256", start) + 2
manifest_function = verifier[start:end]
guard_start = verifier.index("patch_sha=$(manifest_value RUNTIME_PATCH_SHA256)")
guard_end = verifier.index('check_sha256 "$artifact_dir/runtime-patch.diff" "$patch_sha"', guard_start)
hash_guard = verifier[guard_start:guard_end]
shell = """set -euo pipefail
manifest=$1
fail() { printf 'verification failed: %s\\n' "$1" >&2; exit 1; }
""" + manifest_function + "\n" + hash_guard

with tempfile.TemporaryDirectory(prefix="phase5-stable-patch-contract-") as directory:
    manifest = Path(directory) / "ANGLE_RELEASE_MANIFEST"
    for label, digest, expected in (
        ("current hash accepted", patch_sha, 0),
        ("stale hash rejected", "98c5b573da41d8f0a3d64d6a4352c25adbf89ca823c47b8fa56178cf9f1c1f4b", 1),
    ):
        manifest.write_text(f"RUNTIME_PATCH_SHA256={digest}\n")
        result = subprocess.run(["bash", "-c", shell, "--", str(manifest)],
                                text=True, capture_output=True, check=False)
        if result.returncode != expected:
            raise SystemExit(f"{label}: returned {result.returncode}, expected {expected}: {result.stderr.strip()}")
        if expected and "runtime patch hash does not match" not in result.stderr:
            raise SystemExit(f"{label}: missing stale-patch diagnostic")
print("patch hash contract: current accepted; previous hash rejected")
PY

grep -F 'fetch --depth=1 origin "$CHROMIUM_REVISION"' "$workflow" >/dev/null
grep -F 'test "$chromium_revision" = "$CHROMIUM_REVISION"' "$workflow" >/dev/null
grep -F 'resolved_angle_revision' "$workflow" >/dev/null
! grep -E 'refs/tags|git fetch[^[:cntrl:]]*CHROME_VERSION' "$workflow" >/dev/null

grep -F 'group: phase5-metal-family1-runtime-${{ github.workflow }}-${{ github.run_id }}-${{ github.run_attempt }}' "$workflow" >/dev/null
grep -F 'cancel-in-progress: false' "$workflow" >/dev/null
grep -F 'runs-on: macos-15-intel' "$workflow" >/dev/null
grep -F 'timeout-minutes: 120' "$workflow" >/dev/null
grep -F 'contents: read' "$workflow" >/dev/null
grep -F 'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683' "$workflow" >/dev/null
grep -F 'actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02' "$workflow" >/dev/null
grep -F 'persist-credentials: false' "$workflow" >/dev/null
grep -F 'retention-days: 14' "$workflow" >/dev/null
grep -F 'developer_dir=/Applications/Xcode_16.4.app/Contents/Developer' "$workflow" >/dev/null
grep -F 'test "$(xcodebuild -version | awk' "$workflow" >/dev/null
grep -F 'test "$(xcrun --show-sdk-version)" = 15.5' "$workflow" >/dev/null
grep -F 'xcodebuild -version' "$workflow" >/dev/null
grep -F 'mac_deployment_target = "13.0"' "$workflow" >/dev/null
grep -F 'mac_min_system_version = "13.0"' "$workflow" >/dev/null
grep -F 'target_cpu = "x64"' "$workflow" >/dev/null
grep -F 'angle_enable_metal = true' "$workflow" >/dev/null
grep -F 'angle_enable_gl = false' "$workflow" >/dev/null
grep -F 'ninja -C out/Phase5 libEGL >' "$workflow" >/dev/null
grep -F 'ninja -C out/Phase5 libGLESv2 >' "$workflow" >/dev/null
grep -F 'ANGLE_PHASE5_ENABLE_METAL_FAMILY1=1 --disable-angle-features=requireGpuFamily2' "$workflow" >/dev/null
grep -F 'UNSIGNED_ARTIFACT=true' "$workflow" >/dev/null
grep -F 'RUNTIME_DEVICE_READY=false' "$workflow" >/dev/null
grep -F 'scripts/verify-artifact.sh' "$workflow" >/dev/null
grep -F 'scripts/verify-phase5-runtime-artifact.sh' "$workflow" >/dev/null
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
grep -F 'DEPOT_TOOLS_UPDATE: "0"' "$workflow" >/dev/null
grep -F 'if: success()' "$workflow" >/dev/null
grep -F 'if: always()' "$workflow" >/dev/null
grep -F 'git apply --unidiff-zero --check' "$workflow" >/dev/null
grep -F 'RUNTIME_ARTIFACT_SCHEMA=phase5-metal-family1-runtime-v1' "$workflow" >/dev/null
grep -F 'RUNTIME_PATCH_APPLIED=true' "$workflow" >/dev/null
grep -F 'phase5-metal-family1-runtime-diagnostics-' "$workflow" >/dev/null

patch_paths=$(git apply --numstat "$patch" | awk '{print $3}' | LC_ALL=C sort)
expected_patch_paths=$(printf '%s\n' \
  include/GLSLANG/ShaderLang.h \
  src/common/apple_platform_utils.mm \
  src/compiler/translator/msl/EmitMetal.cpp \
  src/libANGLE/renderer/metal/ShaderMtl.mm \
  src/libANGLE/renderer/metal/mtl_utils.mm | LC_ALL=C sort)
test "$patch_paths" = "$expected_patch_paths"
for source_path in $expected_patch_paths; do
  grep -F "'$source_path'" "$workflow" >/dev/null
done

grep -F 'ANGLE_PHASE5_ENABLE_METAL_FAMILY1' "$patch" >/dev/null
grep -F 'family1RuntimeOptIn' "$patch" >/dev/null
grep -F 'supportsMacFamily1 && !supportsMacFamily2' "$patch" >/dev/null
grep -F 'UseLegacyMathOptionsForPhase5Family1' "$patch" >/dev/null
grep -F 'UsePhase5VertexUnpackSnorm4x8' "$patch" >/dev/null
grep -F 'ANGLE_phase5::unpackSnorm4x8' "$patch" >/dev/null
grep -F 'bool emulateUnpackSnorm4x8 = false;' "$patch" >/dev/null
grep -F 'angle::GetEnvironmentVar("ANGLE_PHASE5_ENABLE_METAL_FAMILY1") == "1"' "$patch" >/dev/null
grep -F 'angle::GetEnvironmentVar("ANGLE_PHASE5_ENABLE_METAL_FAMILY1") != "1"' "$patch" >/dev/null
grep -F 'TARGET_OS_OSX && !TARGET_OS_MACCATALYST' "$patch" >/dev/null
grep -F 'RUNTIME_OPT_IN=ANGLE_PHASE5_ENABLE_METAL_FAMILY1=1 --disable-angle-features=requireGpuFamily2' "$workflow" >/dev/null
grep -F 'RUNTIME_DEVICE_READY=false' "$workflow" >/dev/null
! grep -E 'test-stub|TEST_STUB|DisplayMtlFamily1Test|family.?bypass|force.?family' "$patch" >/dev/null
! grep -E '^\+.*(codesign|xattr|security|sudo|git push|force-push|KOOV|--user-data-dir|Google Chrome|open -a)' "$workflow" >/dev/null

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
required.update(("LIBEGL_SHA256", "LIBGLESV2_SHA256"))
missing = required - produced
if missing:
    raise SystemExit("manifest producer is missing verifier fields")
probe = sorted(required)[0]
if required - (produced - {probe}) != {probe}:
    raise SystemExit("manifest missing-field rejection contract failed")
print(f"manifest contract: {len(required)} verifier fields produced; missing-field rejection checked")
PY

python3 - scripts/verify-phase5-runtime-artifact.sh <<'PY'
import subprocess
import sys
from pathlib import Path

verifier = Path(sys.argv[1]).read_text()
assignment_start = verifier.index("deployment_target=$(printf")
parser_start = verifier.index("| awk '", assignment_start) + len("| awk '")
parser_end = verifier.index("\n  ')", parser_start)
parser = verifier[parser_start:parser_end]
fixtures = {
    "numeric platform 1": ("cmd LC_BUILD_VERSION\n platform 1\n minos 13.0\n sdk 15.0\n", "13.0"),
    "named macOS platform": ("cmd LC_BUILD_VERSION\n platform MACOS\n minos 13.0\n sdk 15.0\n", "13.0"),
    "legacy macOS command": ("cmd LC_VERSION_MIN_MACOSX\n version 13.0\n sdk 15.0\n", "13.0"),
    "other platform rejected": ("cmd LC_BUILD_VERSION\n platform 2\n minos 13.0\n sdk 15.0\n", ""),
}
for label, (load_commands, expected) in fixtures.items():
    result = subprocess.run(["awk", parser], input=load_commands, text=True,
                            capture_output=True, check=True).stdout.strip()
    if result != expected:
        raise SystemExit(f"deployment parser failed: {label}")
print("deployment parser: macOS forms accepted; other platform rejected")
PY

bash -n scripts/verify-phase5-runtime-artifact.sh
ruby -e 'require "yaml"; YAML.parse_file(ARGV.fetch(0))' "$workflow"
printf '%s\n' 'phase5-metal-family1-runtime-static: Chrome Stable 156 candidate checks passed'
