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
if [[ "$1" == gen ]]; then
  exit 0
elif [[ "$1" == desc && "$4" == type ]]; then
  case "$3" in
    //services/network:network_content_security_policy_fuzzer) printf '%s\n' executable ;;
    //content/browser:content_sms_parser_fuzzer) printf '%s\n' group ;;
    *) exit 2 ;;
  esac
else
  exit 2
fi
EOF
cat > "$tmp_dir/bin/ninja" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$*" == *"-t targets all"* ]]; then
  printf '%s\n' 'network_content_security_policy_fuzzer: phony' 'content_sms_parser_fuzzer: phony'
elif [[ "$*" == *"-n network_content_security_policy_fuzzer"* ]]; then
  printf '%s\n' '[1/3] CXX obj/one.o' '[2/3] ACTION generate-header' '[3/3] LINK obj/test'
elif [[ "$*" == *"-n content_sms_parser_fuzzer"* ]]; then
  printf '%s\n' '[1/5] CXX obj/one.o' '[2/5] CXX obj/two.o' '[3/5] LINK obj/test' '[4/5] STAMP obj/a.stamp' '[5/5] STAMP obj/b.stamp'
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
chmod +x "$tmp_dir/bin/gn" "$tmp_dir/bin/ninja" "$tmp_dir/bin/autoninja"

probe_output=$(
  PATH="$tmp_dir/bin:$PATH" \
  PREFLIGHT_DIAG_DIR="$tmp_dir/diag" \
  CHROMIUM_ROOT="$tmp_dir/source" \
  RUN_SMALL_TARGET=false \
  PROBE_SMALL_TARGET=true \
  PROBE_SMALL_TARGET_NINJAS=network_content_security_policy_fuzzer,content_sms_parser_fuzzer \
  PROBE_SMALL_TARGET_GN_LABELS=//services/network:network_content_security_policy_fuzzer,//content/browser:content_sms_parser_fuzzer \
  SMALL_TARGET_MAX_TASKS=4 \
  bash "$script" --graph-only
)
grep -F 'probe_candidate_1_dry_run_task_count=3' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_1_gn_type=executable' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_1_dry_run_step_kinds=1:CXX,2:ACTION,3:LINK' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_1_compile_step_count=1' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_1_link_step_count=1' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_1_status=within-cap' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_2_dry_run_task_count=5' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_2_gn_type=group' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_2_compile_step_count=2' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_2_link_step_count=1' <<< "$probe_output" >/dev/null
grep -F 'probe_candidate_2_status=too-large' <<< "$probe_output" >/dev/null
grep -F 'small_target_status=probe-success' <<< "$probe_output" >/dev/null
test ! -e "$tmp_dir/diag/autoninja-was-run"

if PATH="$tmp_dir/bin:$PATH" \
  PREFLIGHT_DIAG_DIR="$tmp_dir/missing-diag" \
  CHROMIUM_ROOT="$tmp_dir/source" \
  RUN_SMALL_TARGET=false \
  PROBE_SMALL_TARGET=true \
  PROBE_SMALL_TARGET_NINJAS=missing_target \
  PROBE_SMALL_TARGET_GN_LABELS=//missing:missing_target \
  bash "$script" --graph-only > "$tmp_dir/missing-target.out" 2>&1; then
  printf '%s\n' 'missing probe target was incorrectly accepted' >&2
  exit 1
fi
grep -F 'probe_candidate_1_status=not-found' "$tmp_dir/missing-target.out" >/dev/null
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
