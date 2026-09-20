#!/usr/bin/env bash
set -euo pipefail

readonly REPOSITORY='naokikambe/chromium-angle-family1-experiment'
readonly RUN_ID='35501697418'
readonly ARTIFACT_NAME='angle-macos-x86_64-35501697418'
readonly ANGLE_REVISION='8efd15f71c27cd0bc2a9cf0074d77e899ca9c448'
readonly LIBEGL_SHA256='f4a8a7575183a41373404f7c25b4f56e1a1540c5b1578d11437c180b1f698db8'
readonly LIBGLESV2_SHA256='2e0aadc21e76b0bb1adcfb3b908e757906995b75abb9e90edb3dfb5c1d1adef0'

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
if ! gh run download "$RUN_ID" \
  --repo "$REPOSITORY" \
  --name "$ARTIFACT_NAME" \
  --dir "$output_dir"; then
  fail "artifact download failed for run $RUN_ID"
fi

for required in libEGL.dylib libGLESv2.dylib ANGLE_REVISION args.gn build-environment.txt licenses; do
  [[ -e "$output_dir/$required" ]] || fail "downloaded artifact is missing: $required"
done

actual_angle_revision=$(cat "$output_dir/ANGLE_REVISION")
[[ "$actual_angle_revision" == "$ANGLE_REVISION" ]] ||
  fail "ANGLE revision mismatch: expected $ANGLE_REVISION, got $actual_angle_revision"

actual_libegl=$(shasum -a 256 "$output_dir/libEGL.dylib" | awk '{print $1}')
actual_libglesv2=$(shasum -a 256 "$output_dir/libGLESv2.dylib" | awk '{print $1}')
[[ "$actual_libegl" == "$LIBEGL_SHA256" ]] ||
  fail "libEGL.dylib SHA-256 mismatch: expected $LIBEGL_SHA256, got $actual_libegl"
[[ "$actual_libglesv2" == "$LIBGLESV2_SHA256" ]] ||
  fail "libGLESv2.dylib SHA-256 mismatch: expected $LIBGLESV2_SHA256, got $actual_libglesv2"

printf 'artifact verified: %s\n' "$output_real"
printf 'ANGLE revision: %s\n' "$actual_angle_revision"
printf 'libEGL.dylib SHA-256: %s\n' "$actual_libegl"
printf 'libGLESv2.dylib SHA-256: %s\n' "$actual_libglesv2"
