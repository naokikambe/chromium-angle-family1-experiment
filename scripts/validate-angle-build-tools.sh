#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  printf 'usage: %s ANGLE_DIRECTORY ANGLE_REVISION DEPOT_TOOLS_DIRECTORY DEPOT_TOOLS_REVISION\n' "$0" >&2
  exit 64
fi

fail() {
  printf 'ANGLE build-tool validation failed: %s\n' "$1" >&2
  exit 1
}

angle_root=$(cd "$1" && pwd -P) || fail 'ANGLE checkout directory is unavailable'
expected_angle_revision=$2
depot_tools_root=$(cd "$3" && pwd -P) || fail 'depot_tools checkout directory is unavailable'
expected_depot_tools_revision=$4
[[ "$expected_angle_revision" =~ ^[0-9a-f]{40}$ ]] || fail 'ANGLE revision is malformed'
[[ "$expected_depot_tools_revision" =~ ^[0-9a-f]{40}$ ]] || fail 'depot_tools revision is malformed'

current_directory=$(pwd -P)
[[ "$current_directory" == "$angle_root" ]] || \
  fail 'must run from the ANGLE checkout after gclient sync'

if [[ -n "${FAILURE_STAGE_FILE:-}" ]]; then
  printf 'angle-build-tool-validation\n' > "$FAILURE_STAGE_FILE"
fi

actual_angle_revision=$(git -C "$angle_root" rev-parse HEAD 2>/dev/null) || \
  fail 'cannot read ANGLE checkout revision after gclient sync'
[[ "$actual_angle_revision" == "$expected_angle_revision" ]] || \
  fail "ANGLE checkout revision is $actual_angle_revision, expected $expected_angle_revision"
actual_depot_tools_revision=$(git -C "$depot_tools_root" rev-parse HEAD 2>/dev/null) || \
  fail 'cannot read depot_tools checkout revision after gclient sync'
[[ "$actual_depot_tools_revision" == "$expected_depot_tools_revision" ]] || \
  fail "depot_tools checkout revision is $actual_depot_tools_revision, expected $expected_depot_tools_revision"

# These are the macOS x64 CIPD dependency locations in the pinned ANGLE DEPS.
# Invoke the dependency files directly; depot_tools wrappers have PATH fallback behavior.
gn_entry="$angle_root/buildtools/mac/gn"
ninja_entry="$angle_root/third_party/ninja/ninja"
for entry in "$gn_entry" "$ninja_entry"; do
  [[ -f "$entry" && -x "$entry" && ! -L "$entry" ]] || \
    fail "pinned ANGLE dependency is missing, non-executable, or a symlink: ${entry#"$angle_root"/}"
  parent=$(cd "$(dirname "$entry")" 2>/dev/null && pwd -P) || \
    fail "pinned ANGLE dependency directory is unavailable: ${entry#"$angle_root"/}"
  case "$parent/" in
    "$angle_root/"*) ;;
    *) fail "pinned ANGLE dependency escapes the checkout: ${entry#"$angle_root"/}" ;;
  esac
done

for entry in "$gn_entry" "$ninja_entry"; do
  description=$(/usr/bin/file -b "$entry" 2>/dev/null) || \
    fail "cannot identify pinned ANGLE dependency: ${entry#"$angle_root"/}"
  case "$description" in
    *Mach-O*x86_64*) ;;
    *) fail "pinned ANGLE dependency is not a macOS x86_64 executable: ${entry#"$angle_root"/}" ;;
  esac
done

gn_version=$("$gn_entry" --version 2>&1) || fail 'ANGLE DEPS GN could not start'
ninja_version=$("$ninja_entry" --version 2>&1) || fail 'ANGLE DEPS Ninja could not start'
[[ -n "$gn_version" ]] || fail 'ANGLE DEPS GN returned an empty version'
[[ -n "$ninja_version" ]] || fail 'ANGLE DEPS Ninja returned an empty version'

printf 'ANGLE GN path: buildtools/mac/gn\n'
printf 'ANGLE GN version: %s\n' "$gn_version"
printf 'ANGLE Ninja path: third_party/ninja/ninja\n'
printf 'ANGLE Ninja version: %s\n' "$ninja_version"
