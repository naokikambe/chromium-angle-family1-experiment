#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  printf 'usage: %s DEPOT_TOOLS_DIRECTORY EXPECTED_REVISION\n' "$0" >&2
  exit 64
fi

fail() {
  printf 'depot_tools initialization failed: %s\n' "$1" >&2
  exit 1
}

depot_tools_root=$(cd "$1" && pwd -P) || fail 'checkout directory is unavailable'
expected_revision=$2
[[ "$expected_revision" =~ ^[0-9a-f]{40}$ ]] || fail 'expected revision is malformed'

actual_revision=$(git -C "$depot_tools_root" rev-parse HEAD 2>/dev/null) || \
  fail 'cannot read depot_tools checkout revision'
[[ "$actual_revision" == "$expected_revision" ]] || \
  fail "checkout revision before bootstrap is $actual_revision, expected $expected_revision"

if [[ -n "${FAILURE_STAGE_FILE:-}" ]]; then
  printf 'depot-tools-python-bootstrap\n' > "$FAILURE_STAGE_FILE"
fi
[[ -x "$depot_tools_root/ensure_bootstrap" ]] || \
  fail 'pinned checkout does not contain executable ensure_bootstrap'

export DEPOT_TOOLS_DIR="$depot_tools_root"
export DEPOT_TOOLS_UPDATE=0
# ensure_bootstrap skips the dedicated Python bootstrap when this is 0.
export DEPOT_TOOLS_BOOTSTRAP_PYTHON3=1
export PATH="$depot_tools_root/python-bin:$depot_tools_root:$PATH"

if ! "$depot_tools_root/ensure_bootstrap"; then
  fail 'pinned ensure_bootstrap exited unsuccessfully'
fi

if [[ -n "${FAILURE_STAGE_FILE:-}" ]]; then
  printf 'depot-tools-python-validation\n' > "$FAILURE_STAGE_FILE"
fi
actual_revision=$(git -C "$depot_tools_root" rev-parse HEAD 2>/dev/null) || \
  fail 'cannot read depot_tools checkout revision after bootstrap'
[[ "$actual_revision" == "$expected_revision" ]] || \
  fail "checkout revision after bootstrap is $actual_revision, expected $expected_revision"

python_reldir_file="$depot_tools_root/python3_bin_reldir.txt"
[[ -s "$python_reldir_file" ]] || \
  fail 'python3_bin_reldir.txt is missing after ensure_bootstrap; refusing to run GN or Ninja'
IFS= read -r python_reldir < "$python_reldir_file" || true
[[ -n "$python_reldir" && "$python_reldir" != /* ]] || \
  fail 'python3_bin_reldir.txt does not contain a relative Python directory'
case "/$python_reldir/" in
  */../*) fail 'python3_bin_reldir.txt points outside the pinned checkout' ;;
esac

python_bin_dir=$(cd "$depot_tools_root/$python_reldir" 2>/dev/null && pwd -P) || \
  fail 'the Python directory named by python3_bin_reldir.txt is unavailable'
case "$python_bin_dir/" in
  "$depot_tools_root/"*) ;;
  *) fail 'the Python directory named by python3_bin_reldir.txt escapes the pinned checkout' ;;
esac
[[ -x "$python_bin_dir/python3" ]] || \
  fail 'the dedicated Python binary named by python3_bin_reldir.txt is unavailable'

python_entry="$depot_tools_root/python-bin/python3"
[[ -f "$python_entry" && -x "$python_entry" && ! -L "$python_entry" ]] || \
  fail 'depot_tools/python-bin/python3 is missing, non-executable, or a symlink'

resolved_python=$(command -v python3 || true)
[[ "$resolved_python" == "$python_entry" ]] || \
  fail 'python3 resolves outside the pinned depot_tools checkout'

python_version=$("$python_entry" --version 2>&1) || \
  fail 'the dedicated depot_tools Python could not start'
python_executable=$("$python_entry" -c 'import os, sys; print(os.path.realpath(sys.executable))' 2>/dev/null) || \
  fail 'the dedicated depot_tools Python did not report its executable'
case "$python_executable" in
  "$python_bin_dir"/*) ;;
  *) fail 'python-bin/python3 did not start the Python binary selected by python3_bin_reldir.txt' ;;
esac

printf 'depot_tools revision: %s\n' "$expected_revision"
printf 'depot_tools/python-bin/python3: %s\n' "$python_version"
printf 'depot_tools Python path: python-bin/python3 -> %s\n' "${python_reldir%/}/python3"
