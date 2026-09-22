#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd -P)
preflight="$repo_root/scripts/run-phase3c-preflight.sh"
source "$repo_root/scripts/phase3-test-copy-common.sh"
fixture=$(mktemp -d /private/tmp/phase3c-preflight.XXXXXX)
stub_dir="$fixture/stubs"
mkdir -p "$stub_dir"
export PATH="$stub_dir:$PATH"
fixture_log="$fixture/command.log"
export PHASE3C_FIXTURE_LOG="$fixture_log"
inspect_log="$fixture/inspect.log"
export PHASE3C_INSPECT_LOG="$inspect_log"

cat > "$stub_dir/mkdir" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
target="${@: -1}"
if [[ "${PHASE3C_FIXTURE_FAIL_ROOT_MKDIR:-0}" == 1 && "$(basename "$target")" == retry9 && "$#" == 1 ]]; then
  exit 1
fi
/bin/mkdir "$@"
if [[ "${PHASE3C_FIXTURE_POST_CREATE_SYMLINK_SWAP:-0}" == 1 && "$(basename "$target")" == retry9 && "$#" == 1 ]]; then
  /bin/rmdir "$target"
  /bin/ln -s "$(dirname "$target")" "$target"
fi
if [[ "${PHASE3C_FIXTURE_FAIL_RESULTS_MKDIR:-0}" == 1 && "$(basename "$target")" == results && "$#" == 1 ]]; then
  /bin/rmdir "$target"
  exit 1
fi
EOF
chmod +x "$stub_dir/mkdir"
cat > "$stub_dir/git" <<'EOF'
#!/usr/bin/env bash
if [[ "$*" == *' branch --show-current' ]]; then
  printf 'phase3-dynamic-angle-prep\n'
elif [[ "$*" == *' status --porcelain' ]]; then
  :
else
  exec /usr/bin/git "$@"
fi
EOF
chmod +x "$stub_dir/git"
cat > "$fixture/explicit-inspect" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'INJECTED_INSPECT %s\n' "$1" >> "${PHASE3C_INSPECT_LOG:?}"
EOF
chmod +x "$fixture/explicit-inspect"

cat > "$stub_dir/codesign" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'PATH_STUB_CODESIGN_INVOKED\n' >> "${PHASE3C_FIXTURE_LOG:?}"
target=${!#}
case " $* " in
  *' --verify '*)
    if [[ "$target" == *'ANGLE Test.app' && -f "$target/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib" ]]; then
      printf '%s: a sealed resource is missing or invalid\n' "$target" >&2
      printf 'In subcomponent: %s\n' "$target/Contents/Frameworks/Google Chrome Framework.framework" >&2
      exit 1
    fi
    exit 0 ;;
  *' -dvvv '*)
    if [[ "$target" == *.framework ]]; then
      echo "Executable=$target/Versions/Current/Google Chrome Framework"
    elif [[ "$target" == *.app ]]; then
      echo "Executable=$target/Contents/MacOS/Google Chrome"
    else
      echo "Executable=$target"
    fi
    echo 'Authority=Developer ID Application: Google LLC (EQHXZ8M8AV)'
    echo 'TeamIdentifier=EQHXZ8M8AV'
    echo 'CodeDirectory v=20500 flags=0x10000(runtime)'
    ;;
  *) exit 0 ;;
esac
EOF
cat > "$stub_dir/xattr" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat > "$stub_dir/lipo" <<'EOF'
#!/usr/bin/env bash
echo 'Architectures in the fat file: x86_64'
EOF
cat > "$stub_dir/file" <<'EOF'
#!/usr/bin/env bash
printf '%s: Mach-O 64-bit executable x86_64\n' "$1"
EOF
cat > "$stub_dir/ps" <<'EOF'
#!/usr/bin/env bash
if [[ "${PHASE3C_SOURCE_SELF_PROCESS:-0}" == 1 ]]; then
  printf '%s %s/Contents/MacOS/Google Chrome --type=self-fixture\n' "$PPID" "$PHASE3C_SOURCE_APP"
elif [[ "${PHASE3C_SOURCE_PROCESS:-0}" == 1 ]]; then
  printf '777 %s/Contents/MacOS/Google Chrome --type=gpu-process\n' "$PHASE3C_SOURCE_APP"
fi
EOF
cat > "$stub_dir/ditto" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
source="${@: -2:1}"
output="${@: -1}"
printf 'ditto %s\n' "$output" >> "${PHASE3C_FIXTURE_LOG:-/dev/null}"
if [[ "${PHASE3C_FIXTURE_FAIL_DITTO:-0}" == 1 ]]; then
  printf 'synthetic ditto failure\n' >&2
  exit 23
fi
cp -R "$source" "$output"
libraries="$output/Contents/Frameworks/Google Chrome Framework.framework/Libraries"
target="$output/Contents/Frameworks/Google Chrome Framework.framework/Versions/Current/Libraries"
if [[ -d "$libraries" && ! -L "$libraries" ]]; then
  mkdir -p "$target"
  find "$libraries" -mindepth 1 -maxdepth 1 -exec mv {} "$target" \;
  rmdir "$libraries"
  ln -s Versions/Current/Libraries "$libraries"
fi
EOF
cat > "$stub_dir/shasum" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
for argument in "$@"; do
  case "$argument" in
    */libEGL.dylib) echo 'f4a8a7575183a41373404f7c25b4f56e1a1540c5b1578d11437c180b1f698db8  '"$argument"; exit 0 ;;
    */libGLESv2.dylib) [[ "${FORCE_HASH_MISMATCH:-0}" != 1 ]] && echo '8d3d188d3d4f23cf3f96ecea209b084c6db9c6192244f879cfb6bf0fb2e02cf0  '"$argument" || echo '0000000000000000000000000000000000000000000000000000000000000000  '"$argument"; exit 0 ;;
  esac
done
exec /usr/bin/shasum "$@"
EOF
chmod +x "$stub_dir"/*

preflight_wrapper="$fixture/preflight-wrapper"
sign_injection="$fixture/explicit-sign-dry-run"
cat > "$sign_injection" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'INJECTED_SIGN_DRY_RUN %s\n' "$*" >> "${PHASE3C_FIXTURE_LOG:?}"
if [[ "${PHASE3C_SIGN_MODE:-success}" == fail ]]; then
  printf 'synthetic-sign-stdout\n'
  printf 'synthetic-sign-stderr\n' >&2
  exit 42
fi
printf 'synthetic sign dry-run success\n'
EOF
chmod +x "$sign_injection"
cat > "$preflight_wrapper" <<EOF
#!/usr/bin/env bash
source "$repo_root/scripts/run-phase3c-preflight.sh"
phase3_preflight_main "$fixture/explicit-codesign-injection" "$sign_injection" "$fixture/explicit-inspect" "\$@"
EOF
chmod +x "$preflight_wrapper"
preflight="$preflight_wrapper"

injection_stub="$fixture/explicit-codesign-injection"
cat > "$injection_stub" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'INJECTED_CODESIGN %s\n' "$*" >> "${PHASE3C_FIXTURE_LOG:?}"
target=${!#}
verify_requested=0
for argument in "$@"; do
  if [[ "$argument" == --verify ]]; then
    verify_requested=1
  fi
done
if [[ "${PHASE3C_INJECT_MODE:-success}" == copy-fail && "$verify_requested" == 1 && "$target" == */Contents/MacOS/Google\ Chrome && "$target" != "${PHASE3C_SOURCE_MAIN:-}" ]]; then
  printf 'synthetic-copy-stdout\n'
  printf 'synthetic-copy-stderr\n' >&2
  exit 41
fi
if [[ "${PHASE3C_INJECT_MODE:-success}" == sign-fail ]]; then
  printf 'unexpected-sign-injection\n' >&2
  exit 29
fi
case " $* " in
  *' --verify '*)
    if [[ "$target" == *'ANGLE Test.app' && -f "$target/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib" ]]; then
      printf '%s: a sealed resource is missing or invalid\n' "$target" >&2
      printf 'In subcomponent: %s\n' "$target/Contents/Frameworks/Google Chrome Framework.framework" >&2
      exit 1
    fi
    exit 0 ;;
  *' -dvvv '*|*' -d --entitlements '*)
    if [[ "$target" == *.framework ]]; then
      printf 'Executable=%s\n' "$target/Versions/Current/Google Chrome Framework"
    elif [[ "$target" == *.app ]]; then
      printf 'Executable=%s\n' "$target/Contents/MacOS/Google Chrome"
    else
      printf 'Executable=%s\n' "$target"
    fi
    printf 'Authority=Developer ID Application: Google LLC (EQHXZ8M8AV)\nTeamIdentifier=EQHXZ8M8AV\nCodeDirectory v=20500 flags=0x10000(runtime)\n' ;;
esac
EOF
chmod +x "$injection_stub"
phase3_run_codesign "$injection_stub" --fixture-probe > "$fixture/explicit-codesign-output.txt"
grep -F 'INJECTED_CODESIGN --fixture-probe' "$fixture_log" >/dev/null
! grep -F 'PATH_STUB_CODESIGN_INVOKED' "$fixture_log" 2>/dev/null
help_output="$fixture/preflight-help.txt"
"$preflight" --help > "$help_output"
grep -F -- '--source-app APP' "$help_output" >/dev/null
grep -F -- '--artifact-dir DIR' "$help_output" >/dev/null
grep -F -- '--output-app APP' "$help_output" >/dev/null
grep -F -- '--results-dir DIR' "$help_output" >/dev/null
grep -F 'phase3_preflight_main /usr/bin/codesign' "$repo_root/scripts/run-phase3c-preflight.sh" >/dev/null

source_app="$fixture/Google Chrome.app"
artifact_dir="$fixture/angle-artifact"
mkdir -p "$source_app/Contents/MacOS" "$source_app/Contents/Resources" \
  "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Versions/Current" \
  "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Helpers/Google Chrome Helper (GPU).app/Contents/MacOS" \
  "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries" "$artifact_dir"
cat > "$source_app/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>CFBundleShortVersionString</key><string>154.0.8037.45</string><key>CFBundleVersion</key><string>8037.45</string><key>CFBundleExecutable</key><string>Google Chrome</string></dict></plist>
EOF
printf '#!/bin/sh\nexit 0\n' > "$source_app/Contents/MacOS/Google Chrome"
printf 'framework\n' > "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Versions/Current/Google Chrome Framework"
printf '#!/bin/sh\nexit 0\n' > "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Helpers/Google Chrome Helper (GPU).app/Contents/MacOS/Google Chrome Helper (GPU)"
chmod +x "$source_app/Contents/MacOS/Google Chrome" "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Versions/Current/Google Chrome Framework" "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Helpers/Google Chrome Helper (GPU).app/Contents/MacOS/Google Chrome Helper (GPU)"
export PHASE3C_SOURCE_MAIN="$source_app/Contents/MacOS/Google Chrome"
printf 'baseline\n' > "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libchrome.dylib"
mkdir -p "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/IwaKeyDistribution/nested"
printf 'nested baseline\n' > "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/IwaKeyDistribution/nested/file"
ln -s nested/file "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/IwaKeyDistribution/internal-link"
printf 'egl\n' > "$artifact_dir/libEGL.dylib"
printf 'gles\n' > "$artifact_dir/libGLESv2.dylib"
printf '%s\n' '72b8f72a7587ec776d7d2a57d275a6e9b1781b1d' > "$artifact_dir/ANGLE_REVISION"
source_main_hash=$(shasum -a 256 "$source_app/Contents/MacOS/Google Chrome" | awk '{print $1}')

expect_fail() { if "$@" >/dev/null 2>&1; then printf 'expected failure: %s\n' "$*" >&2; exit 1; fi; }
expect_rejected_without_prepare() {
  : > "$fixture_log"
  expect_fail "$@"
  test ! -s "$fixture_log"
}
"$preflight" --help >/dev/null
expect_fail "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/retry0/out.app" --results-dir "$fixture/results-retry0"
expect_rejected_without_prepare "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/retry4/out.app" --results-dir "$fixture/results-retry4"
expect_rejected_without_prepare "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/retry6/output.app" --results-dir "$fixture/retry6/results"
expect_rejected_without_prepare "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/retry8/output.app" --results-dir "$fixture/retry8/results"
mkdir -p "$fixture/existing-output-root/retry9" "$fixture/existing-results-root/retry9"
mkdir "$fixture/existing-output-root/retry9/existing-output.app" "$fixture/existing-results-root/retry9/existing-results"
mkdir -p "$fixture/existing-root/retry9"
expect_rejected_without_prepare "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/existing-root/retry9/output.app" --results-dir "$fixture/existing-root/retry9/results"
expect_rejected_without_prepare "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/existing-output-root/retry9/existing-output.app" --results-dir "$fixture/existing-output-root/retry9/new-results"
expect_rejected_without_prepare "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/existing-results-root/retry9/new-output.app" --results-dir "$fixture/existing-results-root/retry9/existing-results"
expect_rejected_without_prepare "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app /Applications/retry9/phase3c-writable.app --results-dir /Applications/retry9/phase3c-results
expect_rejected_without_prepare "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$source_app/preflight-root/retry9/output.app" --results-dir "$source_app/preflight-root/retry9/results"
ln -s "$source_app" "$fixture/source-link.app"
mkdir -p "$fixture/link-root" "$fixture/hash-root" "$fixture/process-root"
expect_rejected_without_prepare "$preflight" --source-app "$fixture/source-link.app" --artifact-dir "$artifact_dir" --output-app "$fixture/link-root/retry9/output.app" --results-dir "$fixture/link-root/retry9/results"
expect_rejected_without_prepare env FORCE_HASH_MISMATCH=1 "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/hash-root/retry9/output.app" --results-dir "$fixture/hash-root/retry9/results"
export PHASE3C_SOURCE_APP="$source_app"
expect_rejected_without_prepare env PHASE3C_SOURCE_PROCESS=1 "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/process-root/retry9/output.app" --results-dir "$fixture/process-root/retry9/results"
unset PHASE3C_SOURCE_PROCESS
mkdir -p "$fixture/lifecycle-parent" "$fixture/mismatch-a" "$fixture/mismatch-b" "$fixture/symlink-parent-target" "$fixture/root-mkdir-parent" "$fixture/results-mkdir-parent" "$fixture/swap-parent"
ln -s "$fixture/symlink-parent-target" "$fixture/symlink-parent"
expect_rejected_without_prepare "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/missing-parent/retry9/output.app" --results-dir "$fixture/missing-parent/retry9/results"
expect_rejected_without_prepare "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/symlink-parent/retry9/output.app" --results-dir "$fixture/symlink-parent/retry9/results"
expect_rejected_without_prepare "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/mismatch-a/retry9/output.app" --results-dir "$fixture/mismatch-b/retry9/results"
expect_rejected_without_prepare "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/lifecycle-parent/retry9/nested/output.app" --results-dir "$fixture/lifecycle-parent/retry9/results"
expect_rejected_without_prepare "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/lifecycle-parent/retry9/output.app" --results-dir "$fixture/lifecycle-parent/retry9/output.app"
expect_rejected_without_prepare env PHASE3C_FIXTURE_FAIL_ROOT_MKDIR=1 "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/root-mkdir-parent/retry9/output.app" --results-dir "$fixture/root-mkdir-parent/retry9/results"
test ! -e "$fixture/root-mkdir-parent/retry9"
expect_rejected_without_prepare env PHASE3C_FIXTURE_FAIL_RESULTS_MKDIR=1 "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/results-mkdir-parent/retry9/output.app" --results-dir "$fixture/results-mkdir-parent/retry9/results"
test ! -e "$fixture/results-mkdir-parent/retry9/results"
expect_rejected_without_prepare env PHASE3C_FIXTURE_POST_CREATE_SYMLINK_SWAP=1 "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/swap-parent/retry9/output.app" --results-dir "$fixture/swap-parent/retry9/results"
test ! -e "$fixture/swap-parent/retry9/results"
expect_rejected_without_prepare "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/lifecycle-parent/retry9/../output.app" --results-dir "$fixture/lifecycle-parent/retry9/results"
expect_rejected_without_prepare "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/lifecycle-parent//retry9/output.app" --results-dir "$fixture/lifecycle-parent//retry9/results"
for retry_name in retry0 retry1 retry2 retry3 retry4 retry5 retry6 retry7 retry8; do
  expect_rejected_without_prepare "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/$retry_name/output.app" --results-dir "$fixture/$retry_name/results"
  test ! -e "$fixture/$retry_name"
done
test "$(shasum -a 256 "$source_app/Contents/MacOS/Google Chrome" | awk '{print $1}')" = "$source_main_hash"
mkdir -p "$fixture/post-create-failure-parent"
failure_output="$fixture/post-create-failure-parent/retry9/output.app"
failure_results="$fixture/post-create-failure-parent/retry9/results"
expect_fail env PHASE3C_FIXTURE_FAIL_DITTO=1 "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$failure_output" --results-dir "$failure_results"
test -f "$failure_results/preflight-final-result.txt"
grep -F 'FINAL_STATE=failed' "$failure_results/preflight-final-result.txt" >/dev/null
grep -F 'FINAL_EXIT_STATUS=23' "$failure_results/preflight-final-result.txt" >/dev/null
copy_failure_output="$fixture/copy-before-failure-parent/retry9/output.app"
copy_failure_results="$fixture/copy-before-failure-parent/retry9/results"
mkdir -p "$fixture/copy-before-failure-parent"
expect_fail env PHASE3C_INJECT_MODE=copy-fail "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$copy_failure_output" --results-dir "$copy_failure_results"
copy_failure_evidence="$copy_failure_output.phase3-angle-manifest.evidence"
test "$(<"$copy_failure_evidence/copy-before-dylibs-app-strict-verify-status.txt")" = 0
test "$(<"$copy_failure_evidence/copy-before-dylibs-main-strict-verify-status.txt")" = 41
grep -F 'synthetic-copy-stdout' "$copy_failure_evidence/copy-before-dylibs-main-strict-verify-stdout.txt" >/dev/null
grep -F 'synthetic-copy-stderr' "$copy_failure_evidence/copy-before-dylibs-main-strict-verify-stderr.txt" >/dev/null
grep -F 'raw_exit_status=41' "$copy_failure_evidence/copy-before-dylibs-main-strict-verify-metadata.txt" >/dev/null
test ! -e "$copy_failure_output/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib"
test ! -e "$copy_failure_results/sign-dry-run.txt"
grep -F 'FINAL_EXIT_STATUS=1' "$copy_failure_results/preflight-final-result.txt" >/dev/null
grep -F $'prepare\tfail\t1' "$copy_failure_results/preflight-step-journal.tsv" >/dev/null
sign_failure_output="$fixture/sign-dry-run-failure-parent/retry9/output.app"
sign_failure_results="$fixture/sign-dry-run-failure-parent/retry9/results"
mkdir -p "$fixture/sign-dry-run-failure-parent"
expect_fail env PHASE3C_SIGN_MODE=fail "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$sign_failure_output" --results-dir "$sign_failure_results"
grep -F 'synthetic-sign-stdout' "$sign_failure_results/sign-dry-run-stdout.txt" >/dev/null
grep -F 'synthetic-sign-stderr' "$sign_failure_results/sign-dry-run-stderr.txt" >/dev/null
grep -F 'FINAL_EXIT_STATUS=42' "$sign_failure_results/preflight-final-result.txt" >/dev/null
grep -F 'FAILED_STEP=sign-dry-run' "$sign_failure_results/preflight-final-result.txt" >/dev/null
grep -F $'sign-dry-run\tfail\t42' "$sign_failure_results/preflight-step-journal.tsv" >/dev/null
applications_source="$fixture/Applications/Google Chrome.app"
mkdir -p "$(dirname "$applications_source")"
cp -R "$source_app" "$applications_source"
mkdir -p "$fixture/applications-source" "$fixture/phase3c"
"$preflight" --source-app "$applications_source" --artifact-dir "$artifact_dir" --output-app "$fixture/applications-source-retry9/output.app" --results-dir "$fixture/applications-source-retry9/results" >/dev/null
export PHASE3C_SOURCE_SELF_PROCESS=1
"$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/self-process-retry9/output.app" --results-dir "$fixture/self-process-retry9/results" >/dev/null
unset PHASE3C_SOURCE_SELF_PROCESS
success_log="$fixture/success-preflight.log"
if ! bash -x "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/phase3c-preflight-retry9/output.app" --results-dir "$fixture/phase3c-preflight-retry9/results" > "$success_log" 2>&1; then
  cat "$success_log" >&2
  exit 1
fi
test -f "$fixture/phase3c-preflight-retry9/output.app.phase3-angle-manifest"
grep -F 'SCHEMA=phase3-angle-test-copy-v4' "$fixture/phase3c-preflight-retry9/output.app.phase3-angle-manifest" >/dev/null
grep -F $'IwaKeyDistribution\tdir\t-' "$fixture/phase3c-preflight-retry9/output.app.phase3-angle-manifest.evidence/libraries-source-baseline.txt" >/dev/null
test -f "$fixture/phase3c-preflight-retry9/output.app.phase3-angle-manifest.evidence/libraries-source-baseline.sha256"
test -f "$fixture/phase3c-preflight-retry9/output.app.phase3-angle-manifest.evidence/libraries-copy-baseline.sha256"
test -f "$fixture/phase3c-preflight-retry9/output.app.phase3-angle-manifest.evidence/libraries-post-install.sha256"
test -f "$fixture/phase3c-preflight-retry9/results/sign-dry-run.txt"
grep -F 'synthetic sign dry-run success' "$fixture/phase3c-preflight-retry9/results/sign-dry-run.txt" >/dev/null
journal="$fixture/phase3c-preflight-retry9/results/preflight-step-journal.tsv"
result="$fixture/phase3c-preflight-retry9/results/preflight-final-result.txt"
test -f "$journal"
test -f "$result"
grep -F 'INJECTED_INSPECT ' "$inspect_log" >/dev/null
grep -F 'INJECTED_SIGN_DRY_RUN ' "$fixture_log" >/dev/null
grep -F $'prepare\tstart\t0' "$journal" >/dev/null
grep -F $'prepare\tpass\t0' "$journal" >/dev/null
grep -F $'sign-dry-run\tpass\t0' "$journal" >/dev/null
grep -F 'FINAL_EXIT_STATUS=0' "$result" >/dev/null
! grep -F 'PATH_STUB_CODESIGN_INVOKED' "$fixture_log" 2>/dev/null
awk -F '\t' 'BEGIN { ok = 0 } $2 == "readonly-gates" && $3 == "pass" { ok = ok < 1 ? 1 : ok } $2 == "source-inspection" && $3 == "pass" { ok = ok == 1 ? 2 : 99 } $2 == "retry-root-created" && $3 == "pass" { ok = ok == 2 ? 3 : 99 } $2 == "prepare" && $3 == "pass" { ok = ok == 3 ? 4 : 99 } $2 == "sign-dry-run" && $3 == "pass" { ok = ok == 4 ? 5 : 99 } END { exit !(ok == 5) }' "$journal"
failure_journal="$failure_results/preflight-step-journal.tsv"
grep -F $'prepare\tfail\t23' "$failure_journal" >/dev/null
grep -F $'final-result\tfail\t23' "$failure_journal" >/dev/null
# Static regression checks for the real signing script. The synthetic
# preflight does not perform codesign, so these checks ensure the
# versioned Framework workaround remains present and app-level --deep
# signing is not reintroduced.
sign_script="$repo_root/scripts/sign-chrome-angle-test-copy.sh"
grep -F 'phase3_sign_versioned_framework' "$sign_script" >/dev/null
grep -F 'phase3_sign_framework_version' "$sign_script" >/dev/null
grep -F 'phase3_sign_target' "$sign_script" >/dev/null
grep -F 'framework-version' "$sign_script" >/dev/null
grep -F 'phase3_sign_target "$codesign_executable" "$framework"' "$sign_script" >/dev/null
! grep -F 'sign_command=("$codesign_executable" --force --sign - --deep "$test_app_real")' "$sign_script" >/dev/null
grep -F "SIGNING_METHOD=ad-hoc-versioned-framework" "$sign_script" >/dev/null
printf '%s\n' 'phase3c preflight fixture tests passed'
