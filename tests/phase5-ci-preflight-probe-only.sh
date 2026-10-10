#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd -P)
script="$repo_root/scripts/phase5-ci-preflight.sh"
tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/phase5-preflight-probe.XXXXXX")
trap 'rm -rf -- "$tmp_dir"' EXIT

mkdir -p "$tmp_dir/bin" "$tmp_dir/source/src"
cat > "$tmp_dir/bin/gn" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ -n "${FAKE_TRACE_LOG:-}" ]]; then
  printf 'gn:%s\n' "$*" >> "$FAKE_TRACE_LOG"
fi
if [[ "$1" == gen ]]; then
  exit 0
elif [[ "$1" == desc && "$4" == type ]]; then
  if [[ "${FAKE_GN_DESC_MODE:-}" == slow ]]; then
    exec sleep 5
  fi
  case "$3" in
    //services/network:network_content_security_policy_fuzzer) printf '%s\n' executable ;;
    //content/browser:content_sms_parser_fuzzer) printf '%s\n' group ;;
    //url:url_unittests) printf '%s\n' executable ;;
    //ui/gfx/geometry:geometry) printf '%s\n' shared_library ;;
    *) exit 2 ;;
  esac
else
  exit 2
fi
EOF
cat > "$tmp_dir/bin/ninja" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ -n "${FAKE_TRACE_LOG:-}" ]]; then
  printf 'ninja:%s\n' "$*" >> "$FAKE_TRACE_LOG"
fi
if [[ "$*" == *"-t targets all"* ]]; then
  printf '%s\n' 'network_content_security_policy_fuzzer: phony' 'content_sms_parser_fuzzer: phony' 'url_unittests: phony' 'ui/gfx/geometry/geometry: phony' 'ui/gfx/geometry:geometry_skia: phony'
elif [[ "$*" == *"-t query network_content_security_policy_fuzzer"* ]]; then
  printf '%s\n' 'network_content_security_policy_fuzzer:' '  input: phony' '    obj/services/network/network_content_security_policy_fuzzer.stamp' '  outputs:' '    all'
elif [[ "$*" == *"-t query content_sms_parser_fuzzer"* ]]; then
  printf '%s\n' 'content_sms_parser_fuzzer:' '  input: phony' '    obj/content/browser/content_sms_parser_fuzzer.stamp' '  outputs:' '    all'
elif [[ "$*" == *"-t query url_unittests"* ]]; then
  printf '%s\n' 'url_unittests:' '  input: phony' '    obj/url/url_unittests.stamp' '  outputs:' '    all'
elif [[ "$*" == *"-n network_content_security_policy_fuzzer"* ]]; then
  if [[ "${FAKE_NINJA_DRY_RUN_MODE:-}" == slow ]]; then
    exec sleep 5
  elif [[ "${FAKE_NINJA_DRY_RUN_MODE:-}" == no-work ]]; then
    printf '%s\n' 'ninja: Entering directory' 'ninja: no work to do.'
    exit 0
  fi
  printf '%s\n' '[1/3] CXX obj/one.o' '[2/3] ACTION generate-header' '[3/3] LINK obj/test'
elif [[ "$*" == *"-n content_sms_parser_fuzzer"* ]]; then
  if [[ "${FAKE_NINJA_DRY_RUN_MODE:-}" == slow ]]; then
    exec sleep 5
  elif [[ "${FAKE_NINJA_DRY_RUN_MODE:-}" == no-work ]]; then
    printf '%s\n' 'ninja: Entering directory' 'ninja: no work to do.'
    exit 0
  fi
  printf '%s\n' '[1/5] CXX obj/one.o' '[2/5] CXX obj/two.o' '[3/5] LINK obj/test' '[4/5] STAMP obj/a.stamp' '[5/5] STAMP obj/b.stamp'
elif [[ "$*" == *"-n url_unittests"* ]]; then
  if [[ "${FAKE_NINJA_DRY_RUN_MODE:-}" == slow ]]; then
    exec sleep 5
  elif [[ "${FAKE_NINJA_DRY_RUN_MODE:-}" == no-work ]]; then
    printf '%s\n' 'ninja: Entering directory' 'ninja: no work to do.'
    exit 0
  fi
  printf '%s\n' '[1/2] CXX obj/url/url_unittests.o' '[2/2] LINK url_unittests'
elif [[ "$*" == *"-n ui/gfx/geometry/geometry"* ]]; then
  printf '%s\n' '[1/2] CXX obj/ui/gfx/geometry/rect.o' '[2/2] SOLINK libgeometry.dylib'
else
  printf 'unexpected ninja invocation: %s\n' "$*" >&2
  exit 2
fi
EOF
cat > "$tmp_dir/bin/autoninja" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
: > "$PREFLIGHT_DIAG_DIR/autoninja-was-run"
exit 99
EOF
cat > "$tmp_dir/bin/siso" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
[[ "$1" == --version ]] || exit 2
[[ -f build/config/siso/.sisoenv ]] || { printf '%s\n' 'project .sisoenv missing' >&2; exit 3; }
printf '%s\n' 'siso test-version-1.2.3'
EOF
chmod +x "$tmp_dir/bin/gn" "$tmp_dir/bin/ninja" "$tmp_dir/bin/autoninja" "$tmp_dir/bin/siso"

mkdir -p "$tmp_dir/source/src/build/config/siso"
touch "$tmp_dir/source/src/build/config/siso/.sisoenv"
post_sync_facts_output=$(
  PATH="$tmp_dir/bin:$PATH" \
  PREFLIGHT_DIAG_DIR="$tmp_dir/post-sync-diag" \
  CHROMIUM_ROOT="$tmp_dir/source" \
  SISO_MODE_REQUESTED=not-run \
  FASTLOCAL_REQUESTED=not-run \
  bash "$script" --post-sync-facts
)
grep -F 'siso_project_env_present_after_sync=true' <<< "$post_sync_facts_output" >/dev/null
grep -F 'siso_version_after_sync=siso test-version-1.2.3' <<< "$post_sync_facts_output" >/dev/null
grep -F 'siso_version_after_sync_status=success' <<< "$post_sync_facts_output" >/dev/null
grep -F 'siso_mode_effective=not-run' <<< "$post_sync_facts_output" >/dev/null

probe_output=$(
  PATH="$tmp_dir/bin:$PATH" \
  PREFLIGHT_DIAG_DIR="$tmp_dir/diag" \
  CHROMIUM_ROOT="$tmp_dir/source" \
  RUN_SMALL_TARGET=false \
  PROBE_SMALL_TARGET=true \
  PROBE_SMALL_TARGET_NINJAS=network_content_security_policy_fuzzer,content_sms_parser_fuzzer,url_unittests \
  PROBE_SMALL_TARGET_GN_LABELS=//services/network:network_content_security_policy_fuzzer,//content/browser:content_sms_parser_fuzzer,//url:url_unittests \
  SMALL_TARGET_MAX_TASKS=4 \
  FAKE_TRACE_LOG="$tmp_dir/normal-trace.log" \
  bash "$script" --graph-only
)
grep -F 'probe_candidate_1_dry_run_task_count=3' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_1_dry_run_output_line_count=3' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_1_gn_type=executable' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_1_dry_run_step_kinds=1:CXX,2:ACTION,3:LINK' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_1_compile_step_count=1' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_1_link_step_count=1' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_1_status=within-cap' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_2_dry_run_task_count=5' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_2_dry_run_output_line_count=5' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_2_gn_type=group' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_2_compile_step_count=2' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_2_link_step_count=1' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_2_status=too-large' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_3_dry_run_task_count=2' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_3_gn_type=executable' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_3_status=within-cap' <<< "$probe_output" >/dev/null
grep -F 'small_target_probe_measurement=task-counted' <<< "$probe_output" >/dev/null
grep -F 'small_target_status=probe-success' <<< "$probe_output" >/dev/null
test ! -e "$tmp_dir/diag/autoninja-was-run"
first_dry_run_line=$(grep -n -F 'ninja:-C ' "$tmp_dir/normal-trace.log" | grep -F -- '-n network_content_security_policy_fuzzer' | head -n 1 | cut -d: -f1)
first_type_query_line=$(grep -n -F 'gn:desc ' "$tmp_dir/normal-trace.log" | head -n 1 | cut -d: -f1)
test "$first_dry_run_line" -lt "$first_type_query_line"

geometry_probe_output=$(
  PATH="$tmp_dir/bin:$PATH" \
  PREFLIGHT_DIAG_DIR="$tmp_dir/geometry-diag" \
  CHROMIUM_ROOT="$tmp_dir/source" \
  RUN_SMALL_TARGET=false \
  PROBE_SMALL_TARGET=true \
  PROBE_SMALL_TARGET_NINJAS=geometry \
  PROBE_SMALL_TARGET_GN_LABELS=//ui/gfx/geometry:geometry \
  SMALL_TARGET_MAX_TASKS=4 \
  FAKE_TRACE_LOG="$tmp_dir/geometry-trace.log" \
  bash "$script" --graph-only
)
grep -F 'probe_candidate_1_target=geometry' <<< "$geometry_probe_output" >/dev/null
grep -F 'probe_candidate_1_ninja_target=ui/gfx/geometry/geometry' <<< "$geometry_probe_output" >/dev/null
grep -F 'probe_candidate_1_ninja_target_resolution=label-derived' <<< "$geometry_probe_output" >/dev/null
grep -F 'probe_candidate_1_dry_run_task_count=2' <<< "$geometry_probe_output" >/dev/null
grep -F 'probe_candidate_1_status=within-cap' <<< "$geometry_probe_output" >/dev/null
grep -F 'ninja:-C ' "$tmp_dir/geometry-trace.log" | grep -F -- '-n ui/gfx/geometry/geometry' >/dev/null
test ! -e "$tmp_dir/geometry-diag/autoninja-was-run"

no_work_output=$(
  PATH="$tmp_dir/bin:$PATH" \
  PREFLIGHT_DIAG_DIR="$tmp_dir/no-work-diag" \
  CHROMIUM_ROOT="$tmp_dir/source" \
  RUN_SMALL_TARGET=false \
  PROBE_SMALL_TARGET=true \
  PROBE_SMALL_TARGET_NINJAS=network_content_security_policy_fuzzer,content_sms_parser_fuzzer,url_unittests \
  PROBE_SMALL_TARGET_GN_LABELS=//services/network:network_content_security_policy_fuzzer,//content/browser:content_sms_parser_fuzzer,//url:url_unittests \
  SMALL_TARGET_MAX_TASKS=4 \
  NINJA_QUERY_BUDGET_SECONDS=1 \
  FAKE_NINJA_DRY_RUN_MODE=no-work \
  bash "$script" --graph-only
)
grep -F 'probe_candidate_1_dry_run_task_count=0' <<< "$no_work_output" >/dev/null
grep -F 'probe_candidate_1_dry_run_output_line_count=2' <<< "$no_work_output" >/dev/null
grep -F 'probe_candidate_1_no_work_line_count=1' <<< "$no_work_output" >/dev/null
grep -F 'probe_candidate_1_status=no-work' <<< "$no_work_output" >/dev/null
grep -F 'probe_candidate_1_dry_run_excerpt=ninja: Entering directory ninja: no work to do.' <<< "$no_work_output" >/dev/null
grep -F 'probe_candidate_1_ninja_query_status=success' <<< "$no_work_output" >/dev/null
grep -F 'probe_candidate_1_ninja_query_excerpt=network_content_security_policy_fuzzer: input: phony obj/services/network/network_content_security_policy_fuzzer.stamp outputs: all' <<< "$no_work_output" >/dev/null
grep -F 'probe_candidate_2_dry_run_task_count=0' <<< "$no_work_output" >/dev/null
grep -F 'probe_candidate_2_status=no-work' <<< "$no_work_output" >/dev/null
grep -F 'probe_candidate_3_status=no-work' <<< "$no_work_output" >/dev/null
grep -F 'small_target_probe_measurement=no-work' <<< "$no_work_output" >/dev/null
grep -F 'graph_inspection_status=success' <<< "$no_work_output" >/dev/null

slow_type_output=$(
  PATH="$tmp_dir/bin:$PATH" \
  PREFLIGHT_DIAG_DIR="$tmp_dir/slow-type-diag" \
  CHROMIUM_ROOT="$tmp_dir/source" \
  RUN_SMALL_TARGET=false \
  PROBE_SMALL_TARGET=true \
  PROBE_SMALL_TARGET_NINJAS=network_content_security_policy_fuzzer,content_sms_parser_fuzzer,url_unittests \
  PROBE_SMALL_TARGET_GN_LABELS=//services/network:network_content_security_policy_fuzzer,//content/browser:content_sms_parser_fuzzer,//url:url_unittests \
  SMALL_TARGET_MAX_TASKS=4 \
  GN_TYPE_QUERY_BUDGET_SECONDS=1 \
  FAKE_GN_DESC_MODE=slow \
  bash "$script" --graph-only
)
grep -F 'probe_candidate_1_dry_run_task_count=3' <<< "$slow_type_output" >/dev/null
grep -F 'probe_candidate_1_dry_run_output_line_count=3' <<< "$slow_type_output" >/dev/null
grep -F 'probe_candidate_1_type_status=timeout' <<< "$slow_type_output" >/dev/null
grep -F 'probe_candidate_2_dry_run_task_count=5' <<< "$slow_type_output" >/dev/null
grep -F 'probe_candidate_2_dry_run_output_line_count=5' <<< "$slow_type_output" >/dev/null
grep -F 'probe_candidate_2_type_status=timeout' <<< "$slow_type_output" >/dev/null
grep -F 'graph_inspection_status=success' <<< "$slow_type_output" >/dev/null
slow_type_classify=$(
  PREFLIGHT_DIAG_DIR="$tmp_dir/slow-type-diag" \
  PREFLIGHT_SOURCE_OUTCOME=success \
  PREFLIGHT_GRAPH_OUTCOME=success \
  RUN_SMALL_TARGET=false \
  PROBE_SMALL_TARGET=true \
  bash "$script" --classify
)
grep -F 'classification=success' <<< "$slow_type_classify" >/dev/null

if PATH="$tmp_dir/bin:$PATH" \
  PREFLIGHT_DIAG_DIR="$tmp_dir/slow-dry-run-diag" \
  CHROMIUM_ROOT="$tmp_dir/source" \
  RUN_SMALL_TARGET=false \
  PROBE_SMALL_TARGET=true \
  PROBE_SMALL_TARGET_NINJAS=network_content_security_policy_fuzzer,content_sms_parser_fuzzer,url_unittests \
  PROBE_SMALL_TARGET_GN_LABELS=//services/network:network_content_security_policy_fuzzer,//content/browser:content_sms_parser_fuzzer,//url:url_unittests \
  SMALL_TARGET_MAX_TASKS=4 \
  GRAPH_INSPECTION_BUDGET_SECONDS=1 \
  FAKE_NINJA_DRY_RUN_MODE=slow \
  bash "$script" --graph-only > "$tmp_dir/slow-dry-run.out" 2>&1; then
  printf '%s\n' 'timed out Ninja dry-run was incorrectly accepted' >&2
  exit 1
fi
grep -F 'graph_inspection_status=timeout' "$tmp_dir/slow-dry-run.out" >/dev/null
timeout_classify=$(
  PREFLIGHT_DIAG_DIR="$tmp_dir/slow-dry-run-diag" \
  PREFLIGHT_SOURCE_OUTCOME=success \
  PREFLIGHT_GRAPH_OUTCOME=failure \
  RUN_SMALL_TARGET=false \
  PROBE_SMALL_TARGET=true \
  bash "$script" --classify || true
)
grep -F 'classification=timeout' <<< "$timeout_classify" >/dev/null

if PATH="$tmp_dir/bin:$PATH" \
  PREFLIGHT_DIAG_DIR="$tmp_dir/missing-diag" \
  CHROMIUM_ROOT="$tmp_dir/source" \
  RUN_SMALL_TARGET=false \
  PROBE_SMALL_TARGET=true \
  PROBE_SMALL_TARGET_NINJAS=missing_target \
  PROBE_SMALL_TARGET_GN_LABELS=//ui/gfx/geometry:missing_target \
  bash "$script" --graph-only > "$tmp_dir/missing-target.out" 2>&1; then
  printf '%s\n' 'missing probe target was incorrectly accepted' >&2
  exit 1
fi
grep -F 'probe_candidate_1_status=not-found' "$tmp_dir/missing-target.out" >/dev/null
grep -F 'probe_candidate_1_related_targets=ui/gfx/geometry/geometry,ui/gfx/geometry:geometry_skia' "$tmp_dir/missing-target.out" >/dev/null
grep -F 'graph_inspection_status=not-found' "$tmp_dir/missing-target.out" >/dev/null

if PATH="$tmp_dir/bin:$PATH" \
  PREFLIGHT_DIAG_DIR="$tmp_dir/mismatched-labels-diag" \
  CHROMIUM_ROOT="$tmp_dir/source" \
  RUN_SMALL_TARGET=false \
  PROBE_SMALL_TARGET=true \
  PROBE_SMALL_TARGET_NINJAS=network_content_security_policy_fuzzer,content_sms_parser_fuzzer \
  PROBE_SMALL_TARGET_GN_LABELS=//services/network:network_content_security_policy_fuzzer \
  bash "$script" --graph-only > "$tmp_dir/mismatched-labels.out" 2>&1; then
  printf '%s\n' 'mismatched probe target/GN label lists were incorrectly accepted' >&2
  exit 1
fi
grep -F 'probe target and GN label counts differ' "$tmp_dir/mismatched-labels.out" >/dev/null

classify_output=$(
  PREFLIGHT_DIAG_DIR="$tmp_dir/diag" \
  PREFLIGHT_SOURCE_OUTCOME=success \
  PREFLIGHT_GRAPH_OUTCOME=success \
  PREFLIGHT_SMALL_TARGET_OUTCOME=skipped \
  RUN_SMALL_TARGET=false \
  PROBE_SMALL_TARGET=true \
  bash "$script" --classify
)
grep -F 'classification=success' <<< "$classify_output" >/dev/null

printf '%s\n' 'phase5 preflight probe-only tests passed'
