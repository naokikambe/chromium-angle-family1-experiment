#!/usr/bin/env bash

# Synthetic-testable GPU evidence predicates shared by the VM probe.

phase3_gpu_process_map_has_both_paths() {
  local results_dir=$1 libegl=$2 libglesv2=$3 evidence_file pid
  while IFS= read -r pid; do
    [[ "$pid" =~ ^[0-9]+$ ]] || continue
    local egl_seen=false glesv2_seen=false
    for evidence_file in "$results_dir"/gpu-"$pid"-lsof-*.txt "$results_dir"/gpu-"$pid"-vmmap.txt; do
      [[ -f "$evidence_file" ]] || continue
      grep -F -- "$libegl" "$evidence_file" >/dev/null && egl_seen=true
      grep -F -- "$libglesv2" "$evidence_file" >/dev/null && glesv2_seen=true
    done
    if [[ "$egl_seen" == true && "$glesv2_seen" == true ]]; then
      printf '%s\n' "$pid"
      return 0
    fi
  done < <(find "$results_dir" -maxdepth 1 -type f \
    \( -name 'gpu-*-lsof-*.txt' -o -name 'gpu-*-vmmap.txt' \) -print \
    | sed -E 's#.*/gpu-([0-9]+)-.*#\1#' | sort -u)
  return 1
}

phase3_egl_initialization_failure_observed() {
  local log_file=$1
  grep -Eq 'Initialization of all \([0-9]+\) EGL display types failed|GLDisplayEGL::Initialize([^[:cntrl:]]*)failed' \
    "$log_file"
}
