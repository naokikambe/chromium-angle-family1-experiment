#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd -P)
source "$repo_root/scripts/phase3-test-copy-common.sh"
fixture=$(mktemp -d /private/tmp/phase3b-fixture.XXXXXX)
printf 'fixture directory retained for inspection: %s\n' "$fixture"
stub_dir="$fixture/stubs"
mkdir "$stub_dir" "$fixture/output with spaces"
export PHASE3_FIXTURE_LOG="$fixture/command.log"

fixture_checkpoint() {
  local name=$1
  printf '[fixture] checkpoint=%s\n' "$name"
  if [[ "${PHASE3B_FIXTURE_STOP_AFTER:-}" == "$name" ]]; then
    printf '[fixture] bounded stop after=%s\n' "$name"
    exit 0
  fi
}

cat > "$stub_dir/codesign" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'codesign %q\n' "$*" >> "$PHASE3_FIXTURE_LOG"
target=${!#}
if [[ " $* " == *' --force '* ]]; then touch "$target/.fixture-ad-hoc"; exit 0; fi
if [[ " $* " == *' --verify '* ]]; then
  [[ "${CODESIGN_INVALID:-0}" != 1 ]] || exit 1
  if [[ "$target" == *'Chrome Source.app'* ]]; then
    case "${CODESIGN_SOURCE_STRICT:-success}" in
      detritus) printf '%s: resource fork, Finder information, or similar detritus not allowed\n' "$target" >&2; exit 1 ;;
      unknown) printf '%s: fixture unknown signature failure\n' "$target" >&2; exit 1 ;;
    esac
  fi
  if [[ "$target" == *'ANGLE Test.app'* && -n "${CODESIGN_COPY_STRICT_TARGET:-}" ]]; then
    case "${CODESIGN_COPY_STRICT_TARGET}" in
      app) [[ "$target" == *.app ]] && { printf 'fixture copy app strict failure\n' >&2; exit 1; } ;;
      main) [[ "$target" == */Contents/MacOS/Google\ Chrome ]] && { printf 'fixture copy main strict failure\n' >&2; exit 1; } ;;
      framework) [[ "$target" == *.framework ]] && { printf 'fixture copy Framework strict failure\n' >&2; exit 1; } ;;
      gpu) [[ "$target" == *'Google Chrome Helper (GPU)' ]] && { printf 'fixture copy GPU Helper strict failure\n' >&2; exit 1; } ;;
    esac
  fi
  if [[ "$target" == *'ANGLE Test.app'* && -f "$target/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib" && ! -e "$target/.fixture-ad-hoc" ]]; then exit 1; fi
  exit 0
fi
case "$target" in
  *.framework) executable="$target/Versions/Current/Google Chrome Framework" ;;
  *.app) executable="$target/Contents/MacOS/Google Chrome" ;;
  *) executable="$target" ;;
esac
printf 'Executable=%s\n' "$executable"
if [[ -e "$target/.fixture-ad-hoc" && "${CODESIGN_NONADHOC:-0}" != 1 ]]; then
  echo 'Signature=adhoc'
elif [[ "$target" == *'ANGLE Test.app'* && "${CODESIGN_COPY_TEAM_MISMATCH:-0}" == 1 ]]; then
  echo 'Authority=Developer ID Application: Other LLC (BADTEAM)'
  echo 'TeamIdentifier=BADTEAM'
  echo 'CodeDirectory v=20500 flags=0x10000(runtime)'
else
  echo 'Authority=Developer ID Application: Google LLC (EQHXZ8M8AV)'
  echo 'TeamIdentifier=EQHXZ8M8AV'
  echo 'CodeDirectory v=20500 flags=0x10000(runtime)'
fi
EOF
cat > "$stub_dir/xattr" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'xattr %q\n' "$*" >> "$PHASE3_FIXTURE_LOG"
target=${!#}
if [[ "${XATTR_COPY_DETRITUS:-0}" == 1 && "$target" == *'ANGLE Test.app'* ]]; then
  printf '%s: com.apple.FinderInfo: fixture\n' "$target"
fi
exit 0
EOF
cat > "$stub_dir/ditto" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'ditto %q\n' "$*" >> "$PHASE3_FIXTURE_LOG"
args=("$@")
source=${args[$(( ${#args[@]} - 2 ))]}
output=${args[$(( ${#args[@]} - 1 ))]}
if [[ "${PHASE3_FIXTURE_ENFORCE_DITTO_OPTIONS:-0}" == 1 ]]; then
  for required in --norsrc --noextattr --noacl --noqtn; do
    [[ " ${args[*]} " == *" $required "* ]] || { echo "missing required ditto option: $required" >&2; exit 1; }
  done
  for argument in "${args[@]}"; do
    case "$argument" in --rsrc|--extattr|--acl) echo "forbidden ditto option: $argument" >&2; exit 1 ;; esac
  done
fi
cp -R "$source" "$output"
libraries="$output/Contents/Frameworks/Google Chrome Framework.framework/Libraries"
target_libraries="$output/Contents/Frameworks/Google Chrome Framework.framework/Versions/Current/Libraries"
mkdir -p "$target_libraries"
if [[ -d "$libraries" && ! -L "$libraries" && "${DITTO_LIBRARY_LINK:-valid}" != directory ]]; then
  find "$libraries" -mindepth 1 -maxdepth 1 -exec mv {} "$target_libraries" \;
  rmdir "$libraries"
fi
case "${DITTO_LIBRARY_LINK:-valid}" in
  valid) ln -s Versions/Current/Libraries "$libraries" ;;
  directory) : ;;
  other) ln -s Versions/Other/Libraries "$libraries" ;;
  foo) ln -s Foo/Libraries "$libraries" ;;
  parent) ln -s ../Framework.framework/Libraries "$libraries" ;;
  dot) ln -s ./Versions/Current/Libraries "$libraries" ;;
  normalized) ln -s Versions/Current/../Current/Libraries "$libraries" ;;
  trailing) ln -s Versions/Current/Libraries/ "$libraries" ;;
  external) ln -s /Applications "$libraries" ;;
  absolute-internal) ln -s "$output/Contents/Frameworks/Google Chrome Framework.framework/Versions/Current/Libraries" "$libraries" ;;
  broken) ln -s Versions/Missing/Libraries "$libraries" ;;
  source) ln -s /Applications/Google\ Chrome.app/Contents/Frameworks/Google\ Chrome\ Framework.framework/Libraries "$libraries" ;;
  regular-file) printf 'not a directory\n' > "$libraries" ;;
esac
case "${DITTO_BASELINE_MUTATION:-}" in
  missing) rm -f "$target_libraries/libaperitif.dylib" ;;
  sha) printf 'changed\n' > "$target_libraries/libaperitif.dylib" ;;
  link) rm -f "$target_libraries/baseline-link"; ln -s changed-target "$target_libraries/baseline-link" ;;
  control-name) mv "$target_libraries/libaperitif.dylib" "$target_libraries/libaperitif"$'\t'"name.dylib" ;;
  control-link) control_target=$'changed\t-target'; rm -f "$target_libraries/baseline-link"; ln -s "$control_target" "$target_libraries/baseline-link" ;;
esac
case "${DITTO_COPY_MUTATION:-}" in
  missing-main) mv "$output/Contents/MacOS/Google Chrome" "$output/Contents/MacOS/Google Chrome.missing" ;;
  nonexec-main) chmod -x "$output/Contents/MacOS/Google Chrome" ;;
esac
EOF
cat > "$stub_dir/lipo" <<'EOF'
#!/usr/bin/env bash
echo 'Architectures in the fat file: x86_64'
EOF
cat > "$stub_dir/shasum" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
for argument in "$@"; do
  case "$argument" in
    */libEGL.dylib) echo "f4a8a7575183a41373404f7c25b4f56e1a1540c5b1578d11437c180b1f698db8  $argument"; exit 0 ;;
    */libGLESv2.dylib)
      if [[ "${FORCE_HASH_MISMATCH:-0}" == 1 ]]; then echo "0000000000000000000000000000000000000000000000000000000000000000  $argument"; else echo "8d3d188d3d4f23cf3f96ecea209b084c6db9c6192244f879cfb6bf0fb2e02cf0  $argument"; fi
      exit 0 ;;
  esac
done
exec /usr/bin/shasum "$@"
EOF
cat > "$stub_dir/ps" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ " $* " == *' -wwaxo pid=,command= '* ]]; then
  cat "$PHASE3_FIXTURE_PS_SNAPSHOT"
  exit 0
fi
printf '%s fixture process\n' "${PHASE3_FIXTURE_PS_PID:-0}"
EOF
cat > "$stub_dir/file" <<'EOF'
#!/usr/bin/env bash
printf '%s: fixture Mach-O\n' "$1"
EOF
cat > "$stub_dir/otool" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat > "$stub_dir/lsof" <<'EOF'
#!/usr/bin/env bash
if [[ "${PHASE3_FIXTURE_LSOF_BOTH:-0}" == 1 ]]; then
  printf 'fixture %s\n' "$PHASE3_FIXTURE_LIBRARIES/libEGL.dylib"
  printf 'fixture %s\n' "$PHASE3_FIXTURE_LIBRARIES/libGLESv2.dylib"
else
  printf 'fixture %s\n' "$PHASE3_FIXTURE_LIBRARIES/libEGL.dylib"
fi
EOF
cat > "$stub_dir/vmmap" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$stub_dir"/*
export PATH="$stub_dir:$PATH"
export PHASE3_FIXTURE_ENFORCE_DITTO_OPTIONS=1

source_app="$fixture/Chrome Source.app"
artifact="$fixture/artifact"
mkdir -p "$source_app/Contents/MacOS" "$source_app/Contents/Resources" "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Versions/Current" "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Helpers/Google Chrome Helper (GPU).app/Contents/MacOS" "$artifact"
cat > "$source_app/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>CFBundleShortVersionString</key><string>154.0.8037.45</string><key>CFBundleExecutable</key><string>Google Chrome</string></dict></plist>
EOF
printf '#!/usr/bin/env bash\nexit 0\n' > "$source_app/Contents/MacOS/Google Chrome"
printf 'fixture framework\n' > "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Versions/Current/Google Chrome Framework"
printf '#!/usr/bin/env bash\nexit 0\n' > "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Helpers/Google Chrome Helper (GPU).app/Contents/MacOS/Google Chrome Helper (GPU)"
chmod +x "$source_app/Contents/MacOS/Google Chrome" "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Versions/Current/Google Chrome Framework" "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Helpers/Google Chrome Helper (GPU).app/Contents/MacOS/Google Chrome Helper (GPU)"
mkdir -p "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries"
printf 'fixture egl\n' > "$artifact/libEGL.dylib"
printf 'fixture gles\n' > "$artifact/libGLESv2.dylib"
printf '%s\n' '72b8f72a7587ec776d7d2a57d275a6e9b1781b1d' > "$artifact/ANGLE_REVISION"
for baseline_name in libaperitif.dylib libchromecompaneros.dylib liboptimization_guide_internal.dylib libvk_swiftshader.dylib libvulkan.dylib; do
  printf 'fixture %s\n' "$baseline_name" > "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/$baseline_name"
done
ln -s baseline-target "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/baseline-link"
printf 'fixture baseline target\n' > "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/baseline-target"

expect_fail() { if "$@" >/dev/null 2>&1; then printf 'expected failure: %q\n' "$*" >&2; exit 1; fi; }
prepare="$repo_root/scripts/prepare-chrome-angle-test-copy.sh"
sign="$repo_root/scripts/sign-chrome-angle-test-copy.sh"
run="$repo_root/scripts/run-dynamic-angle-test.sh"
collect="$repo_root/scripts/collect-phase3-evidence.sh"
output="$fixture/output with spaces/Google Chrome 154 ANGLE Test.app"
output_after_tamper="$fixture/output after tamper/Google Chrome 154 ANGLE Test.app"

fixture_group=${PHASE3B_FIXTURE_GROUP:-all}
case "$fixture_group" in
  all|source-detritus|source-unknown|control-link|evidence-receipt-policy) ;;
  *) printf 'unknown fixture group: %s\n' "$fixture_group" >&2; exit 64 ;;
esac

fixture_group_start() {
  printf '[fixture] group-start=%s\n' "$1"
}

fixture_group_end() {
  printf '[fixture] group-end=%s\n' "$1"
}

source_snapshot="$fixture/source-snapshot"
cp -R "$source_app" "$source_snapshot"
assert_source_unchanged() { diff -qr "$source_app" "$source_snapshot"; }

source_detritus_output="$fixture/source detritus/Google Chrome 154 ANGLE Test.app"
source_unknown_output="$fixture/source unknown/Google Chrome 154 ANGLE Test.app"

run_inventory_final_record_regression() {
  local inventory="$fixture/inventory-final-record.tsv"
  printf 'newline\tsymlink\ttarget\n' > "$inventory"
  printf 'final\tfile\t0000000000000000000000000000000000000000000000000000000000000000' >> "$inventory"
  phase3_validate_inventory_file "$inventory"
}

run_source_detritus_group() {
  fixture_group_start source-detritus
  mkdir -p "$(dirname "$source_detritus_output")"
  env CODESIGN_SOURCE_STRICT=detritus "$prepare" "$source_app" "$artifact" "$source_detritus_output"
  assert_source_unchanged
  test -f "$source_detritus_output/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib"
  run_inventory_final_record_regression
  fixture_checkpoint source-detritus
  fixture_group_end source-detritus
}

run_source_unknown_group() {
  fixture_group_start source-unknown
  mkdir -p "$(dirname "$source_unknown_output")"
  fixture_checkpoint before-source-unknown
  printf '' > "$PHASE3_FIXTURE_LOG"
  expect_fail env CODESIGN_SOURCE_STRICT=unknown "$prepare" "$source_app" "$artifact" "$source_unknown_output"
  assert_source_unchanged
  test ! -e "$source_unknown_output"
  ! grep -F 'ditto ' "$PHASE3_FIXTURE_LOG"
  fixture_checkpoint source-unknown
  fixture_group_end source-unknown
}

run_control_link_group() {
  fixture_group_start control-link
  local control_link_source="$fixture/control-link Source.app"
  cp -R "$source_app" "$control_link_source"
  rm "$control_link_source/Contents/Frameworks/Google Chrome Framework.framework/Libraries/baseline-link"
  local control_target=$'changed\t-target'
  ln -s "$control_target" "$control_link_source/Contents/Frameworks/Google Chrome Framework.framework/Libraries/baseline-link"
  local control_link_path="$control_link_source/Contents/Frameworks/Google Chrome Framework.framework/Libraries/baseline-link"
  test "$(readlink -n "$control_link_path" | od -An -tx1 | tr -d ' \n')" = '6368616e676564092d746172676574'
  local control_link_output="$fixture/control-link/Google Chrome 154 ANGLE Test.app"
  mkdir -p "$(dirname "$control_link_output")"
  expect_fail "$prepare" "$control_link_source" "$artifact" "$control_link_output"
  local control_link_libraries="$control_link_output/Contents/Frameworks/Google Chrome Framework.framework/Versions/Current/Libraries"
  test ! -e "$control_link_libraries/libEGL.dylib"
  test ! -e "$control_link_libraries/libGLESv2.dylib"
  fixture_group_end control-link
}

run_evidence_receipt_policy_group() {
  fixture_group_start evidence-receipt-policy
  local focused_output="$fixture/evidence focused/Google Chrome 154 ANGLE Test.app"
  local focused_results="$fixture/evidence focused signed"
  local focused_manifest="$focused_output.phase3-angle-manifest"
  local focused_receipt="$focused_output.phase3-angle-signing-receipt"
  local focused_process_snapshot="$fixture/evidence focused process-snapshot.txt"
  local focused_libraries="$focused_output/Contents/Frameworks/Google Chrome Framework.framework/Libraries"

  mkdir -p "$(dirname "$focused_output")"
  fixture_checkpoint evidence-before-prepare
  "$prepare" "$source_app" "$artifact" "$focused_output"
  fixture_checkpoint evidence-after-prepare
  "$sign" "$focused_output" "$focused_results" --confirm-ad-hoc-signing
  fixture_checkpoint evidence-after-sign

  export PHASE3_FIXTURE_LIBRARIES="$focused_libraries"
  cat > "$focused_process_snapshot" <<EOF
333 /unrelated/Google Chrome Framework.framework/Helpers/Google Chrome Helper (GPU) --type=gpu-process
444 $focused_output/Contents/Frameworks/Google Chrome Framework.framework/Helpers/Google Chrome Helper (GPU).app/Contents/MacOS/Google Chrome Helper (GPU) --type=gpu-process
EOF
  export PHASE3_FIXTURE_PS_SNAPSHOT="$focused_process_snapshot"
  mkdir "$fixture/evidence one-library" "$fixture/evidence both-libraries"
  unset PHASE3_FIXTURE_LSOF_BOTH
  fixture_checkpoint evidence-before-one-library
  "$collect" "$focused_output" "$fixture/evidence one-library"
  ! grep -F 'direct dynamic ANGLE load evidence' "$fixture/evidence one-library/load-evidence.txt"
  export PHASE3_FIXTURE_LSOF_BOTH=1
  fixture_checkpoint evidence-before-both-libraries
  "$collect" "$focused_output" "$fixture/evidence both-libraries"
  grep -F 'direct dynamic ANGLE load evidence: lsof confirmed both test-copy dylib absolute paths for GPU PID 444' \
    "$fixture/evidence both-libraries/load-evidence.txt" >/dev/null
  grep -F '444 ' "$fixture/evidence both-libraries/gpu-processes.txt" >/dev/null
  ! grep -F '333 ' "$fixture/evidence both-libraries/gpu-processes.txt"
  fixture_checkpoint evidence-after-both-libraries

  mkdir "$fixture/evidence invalid-signature" "$fixture/evidence nonadhoc"
  fixture_checkpoint evidence-before-invalid-signature
  expect_fail env CODESIGN_INVALID=1 "$collect" "$focused_output" "$fixture/evidence invalid-signature"
  fixture_checkpoint evidence-before-nonadhoc
  expect_fail env CODESIGN_NONADHOC=1 "$collect" "$focused_output" "$fixture/evidence nonadhoc"
  fixture_checkpoint evidence-after-signature-rejections

  chmod u+w "$focused_manifest" "$focused_manifest.sha256"
  awk 'BEGIN { FS = OFS = "=" } $1 == "COPY_POLICY" { $2 = "unexpected" } { print }' \
    "$focused_manifest" > "$focused_manifest.new"
  mv "$focused_manifest.new" "$focused_manifest"
  printf '%s  %s\n' "$(shasum -a 256 "$focused_manifest" | awk '{print $1}')" "$(basename "$focused_manifest")" > "$focused_manifest.sha256"
  chmod 0444 "$focused_manifest" "$focused_manifest.sha256"
  mkdir "$fixture/evidence policy-mismatch"
  fixture_checkpoint evidence-policy-mismatch
  expect_fail "$collect" "$focused_output" "$fixture/evidence policy-mismatch"

  chmod u+w "$focused_manifest" "$focused_manifest.sha256"
  awk 'BEGIN { FS = OFS = "=" } $1 == "COPY_POLICY" { $2 = "norsrc,noextattr,noacl,noqtn" } { print }' \
    "$focused_manifest" > "$focused_manifest.new"
  mv "$focused_manifest.new" "$focused_manifest"
  printf '%s  %s\n' "$(shasum -a 256 "$focused_manifest" | awk '{print $1}')" "$(basename "$focused_manifest")" > "$focused_manifest.sha256"
  chmod 0444 "$focused_manifest" "$focused_manifest.sha256"

  chmod u+w "$focused_receipt" "$focused_receipt.sha256"
  awk 'BEGIN { FS = OFS = "=" } $1 == "PREPARE_MANIFEST_SHA256" { $2 = "0000000000000000000000000000000000000000000000000000000000000000" } { print }' \
    "$focused_receipt" > "$focused_receipt.new"
  mv "$focused_receipt.new" "$focused_receipt"
  printf '%s  %s\n' "$(shasum -a 256 "$focused_receipt" | awk '{print $1}')" "$(basename "$focused_receipt")" > "$focused_receipt.sha256"
  chmod 0444 "$focused_receipt" "$focused_receipt.sha256"
  mkdir "$fixture/evidence tampered-receipt"
  fixture_checkpoint evidence-tampered-receipt
  expect_fail "$collect" "$focused_output" "$fixture/evidence tampered-receipt"
  fixture_group_end evidence-receipt-policy
}

if [[ "$fixture_group" == source-detritus ]]; then
  run_source_detritus_group
  exit 0
fi
if [[ "$fixture_group" == source-unknown ]]; then
  run_source_unknown_group
  exit 0
fi
if [[ "$fixture_group" == control-link ]]; then
  run_control_link_group
  exit 0
fi
if [[ "$fixture_group" == evidence-receipt-policy ]]; then
  run_evidence_receipt_policy_group
  exit 0
fi

expect_fail "$prepare" "$source_app" "$artifact" "$source_app"
expect_fail "$prepare" "$source_app" "$artifact" '/Applications/Rejected.app'
mkdir "$fixture/existing.app"
expect_fail "$prepare" "$source_app" "$artifact" "$fixture/existing.app"
ln -s /Applications "$fixture/applications-link"
expect_fail "$prepare" "$source_app" "$artifact" "$fixture/applications-link/Rejected.app"
expect_fail env PHASE3_FIXTURE_FORCE_ROOT=1 "$prepare" "$source_app" "$artifact" "$fixture/root.app"
expect_fail env FORCE_HASH_MISMATCH=1 "$prepare" "$source_app" "$artifact" "$fixture/hash-mismatch.app"
artifact_missing="$fixture/artifact-missing-library"
mkdir "$artifact_missing"
cp "$artifact/libEGL.dylib" "$artifact_missing/libEGL.dylib"
cp "$artifact/ANGLE_REVISION" "$artifact_missing/ANGLE_REVISION"
expect_fail "$prepare" "$source_app" "$artifact_missing" "$fixture/missing-library.app"

cp -R "$source_app" "$fixture/wrong-version.app"
/usr/libexec/PlistBuddy -c 'Set :CFBundleShortVersionString 0.0.0.0' "$fixture/wrong-version.app/Contents/Info.plist"
expect_fail "$prepare" "$fixture/wrong-version.app" "$artifact" "$fixture/version-mismatch.app"

run_source_detritus_group
run_source_unknown_group

for copy_failure in app main framework gpu; do
  copy_failure_output="$fixture/copy strict ${copy_failure}/Google Chrome 154 ANGLE Test.app"
  mkdir -p "$(dirname "$copy_failure_output")"
  expect_fail env CODESIGN_COPY_STRICT_TARGET="$copy_failure" "$prepare" "$source_app" "$artifact" "$copy_failure_output"
  assert_source_unchanged
  test -d "$copy_failure_output"
  test ! -e "$copy_failure_output/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib"
done

copy_team_output="$fixture/copy team mismatch/Google Chrome 154 ANGLE Test.app"
mkdir -p "$(dirname "$copy_team_output")"
expect_fail env CODESIGN_COPY_TEAM_MISMATCH=1 "$prepare" "$source_app" "$artifact" "$copy_team_output"
assert_source_unchanged
test ! -e "$copy_team_output/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib"

copy_xattr_output="$fixture/copy xattr detritus/Google Chrome 154 ANGLE Test.app"
mkdir -p "$(dirname "$copy_xattr_output")"
expect_fail env XATTR_COPY_DETRITUS=1 "$prepare" "$source_app" "$artifact" "$copy_xattr_output"
assert_source_unchanged
test ! -e "$copy_xattr_output/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib"

for copy_mutation in missing-main nonexec-main; do
  copy_mutation_output="$fixture/copy mutation ${copy_mutation}/Google Chrome 154 ANGLE Test.app"
  mkdir -p "$(dirname "$copy_mutation_output")"
  expect_fail env DITTO_COPY_MUTATION="$copy_mutation" "$prepare" "$source_app" "$artifact" "$copy_mutation_output"
  assert_source_unchanged
  test ! -e "$copy_mutation_output/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib"
done

for library_link in other foo parent dot normalized trailing external absolute-internal broken source regular-file; do
  library_link_output="$fixture/library link ${library_link}/Google Chrome 154 ANGLE Test.app"
  mkdir -p "$(dirname "$library_link_output")"
  expect_fail env DITTO_LIBRARY_LINK="$library_link" "$prepare" "$source_app" "$artifact" "$library_link_output"
  assert_source_unchanged
  test ! -e "$library_link_output/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib"
done

for baseline_mutation in missing sha link control-name control-link; do
  baseline_output="$fixture/baseline ${baseline_mutation}/Google Chrome 154 ANGLE Test.app"
  mkdir -p "$(dirname "$baseline_output")"
  expect_fail env DITTO_BASELINE_MUTATION="$baseline_mutation" "$prepare" "$source_app" "$artifact" "$baseline_output"
  test ! -e "$baseline_output/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib"
done

control_name_source="$fixture/control-name Source.app"
cp -R "$source_app" "$control_name_source"
mv "$control_name_source/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libaperitif.dylib" \
  "$control_name_source/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libaperitif"$'\t'"name.dylib"
control_name_output="$fixture/control-name/Google Chrome 154 ANGLE Test.app"
mkdir -p "$(dirname "$control_name_output")"
expect_fail "$prepare" "$control_name_source" "$artifact" "$control_name_output"
test ! -e "$control_name_output/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib"

run_control_link_group

collision_source="$fixture/ANGLE collision Source.app"
cp -R "$source_app" "$collision_source"
printf 'collision\n' > "$collision_source/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib"
collision_output="$fixture/angle collision/Google Chrome 154 ANGLE Test.app"
mkdir -p "$(dirname "$collision_output")"
expect_fail "$prepare" "$collision_source" "$artifact" "$collision_output"
grep -F 'collision' "$collision_output/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib" >/dev/null

"$prepare" "$source_app" "$artifact" "$output"
assert_source_unchanged
test -f "$output.phase3-angle-manifest"
grep -F 'SCHEMA=phase3-angle-test-copy-v3' "$output.phase3-angle-manifest" >/dev/null
grep -F 'COPY_POLICY=norsrc,noextattr,noacl,noqtn' "$output.phase3-angle-manifest" >/dev/null
grep -F 'COPY_POLICY=norsrc,noextattr,noacl,noqtn' "$output.phase3-angle-manifest.evidence/copy-policy.txt" >/dev/null
grep -F -- 'ditto --norsrc --noextattr --noacl --noqtn SOURCE_APP OUTPUT_APP' "$output.phase3-angle-manifest.evidence/copy-command.txt" >/dev/null
test -f "$output.phase3-angle-manifest.evidence/libraries-baseline-inventory.txt"
test -f "$output.phase3-angle-manifest.evidence/libraries-final-inventory.txt"
directory_output="$fixture/regular directory/Google Chrome 154 ANGLE Test.app"
mkdir -p "$(dirname "$directory_output")"
env DITTO_LIBRARY_LINK=directory "$prepare" "$source_app" "$artifact" "$directory_output"
test -f "$directory_output/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib"
empty_source="$fixture/Empty Source.app"
cp -R "$source_app" "$empty_source"
find "$empty_source/Contents/Frameworks/Google Chrome Framework.framework/Libraries" -type f -delete
empty_output="$fixture/empty baseline/Google Chrome 154 ANGLE Test.app"
mkdir -p "$(dirname "$empty_output")"
"$prepare" "$empty_source" "$artifact" "$empty_output"
test -f "$empty_output/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib"
expect_fail "$run" CASE_B "$output" "$fixture/run-unsigned"
expect_fail "$sign" "$source_app" "$fixture/sign-original" --dry-run
expect_fail "$sign" "$output" "$fixture/sign-no-confirm"
printf '' > "$PHASE3_FIXTURE_LOG"
"$sign" "$output" "$fixture/sign-dry-run" --dry-run
test ! -s "$PHASE3_FIXTURE_LOG"
manifest="$output.phase3-angle-manifest"
manifest_hash="$manifest.sha256"
chmod u+w "$manifest" "$manifest_hash"
awk 'BEGIN { FS = OFS = "=" } $1 == "COPY_POLICY" { $2 = "unexpected" } { print }' "$manifest" > "$manifest.new"
mv "$manifest.new" "$manifest"
printf '%s  %s\n' "$(shasum -a 256 "$manifest" | awk '{print $1}')" "$(basename "$manifest")" > "$manifest_hash"
chmod 0444 "$manifest" "$manifest_hash"
expect_fail "$sign" "$output" "$fixture/sign-policy-mismatch" --dry-run
chmod u+w "$manifest" "$manifest_hash"
awk 'BEGIN { FS = OFS = "=" } $1 == "COPY_POLICY" { $2 = "norsrc,noextattr,noacl,noqtn" } { print }' "$manifest" > "$manifest.new"
mv "$manifest.new" "$manifest"
printf '%s  %s\n' "$(shasum -a 256 "$manifest" | awk '{print $1}')" "$(basename "$manifest")" > "$manifest_hash"
chmod 0444 "$manifest" "$manifest_hash"

mkdir -p "$(dirname "$output_after_tamper")"
"$prepare" "$source_app" "$artifact" "$output_after_tamper"
printf 'unexpected\n' > "$output_after_tamper/Contents/Frameworks/Google Chrome Framework.framework/Libraries/unexpected.dylib"
expect_fail "$sign" "$output_after_tamper" "$fixture/sign-unexpected" --dry-run
manifest="$output_after_tamper.phase3-angle-manifest"
chmod 0644 "$manifest"
printf 'tampered\n' >> "$manifest"
expect_fail "$sign" "$output_after_tamper" "$fixture/sign-tampered" --dry-run
output_no_manifest="$fixture/output no manifest/Google Chrome 154 ANGLE Test.app"
mkdir -p "$(dirname "$output_no_manifest")"
cp -R "$output" "$output_no_manifest"
expect_fail "$run" CASE_B "$output_no_manifest" "$fixture/run-missing-manifest"
output_signed="$fixture/output signed/Google Chrome 154 ANGLE Test.app"
mkdir -p "$(dirname "$output_signed")"
"$prepare" "$source_app" "$artifact" "$output_signed"
"$sign" "$output_signed" "$fixture/sign-confirmed" --confirm-ad-hoc-signing
inventory="$output_signed.phase3-angle-manifest.evidence/libraries-baseline-inventory.txt"
cp "$inventory" "$inventory.backup"
chmod u+w "$inventory"
printf 'tampered\n' >> "$inventory"
expect_fail "$sign" "$output_signed" "$fixture/sign-inventory-tampered" --dry-run
expect_fail "$run" CASE_B "$output_signed" "$fixture/run-inventory-tampered"
expect_fail "$collect" "$output_signed" "$fixture/collect-inventory-tampered"
mv "$inventory.backup" "$inventory"
process_snapshot="$fixture/process-snapshot.txt"
printf '111 fixture caller argument only: %s\n' "$output_signed" > "$process_snapshot"
export PHASE3_FIXTURE_PS_SNAPSHOT="$process_snapshot"
"$run" CASE_B "$output_signed" "$fixture/case-b"
"$run" CASE_C "$output_signed" "$fixture/case-c"
! grep -F -- '--disable-angle-features=requireGpuFamily2' "$fixture/case-b/run-metadata.txt"
grep -F -- '--disable-angle-features=requireGpuFamily2' "$fixture/case-c/run-metadata.txt" >/dev/null
printf '222 %s --type=gpu-process\n' "$output_signed/Contents/MacOS/Google Chrome" > "$process_snapshot"
expect_fail "$run" CASE_B "$output_signed" "$fixture/case-already-running"

framework="$output_signed/Contents/Frameworks/Google Chrome Framework.framework"
libraries="$framework/Libraries"
export PHASE3_FIXTURE_LIBRARIES="$libraries"
cat > "$process_snapshot" <<EOF
333 /unrelated/Google Chrome Framework.framework/Helpers/Google Chrome Helper (GPU) --type=gpu-process
444 $framework/Helpers/Google Chrome Helper (GPU).app/Contents/MacOS/Google Chrome Helper (GPU) --type=gpu-process
EOF
mkdir "$fixture/evidence-one-library" "$fixture/evidence-both-libraries" "$fixture/evidence-invalid-signature" "$fixture/evidence-nonadhoc" "$fixture/evidence-tampered-receipt"
unset PHASE3_FIXTURE_LSOF_BOTH
"$collect" "$output_signed" "$fixture/evidence-one-library"
! grep -F 'direct dynamic ANGLE load evidence' "$fixture/evidence-one-library/load-evidence.txt"
export PHASE3_FIXTURE_LSOF_BOTH=1
"$collect" "$output_signed" "$fixture/evidence-both-libraries"
grep -F 'direct dynamic ANGLE load evidence: lsof confirmed both test-copy dylib absolute paths for GPU PID 444' "$fixture/evidence-both-libraries/load-evidence.txt" >/dev/null
grep -F '444 ' "$fixture/evidence-both-libraries/gpu-processes.txt" >/dev/null
! grep -F '333 ' "$fixture/evidence-both-libraries/gpu-processes.txt"
expect_fail env CODESIGN_INVALID=1 "$collect" "$output_signed" "$fixture/evidence-invalid-signature"
expect_fail env CODESIGN_NONADHOC=1 "$collect" "$output_signed" "$fixture/evidence-nonadhoc"

manifest="$output_signed.phase3-angle-manifest"
manifest_hash="$manifest.sha256"
chmod u+w "$manifest" "$manifest_hash"
awk 'BEGIN { FS = OFS = "=" } $1 == "COPY_POLICY" { $2 = "unexpected" } { print }' "$manifest" > "$manifest.new"
mv "$manifest.new" "$manifest"
printf '%s  %s\n' "$(shasum -a 256 "$manifest" | awk '{print $1}')" "$(basename "$manifest")" > "$manifest_hash"
chmod 0444 "$manifest" "$manifest_hash"
mkdir "$fixture/case-policy-mismatch" "$fixture/evidence-policy-mismatch"
expect_fail "$run" CASE_B "$output_signed" "$fixture/case-policy-mismatch"
expect_fail "$collect" "$output_signed" "$fixture/evidence-policy-mismatch"
chmod u+w "$manifest" "$manifest_hash"
awk 'BEGIN { FS = OFS = "=" } $1 == "COPY_POLICY" { $2 = "norsrc,noextattr,noacl,noqtn" } { print }' "$manifest" > "$manifest.new"
mv "$manifest.new" "$manifest"
printf '%s  %s\n' "$(shasum -a 256 "$manifest" | awk '{print $1}')" "$(basename "$manifest")" > "$manifest_hash"
chmod 0444 "$manifest" "$manifest_hash"

receipt="$output_signed.phase3-angle-signing-receipt"
receipt_hash="$receipt.sha256"
chmod u+w "$receipt" "$receipt_hash"
awk 'BEGIN { FS = OFS = "=" } $1 == "PREPARE_MANIFEST_SHA256" { $2 = "0000000000000000000000000000000000000000000000000000000000000000" } { print }' "$receipt" > "$receipt.new"
mv "$receipt.new" "$receipt"
printf '%s  %s\n' "$(shasum -a 256 "$receipt" | awk '{print $1}')" "$(basename "$receipt")" > "$receipt_hash"
chmod 0444 "$receipt" "$receipt_hash"
expect_fail "$run" CASE_B "$output_signed" "$fixture/case-tampered-receipt"
expect_fail "$collect" "$output_signed" "$fixture/evidence-tampered-receipt"
printf 'phase3b fixture tests passed\n'
