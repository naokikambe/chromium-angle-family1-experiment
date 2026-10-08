#!/usr/bin/env bash
set -euo pipefail

trap 'printf "phase5 CI preflight failed at line %s: %s\n" "$LINENO" "$BASH_COMMAND" >&2' ERR

mode="${1:---inventory-only}"
workspace="${GITHUB_WORKSPACE:-$(cd "$(dirname "$0")/.." && pwd -P)}"
runner_temp="${RUNNER_TEMP:-/tmp}"
diag_dir="${PREFLIGHT_DIAG_DIR:-$runner_temp/phase5-ci-preflight}"
source_root="${CHROMIUM_ROOT:-$runner_temp/phase5-ci-preflight-source}"
source_dir="$source_root/src"
out_dir="$source_dir/out/Phase5Preflight"
metrics_file="$diag_dir/preflight-metrics.txt"
progress_file="$diag_dir/small-target-progress.log"
build_log="$diag_dir/small-target.log"

mkdir -p "$diag_dir"
touch "$metrics_file"

emit() {
  local key="$1"
  local value="${2:-}"
  value=$(printf '%s' "$value" | tr '\n' ' ' | sed 's/[[:space:]][[:space:]]*/ /g')
  printf '%s=%s\n' "$key" "$value" | tee -a "$metrics_file"
}

fail() {
  printf 'preflight failure: %s\n' "$*" >&2
  exit 1
}

sha256_file() {
  shasum -a 256 "$1" | awk '{print $1}'
}

gn_args_text() {
  cat <<'EOF'
is_debug = false
is_component_build = false
is_chrome_branded = false
is_official_build = false
target_cpu = "x64"
use_system_xcode = true
use_clang_modules = false
use_unified_system_module = false
enable_precompiled_headers = false
clang_use_chrome_plugins = false
mac_deployment_target = "13.0"
mac_min_system_version = "13.0"
symbol_level = 0
blink_symbol_level = 0
v8_symbol_level = 0
chrome_pgo_phase = 0
EOF
}

gn_args_sha() {
  gn_args_text | shasum -a 256 | awk '{print $1}'
}

command_path() {
  if command -v "$1" >/dev/null 2>&1; then
    command -v "$1"
  else
    printf 'missing\n'
  fi
}

inventory() {
  emit schema phase5-ci-preflight-v1
  emit run_id "${GITHUB_RUN_ID:-local}"
  emit workflow_sha "${GITHUB_SHA:-unknown}"
  emit target_ref_sha "${PREFLIGHT_TARGET_REF_SHA:-unknown}"
  emit runner_os "${RUNNER_OS:-unknown}"
  emit runner_arch "${RUNNER_ARCH:-unknown}"
  emit uname "$(uname -a 2>/dev/null || true)"
  emit machine "$(uname -m 2>/dev/null || true)"
  if command -v sw_vers >/dev/null 2>&1; then
    emit macos_version "$(sw_vers -productVersion)"
    emit macos_build "$(sw_vers -buildVersion)"
  else
    emit macos_version unavailable
    emit macos_build unavailable
  fi
  if command -v sysctl >/dev/null 2>&1; then
    emit cpu_count "$(sysctl -n hw.ncpu 2>/dev/null || true)"
    emit memory_bytes "$(sysctl -n hw.memsize 2>/dev/null || true)"
  else
    emit cpu_count unavailable
    emit memory_bytes unavailable
  fi
  emit disk "$(df -k "$runner_temp" 2>/dev/null | tail -n 1 || true)"
  emit xcode_select "$(xcode-select -p 2>/dev/null || printf unavailable)"
  emit xcode_version "$(xcodebuild -version 2>/dev/null | tr '\n' ';' || printf unavailable)"
  emit sdk_version "$(xcrun --sdk macosx --show-sdk-version 2>/dev/null || printf unavailable)"
  emit sdk_path "$(xcrun --sdk macosx --show-sdk-path 2>/dev/null || printf unavailable)"
  emit clang_path "$(xcrun --find clang 2>/dev/null || printf unavailable)"
  emit clang_version "$(clang --version 2>/dev/null | head -n 1 || printf unavailable)"
  emit git_version "$(git --version 2>/dev/null || true)"
  emit depot_tools_root "${DEPOT_TOOLS_ROOT:-unknown}"
  emit autoninja_path "$(command_path autoninja)"
  emit gn_path "$(command_path gn)"
  emit siso_path "$(command_path siso)"
  if command -v siso >/dev/null 2>&1; then
    emit siso_version "$(siso --version 2>&1 | head -n 1 || printf unavailable)"
  else
    emit siso_version unavailable
  fi
  emit chromium_revision "${CHROMIUM_REVISION:-unknown}"
  emit angle_revision_input "${ANGLE_REVISION:-unknown}"
  emit deps_file_sha256 "${DEPS_FILE_SHA256:-not-yet-fetched}"
  emit diagnostic_patch_sha256 "${DIAGNOSTIC_PATCH_SHA256:-unknown}"
  emit xcode16_patch_sha256 "${XCODE16_COMPAT_PATCH_SHA256:-unknown}"
  emit gn_args_sha256 "${GN_ARGS_SHA256:-unknown}"
  emit cache_key "${PREFLIGHT_CACHE_KEY:-unknown}"
  emit cache_hit "${PREFLIGHT_CACHE_HIT:-not-run}"
  emit source_present "$([[ -d "$source_dir" ]] && printf true || printf false)"
  emit deps_present "$([[ -f "$source_dir/DEPS" ]] && printf true || printf false)"
  emit run_small_target "${RUN_SMALL_TARGET:-false}"
  emit probe_small_target "${PROBE_SMALL_TARGET:-false}"
  emit probe_small_target_ninjas "${PROBE_SMALL_TARGET_NINJAS:-unset}"
  emit siso_mode_requested "${SISO_MODE_REQUESTED:-unknown}"
  emit siso_mode_effective "${SISO_MODE_EFFECTIVE:-not-run}"
  emit fastlocal_requested "${FASTLOCAL_REQUESTED:-unknown}"
  emit fastlocal_effective "${FASTLOCAL_EFFECTIVE:-not-run}"
  emit localexec_parallelism "${LOCALEXEC_PARALLELISM:-not-run}"
  emit remote_execution_configured "${REMOTE_EXECUTION_CONFIGURED:-unknown}"
  emit remote_cache_configured "${REMOTE_CACHE_CONFIGURED:-unknown}"
}

validate_inputs() {
  if [[ "${RUN_SMALL_TARGET:-false}" == true && "${PROBE_SMALL_TARGET:-false}" == true ]]; then
    fail 'run_small_target and probe_small_target are mutually exclusive'
  fi
  [[ "${CHROMIUM_REVISION:-}" =~ ^[0-9a-f]{40}$ ]] || fail 'invalid Chromium revision'
  [[ "${ANGLE_REVISION:-}" =~ ^[0-9a-f]{40}$ ]] || fail 'invalid ANGLE revision'
  [[ "${PREFLIGHT_TARGET_REF_SHA:-}" =~ ^[0-9a-f]{40}$ ]] || fail 'invalid target ref'
  [[ "${DIAGNOSTIC_PATCH_SHA256:-}" =~ ^[0-9a-f]{64}$ ]] || fail 'invalid URLLoader patch SHA'
  [[ "${XCODE16_COMPAT_PATCH_SHA256:-}" =~ ^[0-9a-f]{64}$ ]] || fail 'invalid Xcode patch SHA'
  [[ "${GN_ARGS_SHA256:-}" == "$(gn_args_sha)" ]] || fail 'GN args SHA mismatch'
  if ! git -C "$workspace" cat-file -e "$PREFLIGHT_TARGET_REF_SHA^{commit}" 2>/dev/null; then
    git -C "$workspace" fetch --no-tags origin "$PREFLIGHT_TARGET_REF_SHA"
  fi
  git -C "$workspace" cat-file -e "$PREFLIGHT_TARGET_REF_SHA^{commit}"
  local diagnostic_patch="$workspace/patches/phase5-chromium-url-loader-diagnostics.patch"
  local compat_patch="$workspace/patches/phase5-chromium-xcode16-compat.patch"
  local target_diagnostic_sha target_compat_sha
  target_diagnostic_sha=$(git -C "$workspace" show "$PREFLIGHT_TARGET_REF_SHA:patches/phase5-chromium-url-loader-diagnostics.patch" | shasum -a 256 | awk '{print $1}')
  target_compat_sha=$(git -C "$workspace" show "$PREFLIGHT_TARGET_REF_SHA:patches/phase5-chromium-xcode16-compat.patch" | shasum -a 256 | awk '{print $1}')
  [[ "$(sha256_file "$diagnostic_patch")" == "$DIAGNOSTIC_PATCH_SHA256" ]] || fail 'URLLoader patch SHA mismatch'
  [[ "$(sha256_file "$compat_patch")" == "$XCODE16_COMPAT_PATCH_SHA256" ]] || fail 'Xcode patch SHA mismatch'
  [[ "$target_diagnostic_sha" == "$DIAGNOSTIC_PATCH_SHA256" ]] || fail 'target ref URLLoader patch SHA mismatch'
  [[ "$target_compat_sha" == "$XCODE16_COMPAT_PATCH_SHA256" ]] || fail 'target ref Xcode patch SHA mismatch'
  emit target_ref_verified true
  emit checked_out_head "$(git -C "$workspace" rev-parse HEAD)"
  emit target_ref_patch_sha_verified true
  emit input_validation success
}

source_deps() {
  command -v gclient >/dev/null 2>&1 || fail 'gclient unavailable'
  mkdir -p "$source_root"
  cat > "$source_root/.gclient" <<EOF
solutions = [
  {
    'managed': False,
    'name': 'src',
    'url': 'https://chromium.googlesource.com/chromium/src.git@${CHROMIUM_REVISION}',
    'custom_deps': {},
    'custom_vars': {},
  },
]
target_os = ['mac']
target_os_only = True
EOF
  local started ended angle diagnostic_patch compat_patch expected
  started=$(date +%s)
  (cd "$source_root" && gclient sync --no-history)
  ended=$(date +%s)
  emit source_deps_duration_seconds "$((ended - started))"
  [[ "$(git -C "$source_dir" rev-parse HEAD)" == "$CHROMIUM_REVISION" ]] || fail 'source revision mismatch'
  angle=$(git -C "$source_dir" show "$CHROMIUM_REVISION:DEPS" | sed -nE "s/^[[:space:]]*'angle_revision':[[:space:]]*'([0-9a-f]{40})'.*/\1/p" | head -n 1)
  [[ "$angle" == "$ANGLE_REVISION" ]] || fail 'DEPS ANGLE revision mismatch'
  DEPS_FILE_SHA256=$(sha256_file "$source_dir/DEPS")
  export DEPS_FILE_SHA256
  emit chromium_revision_resolved "$CHROMIUM_REVISION"
  emit angle_revision_resolved "$angle"
  emit deps_file_sha256 "$DEPS_FILE_SHA256"
  diagnostic_patch="$workspace/patches/phase5-chromium-url-loader-diagnostics.patch"
  compat_patch="$workspace/patches/phase5-chromium-xcode16-compat.patch"
  (cd "$source_dir" && git apply --unidiff-zero --check -- "$compat_patch" && git apply --unidiff-zero -- "$compat_patch")
  (cd "$source_dir" && git apply --unidiff-zero --check -- "$diagnostic_patch" && git apply --unidiff-zero -- "$diagnostic_patch")
  expected=$(printf '%s\n' base/process/launch_mac.cc content/browser/storage_partition_impl.cc services/network/url_loader.cc services/network/url_loader_factory.cc skia/ext/skia_utils_mac.mm)
  [[ "$(git -C "$source_dir" status --short | sed 's/^.. //' | LC_ALL=C sort)" == "$expected" ]] || fail 'unexpected temporary source changes'
  emit patches_applied true
}

run_bounded() {
  local budget_seconds="$1"
  local timeout_marker="$2"
  local log_file="$3"
  shift 3
  rm -f "$timeout_marker"
  python3 - "$budget_seconds" "$timeout_marker" "$log_file" "$@" <<'PY'
import os
import signal
import subprocess
import sys

budget = float(sys.argv[1])
marker = sys.argv[2]
log_path = sys.argv[3]
command = sys.argv[4:]
if not command:
    raise SystemExit("run_bounded requires a command")

with open(log_path, "w", encoding="utf-8") as log_file:
    process = subprocess.Popen(
        command,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        raise SystemExit(process.wait(timeout=budget))
    except subprocess.TimeoutExpired:
        with open(marker, "w", encoding="utf-8"):
            pass
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        raise SystemExit(124)
PY
}

target_exists_in_list() {
  local targets_file="$1"
  local candidate="$2"
  awk -v candidate="$candidate" \
    '{ field = $1; sub(/:$/, "", field); if (field == candidate) { found = 1; exit } } END { exit(found ? 0 : 1) }' \
    "$targets_file"
}

summarize_ninja_plan() {
  awk '
    NF {
      line = $0
      if (line ~ /^\[[0-9]+\/[0-9]+\] /) {
        sub(/^\[[0-9]+\/[0-9]+\] /, "", line)
        kind = line
        sub(/[[:space:]].*$/, "", kind)
        if (kind ~ /^(CC|CXX|OBJC|OBJCXX|ASM|SWIFT)$/) {
          compile++
        } else if (kind ~ /^(LINK|SOLINK|SOLINK_MODULE|LINKED_MODULE|CXX_DYLIB|LIBTOOL|AR|LIPO)$/) {
          link++
        } else {
          other++
        }
        if (steps < 8) {
          if (plan != "") plan = plan ","
          plan = plan (steps + 1) ":" kind
        }
        steps++
      } else if (tolower(line) ~ /no work to do/) {
        no_work++
      } else {
        unclassified++
      }
    }
    END {
      if (plan == "") plan = "none"
      printf "%s\t%d\t%d\t%d\t%d\t%d\t%d\n", plan, steps + 0, compile + 0, link + 0, other + 0, unclassified + 0, no_work + 0
    }
  ' "$1"
}

resolve_small_target_from_list() {
  local targets_file="$1"
  local label="$2"
  local requested="$3"
  local label_path label_dir label_name candidate

  if [[ "$requested" != auto ]]; then
    if target_exists_in_list "$targets_file" "$requested"; then
      printf '%s\t%s\n' "$requested" explicit
      return 0
    fi
    return 1
  fi

  [[ "$label" == //*:* ]] || return 1
  label_path="${label#//}"
  label_dir="${label_path%%:*}"
  label_name="${label_path##*:}"
  for candidate in "$label_dir/$label_name" "$label_name" "$label_dir:$label_name"; do
    if target_exists_in_list "$targets_file" "$candidate"; then
      printf '%s\t%s\n' "$candidate" label-derived
      return 0
    fi
  done
  return 1
}

resolve_target_only() {
  local targets_file="${PREFLIGHT_NINJA_TARGETS_FILE:-$diag_dir/ninja-targets.txt}"
  local label="${SMALL_TARGET_LABEL:-//services:services_unittests}"
  local requested="${SMALL_TARGET_NINJA:-auto}"
  local resolved_info ninja_target resolution
  [[ -f "$targets_file" ]] || fail "target list is not present: $targets_file"
  if ! resolved_info=$(resolve_small_target_from_list "$targets_file" "$label" "$requested"); then
    emit small_target_available false
    emit small_target_label "$label"
    emit small_target_ninja "$requested"
    emit small_target_resolution not-found
    emit small_target_status not-found
    return 1
  fi
  IFS=$'\t' read -r ninja_target resolution <<< "$resolved_info"
  printf '%s\n' "$ninja_target" > "$diag_dir/resolved-small-target"
  emit small_target_available true
  emit small_target_label "$label"
  emit small_target_ninja "$ninja_target"
  emit small_target_resolution "$resolution"
  emit small_target_status success
}

graph_only() {
  [[ -d "$source_dir" ]] || fail 'source is not present'
  mkdir -p "$out_dir"
  gn_args_text > "$out_dir/args.gn"
  local started ended label requested ninja_target resolution inspection_budget
  local ninja_targets_file resolved_info
  started=$(date +%s)
  (cd "$source_dir" && gn gen out/Phase5Preflight > "$diag_dir/gn-stdout.log" 2> "$diag_dir/gn-stderr.log")
  ended=$(date +%s)
  emit gn_duration_seconds "$((ended - started))"
  ninja_targets_file="$diag_dir/ninja-targets.txt"
  (cd "$source_dir" && ninja -C "$out_dir" -t targets all > "$ninja_targets_file" 2> "$diag_dir/ninja-targets-stderr.log")
  emit graph_target_count "$(wc -l < "$ninja_targets_file" | tr -d ' ')"
  if [[ "${RUN_SMALL_TARGET:-false}" != true && "${PROBE_SMALL_TARGET:-false}" != true ]]; then
    emit graph_inspection_status not-run
    emit small_target_status not-run
    return 0
  fi
  local max_tasks dry_run_task_count
  max_tasks="${SMALL_TARGET_MAX_TASKS:-12000}"
  [[ "$max_tasks" =~ ^[0-9]+$ ]] || fail 'invalid small target task cap'
  if [[ "${PROBE_SMALL_TARGET:-false}" == true ]]; then
    local requested_targets requested_labels candidate index candidate_log candidate_label candidate_label_name
    local candidate_type_log candidate_type_info candidate_type candidate_type_status type_query_budget
    local plan_kinds plan_steps compile_steps link_steps other_steps unclassified_lines no_work_lines
    local -a candidates=() candidate_labels=()
    requested_targets="${PROBE_SMALL_TARGET_NINJAS:-}"
    requested_labels="${PROBE_SMALL_TARGET_GN_LABELS:-}"
    [[ -n "$requested_targets" ]] || fail 'probe target list is empty'
    [[ -n "$requested_labels" ]] || fail 'probe GN label list is empty'
    IFS=',' read -r -a candidates <<< "$requested_targets"
    IFS=',' read -r -a candidate_labels <<< "$requested_labels"
    ((${#candidates[@]} > 0 && ${#candidates[@]} <= 8)) || fail 'probe target list must contain 1 to 8 targets'
    ((${#candidate_labels[@]} == ${#candidates[@]})) || fail 'probe target and GN label counts differ'
    local seen_candidates=' '
    inspection_budget="${GRAPH_INSPECTION_BUDGET_SECONDS:-300}"
    type_query_budget="${GN_TYPE_QUERY_BUDGET_SECONDS:-60}"
    index=0
    for candidate in "${candidates[@]}"; do
      candidate="$(printf '%s' "$candidate" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
      candidate_label="${candidate_labels[$((index))]}"
      candidate_label="$(printf '%s' "$candidate_label" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
      [[ "$candidate" =~ ^[A-Za-z0-9_./:-]+$ ]] || fail "invalid probe target name: $candidate"
      [[ "$candidate_label" =~ ^//[A-Za-z0-9_./-]+:[A-Za-z0-9_.-]+$ ]] || fail "invalid probe GN label: $candidate_label"
      candidate_label_name="${candidate_label##*:}"
      [[ "$candidate_label_name" == "$candidate" ]] || fail "probe GN label does not match Ninja target: $candidate_label"
      [[ "$seen_candidates" != *" $candidate "* ]] || fail "duplicate probe target: $candidate"
      seen_candidates+="$candidate "
      index=$((index + 1))
      if ! target_exists_in_list "$ninja_targets_file" "$candidate"; then
        emit "probe_candidate_${index}_target" "$candidate"
        emit "probe_candidate_${index}_status" not-found
        emit graph_inspection_status not-found
        return 1
      fi
      candidate_log="$diag_dir/small-target-probe-$index.log"
      if ! run_bounded "$inspection_budget" "$diag_dir/probe-target-$index-timeout" "$candidate_log" ninja -C "$out_dir" -n "$candidate"; then
        if [[ -f "$diag_dir/probe-target-$index-timeout" ]]; then
          emit "probe_candidate_${index}_status" timeout
          emit graph_inspection_status timeout
          return 124
        fi
        emit "probe_candidate_${index}_status" probe-failure
        emit graph_inspection_status probe-failure
        return 1
      fi

      # GN's type lookup walks the generated graph and can be slow on Chromium.
      # It is supplemental metadata: capture it after the useful Ninja dry-run,
      # bound it tightly, and keep the task-count result if the lookup stalls.
      candidate_type_log="$diag_dir/small-target-probe-type-$index.log"
      candidate_type=unknown
      candidate_type_status=lookup-failure
      if run_bounded "$type_query_budget" "$diag_dir/probe-target-type-$index-timeout" "$candidate_type_log" gn desc "$out_dir" "$candidate_label" type; then
        candidate_type="$(tr -d '\r\n' < "$candidate_type_log")"
        if [[ "$candidate_type" =~ ^[a-z_]+$ ]]; then
          candidate_type_status=success
        else
          candidate_type=unknown
          candidate_type_status=invalid-output
        fi
      elif [[ -f "$diag_dir/probe-target-type-$index-timeout" ]]; then
        candidate_type_status=timeout
      fi

      dry_run_task_count="$(awk 'NF { count++ } END { print count + 0 }' "$candidate_log")"
      candidate_type_info="$(summarize_ninja_plan "$candidate_log")"
      IFS=$'\t' read -r plan_kinds plan_steps compile_steps link_steps other_steps unclassified_lines no_work_lines <<< "$candidate_type_info"
      emit "probe_candidate_${index}_target" "$candidate"
      emit "probe_candidate_${index}_gn_label" "$candidate_label"
      emit "probe_candidate_${index}_gn_type" "$candidate_type"
      emit "probe_candidate_${index}_type_status" "$candidate_type_status"
      emit "probe_candidate_${index}_dry_run_task_count" "$dry_run_task_count"
      emit "probe_candidate_${index}_dry_run_step_kinds" "$plan_kinds"
      emit "probe_candidate_${index}_recognized_step_count" "$plan_steps"
      emit "probe_candidate_${index}_compile_step_count" "$compile_steps"
      emit "probe_candidate_${index}_link_step_count" "$link_steps"
      emit "probe_candidate_${index}_other_step_count" "$other_steps"
      emit "probe_candidate_${index}_unclassified_line_count" "$unclassified_lines"
      emit "probe_candidate_${index}_no_work_line_count" "$no_work_lines"
      if (( dry_run_task_count > max_tasks )); then
        emit "probe_candidate_${index}_status" too-large
      else
        emit "probe_candidate_${index}_status" within-cap
      fi
    done
    emit small_target_probe_only true
    emit small_target_probe_count "$index"
    emit small_target_max_tasks "$max_tasks"
    emit small_target_status probe-success
    emit graph_inspection_status success
    return 0
  fi
  label="${SMALL_TARGET_LABEL:-//services:services_unittests}"
  requested="${SMALL_TARGET_NINJA:-auto}"
  inspection_budget="${GRAPH_INSPECTION_BUDGET_SECONDS:-300}"
  if ! resolved_info=$(resolve_small_target_from_list "$ninja_targets_file" "$label" "$requested"); then
    emit small_target_available false
    emit small_target_label "$label"
    emit small_target_ninja "$requested"
    emit small_target_resolution not-found
    emit small_target_probe target-list
    emit small_target_status not-found
    emit graph_inspection_status not-found
    return 1
  fi
  IFS=$'\t' read -r ninja_target resolution <<< "$resolved_info"
  printf '%s\n' "$ninja_target" > "$diag_dir/resolved-small-target"
  emit small_target_label "$label"
  emit small_target_ninja "$ninja_target"
  emit small_target_resolution "$resolution"
  emit small_target_max_tasks "$max_tasks"
  emit small_target_probe_only "${PROBE_SMALL_TARGET:-false}"
  # The target list is already generated for the graph count. The bounded
  # dry-run validates the resolved executable target without another graph walk.
  if run_bounded "$inspection_budget" "$diag_dir/graph-inspection-timeout" "$diag_dir/small-target-dry-run.log" ninja -C "$out_dir" -n "$ninja_target"; then
    dry_run_task_count="$(awk 'NF { count++ } END { print count + 0 }' "$diag_dir/small-target-dry-run.log")"
    emit small_target_dry_run_task_count "$dry_run_task_count"
    if (( dry_run_task_count > max_tasks )); then
      emit small_target_available false
      emit small_target_status too-large
      emit graph_inspection_status too-large
      return 1
    fi
    emit small_target_available true
    emit small_target_probe ninja-dry-run
    emit graph_inspection_status success
  elif [[ -f "$diag_dir/graph-inspection-timeout" ]]; then
    emit graph_inspection_status timeout
    return 124
  elif grep -Eiq 'unknown target|unknown target name' "$diag_dir/small-target-dry-run.log"; then
    emit small_target_available false
    emit small_target_probe ninja-dry-run
    emit small_target_status not-found
    emit graph_inspection_status not-found
    return 1
  else
    emit small_target_available unknown
    emit small_target_probe ninja-dry-run
    emit small_target_status probe-failure
    emit graph_inspection_status probe-failure
    return 1
  fi
}

sample_progress() {
  local now elapsed p completed total remaining rate estimate
  now=$(date +%s)
  elapsed=$((now - ${BUILD_START_SECONDS:-now}))
  p=$(grep -Eo '\[[0-9]+/[0-9]+\]' "$build_log" | tail -n 1 || true)
  completed=$(printf '%s' "$p" | sed -nE 's/^\[([0-9]+)\/([0-9]+)\]$/\1/p')
  total=$(printf '%s' "$p" | sed -nE 's/^\[([0-9]+)\/([0-9]+)\]$/\2/p')
  completed="${completed:-unknown}"
  total="${total:-unknown}"
  if [[ "$completed" =~ ^[0-9]+$ && "$total" =~ ^[0-9]+$ && "$elapsed" -gt 0 ]]; then
    remaining=$((total - completed))
    rate=$(awk -v c="$completed" -v e="$elapsed" 'BEGIN { printf "%.4f", c / e }')
    estimate=$(awk -v r="$remaining" -v q="$rate" 'BEGIN { if (q > 0) printf "%d", r / q; else print "unknown" }')
  else
    remaining=unknown
    rate=unknown
    estimate=unknown
  fi
  printf 'sample_utc=%s elapsed_seconds=%s tasks_completed=%s tasks_total=%s tasks_remaining=%s completed_per_second=%s estimated_remaining_seconds=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$elapsed" "$completed" "$total" "$remaining" "$rate" "$estimate" >> "$progress_file"
}

small_target() {
  [[ "${RUN_SMALL_TARGET:-false}" == true ]] || { emit small_target_status not-run; return 0; }
  if [[ "${PROBE_SMALL_TARGET:-false}" == true ]]; then
    emit small_target_status probe-only
    return 1
  fi
  [[ -f "$diag_dir/small-target-dry-run.log" ]] || { emit small_target_status preflight-rejected; return 1; }
  command -v autoninja >/dev/null 2>&1 || fail 'autoninja unavailable'
  : > "$progress_file"
  : > "$build_log"
  BUILD_START_SECONDS=$(date +%s)
  export BUILD_START_SECONDS
  local build_pid monitor_pid watchdog_pid rc ninja_target
  if [[ -f "$diag_dir/resolved-small-target" ]]; then
    IFS= read -r ninja_target < "$diag_dir/resolved-small-target"
  else
    ninja_target="${SMALL_TARGET_NINJA:-}"
  fi
  [[ -n "$ninja_target" && "$ninja_target" != auto ]] || {
    emit small_target_status preflight-rejected
    return 1
  }
  emit small_target_ninja "$ninja_target"
  (cd "$source_dir" && autoninja -C out/Phase5Preflight "$ninja_target" > "$build_log" 2>&1) &
  build_pid=$!
  (
    while kill -0 "$build_pid" 2>/dev/null; do
      sample_progress
      sleep 60
    done
  ) &
  monitor_pid=$!
  (
    sleep "${SMALL_TARGET_BUDGET_SECONDS:-1200}"
    if kill -0 "$build_pid" 2>/dev/null; then
      : > "$diag_dir/small-target-timeout"
      kill -TERM "$build_pid" 2>/dev/null || true
    fi
  ) &
  watchdog_pid=$!
  set +e
  wait "$build_pid"
  rc=$?
  set -e
  kill "$monitor_pid" "$watchdog_pid" 2>/dev/null || true
  wait "$monitor_pid" "$watchdog_pid" 2>/dev/null || true
  sample_progress || true
  if [[ -f "$diag_dir/small-target-timeout" ]]; then
    emit small_target_status timeout
    return 124
  fi
  emit small_target_exit "$rc"
  if [[ "$rc" -eq 0 ]]; then
    emit small_target_status success
    return 0
  fi
  if grep -E '(^|[[:space:]])(FAILED:|fatal error:|error:)' "$build_log" >/dev/null 2>&1; then
    emit small_target_status compiler_failure
  else
    emit small_target_status environment_failure
  fi
  return "$rc"
}

classify() {
  local source_outcome="${PREFLIGHT_SOURCE_OUTCOME:-unknown}"
  local graph_outcome="${PREFLIGHT_GRAPH_OUTCOME:-unknown}"
  local small_target_outcome="${PREFLIGHT_SMALL_TARGET_OUTCOME:-${PREFLIGHT_PROBE_OUTCOME:-unknown}}"
  local classification=unknown
  if [[ "$source_outcome" != success ]]; then
    classification=environment_failure
  elif [[ -f "$diag_dir/small-target-timeout" || -f "$diag_dir/graph-inspection-timeout" ]] ||
    grep -Eq '^(graph_inspection_status|small_target_status)=timeout$' "$metrics_file"; then
    classification=timeout
  elif [[ "$graph_outcome" != success ]]; then
    if grep -E 'graph_inspection_status=(not-found|too-large)' "$metrics_file" >/dev/null 2>&1; then
      classification=preflight_rejected
    else
      classification=environment_failure
    fi
  elif [[ "${RUN_SMALL_TARGET:-false}" != true ]]; then
    # Graph-only and probe-only preflights are intentional successful modes.
    # The compile step is skipped in both modes and must not turn a valid graph
    # result into an environment failure.
    if [[ "${PROBE_SMALL_TARGET:-false}" == true ]] &&
      ! grep -F 'small_target_status=probe-success' "$metrics_file" >/dev/null 2>&1; then
      classification=preflight_rejected
    else
      classification=success
    fi
  elif [[ "$small_target_outcome" != success ]]; then
    if grep -E '(^|[[:space:]])(FAILED:|fatal error:|error:)' "$build_log" >/dev/null 2>&1; then
      classification=compiler_failure
    else
      classification=environment_failure
    fi
  elif grep -F 'small_target_status=success' "$metrics_file" >/dev/null 2>&1; then
    classification=success
  else
    classification=preflight_rejected
  fi
  emit classification "$classification"
  if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    {
      printf '%s\n' 'Phase 5 CI preflight summary'
      printf 'classification=%s\n' "$classification"
      printf 'target_ref=%s\n' "${PREFLIGHT_TARGET_REF_SHA:-unknown}"
      printf 'chromium_revision=%s\n' "${CHROMIUM_REVISION:-unknown}"
      printf 'angle_revision=%s\n' "${ANGLE_REVISION:-unknown}"
      printf 'cache_hit=%s\n' "${PREFLIGHT_CACHE_HIT:-not-run}"
      printf '%s\n' '--- metrics ---'
      sed -n '1,240p' "$metrics_file"
      if [[ -f "$progress_file" ]]; then
        printf '%s\n' '--- progress ---'
        tail -n 40 "$progress_file"
      fi
    } >> "$GITHUB_STEP_SUMMARY"
  fi
  [[ "$classification" == success ]]
}

case "$mode" in
  --inventory-only) inventory ;;
  --validate-inputs) validate_inputs ;;
  --source-deps) source_deps ;;
  --resolve-target) resolve_target_only ;;
  --graph-only) graph_only ;;
  --small-target) small_target ;;
  --classify) classify ;;
  *) fail "unknown mode: $mode" ;;
esac
