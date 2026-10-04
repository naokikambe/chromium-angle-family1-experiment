#!/usr/bin/env bash
set -euo pipefail

readonly PHASE3_SCRIPT_NAME='phase5-unsigned-chromium-u0u1'
readonly SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd -P)
readonly REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd -P)
readonly SNAPSHOT_BASE_URL='https://commondatastorage.googleapis.com/chromium-browser-snapshots/Mac'
readonly ANGLE_REPOSITORY='naokikambe/chromium-angle-family1-experiment'
source "$SCRIPT_DIR/phase3-test-copy-common.sh"

usage() {
  printf 'usage: %s --snapshot-position POSITION --snapshot-sha256 SHA256 --expected-chromium-revision REVISION --expected-angle-revision REVISION --angle-build-run-id RUN_ID --results-dir DIRECTORY\n' "$0" >&2
  exit 64
}

snapshot_position=''
snapshot_sha256=''
expected_chromium_revision=''
expected_angle_revision=''
angle_build_run_id=''
results_dir=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    --snapshot-position)
      [[ $# -ge 2 ]] || usage
      snapshot_position=$2
      shift 2
      ;;
    --snapshot-sha256)
      [[ $# -ge 2 ]] || usage
      snapshot_sha256=$2
      shift 2
      ;;
    --expected-chromium-revision)
      [[ $# -ge 2 ]] || usage
      expected_chromium_revision=$2
      shift 2
      ;;
    --expected-angle-revision)
      [[ $# -ge 2 ]] || usage
      expected_angle_revision=$2
      shift 2
      ;;
    --angle-build-run-id)
      [[ $# -ge 2 ]] || usage
      angle_build_run_id=$2
      shift 2
      ;;
    --results-dir)
      [[ $# -ge 2 ]] || usage
      results_dir=$2
      shift 2
      ;;
    *) usage ;;
  esac
done

phase3_reject_root
[[ "$snapshot_position" =~ ^[0-9]+$ ]] || usage
[[ "$snapshot_sha256" =~ ^[0-9a-f]{64}$ ]] || usage
[[ "$expected_chromium_revision" =~ ^[0-9a-f]{40}$ ]] || usage
[[ "$expected_angle_revision" =~ ^[0-9a-f]{40}$ ]] || usage
[[ "$angle_build_run_id" =~ ^[0-9]+$ ]] || usage
[[ "$results_dir" == /* ]] || phase3_fail 'results directory must be an absolute path'
[[ ! -e "$results_dir" && ! -L "$results_dir" ]] || phase3_fail "refusing an existing results directory: $results_dir"
phase3_reject_symlink_components "$results_dir"
phase3_reject_applications_path "$results_dir"
case "$results_dir/" in
  "$REPO_ROOT/"*) phase3_fail 'results directory may not be inside the Git repository' ;;
esac
mkdir -p "$results_dir"

for command in curl unzip shasum codesign file lipo otool plutil python3 gh ditto jq diff comm find sort; do
  command -v "$command" >/dev/null 2>&1 || phase3_fail "required command is unavailable: $command"
done

work_parent=$(dirname "$results_dir")
work_dir=$(mktemp -d "$work_parent/phase5-unsigned-u0u1.XXXXXX")
server_pid=''
cleanup() {
  if [[ -n "$server_pid" ]] && kill -0 "$server_pid" 2>/dev/null; then
    server_command=$(ps -p "$server_pid" -o command= 2>/dev/null || true)
    if [[ "$server_command" == *'phase5-unsigned-loopback-server.py'* ]]; then
      kill -TERM "$server_pid" 2>/dev/null || true
      wait "$server_pid" 2>/dev/null || true
    fi
  fi
}
trap cleanup EXIT

archive_url="$SNAPSHOT_BASE_URL/$snapshot_position/chrome-mac.zip"
revisions_url="$SNAPSHOT_BASE_URL/$snapshot_position/REVISIONS"
archive="$work_dir/chrome-mac.zip"
revisions="$work_dir/REVISIONS"
printf 'snapshot_archive_url=%s\n' "$archive_url" > "$results_dir/input-acquisition.txt"
printf 'snapshot_revisions_url=%s\n' "$revisions_url" >> "$results_dir/input-acquisition.txt"
curl --fail --location --retry 2 --output "$archive" "$archive_url"
actual_archive_sha256=$(shasum -a 256 "$archive" | awk '{print $1}')
printf 'snapshot_archive_sha256=%s\n' "$actual_archive_sha256" >> "$results_dir/input-acquisition.txt"
[[ "$actual_archive_sha256" == "$snapshot_sha256" ]] || phase3_fail 'official Chromium archive SHA-256 mismatch'
curl --fail --location --retry 2 --output "$revisions" "$revisions_url"
cp "$revisions" "$results_dir/REVISIONS"

jq -e --arg snapshot_position "$snapshot_position" \
  '(.chromium_revision | tostring) == $snapshot_position' "$revisions" >/dev/null ||
  phase3_fail 'official REVISIONS chromium_revision did not match the snapshot position'
snapshot_chromium_revision=$(jq -er '.got_revision | strings | select(test("^[0-9a-f]{40}$"))' "$revisions") ||
  phase3_fail 'official REVISIONS got_revision was not a 40-character lowercase SHA'
snapshot_angle_revision=$(jq -er '.got_angle_revision | strings | select(test("^[0-9a-f]{40}$"))' "$revisions") ||
  phase3_fail 'official REVISIONS got_angle_revision was not a 40-character lowercase SHA'
[[ "$snapshot_chromium_revision" == "$expected_chromium_revision" ]] ||
  phase3_fail "official Chromium revision mismatch: $snapshot_chromium_revision"

extract_dir="$work_dir/extract"
mkdir "$extract_dir"
unzip -q "$archive" -d "$extract_dir"
source_app="$extract_dir/chrome-mac/Chromium.app"
[[ -d "$source_app" && ! -L "$source_app" ]] || phase3_fail 'official archive did not contain Chromium.app at the expected path'
source_executable="$source_app/Contents/MacOS/Chromium"
source_framework="$source_app/Contents/Frameworks/Chromium Framework.framework/Versions/Current"
source_libraries="$source_framework/Libraries"
[[ -f "$source_executable" && -d "$source_libraries" ]] || phase3_fail 'official Chromium bundle structure is incomplete'
source_file_output=$(file "$source_executable")
printf '%s\n' "$source_file_output" > "$results_dir/source-file.txt"
printf '%s\n' "$source_file_output" | grep -F 'x86_64' >/dev/null || phase3_fail 'official Chromium executable is not x86_64'
lipo -info "$source_executable" > "$results_dir/source-lipo.txt" 2>&1
plutil -p "$source_app/Contents/Info.plist" > "$results_dir/source-info-plist.txt"

angle_artifact="$work_dir/angle-artifact"
mkdir "$work_dir/angle-parent"
"$SCRIPT_DIR/download-angle-artifact.sh" "$angle_build_run_id" "$angle_artifact"
"$SCRIPT_DIR/verify-phase5-runtime-artifact.sh" "$angle_artifact" > "$results_dir/angle-runtime-verification.txt"
angle_manifest="$angle_artifact/ANGLE_RELEASE_MANIFEST"
angle_artifact_name=$(phase3_manifest_value "$angle_manifest" ARTIFACT_NAME)
angle_chromium_revision=$(phase3_manifest_value "$angle_manifest" CHROMIUM_REVISION)
angle_revision=$(phase3_manifest_value "$angle_manifest" ANGLE_REVISION)
angle_runtime_device_ready=$(phase3_manifest_value "$angle_manifest" RUNTIME_DEVICE_READY)
angle_runtime_opt_in=$(phase3_manifest_value "$angle_manifest" RUNTIME_OPT_IN)
[[ "$angle_revision" == "$expected_angle_revision" ]] || phase3_fail 'ANGLE artifact revision does not match the approved input'
[[ "$angle_runtime_device_ready" == false ]] || phase3_fail 'ANGLE artifact unexpectedly changes RUNTIME_DEVICE_READY'
angle_manifest_sha256=$(shasum -a 256 "$angle_manifest" | awk '{print $1}')
angle_artifact_digest=$(gh api "repos/$ANGLE_REPOSITORY/actions/runs/$angle_build_run_id/artifacts" \
  --jq ".artifacts[] | select(.name == \"$angle_artifact_name\") | .digest")
[[ "$angle_artifact_digest" =~ ^sha256:[0-9a-f]{64}$ ]] || phase3_fail 'ANGLE artifact digest was not available'

printf 'snapshot_chromium_revision=%s\n' "$snapshot_chromium_revision" >> "$results_dir/input-acquisition.txt"
printf 'snapshot_angle_revision=%s\n' "$snapshot_angle_revision" >> "$results_dir/input-acquisition.txt"
printf 'angle_artifact_name=%s\n' "$angle_artifact_name" >> "$results_dir/input-acquisition.txt"
printf 'angle_artifact_digest=%s\n' "$angle_artifact_digest" >> "$results_dir/input-acquisition.txt"
printf 'angle_manifest_sha256=%s\n' "$angle_manifest_sha256" >> "$results_dir/input-acquisition.txt"
printf 'angle_chromium_revision=%s\n' "$angle_chromium_revision" >> "$results_dir/input-acquisition.txt"
printf 'angle_revision=%s\n' "$angle_revision" >> "$results_dir/input-acquisition.txt"
printf 'runtime_device_ready=%s\n' "$angle_runtime_device_ready" >> "$results_dir/input-acquisition.txt"

server_log="$results_dir/loopback-server.log"
server_port_file="$work_dir/loopback-port"
server_stdout="$results_dir/loopback-server.stdout"
server_stderr="$results_dir/loopback-server.stderr"
loopback_server_port=0
{
  printf 'python3_path='
  command -v python3
  python3 --version
  python3 -c 'print("python3_exec_ok")'
} > "$results_dir/python3-preflight.txt" 2>&1
python3 -u "$SCRIPT_DIR/phase5-unsigned-loopback-server.py" \
  --directory "$REPO_ROOT/tests/fixtures" \
  --log "$server_log" \
  --port-file "$server_port_file" \
  --port "$loopback_server_port" > "$server_stdout" 2> "$server_stderr" &
server_pid=$!
ps -p "$server_pid" -o pid=,ppid=,stat=,etime=,command= > "$results_dir/loopback-server-process.txt" 2>&1 || true
for _ in $(seq 1 50); do
  [[ -s "$server_port_file" ]] && break
  kill -0 "$server_pid" 2>/dev/null || break
  sleep 0.2
done
if [[ ! -s "$server_port_file" ]]; then
  ps -p "$server_pid" -o pid=,ppid=,stat=,etime=,command= >> "$results_dir/loopback-server-process.txt" 2>&1 || true
  cat "$server_stdout" "$server_stderr" >&2 || true
  phase3_fail 'loopback server did not publish its port'
fi
loopback_port=$(tr -d '[:space:]' < "$server_port_file")
[[ "$loopback_port" =~ ^[0-9]+$ ]] || phase3_fail 'loopback server port is invalid'
curl --fail --silent --show-error --max-time 2 "http://127.0.0.1:$loopback_port/healthz" > "$results_dir/loopback-healthz.txt"
loopback_url="http://127.0.0.1:$loopback_port/probe"

bundle_target_list() {
  local app=$1
  {
    printf '%s\n' "$app"
    find -P "$app/Contents" \( -type d \( -name '*.app' -o -name '*.framework' \) -o -type f \( -name '*.dylib' -o -perm -111 \) \) -print
  } | sort -u
}

validate_unsigned_bundle() {
  local app=$1 evidence_dir=$2 target index=0 code_output
  mkdir -p "$evidence_dir"
  : > "$evidence_dir/targets.txt"
  while IFS= read -r target; do
    index=$((index + 1))
    printf '%s\n' "$target" >> "$evidence_dir/targets.txt"
    code_output=$(printf '%s/target-%04d.txt' "$evidence_dir" "$index")
    if codesign -dvvv --strict "$target" > "$code_output" 2>&1; then
      phase3_fail "unexpected signature on unsigned target: $target"
    fi
    grep -F 'code object is not signed at all' "$code_output" >/dev/null ||
      phase3_fail "unsigned target had an unexpected codesign state: $target"
  done < <(bundle_target_list "$app")
  printf 'UNSIGNED_TARGET_COUNT=%s\n' "$index" > "$evidence_dir/summary.txt"
}

record_bundle_components() {
  local app=$1 output=$2 libraries=$3
  {
    printf 'main_executable_sha256='
    shasum -a 256 "$app/Contents/MacOS/Chromium" | awk '{print $1}'
    printf 'framework_sha256='
    shasum -a 256 "$app/Contents/Frameworks/Chromium Framework.framework/Versions/Current/Chromium Framework" | awk '{print $1}'
    printf 'libEGL_sha256='
    if [[ -f "$libraries/libEGL.dylib" ]]; then shasum -a 256 "$libraries/libEGL.dylib" | awk '{print $1}'; else printf 'absent\n'; fi
    printf 'libGLESv2_sha256='
    if [[ -f "$libraries/libGLESv2.dylib" ]]; then shasum -a 256 "$libraries/libGLESv2.dylib" | awk '{print $1}'; else printf 'absent\n'; fi
    printf 'framework_libraries_listing=\n'
    find -P "$libraries" -maxdepth 1 -mindepth 1 -print | sort
  } > "$output"
}

record_inventory() {
  local app=$1 output=$2
  {
    find -P "$app" -type f -print | sed "s#^$app/##"
    find -P "$app" -type l -print | sed "s#^$app/##"
  } | sort > "$output"
}

run_cdp_probe() {
  local app=$1 profile=$2 url=$3 output=$4 expected_title=$5 expected_prefix=$6
  shift 6
  mkdir -p "$profile" "$output"
  local args=(
    --executable "$app/Contents/MacOS/Chromium"
    --profile "$profile"
    --url "$url"
    --results-dir "$output"
  )
  [[ -n "$expected_title" ]] && args+=(--expected-title "$expected_title")
  [[ -n "$expected_prefix" ]] && args+=(--expected-title-prefix "$expected_prefix")
  while [[ $# -gt 0 ]]; do
    if [[ "$1" == env:* ]]; then
      args+=(--browser-env "${1#env:}")
    else
      args+=(--browser-arg "$1")
    fi
    shift
  done
  python3 "$SCRIPT_DIR/phase5-unsigned-cdp-probe.py" "${args[@]}"
}

validate_url_result() {
  local output=$1 url=$2
  jq -e --arg url "$url" \
    '.probe_success == true and .frame_navigated == true and .load_event_fired == true and .document_url == $url and .title == "Phase 5 unsigned Chromium loopback"' \
    "$output/cdp-result.json" >/dev/null
}

validate_webgl_result() {
  local output=$1
  jq -e \
    '.probe_success == true and .frame_navigated == true and .load_event_fired == true and (.webgl_result.schema == "phase3d-webgl-smoke-v1") and (.webgl_result.page_loaded == true)' \
    "$output/cdp-result.json" >/dev/null
}

run_case() {
  local case_name=$1 angle_added=$2 app case_dir profile libraries framework
  case_dir="$results_dir/$case_name"
  app="$work_dir/$case_name/Chromium.app"
  profile="$work_dir/$case_name/profile"
  mkdir -p "$work_dir/$case_name"
  ditto "$source_app" "$app"
  framework="$app/Contents/Frameworks/Chromium Framework.framework/Versions/Current"
  libraries="$framework/Libraries"
  [[ -d "$libraries" ]] || phase3_fail "$case_name framework Libraries directory is missing"
  if [[ "$angle_added" == false ]]; then
    [[ ! -e "$libraries/libEGL.dylib" && ! -e "$libraries/libGLESv2.dylib" ]] ||
      phase3_fail 'official stock Chromium unexpectedly already contains replacement ANGLE dylibs'
  else
    cp "$angle_artifact/libEGL.dylib" "$libraries/libEGL.dylib"
    cp "$angle_artifact/libGLESv2.dylib" "$libraries/libGLESv2.dylib"
    phase3_verify_hash "$libraries/libEGL.dylib" "$(phase3_manifest_value "$angle_manifest" LIBEGL_SHA256)"
    phase3_verify_hash "$libraries/libGLESv2.dylib" "$(phase3_manifest_value "$angle_manifest" LIBGLESV2_SHA256)"
  fi
  mkdir -p "$case_dir"
  file "$app/Contents/MacOS/Chromium" > "$case_dir/file.txt"
  lipo -info "$app/Contents/MacOS/Chromium" > "$case_dir/lipo.txt" 2>&1
  grep -F 'x86_64' "$case_dir/file.txt" >/dev/null || phase3_fail "$case_name executable is not x86_64"
  file "$app/Contents/Frameworks/Chromium Framework.framework/Versions/Current/Chromium Framework" > \
    "$case_dir/framework-file.txt"
  lipo -info "$app/Contents/Frameworks/Chromium Framework.framework/Versions/Current/Chromium Framework" > \
    "$case_dir/framework-lipo.txt" 2>&1
  grep -F 'x86_64' "$case_dir/framework-file.txt" >/dev/null || phase3_fail "$case_name framework is not x86_64"
  plutil -p "$app/Contents/Info.plist" > "$case_dir/info-plist.txt"
  validate_unsigned_bundle "$app" "$case_dir/unsigned-codesign"
  record_inventory "$app" "$case_dir/inventory.txt"
  record_bundle_components "$app" "$case_dir/components.txt" "$libraries"
  otool -L "$app/Contents/Frameworks/Chromium Framework.framework/Versions/Current/Chromium Framework" > "$case_dir/framework-dependencies.txt"
  if [[ "$angle_added" == true ]]; then
    file "$libraries/libEGL.dylib" "$libraries/libGLESv2.dylib" > "$case_dir/angle-files.txt"
    lipo -info "$libraries/libEGL.dylib" > "$case_dir/libEGL-lipo.txt" 2>&1
    lipo -info "$libraries/libGLESv2.dylib" > "$case_dir/libGLESv2-lipo.txt" 2>&1
    test "$(grep -c 'x86_64' "$case_dir/angle-files.txt")" -eq 2
    otool -L "$libraries/libEGL.dylib" > "$case_dir/libEGL-dependencies.txt"
    otool -L "$libraries/libGLESv2.dylib" > "$case_dir/libGLESv2-dependencies.txt"
  fi

  run_cdp_probe "$app" "$profile/url" "$loopback_url" "$case_dir/url" \
    'Phase 5 unsigned Chromium loopback' '' '--disable-gpu'
  validate_url_result "$case_dir/url" "$loopback_url"
  grep -F 'GET /probe ' "$server_log" >/dev/null || phase3_fail "$case_name loopback server did not receive /probe"

  run_cdp_probe "$app" "$profile/webgl" "file://$REPO_ROOT/tests/fixtures/phase3d-webgl-smoke.html" \
    "$case_dir/webgl" '' 'phase3d-webgl-smoke:' '--disable-gpu'
  validate_webgl_result "$case_dir/webgl"
  if [[ "$angle_added" == true ]]; then
    run_cdp_probe "$app" "$profile/angle-webgl" "file://$REPO_ROOT/tests/fixtures/phase3d-webgl-smoke.html" \
      "$case_dir/angle-webgl" '' 'phase3d-webgl-smoke:' \
      '--use-gl=angle' '--use-angle=metal' '--use-dynamic-angle' "$angle_runtime_opt_in" \
      'env:DYLD_PRINT_LIBRARIES=1'
    validate_webgl_result "$case_dir/angle-webgl"
    grep -E 'libEGL\.dylib|libGLESv2\.dylib' "$case_dir/angle-webgl/browser-stderr.log" > \
      "$case_dir/angle-webgl/angle-load-marker.txt"
    test "$(wc -l < "$case_dir/angle-webgl/angle-load-marker.txt" | tr -d ' ')" -ge 2
  fi
  validate_unsigned_bundle "$app" "$case_dir/unsigned-codesign-after-probe"
  {
    printf 'SCHEMA=phase5-unsigned-chromium-u0u1-bundle-v1\n'
    printf 'CASE=%s\n' "$case_name"
    printf 'ANGLE_ADDED=%s\n' "$angle_added"
    printf 'SNAPSHOT_POSITION=%s\n' "$snapshot_position"
    printf 'SNAPSHOT_ARCHIVE_SHA256=%s\n' "$actual_archive_sha256"
    printf 'SNAPSHOT_CHROMIUM_REVISION=%s\n' "$snapshot_chromium_revision"
    printf 'SNAPSHOT_ANGLE_REVISION=%s\n' "$snapshot_angle_revision"
    printf 'ANGLE_ARTIFACT_NAME=%s\n' "$angle_artifact_name"
    printf 'ANGLE_ARTIFACT_DIGEST=%s\n' "$angle_artifact_digest"
    printf 'ANGLE_MANIFEST_SHA256=%s\n' "$angle_manifest_sha256"
    printf 'ANGLE_CHROMIUM_REVISION=%s\n' "$angle_chromium_revision"
    printf 'ANGLE_REVISION=%s\n' "$angle_revision"
    printf 'REVISION_MATCH_CHROMIUM=%s\n' "$([[ "$snapshot_chromium_revision" == "$angle_chromium_revision" ]] && printf true || printf false)"
    printf 'REVISION_MATCH_ANGLE=%s\n' "$([[ "$snapshot_angle_revision" == "$angle_revision" ]] && printf true || printf false)"
    printf 'RUNTIME_DEVICE_READY=%s\n' "$angle_runtime_device_ready"
    printf 'SIGNING_STATE=unsigned\n'
    printf 'SIGNING_OPERATION=none\n'
    printf 'XATTR_OPERATION=none\n'
    printf 'PROFILE_SCOPE=new-temporary-profile-per-probe\n'
    printf 'LOOPBACK_URL=%s\n' "$loopback_url"
  } > "$case_dir/bundle-manifest.txt"
}

run_case U0 false
run_case U1 true

u0_inventory="$results_dir/U0/inventory.txt"
u1_inventory="$results_dir/U1/inventory.txt"
extra_inventory=$(comm -13 "$u0_inventory" "$u1_inventory")
missing_inventory=$(comm -23 "$u0_inventory" "$u1_inventory")
expected_extra=$(printf '%s\n%s' \
  'Contents/Frameworks/Chromium Framework.framework/Versions/Current/Libraries/libEGL.dylib' \
  'Contents/Frameworks/Chromium Framework.framework/Versions/Current/Libraries/libGLESv2.dylib')
[[ "$extra_inventory" == "$expected_extra" ]] || phase3_fail 'U1 inventory differs from U0 by more than the two ANGLE dylibs'
[[ -z "$missing_inventory" ]] || phase3_fail 'U1 inventory is missing a stock file'
u0_main_hash=$(awk -F= '$1 == "main_executable_sha256" {print $2}' "$results_dir/U0/components.txt")
u1_main_hash=$(awk -F= '$1 == "main_executable_sha256" {print $2}' "$results_dir/U1/components.txt")
u0_framework_hash=$(awk -F= '$1 == "framework_sha256" {print $2}' "$results_dir/U0/components.txt")
u1_framework_hash=$(awk -F= '$1 == "framework_sha256" {print $2}' "$results_dir/U1/components.txt")
[[ "$u0_main_hash" == "$u1_main_hash" && "$u0_framework_hash" == "$u1_framework_hash" ]] ||
  phase3_fail 'U0 and U1 changed a Chromium main/framework binary outside ANGLE dylibs'
printf '%s\n' "$extra_inventory" > "$results_dir/u1-only-files.txt"
printf 'SCHEMA=phase5-unsigned-chromium-u0u1-result-v1\nU0_URL=pass\nU1_URL=pass\nU0_WEBGL_SMOKE=pass\nU1_WEBGL_SMOKE=pass\nU1_ANGLE_LOAD=pass\nINPUT_REVISION_MATCH_CHROMIUM=%s\nINPUT_REVISION_MATCH_ANGLE=%s\n' \
  "$([[ "$snapshot_chromium_revision" == "$angle_chromium_revision" ]] && printf true || printf false)" \
  "$([[ "$snapshot_angle_revision" == "$angle_revision" ]] && printf true || printf false)" \
  > "$results_dir/experiment-summary.txt"
printf '%s\n' 'phase5 unsigned Chromium U0/U1 probe passed'
