#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd -P)
supervisor="$repo_root/scripts/phase5-ci-preflight-build-supervisor.py"
tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/phase5-build-supervisor.XXXXXX")
trap 'rm -rf -- "$tmp_dir"' EXIT

mkdir -p "$tmp_dir/bin" "$tmp_dir/source"
cat > "$tmp_dir/bin/autoninja" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*"
printf '%s\n' '[0/3] CXX obj/example.o'
printf '%s\n' 'fake-autoninja-success-output'
EOF
chmod +x "$tmp_dir/bin/autoninja"

output=$(
  PATH="$tmp_dir/bin:$PATH" \
  python3 "$supervisor" \
    --cwd "$tmp_dir/source" \
    --target chromium_owned_probe \
    --build-log "$tmp_dir/build.log" \
    --progress-log "$tmp_dir/progress.log" \
    --timeout-marker "$tmp_dir/timeout" \
    --budget-seconds 10
)

grep -F 'last_observed_ninja_tasks_completed=0' <<< "$output" >/dev/null
grep -F 'last_observed_ninja_tasks_total=3' <<< "$output" >/dev/null
grep -F 'progress_source=last-ninja-marker build_completion_status=success final=true' <<< "$output" >/dev/null
grep -F 'small_target_build_exit=0' <<< "$output" >/dev/null
grep -F 'small_target_build_log_tail_begin' <<< "$output" >/dev/null
grep -F 'fake-autoninja-success-output' <<< "$output" >/dev/null
grep -F 'small_target_build_log_tail_end' <<< "$output" >/dev/null
test ! -e "$tmp_dir/timeout"
