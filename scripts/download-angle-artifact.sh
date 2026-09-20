#!/usr/bin/env bash
set -euo pipefail

readonly REPOSITORY='naokikambe/chromium-angle-family1-experiment'
readonly CHROME_VERSION='154.0.8037.45'
readonly CHROMIUM_REVISION='731082f0a26ce4b3976c3d82943092f5d13daf13'
readonly ANGLE_REVISION='72b8f72a7587ec776d7d2a57d275a6e9b1781b1d'
readonly ANGLE_SHORT_REVISION='72b8f72a'
readonly WORKFLOW_RUN_ID='35515036255'
readonly LIBEGL_SHA256='f4a8a7575183a41373404f7c25b4f56e1a1540c5b1578d11437c180b1f698db8'
readonly LIBGLESV2_SHA256='8d3d188d3d4f23cf3f96ecea209b084c6db9c6192244f879cfb6bf0fb2e02cf0'

fail() {
  printf 'download-angle-artifact: %s\n' "$1" >&2
  exit 1
}

if [[ $# -ne 1 ]]; then
  printf 'usage: %s OUTPUT_DIRECTORY\n' "$0" >&2
  exit 64
fi

command -v gh >/dev/null 2>&1 || fail 'GitHub CLI (gh) is required'
command -v shasum >/dev/null 2>&1 || fail 'shasum is required'
command -v git >/dev/null 2>&1 || fail 'git is required'

output_dir=$1
run_id=$WORKFLOW_RUN_ID
expected_libegl_sha256=$LIBEGL_SHA256
expected_libglesv2_sha256=$LIBGLESV2_SHA256
artifact_name="angle-macos-x86_64-chrome-${CHROME_VERSION}-angle-${ANGLE_SHORT_REVISION}-${run_id}"
output_parent=$(dirname "$output_dir")
output_name=$(basename "$output_dir")
[[ -d "$output_parent" ]] || fail "output parent does not exist: $output_parent"
[[ ! -e "$output_dir" ]] || fail "refusing to overwrite existing output: $output_dir"

repo_root=$(git rev-parse --show-toplevel 2>/dev/null || true)
output_parent_real=$(cd "$output_parent" && pwd -P)
output_real="$output_parent_real/$output_name"
if [[ -n "$repo_root" ]]; then
  repo_root=$(cd "$repo_root" && pwd -P)
  if [[ "$output_real" == "$repo_root" || "$output_real" == "$repo_root/"* ]]; then
    fail 'refusing to place a downloaded artifact inside the Git repository'
  fi
fi

mkdir "$output_dir"
if ! gh run download "$run_id" \
  --repo "$REPOSITORY" \
  --name "$artifact_name" \
  --dir "$output_dir"; then
  fail "artifact download failed for run $run_id"
fi

for required in libEGL.dylib libGLESv2.dylib ANGLE_REVISION args.gn build-environment.txt licenses; do
  [[ -e "$output_dir/$required" ]] || fail "downloaded artifact is missing: $required"
done

actual_angle_revision=$(cat "$output_dir/ANGLE_REVISION")
[[ "$actual_angle_revision" == "$ANGLE_REVISION" ]] ||
  fail "ANGLE revision mismatch: expected $ANGLE_REVISION, got $actual_angle_revision"
grep -Fx "CHROME_VERSION=$CHROME_VERSION" "$output_dir/build-environment.txt" >/dev/null ||
  fail "artifact build environment does not identify Chrome $CHROME_VERSION"
grep -Fx "CHROMIUM_REVISION=$CHROMIUM_REVISION" "$output_dir/build-environment.txt" >/dev/null ||
  fail "artifact build environment does not identify Chromium $CHROMIUM_REVISION"

actual_libegl=$(shasum -a 256 "$output_dir/libEGL.dylib" | awk '{print $1}')
actual_libglesv2=$(shasum -a 256 "$output_dir/libGLESv2.dylib" | awk '{print $1}')
[[ "$actual_libegl" == "$expected_libegl_sha256" ]] ||
  fail "libEGL.dylib SHA-256 mismatch: expected $expected_libegl_sha256, got $actual_libegl"
[[ "$actual_libglesv2" == "$expected_libglesv2_sha256" ]] ||
  fail "libGLESv2.dylib SHA-256 mismatch: expected $expected_libglesv2_sha256, got $actual_libglesv2"

printf 'artifact verified: %s\n' "$output_real"
printf 'ANGLE revision: %s\n' "$actual_angle_revision"
printf 'libEGL.dylib SHA-256: %s\n' "$actual_libegl"
printf 'libGLESv2.dylib SHA-256: %s\n' "$actual_libglesv2"
