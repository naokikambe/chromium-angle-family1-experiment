#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  printf 'usage: %s REPOSITORY_ROOT INPUTS_JSON OUTPUT_DIRECTORY\n' "$0" >&2
  exit 64
fi
repo_root=$(cd "$1" && pwd -P)
inputs_json=$2
artifact_dir=$3
angle_root="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/angle-source"
depot_tools_root="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/depot-tools"
mkdir -p "$(dirname "$artifact_dir")"
[[ ! -e "$artifact_dir" ]] || { printf 'artifact destination already exists\n' >&2; exit 73; }

read_input() {
  python3 - "$inputs_json" "$1" <<'PY'
import json, sys
value=json.load(open(sys.argv[1], encoding="utf-8"))
for key in sys.argv[2].split("."):
    value=value[key]
if isinstance(value, (dict, list)):
    print(json.dumps(value, sort_keys=True))
else:
    print(value)
PY
}
angle_revision=$(read_input angle_revision)
depot_tools_revision=$(read_input recipe.depot_tools_revision)
chromium_revision=$(read_input chromium_revision)
patch_path="$repo_root/$(read_input patch_path)"
patch_sha=$(read_input patch_sha256)
expected_xcode=$(read_input recipe.xcode_version)
expected_sdk=$(read_input recipe.macos_sdk_version)

actual_xcode=$(xcodebuild -version | sed -n '1s/^Xcode //p')
actual_sdk=$(xcrun --show-sdk-version)
test "$(uname -m)" = x86_64 || { printf 'runner architecture does not match recipe\n' >&2; exit 65; }
test "$actual_xcode" = "$expected_xcode" || { printf 'Xcode version does not match recipe\n' >&2; exit 65; }
test "$actual_sdk" = "$expected_sdk" || { printf 'macOS SDK version does not match recipe\n' >&2; exit 65; }

mkdir -p "$angle_root"
git -C "$angle_root" init -q
git -C "$angle_root" remote add origin https://chromium.googlesource.com/angle/angle.git
git -C "$angle_root" fetch --depth=1 origin "$angle_revision"
git -C "$angle_root" checkout --detach FETCH_HEAD
test "$(git -C "$angle_root" rev-parse HEAD)" = "$angle_revision"

git init -q "$depot_tools_root"
git -C "$depot_tools_root" remote add origin https://chromium.googlesource.com/chromium/tools/depot_tools.git
git -C "$depot_tools_root" fetch --depth=1 origin "$depot_tools_revision"
git -C "$depot_tools_root" checkout --detach FETCH_HEAD
test "$(git -C "$depot_tools_root" rev-parse HEAD)" = "$depot_tools_revision"
export DEPOT_TOOLS_DIR="$depot_tools_root"
export DEPOT_TOOLS_UPDATE=0
export DEPOT_TOOLS_BOOTSTRAP_PYTHON3=1
export PATH="$depot_tools_root/python-bin:$depot_tools_root:$PATH"
bash "$repo_root/scripts/bootstrap-depot-tools.sh" "$depot_tools_root" "$depot_tools_revision"

cd "$angle_root"
printf 'angle-checkout-bootstrap\n' > "${FAILURE_STAGE_FILE:-/dev/null}"
python3 scripts/bootstrap.py
python3 - <<'PY'
from pathlib import Path
from pprint import pformat
path=Path('.gclient')
scope={}
exec(path.read_text(encoding='utf-8'), {'__builtins__': {}}, scope)
solutions=scope.get('solutions')
if not isinstance(solutions, list) or len(solutions) != 1:
    raise SystemExit('unexpected .gclient solutions')
custom_vars=solutions[0].get('custom_vars', {})
if not isinstance(custom_vars, dict):
    raise SystemExit('unexpected .gclient custom_vars')
custom_vars=dict(custom_vars)
for name in ('checkout_angle_cl_deps','checkout_angle_dawn_deps','checkout_angle_internal',
             'checkout_angle_mesa','checkout_angle_partition_alloc','checkout_angle_restricted_traces',
             'checkout_extra_traces'):
    custom_vars[name]=False
solutions[0]['custom_vars']=custom_vars
path.write_text('solutions = ' + pformat(solutions, sort_dicts=False) + '\n', encoding='utf-8')
PY
printf 'angle-dependency-sync\n' > "${FAILURE_STAGE_FILE:-/dev/null}"
gclient sync --no-history
test "$(git rev-parse HEAD)" = "$angle_revision"
test "$(git -C "$depot_tools_root" rev-parse HEAD)" = "$depot_tools_revision" || {
  printf 'depot_tools revision changed before GN; refusing to continue\n' >&2
  exit 1
}
printf 'patch-and-function-checks\n' > "${FAILURE_STAGE_FILE:-/dev/null}"
python3 - "$inputs_json" "$patch_path" "$angle_root" <<'PY'
import hashlib, json, subprocess, sys
inputs=json.load(open(sys.argv[1], encoding="utf-8"))
patch=open(sys.argv[2], "rb").read()
assert hashlib.sha256(patch).hexdigest() == inputs["patch_sha256"]
root=sys.argv[3]
if (inputs["patch_candidate_status"] == "catalog-match" or
        inputs["angle_revision"] == inputs["patch_source_revision"]):
    for path, expected in inputs["patch_source_blobs"].items():
        actual=subprocess.run(["git","-C",root,"hash-object",path], check=True, capture_output=True, text=True).stdout.strip()
        if actual != expected:
            raise SystemExit("patch source blob differs from reviewed baseline: " + path)
subprocess.run(["git","-C",root,"apply","--check",sys.argv[2]], check=True)
subprocess.run(["git","-C",root,"apply","--index",sys.argv[2]], check=True)
paths=subprocess.run(["git","-C",root,"diff","--cached","--name-only"], check=True, capture_output=True, text=True).stdout.splitlines()
if paths != inputs["patch_apply_order"]:
    raise SystemExit("applied patch paths or order differ from catalog")
subprocess.run(["git","-C",root,"diff","--cached","--check"], check=True)
PY
printf 'synthetic-source-policy-tests\n' > "${FAILURE_STAGE_FILE:-/dev/null}"
python3 "$repo_root/tests/angle-policy/native-query-policy.py" \
  --apple-platform-utils "$angle_root/src/common/apple_platform_utils.mm" \
  --mtl-utils "$angle_root/src/libANGLE/renderer/metal/mtl_utils.mm"
python3 "$repo_root/tests/angle-policy/math-options-policy.py" \
  --mtl-utils "$angle_root/src/libANGLE/renderer/metal/mtl_utils.mm"
policy_args=(--source-root "$angle_root")
policy_api_version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("patch_expected_shader_api_version") or "")' "$inputs_json")
if [[ -n "$policy_api_version" ]]; then
  policy_args+=(--expected-sh-version "$policy_api_version")
fi
python3 "$repo_root/tests/angle-policy/vertex-unpack-policy.py" "${policy_args[@]}"
printf 'angle-build\n' > "${FAILURE_STAGE_FILE:-/dev/null}"
mkdir -p out/Release
python3 - "$inputs_json" out/Release/args.gn <<'PY'
import json, sys
value=json.load(open(sys.argv[1], encoding='utf-8'))['recipe']['gn_args']
lines=[]
for name, item in value.items():
    rendered=('true' if item else 'false') if isinstance(item,bool) else (f'"{item}"' if isinstance(item,str) else str(item))
    lines.append(f'{name} = {rendered}')
open(sys.argv[2], 'w', encoding='utf-8').write('\n'.join(lines)+'\n')
PY
"$depot_tools_root/gn" gen out/Release
"$depot_tools_root/ninja" -C out/Release libEGL libGLESv2

printf 'artifact-assembly\n' > "${FAILURE_STAGE_FILE:-/dev/null}"
mkdir -p "$artifact_dir/licenses"
install -m 0644 "$patch_path" "$artifact_dir/runtime-patch.diff"
install -m 0755 out/Release/libEGL.dylib "$artifact_dir/libEGL.dylib"
install -m 0755 out/Release/libGLESv2.dylib "$artifact_dir/libGLESv2.dylib"
install -m 0644 out/Release/args.gn "$artifact_dir/args.gn"
install -m 0644 LICENSE "$artifact_dir/LICENSE"
while IFS= read -r -d '' license_file; do
  relative_path=${license_file#"$angle_root"/}
  destination="$artifact_dir/licenses/$relative_path"
  mkdir -p "$(dirname "$destination")"
  install -m 0644 "$license_file" "$destination"
done < <(find "$angle_root" -type f \( -iname 'LICENSE*' -o -iname 'NOTICE*' \) \
  -not -path "$angle_root/.git/*" -not -path "$angle_root/out/*" -print0)
printf '%s\n' "$angle_revision" > "$artifact_dir/ANGLE_REVISION"
{
  printf 'ANGLE_REVISION=%s\n' "$angle_revision"
  printf 'CHROMIUM_REVISION=%s\n' "$chromium_revision"
  printf 'DEPOT_TOOLS_REVISION=%s\n' "$depot_tools_revision"
  printf 'RUNNER_OS=%s\n' "$RUNNER_OS"
  printf 'RUNNER_ARCH=%s\n' "$RUNNER_ARCH"
  printf 'CPU_ARCHITECTURE=%s\n' "$(uname -m)"
  xcodebuild -version
  printf 'MACOS_SDK_VERSION=%s\n' "$(xcrun --show-sdk-version)"
  xcrun clang --version
  printf 'DEPOT_TOOLS_PYTHON=%s\n' "$("$depot_tools_root/python-bin/python3" --version 2>&1)"
  printf 'DEPOT_TOOLS_GN=%s\n' "$("$depot_tools_root/gn" --version)"
  printf 'DEPOT_TOOLS_NINJA=%s\n' "$("$depot_tools_root/ninja" --version)"
  printf 'NINJA_TARGETS=libEGL libGLESv2\n'
} > "$artifact_dir/build-environment.txt"
