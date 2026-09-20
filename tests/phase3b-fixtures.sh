#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd -P)
fixture=$(mktemp -d /private/tmp/phase3b-fixture.XXXXXX)
printf 'fixture directory retained for inspection: %s\n' "$fixture"
stub_dir="$fixture/stubs"
mkdir "$stub_dir" "$fixture/output with spaces"
export PHASE3_FIXTURE_LOG="$fixture/command.log"

cat > "$stub_dir/codesign" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'codesign %q\n' "$*" >> "$PHASE3_FIXTURE_LOG"
target=${!#}
if [[ " $* " == *' --force '* ]]; then touch "$target/.fixture-ad-hoc"; exit 0; fi
if [[ " $* " == *' --verify '* ]]; then
  [[ "${CODESIGN_INVALID:-0}" != 1 ]] || exit 1
  if [[ "$target" == *'ANGLE Test.app'* && -f "$target/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib" && ! -e "$target/.fixture-ad-hoc" ]]; then exit 1; fi
  exit 0
fi
if [[ -e "$target/.fixture-ad-hoc" && "${CODESIGN_NONADHOC:-0}" != 1 ]]; then echo 'Signature=adhoc'; else echo 'TeamIdentifier=EQHXZ8M8AV'; echo 'flags=0x10000(runtime)'; fi
EOF
cat > "$stub_dir/xattr" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'xattr %q\n' "$*" >> "$PHASE3_FIXTURE_LOG"
exit 0
EOF
cat > "$stub_dir/ditto" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'ditto %q\n' "$*" >> "$PHASE3_FIXTURE_LOG"
args=("$@")
source=${args[$(( ${#args[@]} - 2 ))]}
output=${args[$(( ${#args[@]} - 1 ))]}
cp -R "$source" "$output"
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

source_app="$fixture/Chrome Source.app"
artifact="$fixture/artifact"
mkdir -p "$source_app/Contents/MacOS" "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Helpers/Google Chrome Helper (GPU).app/Contents/MacOS" "$artifact"
cat > "$source_app/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>CFBundleShortVersionString</key><string>154.0.8037.45</string><key>CFBundleExecutable</key><string>Google Chrome</string></dict></plist>
EOF
printf '#!/usr/bin/env bash\nexit 0\n' > "$source_app/Contents/MacOS/Google Chrome"
printf '#!/usr/bin/env bash\nexit 0\n' > "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Helpers/Google Chrome Helper (GPU).app/Contents/MacOS/Google Chrome Helper (GPU)"
chmod +x "$source_app/Contents/MacOS/Google Chrome" "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Helpers/Google Chrome Helper (GPU).app/Contents/MacOS/Google Chrome Helper (GPU)"
printf 'fixture egl\n' > "$artifact/libEGL.dylib"
printf 'fixture gles\n' > "$artifact/libGLESv2.dylib"
printf '%s\n' '72b8f72a7587ec776d7d2a57d275a6e9b1781b1d' > "$artifact/ANGLE_REVISION"

expect_fail() { if "$@" >/dev/null 2>&1; then printf 'expected failure: %q\n' "$*" >&2; exit 1; fi; }
prepare="$repo_root/scripts/prepare-chrome-angle-test-copy.sh"
sign="$repo_root/scripts/sign-chrome-angle-test-copy.sh"
run="$repo_root/scripts/run-dynamic-angle-test.sh"
collect="$repo_root/scripts/collect-phase3-evidence.sh"
output="$fixture/output with spaces/Google Chrome 154 ANGLE Test.app"
output_after_tamper="$fixture/output after tamper/Google Chrome 154 ANGLE Test.app"

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

source_snapshot="$fixture/source-snapshot"
cp -R "$source_app" "$source_snapshot"
"$prepare" "$source_app" "$artifact" "$output"
diff -qr "$source_app" "$source_snapshot"
test -f "$output.phase3-angle-manifest"
expect_fail "$run" CASE_B "$output" "$fixture/run-unsigned"
expect_fail "$sign" "$source_app" "$fixture/sign-original" --dry-run
expect_fail "$sign" "$output" "$fixture/sign-no-confirm"
printf '' > "$PHASE3_FIXTURE_LOG"
"$sign" "$output" "$fixture/sign-dry-run" --dry-run
test ! -s "$PHASE3_FIXTURE_LOG"

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
