#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf 'usage: %s CHROME_VERSION RESULTS_DIRECTORY [--loader-trace]\n' "$0" >&2
  exit 64
}

[[ $# -ge 2 && $# -le 3 ]] || usage
chrome_version=$1
results_dir=$2
loader_trace=false
if [[ $# -eq 3 ]]; then
  [[ "$3" == '--loader-trace' ]] || usage
  loader_trace=true
fi
[[ "$chrome_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo 'chrome_version must be four numeric components' >&2
  exit 64
}
[[ "$results_dir" == /* ]] || { echo 'results directory must be absolute' >&2; exit 64; }
[[ ! -e "$results_dir" && ! -L "$results_dir" ]] || { echo 'results directory already exists' >&2; exit 1; }
mkdir -p "$results_dir"

readonly EXPECTED_PLATFORM='mac-x64'
readonly KNOWN_GOOD_URL='https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json'
readonly PROBE_SECONDS=20
readonly SAMPLE_INTERVAL_SECONDS=0.05
probe_tmp=''
profile_dir=''
browser_pid=''
sampler_pid=''
sampler_active=''
stderr_watcher_pid=''
stderr_watcher_active=''
stderr_tail_pid=''
stderr_event_fifo=''
browser_executable=''
browser_profile_arg=''
browser_app=''
log_stream_pid=''
cleanup_done=false
browser_started=false
browser_observed=false
browser_exit='not-started'
gpu_seen=false
gpu_pid_count=0
gpu_pid_count_ps=0
gpu_pid_count_stderr=0
browser_pid_count=0
final_gpu_command=''
observation_complete=false
infrastructure_failure=''
log_stream_exit='not-started'
browser_alive_at_deadline=false

record_failure() {
  infrastructure_failure=$1
  printf 'probe infrastructure failure: %s\n' "$1" >&2
}

write_final_result() {
  local final_exit=$1
  {
    printf 'SCHEMA=phase3d-chrome-launch-probe-v1\n'
    printf 'CHROME_VERSION=%s\n' "$chrome_version"
    printf 'BROWSER_STARTED=%s\n' "$browser_started"
    printf 'BROWSER_OBSERVED=%s\n' "$browser_observed"
    printf 'BROWSER_ALIVE_AT_DEADLINE=%s\n' "$browser_alive_at_deadline"
    printf 'BROWSER_EXIT=%s\n' "$browser_exit"
    printf 'BROWSER_PID_COUNT=%s\n' "$browser_pid_count"
    printf 'GPU_SEEN=%s\n' "$gpu_seen"
    printf 'GPU_PID_COUNT=%s\n' "$gpu_pid_count"
    printf 'GPU_PID_COUNT_PROCESS_SAMPLER=%s\n' "$gpu_pid_count_ps"
    printf 'GPU_PID_COUNT_STDERR=%s\n' "$gpu_pid_count_stderr"
    printf 'FINAL_GPU_COMMAND=%s\n' "$final_gpu_command"
    printf 'LOADER_TRACE_REQUESTED=%s\n' "$loader_trace"
    printf 'OBSERVATION_COMPLETE=%s\n' "$observation_complete"
    printf 'LOG_STREAM_EXIT=%s\n' "$log_stream_exit"
    printf 'INFRASTRUCTURE_FAILURE=%s\n' "$infrastructure_failure"
    printf 'PROBE_EXIT_STATUS=%s\n' "$final_exit"
  } > "$results_dir/authoritative-result.txt"
}

process_command_for_pid() {
  ps -ww -p "$1" -o command= 2>/dev/null || true
}

safe_test_process() {
  local pid=$1 command_line
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  command_line=$(process_command_for_pid "$pid")
  [[ -n "$command_line" && "$command_line" == *"$browser_executable"* &&
    "$command_line" == *"--user-data-dir=$profile_dir"* ]]
}

safe_test_gpu_helper() {
  local pid=$1 command_line
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  command_line=$(process_command_for_pid "$pid")
  [[ -n "$command_line" && "$command_line" == *"$browser_app/"* &&
    "$command_line" == *'--type=gpu-process'* ]]
}

capture_gpu_process_evidence() {
  local pid=$1 source=$2 attempt
  {
    printf 'source=%s\n' "$source"
    printf 'detected_utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf 'pid=%s\n' "$pid"
    ps -ww -p "$pid" -o pid=,ppid=,stat=,etime=,command= 2>&1 || true
  } > "$results_dir/gpu-$pid-detection.txt"

  for attempt in 1 2 3; do
    if safe_test_gpu_helper "$pid"; then
      lsof -nP -p "$pid" > "$results_dir/gpu-$pid-lsof-$attempt.txt" 2>&1 || true
    else
      break
    fi
    sleep 0.05
  done
  if safe_test_gpu_helper "$pid"; then
    vmmap "$pid" > "$results_dir/gpu-$pid-vmmap.txt" 2>&1 || true
  fi
}

start_gpu_collector_once() {
  local pid=$1 source=$2
  [[ "$pid" =~ ^[0-9]+$ ]] || return 0
  if mkdir "$gpu_seen_dir/$pid" 2>/dev/null; then
    capture_gpu_process_evidence "$pid" "$source" &
    printf '%s\n' "$!" > "$gpu_collectors_dir/$pid.pid"
  fi
}

watch_gpu_stderr() {
  local line stamp pid
  while IFS= read -r line; do
    [[ -e "$stderr_watcher_active" ]] || break
    if [[ "$line" =~ \[([0-9]+):[0-9]+: ]] &&
      [[ "$line" == *'gpu-process'* || "$line" == *'EGL display'* ||
         "$line" == *'GLDisplayEGL'* || "$line" == *'GPU process due to errors'* ||
         "$line" == *'InitializeGLNoExtensionsOneOff'* ]]; then
      pid=${BASH_REMATCH[1]}
      stamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
      printf '%s\t%s\tstderr\t%s\n' "$stamp" "$pid" "$line" >> "$results_dir/gpu-pid-events.tsv"
      start_gpu_collector_once "$pid" 'stderr'
    fi
  done
}

start_stderr_observer() {
  stderr_event_fifo="$probe_tmp/browser-stderr-events.fifo"
  mkfifo "$stderr_event_fifo"
  stderr_watcher_active="$probe_tmp/stderr-watcher-active"
  touch "$stderr_watcher_active"
  tail -n 0 -F "$results_dir/browser-stderr.txt" > "$stderr_event_fifo" 2> "$results_dir/stderr-tail-errors.txt" &
  stderr_tail_pid=$!
  watch_gpu_stderr < "$stderr_event_fifo" &
  stderr_watcher_pid=$!
}

stop_stderr_observer() {
  local status=0 watcher_command tail_command
  [[ -n "$stderr_watcher_active" ]] && rm -f "$stderr_watcher_active"
  if [[ -n "$stderr_tail_pid" ]] && kill -0 "$stderr_tail_pid" 2>/dev/null; then
    tail_command=$(process_command_for_pid "$stderr_tail_pid")
    if [[ "$tail_command" == *'tail -n 0 -F'* && "$tail_command" == *"$results_dir/browser-stderr.txt"* ]]; then
      kill -TERM "$stderr_tail_pid" 2>/dev/null || true
    else
      record_failure 'could not verify stderr tail process for cleanup'
      status=1
    fi
  fi
  if [[ -n "$stderr_watcher_pid" ]]; then
    watcher_command=$(process_command_for_pid "$stderr_watcher_pid")
    [[ -n "$watcher_command" ]] || true
    wait "$stderr_watcher_pid" 2>/dev/null || status=1
    stderr_watcher_pid=''
  fi
  if [[ -n "$stderr_tail_pid" ]]; then
    wait "$stderr_tail_pid" 2>/dev/null || true
    stderr_tail_pid=''
  fi
  stderr_watcher_active=''
  return "$status"
}

safe_test_bundle_helper() {
  local pid=$1 command_line
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  command_line=$(process_command_for_pid "$pid")
  [[ -n "$command_line" && "$command_line" == *"$browser_app/"* ]]
}

safe_probe_process() {
  safe_test_process "$1" || safe_test_bundle_helper "$1"
}

is_descendant_in_snapshot() {
  local candidate=$1 root=$2 snapshot=$3 cursor=$1 parent step
  for step in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
    [[ "$cursor" == "$root" ]] && return 0
    parent=$(awk -v target="$cursor" '$1 == target {print $2; exit}' "$snapshot")
    [[ "$parent" =~ ^[0-9]+$ && "$parent" != "$cursor" ]] || return 1
    cursor=$parent
  done
  return 1
}

cleanup_test_processes() {
  local snapshot="$results_dir/processes-before-cleanup.txt"
  local line pid ppid stat command_line target_pid remaining=0 attempt
  [[ "$cleanup_done" == true ]] && return 0
  cleanup_done=true
  [[ -n "$browser_pid" && -n "$browser_executable" && -n "$profile_dir" ]] || return 0
  ps -wwaxo pid=,ppid=,stat=,command= > "$snapshot" || return 1

  # Signal only the exact launch process and processes shown in this snapshot
  # as its descendants, after rechecking their unique profile and executable.
  if kill -0 "$browser_pid" 2>/dev/null; then
    if ! safe_test_process "$browser_pid"; then
      record_failure 'launch PID is alive but no longer matches the test executable/profile'
      return 1
    fi
    kill -TERM "$browser_pid" 2>/dev/null || true
  fi
  for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    kill -0 "$browser_pid" 2>/dev/null || break
    sleep 0.1
  done

  while IFS= read -r line; do
    read -r pid ppid stat command_line <<< "$line"
    [[ "$pid" =~ ^[0-9]+$ && "$pid" != "$browser_pid" ]] || continue
    [[ "$command_line" == *"$browser_executable"* && "$command_line" == *"--user-data-dir=$profile_dir"* ]] ||
      [[ "$command_line" == *"$browser_app/"* ]] || continue
    is_descendant_in_snapshot "$pid" "$browser_pid" "$snapshot" || continue
    if safe_probe_process "$pid"; then
      kill -TERM "$pid" 2>/dev/null || true
    fi
  done < "$snapshot"

  for attempt in 1 2 3 4 5 6 7 8 9 10; do
    remaining=0
    while IFS= read -r line; do
      read -r pid ppid stat command_line <<< "$line"
      [[ "$pid" =~ ^[0-9]+$ ]] || continue
      if safe_probe_process "$pid" && { [[ "$pid" == "$browser_pid" ]] || is_descendant_in_snapshot "$pid" "$browser_pid" "$snapshot"; }; then
        remaining=$((remaining + 1))
      fi
    done < <(ps -wwaxo pid=,ppid=,stat=,command=)
    [[ "$remaining" -eq 0 ]] && break
    sleep 0.1
  done

  if [[ "$remaining" -gt 0 ]]; then
    while IFS= read -r line; do
      read -r pid ppid stat command_line <<< "$line"
      [[ "$pid" =~ ^[0-9]+$ ]] || continue
      if safe_probe_process "$pid" && { [[ "$pid" == "$browser_pid" ]] || is_descendant_in_snapshot "$pid" "$browser_pid" "$snapshot"; }; then
        kill -KILL "$pid" 2>/dev/null || true
      fi
    done < <(ps -wwaxo pid=,ppid=,stat=,command=)
    sleep 0.2
  fi

  remaining=0
  while IFS= read -r line; do
    read -r pid ppid stat command_line <<< "$line"
    [[ "$pid" =~ ^[0-9]+$ ]] || continue
    if safe_probe_process "$pid" && { [[ "$pid" == "$browser_pid" ]] || is_descendant_in_snapshot "$pid" "$browser_pid" "$snapshot"; }; then
      remaining=$((remaining + 1))
    fi
  done < <(ps -wwaxo pid=,ppid=,stat=,command=)
  [[ "$remaining" -eq 0 ]]
}

finish_on_exit() {
  local status=$?
  trap - EXIT
  if ! stop_stderr_observer; then
    record_failure 'stderr GPU observer failed during exit cleanup'
    status=1
  fi
  if [[ -n "$sampler_active" ]]; then
    : > "$sampler_active"
    rm -f "$sampler_active"
  fi
  if [[ -n "$sampler_pid" ]]; then
    if ! wait "$sampler_pid" 2>/dev/null; then
      record_failure 'process sampler or GPU evidence collector failed during exit cleanup'
      status=1
    fi
    sampler_pid=''
  fi
  if [[ "$cleanup_done" != true && -n "$browser_pid" ]]; then
    cleanup_test_processes || { record_failure 'test browser cleanup failed'; status=1; }
  fi
  stop_log_stream
  if [[ -n "$results_dir" && ! -f "$results_dir/authoritative-result.txt" ]]; then
    observation_complete=false
    write_final_result "$status"
  fi
  exit "$status"
}

stop_log_stream() {
  local log_command status
  [[ -n "$log_stream_pid" ]] || return 0
  if kill -0 "$log_stream_pid" 2>/dev/null; then
    log_command=$(process_command_for_pid "$log_stream_pid")
    if [[ "$log_command" == *'log stream'* && "$log_command" == *"$log_predicate"* ]]; then
      kill -TERM "$log_stream_pid" 2>/dev/null || true
    else
      record_failure 'could not verify unified log stream process for cleanup'
    fi
  fi
  set +e
  wait "$log_stream_pid"
  status=$?
  set -e
  log_stream_exit=$status
  printf 'log_stream_exit_status=%s\n' "$status" >> "$results_dir/probe-metadata.txt"
  log_stream_pid=''
}
trap finish_on_exit EXIT

for command in curl jq unzip shasum codesign spctl system_profiler ioreg ps lsof vmmap log plutil xattr tail mkfifo env; do
  command -v "$command" >/dev/null 2>&1 || { record_failure "required command unavailable: $command"; exit 1; }
done

probe_tmp=$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/phase3d-cft-probe.XXXXXX") || {
  record_failure 'could not create probe temporary directory'
  exit 1
}
profile_dir=$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/phase3d-cft-profile.XXXXXX") || {
  record_failure 'could not create isolated browser profile'
  exit 1
}
readonly browser_profile_arg="--user-data-dir=$profile_dir"
artifact_json="$probe_tmp/known-good-versions-with-downloads.json"
zip_path="$probe_tmp/chrome-for-testing.zip"
extract_dir="$probe_tmp/extracted"
mkdir "$extract_dir"

date -u '+probe_started_utc=%Y-%m-%dT%H:%M:%SZ' > "$results_dir/probe-metadata.txt"
printf 'requested_version=%s\nplatform=%s\nknown_good_json=%s\n' \
  "$chrome_version" "$EXPECTED_PLATFORM" "$KNOWN_GOOD_URL" >> "$results_dir/probe-metadata.txt"

curl -fsSL "$KNOWN_GOOD_URL" -o "$artifact_json" || {
  record_failure 'could not download Chrome for Testing known-good versions JSON'
  exit 1
}
download_count=$(jq --arg version "$chrome_version" '[.versions[] | select(.version == $version) | .downloads.chrome[] | select(.platform == "mac-x64")] | length' "$artifact_json") || {
  record_failure 'could not parse CfT version metadata'
  exit 1
}
[[ "$download_count" == 1 ]] || { record_failure 'exact CfT mac-x64 version entry was not unique'; exit 1; }
download_url=$(jq -er --arg version "$chrome_version" '.versions[] | select(.version == $version) | .downloads.chrome[] | select(.platform == "mac-x64") | .url' "$artifact_json") || {
  record_failure 'CfT mac-x64 download URL was unavailable'
  exit 1
}
[[ "$download_url" == https://storage.googleapis.com/chrome-for-testing-public/* ]] || {
  record_failure 'CfT download URL host was unexpected'
  exit 1
}
curl -fL --retry 2 --retry-delay 2 "$download_url" -o "$zip_path" || {
  record_failure 'Chrome for Testing download failed'
  exit 1
}
zip_sha256=$(shasum -a 256 "$zip_path" | awk '{print $1}') || {
  record_failure 'could not hash CfT archive'
  exit 1
}
printf 'download_url=%s\narchive_sha256=%s\n' "$download_url" "$zip_sha256" >> "$results_dir/probe-metadata.txt"
unzip -q "$zip_path" -d "$extract_dir" || { record_failure 'CfT archive extraction failed'; exit 1; }
browser_app="$extract_dir/chrome-mac-x64/Google Chrome for Testing.app"
browser_executable="$browser_app/Contents/MacOS/Google Chrome for Testing"
[[ -d "$browser_app" && -x "$browser_executable" ]] || { record_failure 'CfT app or executable missing'; exit 1; }
actual_version=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$browser_app/Contents/Info.plist") || {
  record_failure 'could not read CfT app version'
  exit 1
}
[[ "$actual_version" == "$chrome_version" ]] || { record_failure "CfT bundle version mismatch: $actual_version"; exit 1; }
printf 'bundle_version=%s\n' "$actual_version" >> "$results_dir/probe-metadata.txt"
printf 'loader_trace_requested=%s\n' "$loader_trace" >> "$results_dir/probe-metadata.txt"

sw_vers > "$results_dir/runner-sw-vers.txt" 2>&1 || true
uname -a > "$results_dir/runner-uname.txt" 2>&1 || true
system_profiler SPDisplaysDataType > "$results_dir/system-profiler-displays.txt" 2>&1 || true
system_profiler SPHardwareDataType 2>&1 | sed -E '/Serial Number|Hardware UUID|Provisioning UDID/d' > "$results_dir/system-profiler-hardware-redacted.txt" || true
ioreg -l -w0 2>&1 | grep -Ei 'IOAccelerator|IODisplayConnect|class-code|model-name' > "$results_dir/ioreg-display-gpu.txt" || true
ps -wwaxo pid=,ppid=,stat=,command= > "$results_dir/process-snapshot-before.txt" || {
  record_failure 'could not capture initial process snapshot'
  exit 1
}
grep -E 'WindowServer|Chrome for Testing|Google Chrome' "$results_dir/process-snapshot-before.txt" > "$results_dir/windowserver-browser-processes-before.txt" || true

set +e
codesign -dvvv "$browser_app" > "$results_dir/codesign-details.txt" 2>&1
codesign_details_status=$?
codesign --verify --deep --strict --verbose=4 "$browser_app" > "$results_dir/codesign-strict.txt" 2>&1
codesign_strict_status=$?
spctl --assess --type execute --verbose=4 "$browser_app" > "$results_dir/gatekeeper-assessment.txt" 2>&1
gatekeeper_status=$?
set -e
printf 'codesign_details_status=%s\ncodesign_strict_status=%s\ngatekeeper_assessment_status=%s\n' \
  "$codesign_details_status" "$codesign_strict_status" "$gatekeeper_status" >> "$results_dir/probe-metadata.txt"
codesign -dr - "$browser_app" > "$results_dir/codesign-designated-requirement.txt" 2>&1 || true
xattr -lr "$browser_app" > "$results_dir/cft-extended-attributes-readonly.txt" 2>&1 || true

log_predicate='process == "taskgated" OR process == "amfid" OR process == "syspolicyd" OR process == "runningboardd" OR process == "kernel" OR process CONTAINS[c] "Chrome for Testing" OR process CONTAINS[c] "Google Chrome"'
log show --last 2m --style compact --predicate "$log_predicate" > "$results_dir/unified-log-before.txt" 2>&1 || true
crash_roots=("$HOME/Library/Logs/DiagnosticReports" "/Library/Logs/DiagnosticReports")
snapshot_crash_reports() {
  local destination=$1 root
  : > "$destination"
  for root in "${crash_roots[@]}"; do
    if [[ -d "$root" ]]; then
      find "$root" -maxdepth 1 -type f -print >> "$destination" 2>> "$results_dir/crash-report-snapshot-errors.txt" || true
    fi
  done
  sort -u "$destination" -o "$destination"
}
snapshot_crash_reports "$results_dir/crash-reports-before.txt"
log stream --style compact --predicate "$log_predicate" > "$results_dir/unified-log-stream.txt" 2>&1 &
log_stream_pid=$!

sampler_active="$probe_tmp/sampler-active"
touch "$sampler_active"
gpu_seen_dir="$probe_tmp/gpu-seen"
gpu_collectors_dir="$probe_tmp/gpu-collectors"
mkdir "$gpu_seen_dir"
mkdir "$gpu_collectors_dir"
gpu_observations="$results_dir/gpu-observations.tsv"
: > "$gpu_observations"
gpu_pid_events="$results_dir/gpu-pid-events.tsv"
: > "$gpu_pid_events"
browser_observations="$results_dir/browser-observations.tsv"
: > "$browser_observations"

sample_session_processes() {
  local process_file="$probe_tmp/processes-current.txt" stamp line pid ppid stat command_line
  while [[ -e "$sampler_active" ]]; do
    stamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    ps -wwaxo pid=,ppid=,stat=,command= > "$process_file" || return 1
    while IFS= read -r line; do
      read -r pid ppid stat command_line <<< "$line"
      [[ "$pid" =~ ^[0-9]+$ ]] || continue
      if [[ "$command_line" == *"$browser_profile_arg"* && "$command_line" == *"$browser_executable"* ]] ||
        [[ "$command_line" == *"$browser_app/"* ]]; then
        printf '%s\n' "$line" >> "$results_dir/process-snapshots-during.txt"
      else
        continue
      fi
      if [[ "$command_line" == *"$browser_app/"* && "$command_line" == *'--type=gpu-process'* ]]; then
        printf '%s\t%s\t%s\t%s\t%s\n' "$stamp" "$pid" "$ppid" "$stat" "$command_line" >> "$gpu_observations"
        printf '%s\t%s\tprocess-sampler\t%s\n' "$stamp" "$pid" "$command_line" >> "$gpu_pid_events"
        start_gpu_collector_once "$pid" 'process-sampler'
      elif [[ "$command_line" == *"$browser_executable"* && "$command_line" != *'--type='* ]]; then
        printf '%s\t%s\t%s\t%s\t%s\n' "$stamp" "$pid" "$ppid" "$stat" "$command_line" >> "$browser_observations"
      fi
    done < "$process_file"
    sleep "$SAMPLE_INTERVAL_SECONDS"
  done
  local collector_pid_file collector_pid wait_status=0
  for collector_pid_file in "$gpu_collectors_dir"/*.pid; do
    [[ -f "$collector_pid_file" ]] || continue
    collector_pid=$(cat "$collector_pid_file")
    [[ "$collector_pid" =~ ^[0-9]+$ ]] || { wait_status=1; continue; }
    wait "$collector_pid" || wait_status=1
  done
  return "$wait_status"
}

: > "$results_dir/process-snapshots-during.txt"
 : > "$results_dir/browser-stderr.txt"
 : > "$results_dir/browser-stdout.txt"
sample_session_processes &
sampler_pid=$!
start_stderr_observer
sleep 0.1
launch_utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
printf 'launch_utc=%s\nbrowser_command=%q --no-first-run --no-default-browser-check --disable-background-networking --disable-sync --enable-logging=stderr --v=1 about:blank\n' \
  "$launch_utc" "$browser_executable" > "$results_dir/launch-command.txt"
printf 'loader_trace=%s\n' "$loader_trace" >> "$results_dir/launch-command.txt"
if [[ "$loader_trace" == true ]]; then
  env DYLD_PRINT_LIBRARIES=1 "$browser_executable" "$browser_profile_arg" --no-first-run --no-default-browser-check \
    --disable-background-networking --disable-sync --enable-logging=stderr --v=1 about:blank \
    > "$results_dir/browser-stdout.txt" 2> "$results_dir/browser-stderr.txt" &
else
  "$browser_executable" "$browser_profile_arg" --no-first-run --no-default-browser-check \
    --disable-background-networking --disable-sync --enable-logging=stderr --v=1 about:blank \
    > "$results_dir/browser-stdout.txt" 2> "$results_dir/browser-stderr.txt" &
fi
browser_pid=$!
browser_started=true
printf 'launch_pid=%s\n' "$browser_pid" >> "$results_dir/launch-command.txt"

tick=0
while [[ "$tick" -lt $((PROBE_SECONDS * 20)) ]]; do
  sleep "$SAMPLE_INTERVAL_SECONDS"
  tick=$((tick + 1))
done

if kill -0 "$browser_pid" 2>/dev/null; then browser_alive_at_deadline=true; fi
if [[ -s "$browser_observations" ]]; then browser_observed=true; fi
cleanup_test_processes || { record_failure 'could not safely terminate all test browser processes'; }
set +e
wait "$browser_pid"
browser_exit=$?
set -e
browser_pid=''

: > "$sampler_active"
rm -f "$sampler_active"
set +e
wait "$sampler_pid"
sampler_status=$?
set -e
sampler_pid=''
[[ "$sampler_status" -eq 0 ]] || record_failure "process sampler failed with status $sampler_status"
stop_stderr_observer || record_failure 'stderr GPU observer failed'
awk -F '\t' 'NF >= 5 {pid=$2; if (!(pid in first)) {first[pid]=$1; order[++n]=pid} last[pid]=$1; ppid[pid]=$3; stat[pid]=$4; command[pid]=$5} END {for (i=1;i<=n;i++) {pid=order[i]; print first[pid] "\t" last[pid] "\t" pid "\t" ppid[pid] "\t" stat[pid] "\t" command[pid]}}' \
  "$gpu_observations" > "$results_dir/gpu-pid-first-last.tsv"
awk -F '\t' 'NF >= 5 {pid=$2; if (!(pid in first)) {first[pid]=$1; order[++n]=pid} last[pid]=$1; ppid[pid]=$3; stat[pid]=$4; command[pid]=$5} END {for (i=1;i<=n;i++) {pid=order[i]; print first[pid] "\t" last[pid] "\t" pid "\t" ppid[pid] "\t" stat[pid] "\t" command[pid]}}' \
  "$browser_observations" > "$results_dir/browser-pid-first-last.tsv"
awk -F '\t' 'NF >= 4 {pid=$2; source=$3; if (!(pid in first)) {first[pid]=$1; order[++n]=pid} last[pid]=$1; sources[pid]=sources[pid] (sources[pid] ? "," : "") source; evidence[pid]++} END {for (i=1;i<=n;i++) {pid=order[i]; print first[pid] "\t" last[pid] "\t" pid "\t" sources[pid] "\t" evidence[pid]}}' \
  "$gpu_pid_events" > "$results_dir/gpu-pid-all-sources.tsv"
gpu_pid_count=$(awk 'END {print NR+0}' "$results_dir/gpu-pid-all-sources.tsv")
gpu_pid_count_ps=$(awk 'END {print NR+0}' "$results_dir/gpu-pid-first-last.tsv")
gpu_pid_count_stderr=$(awk -F '\t' '$3 == "stderr" {seen[$2]=1} END {for (pid in seen) count++; print count+0}' "$gpu_pid_events")
browser_pid_count=$(awk 'END {print NR+0}' "$results_dir/browser-pid-first-last.tsv")
[[ "$gpu_pid_count" -gt 0 ]] && gpu_seen=true
if [[ "$gpu_pid_count" -gt 0 ]]; then
  final_gpu_command=$(tail -n 1 "$gpu_observations" | cut -f5-)
fi

grep -Eai 'ANGLE|SwiftShader|fallback|GPU process|GL_RENDERER|GL_VENDOR|command line' \
  "$results_dir/browser-stdout.txt" "$results_dir/browser-stderr.txt" "$results_dir/process-snapshots-during.txt" \
  > "$results_dir/gpu-switches-fallback.txt" || true
grep -E 'dyld\[[0-9]+\].*(Libraries/(libEGL|libGLESv2)\.dylib|Google Chrome for Testing Framework)' \
  "$results_dir/browser-stderr.txt" > "$results_dir/dyld-library-loads.txt" || true
ps -wwaxo pid=,ppid=,stat=,command= > "$results_dir/process-snapshot-after.txt" || {
  record_failure 'could not capture final process snapshot'
}
grep -E 'WindowServer|Chrome for Testing|Google Chrome' "$results_dir/process-snapshot-after.txt" > "$results_dir/windowserver-browser-processes-after.txt" || true
log show --last 2m --style compact --predicate "$log_predicate" > "$results_dir/unified-log-after.txt" 2>&1 || true
if [[ -n "$log_stream_pid" ]]; then
  stop_log_stream
fi
snapshot_crash_reports "$results_dir/crash-reports-after.txt"
comm -13 "$results_dir/crash-reports-before.txt" "$results_dir/crash-reports-after.txt" > "$results_dir/crash-reports-added.txt" || true
mkdir "$results_dir/new-crash-reports"
while IFS= read -r crash_report; do
  [[ -f "$crash_report" ]] && cp "$crash_report" "$results_dir/new-crash-reports/" || true
done < "$results_dir/crash-reports-added.txt"

[[ -n "$infrastructure_failure" ]] || observation_complete=true
final_exit_status=0
if [[ -n "$infrastructure_failure" ]]; then final_exit_status=1; fi
write_final_result "$final_exit_status"
if [[ -n "$infrastructure_failure" ]]; then exit 1; fi
exit 0
