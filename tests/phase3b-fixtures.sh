#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd -P)
source "$repo_root/scripts/phase3-test-copy-common.sh"
fixture=$(mktemp -d /private/tmp/phase3b-fixture.XXXXXX)
printf 'fixture directory retained for inspection: %s\n' "$fixture"
stub_dir="$fixture/stubs"
mkdir "$stub_dir" "$fixture/output with spaces"
export PHASE3_FIXTURE_LOG="$fixture/command.log"
export PHASE3_FIXTURE_VERSION='154.0.8037.58'
export PHASE3_FIXTURE_PREVIOUS_VERSION='154.0.8037.57'
export PHASE3_FIXTURE_APPLE_DEVELOPMENT_ID='0123456789ABCDEF0123456789ABCDEF01234567'

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
if [[ " $* " == *' --force '* ]]; then
  signature_marker='.fixture-ad-hoc'
  [[ " $* " == *' --sign - '* ]] || signature_marker='.fixture-apple-development'
  if [[ "$target" == *.framework ]]; then
    current_version=$(readlink "$target/Versions/Current")
    touch "$target/Versions/$current_version/$signature_marker"
    touch "$target/$signature_marker"
  elif [[ -d "$target" ]]; then
    touch "$target/$signature_marker"
    if [[ " $* " == *' --options runtime,kill,restrict '* ]]; then
      touch "$target/.fixture-jit-options"
    fi
  elif [[ "$target" == *'/Libraries/'*.dylib ]]; then
    # Model the fact that real codesign changes a Mach-O's bytes. This keeps
    # the synthetic fixture from accepting a prepared inventory after sign.
    printf 'fixture ad-hoc signature\n' >> "$target"
  fi
  exit 0
fi
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
  if [[ "$target" == *'ANGLE Test.app'* && -f "$target/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib" ]]; then
    framework="$target/Contents/Frameworks/Google Chrome Framework.framework"

    # During prepare, unsigned ANGLE dylibs must produce the original
    # Framework-root error expected by prepare's post-install gate.
    if [[ ! -e "$target/.fixture-ad-hoc" && ! -e "$target/.fixture-apple-development" ]]; then
      printf '%s: a sealed resource is missing or invalid\n' "$target" >&2
      printf 'In subcomponent: %s\n' "$framework" >&2
      exit 1
    fi

    [[ ! -e "$framework/Versions/$PHASE3_FIXTURE_PREVIOUS_VERSION" ]] || exit 1
    if [[ ! -e "$framework/Versions/$PHASE3_FIXTURE_VERSION/.fixture-ad-hoc" && ! -e "$framework/Versions/$PHASE3_FIXTURE_VERSION/.fixture-apple-development" ]]; then
      printf '%s: a sealed resource is missing or invalid\n' "$target" >&2
      printf 'In subcomponent: %s/Versions/%s\n' "$framework" "$PHASE3_FIXTURE_VERSION" >&2
      exit 1
    fi
    if [[ ! -e "$framework/.fixture-ad-hoc" && ! -e "$framework/.fixture-apple-development" ]]; then
      printf '%s: a sealed resource is missing or invalid\n' "$target" >&2
      printf 'In subcomponent: %s\n' "$framework" >&2
      exit 1
    fi
  fi
  exit 0
fi
if [[ " $* " == *' -d --entitlements '* && -e "$target/.fixture-apple-development" ]]; then
  cat <<'PLIST'
<?xml version="1.0"?><plist version="1.0"><dict>
<key>com.apple.security.device.audio-input</key><true/>
<key>com.apple.security.device.bluetooth</key><true/>
<key>com.apple.security.device.camera</key><true/>
<key>com.apple.security.device.print</key><true/>
<key>com.apple.security.device.usb</key><true/>
<key>com.apple.security.personal-information.location</key><true/>
<key>com.apple.security.personal-information.photos-library</key><true/>
</dict></plist>
PLIST
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
elif [[ -e "$target/.fixture-apple-development" && "${CODESIGN_NONADHOC:-0}" != 1 ]]; then
  echo 'Authority=Apple Development: Fixture User (FIXTURETEAM)'
  echo 'TeamIdentifier=FIXTURETEAM'
  echo 'CodeDirectory v=20500 flags=0x10000(runtime)'
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
cat > "$stub_dir/security" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ " $* " == *' find-identity '* && " $* " == *' codesigning '* ]]; then
  printf '  1) %s "Apple Development: Fixture User (FIXTURETEAM)"\n' "${PHASE3_FIXTURE_APPLE_DEVELOPMENT_ID:?}"
  exit 0
fi
exit 64
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
  nested-missing) rm -f "$target_libraries/nested/deeper/nested-file.dylib" ;;
  nested-sha) printf 'changed\n' > "$target_libraries/nested/deeper/nested-file.dylib" ;;
  nested-add) printf 'unexpected\n' > "$target_libraries/nested/deeper/nested-added.dylib" ;;
  nested-type) rm -f "$target_libraries/nested/deeper/nested-file.dylib"; mkdir "$target_libraries/nested/deeper/nested-file.dylib" ;;
  nested-link) rm -f "$target_libraries/nested/deeper/nested-file.dylib"; ln -s changed-target "$target_libraries/nested/deeper/nested-file.dylib" ;;
  nested-special) mkfifo "$target_libraries/nested/deeper/unexpected.fifo" ;;
  nested-socket) ruby -rsocket -e 'socket = Socket.new(Socket::AF_UNIX, Socket::SOCK_STREAM, 0); socket.bind(Socket.sockaddr_un(ARGV.fetch(0))); socket.close' "$target_libraries/nested/deeper/unexpected.sock" ;;
  nested-control-name) mv "$target_libraries/nested/deeper/nested-file.dylib" "$target_libraries/nested/deeper/nested"$'\t'"file.dylib" ;;
  nested-control-link) rm -f "$target_libraries/nested/internal-link"; ln -s $'changed\t-target' "$target_libraries/nested/internal-link" ;;
  nested-control-name-newline) mv "$target_libraries/nested/deeper/nested-file.dylib" "$target_libraries/nested/deeper/nested"$'\n'"file.dylib" ;;
  nested-control-link-newline) rm -f "$target_libraries/nested/internal-link"; ln -s $'changed\n-target' "$target_libraries/nested/internal-link" ;;
esac
case "${DITTO_COPY_MUTATION:-}" in
  missing-main) mv "$output/Contents/MacOS/Google Chrome" "$output/Contents/MacOS/Google Chrome.missing" ;;
  nonexec-main) chmod -x "$output/Contents/MacOS/Google Chrome" ;;
esac
versions="$output/Contents/Frameworks/Google Chrome Framework.framework/Versions"
case "${DITTO_VERSION_MUTATION:-}" in
  extra) mkdir "$versions/unexpected" ;;
  missing-current) rm -rf "$versions/$PHASE3_FIXTURE_VERSION" ;;
  current-legacy) rm "$versions/Current"; ln -s "$PHASE3_FIXTURE_PREVIOUS_VERSION" "$versions/Current" ;;
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
    */libEGL.dylib|*/libGLESv2.dylib)
      if [[ "${FORCE_HASH_MISMATCH:-0}" == 1 && "$argument" == */libGLESv2.dylib ]]; then
        echo "0000000000000000000000000000000000000000000000000000000000000000  $argument"
      else
        /usr/bin/shasum -a 256 "$argument"
      fi
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
framework="$source_app/Contents/Frameworks/Google Chrome Framework.framework"
versions="$framework/Versions"
legacy_version="$versions/$PHASE3_FIXTURE_PREVIOUS_VERSION"
current_version="$versions/$PHASE3_FIXTURE_VERSION"
mkdir -p "$source_app/Contents/MacOS" "$source_app/Contents/Resources" "$legacy_version" \
  "$current_version/Helpers/Google Chrome Helper (GPU).app/Contents/MacOS" \
  "$current_version/Helpers/Google Chrome Helper (Renderer).app/Contents/MacOS" "$artifact"
ln -s "$PHASE3_FIXTURE_VERSION" "$versions/Current"
cat > "$source_app/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>CFBundleShortVersionString</key><string>154.0.8037.58</string><key>CFBundleExecutable</key><string>Google Chrome</string></dict></plist>
EOF
printf '#!/usr/bin/env bash\nexit 0\n' > "$source_app/Contents/MacOS/Google Chrome"
printf 'fixture legacy framework\n' > "$legacy_version/Google Chrome Framework"
printf 'fixture current framework\n' > "$current_version/Google Chrome Framework"
printf '#!/usr/bin/env bash\nexit 0\n' > "$current_version/Helpers/Google Chrome Helper (GPU).app/Contents/MacOS/Google Chrome Helper (GPU)"
printf '#!/usr/bin/env bash\nexit 0\n' > "$current_version/Helpers/Google Chrome Helper (Renderer).app/Contents/MacOS/Google Chrome Helper (Renderer)"
chmod +x "$source_app/Contents/MacOS/Google Chrome" "$legacy_version/Google Chrome Framework" "$current_version/Google Chrome Framework" \
  "$current_version/Helpers/Google Chrome Helper (GPU).app/Contents/MacOS/Google Chrome Helper (GPU)" \
  "$current_version/Helpers/Google Chrome Helper (Renderer).app/Contents/MacOS/Google Chrome Helper (Renderer)"
google_update_agent="$current_version/Helpers/GoogleUpdater.app/Contents/Helpers/GoogleSoftwareUpdate.bundle/Contents/Resources/GoogleSoftwareUpdateAgent.app"
mkdir -p "$google_update_agent/Contents/MacOS"
printf '#!/usr/bin/env bash\nexit 0\n' > "$google_update_agent/Contents/MacOS/GoogleSoftwareUpdateAgent"
chmod +x "$google_update_agent/Contents/MacOS/GoogleSoftwareUpdateAgent"
mkdir -p "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries"
printf 'fixture egl\n' > "$artifact/libEGL.dylib"
printf 'fixture gles\n' > "$artifact/libGLESv2.dylib"
cat > "$artifact/args.gn" <<'EOF'
target_os = "mac"
target_cpu = "x64"
EOF
fixture_egl_sha=$(/usr/bin/shasum -a 256 "$artifact/libEGL.dylib" | awk '{print $1}')
fixture_gles_sha=$(/usr/bin/shasum -a 256 "$artifact/libGLESv2.dylib" | awk '{print $1}')
fixture_gn_sha=$(/usr/bin/shasum -a 256 "$artifact/args.gn" | awk '{print $1}')
cat > "$artifact/ANGLE_RELEASE_MANIFEST" <<EOF
SCHEMA=angle-release-v1
ARTIFACT_SCHEMA=angle-artifact-v1
CHROME_VERSION=$PHASE3_FIXTURE_VERSION
CHROMIUM_REVISION=1111111111111111111111111111111111111111
ANGLE_REVISION=2222222222222222222222222222222222222222
DEPOT_TOOLS_REVISION=3333333333333333333333333333333333333333
LIBEGL_SHA256=$fixture_egl_sha
LIBGLESV2_SHA256=$fixture_gles_sha
ARTIFACT_NAME=angle-macos-x86_64-chrome-$PHASE3_FIXTURE_VERSION-angle-22222222-123456789
BUILD_RUN_ID=123456789
BUILT_AT_UTC=2026-09-23T12:00:00Z
GN_ARGS_SHA256=$fixture_gn_sha
EOF
/usr/bin/shasum -a 256 "$artifact/ANGLE_RELEASE_MANIFEST" | awk '{print $1 "  ANGLE_RELEASE_MANIFEST"}' > "$artifact/ANGLE_RELEASE_MANIFEST.sha256"
for baseline_name in libaperitif.dylib libchromecompaneros.dylib liboptimization_guide_internal.dylib libvk_swiftshader.dylib libvulkan.dylib; do
  printf 'fixture %s\n' "$baseline_name" > "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/$baseline_name"
done
ln -s baseline-target "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/baseline-link"
printf 'fixture baseline target\n' > "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/baseline-target"
mkdir -p "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/IwaKeyDistribution/empty" \
  "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/nested/deeper" \
  "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/nested/one" \
  "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/nested/two"
printf 'fixture nested\n' > "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/nested/deeper/nested-file.dylib"
: > "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/nested/zero-leaf"
printf 'fixture duplicate one\n' > "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/nested/one/duplicate"
printf 'fixture duplicate two\n' > "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/nested/two/duplicate"
ln -s deeper/nested-file.dylib "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/nested/internal-link"
ln -s cycle-b "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/nested/cycle-a"
ln -s cycle-a "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/nested/cycle-b"

expect_fail() { if "$@" >/dev/null 2>&1; then printf 'expected failure: %q\n' "$*" >&2; exit 1; fi; }
production_prepare="$repo_root/scripts/prepare-chrome-angle-test-copy.sh"
prepare="$fixture/prepare-wrapper"
cat > "$prepare" <<EOF
#!/usr/bin/env bash
source "$production_prepare"
phase3_prepare_main "\$@" "$stub_dir/codesign"
EOF
chmod +x "$prepare"
grep -F 'phase3_prepare_main "$@" /usr/bin/codesign' "$production_prepare" >/dev/null
production_sign="$repo_root/scripts/sign-chrome-angle-test-copy.sh"
sign="$fixture/sign-wrapper"
cat > "$sign" <<EOF
#!/usr/bin/env bash
source "$production_sign"
phase3_sign_main "$stub_dir/codesign" "$stub_dir/security" "\$@"
EOF
chmod +x "$sign"
grep -F 'phase3_sign_main /usr/bin/codesign /usr/bin/security' "$production_sign" >/dev/null
run="$repo_root/scripts/run-dynamic-angle-test.sh"
collect="$repo_root/scripts/collect-phase3-evidence.sh"
run_wrapper="$fixture/run-wrapper"
cat > "$run_wrapper" <<EOF
#!/usr/bin/env bash
source "$run"
phase3_run_main "$stub_dir/codesign" "\$@"
EOF
chmod +x "$run_wrapper"
run="$run_wrapper"
collect_wrapper="$fixture/collect-wrapper"
cat > "$collect_wrapper" <<EOF
#!/usr/bin/env bash
source "$collect"
phase3_collect_main "$stub_dir/codesign" "\$@"
EOF
chmod +x "$collect_wrapper"
collect="$collect_wrapper"
grep -F 'phase3_run_main /usr/bin/codesign' "$repo_root/scripts/run-dynamic-angle-test.sh" >/dev/null
grep -F 'phase3_collect_main /usr/bin/codesign' "$repo_root/scripts/collect-phase3-evidence.sh" >/dev/null
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
  printf 'directory\tdir\t-\nnewline\tsymlink\ttarget\n' > "$inventory"
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
  "$sign" "$focused_output" "$focused_results" --identity "$PHASE3_FIXTURE_APPLE_DEVELOPMENT_ID" --confirm-apple-development-signing
  test -f "$focused_receipt.evidence/libraries-post-sign.txt"
  test -f "$focused_receipt.evidence/libraries-post-sign.txt.sha256"
  ! cmp "$focused_output.phase3-angle-manifest.evidence/libraries-post-install.txt" \
    "$focused_receipt.evidence/libraries-post-sign.txt"
  grep -F 'SCHEMA=phase3-angle-signing-receipt-v3' "$focused_receipt" >/dev/null
  grep -F 'SIGNING_METHOD=apple-development-current-framework' "$focused_receipt" >/dev/null
  grep -F 'SIGNED_LIBRARIES_INVENTORY_SHA256=' "$focused_receipt" >/dev/null
  test ! -e "$focused_output/Contents/Frameworks/Google Chrome Framework.framework/Versions/$PHASE3_FIXTURE_PREVIOUS_VERSION"
  test -e "$focused_output/Contents/Frameworks/Google Chrome Framework.framework/Versions/$PHASE3_FIXTURE_VERSION/.fixture-apple-development"
  test -e "$focused_output/Contents/Frameworks/Google Chrome Framework.framework/Versions/$PHASE3_FIXTURE_VERSION/Helpers/Google Chrome Helper (GPU).app/.fixture-jit-options"
  test -e "$focused_output/Contents/Frameworks/Google Chrome Framework.framework/Versions/$PHASE3_FIXTURE_VERSION/Helpers/Google Chrome Helper (Renderer).app/.fixture-jit-options"
  grep -F "Versions/$PHASE3_FIXTURE_VERSION" "$PHASE3_FIXTURE_LOG" >/dev/null
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
  expect_fail "$run" CASE_B "$focused_output" "$fixture/evidence policy-mismatch run"
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
  expect_fail "$run" CASE_B "$focused_output" "$fixture/evidence tampered-receipt run"
  expect_fail "$collect" "$focused_output" "$fixture/evidence tampered-receipt"

  # A v1 receipt is not silently accepted as a v2 signed-inventory receipt.
  chmod u+w "$focused_receipt" "$focused_receipt.sha256"
  awk -v prepare_hash="$(phase3_hash "$focused_manifest")" 'BEGIN { FS = OFS = "=" }
    $1 == "SCHEMA" { $2 = "phase3-angle-signing-receipt-v1" }
    $1 == "PREPARE_MANIFEST_SHA256" { $2 = prepare_hash }
    { print }' "$focused_receipt" > "$focused_receipt.new"
  mv "$focused_receipt.new" "$focused_receipt"
  printf '%s  %s\n' "$(shasum -a 256 "$focused_receipt" | awk '{print $1}')" "$(basename "$focused_receipt")" > "$focused_receipt.sha256"
  chmod 0444 "$focused_receipt" "$focused_receipt.sha256"
  mkdir "$fixture/evidence old-receipt"
  fixture_checkpoint evidence-old-receipt
  expect_fail "$run" CASE_B "$focused_output" "$fixture/evidence old-receipt run"
  expect_fail "$collect" "$focused_output" "$fixture/evidence old-receipt"
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
cp "$artifact/ANGLE_RELEASE_MANIFEST" "$artifact_missing/ANGLE_RELEASE_MANIFEST"
cp "$artifact/ANGLE_RELEASE_MANIFEST.sha256" "$artifact_missing/ANGLE_RELEASE_MANIFEST.sha256"
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
  if [[ "$library_link" == source ]]; then
    library_link_path="$library_link_output/Contents/Frameworks/Google Chrome Framework.framework/Libraries"
    test -L "$library_link_path"
    test "$(readlink -n "$library_link_path")" = '/Applications/Google Chrome.app/Contents/Frameworks/Google Chrome Framework.framework/Libraries'
  else
    test ! -e "$library_link_output/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib"
  fi
done

for baseline_mutation in missing sha link control-name control-link nested-missing nested-sha nested-add nested-type nested-link nested-special nested-socket nested-control-name nested-control-link nested-control-name-newline nested-control-link-newline; do
  baseline_output="$fixture/baseline ${baseline_mutation}/Google Chrome 154 ANGLE Test.app"
  mkdir -p "$(dirname "$baseline_output")"
  expect_fail env DITTO_BASELINE_MUTATION="$baseline_mutation" "$prepare" "$source_app" "$artifact" "$baseline_output"
  test ! -e "$baseline_output/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib"
  assert_source_unchanged
done

for version_mutation in extra missing-current current-legacy; do
  version_output="$fixture/version ${version_mutation}/Google Chrome 154 ANGLE Test.app"
  mkdir -p "$(dirname "$version_output")"
  expect_fail env DITTO_VERSION_MUTATION="$version_mutation" "$prepare" "$source_app" "$artifact" "$version_output"
  test ! -e "$version_output/Contents/Frameworks/Google Chrome Framework.framework/Versions/$PHASE3_FIXTURE_VERSION/Libraries/libEGL.dylib"
  assert_source_unchanged
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
grep -F 'SCHEMA=phase3-angle-test-copy-v6' "$output.phase3-angle-manifest" >/dev/null
grep -F 'LIBRARIES_SOURCE_BASELINE_SHA256=' "$output.phase3-angle-manifest" >/dev/null
grep -F 'LIBRARIES_COPY_BASELINE_SHA256=' "$output.phase3-angle-manifest" >/dev/null
grep -F 'LIBRARIES_POST_INSTALL_SHA256=' "$output.phase3-angle-manifest" >/dev/null
grep -F 'FRAMEWORK_VERSION_POLICY=current-only' "$output.phase3-angle-manifest" >/dev/null
grep -F "FRAMEWORK_CURRENT_VERSION=$PHASE3_FIXTURE_VERSION" "$output.phase3-angle-manifest" >/dev/null
grep -F 'FRAMEWORK_REMOVED_VERSION_NAMES_SHA256=' "$output.phase3-angle-manifest" >/dev/null
grep -F 'FRAMEWORK_VERSIONS_BEFORE_SHA256=' "$output.phase3-angle-manifest" >/dev/null
grep -F 'FRAMEWORK_REMOVED_VERSION_INVENTORY_SHA256=' "$output.phase3-angle-manifest" >/dev/null
grep -F 'FRAMEWORK_VERSIONS_AFTER_SHA256=' "$output.phase3-angle-manifest" >/dev/null
test -d "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Versions/$PHASE3_FIXTURE_PREVIOUS_VERSION"
test ! -e "$output/Contents/Frameworks/Google Chrome Framework.framework/Versions/$PHASE3_FIXTURE_PREVIOUS_VERSION"
test -d "$output/Contents/Frameworks/Google Chrome Framework.framework/Versions/$PHASE3_FIXTURE_VERSION"
test "$(readlink "$output/Contents/Frameworks/Google Chrome Framework.framework/Versions/Current")" = "$PHASE3_FIXTURE_VERSION"
test -f "$output.phase3-angle-manifest.evidence/framework-versions-before.txt"
test -f "$output.phase3-angle-manifest.evidence/framework-removed-version-inventory.txt"
grep -Fx "$PHASE3_FIXTURE_PREVIOUS_VERSION" "$output.phase3-angle-manifest.evidence/framework-removed-version-names.txt" >/dev/null
test -f "$output.phase3-angle-manifest.evidence/framework-versions-after.txt"
grep -F "$PHASE3_FIXTURE_PREVIOUS_VERSION"$'\tdir\t-' "$output.phase3-angle-manifest.evidence/framework-versions-before.txt" >/dev/null
grep -F "$PHASE3_FIXTURE_VERSION"$'\tdir\t-' "$output.phase3-angle-manifest.evidence/framework-versions-after.txt" >/dev/null
test "$(wc -l < "$output.phase3-angle-manifest.evidence/framework-versions-after.txt" | tr -d ' ')" = 2
grep -F 'COPY_POLICY=norsrc,noextattr,noacl,noqtn' "$output.phase3-angle-manifest" >/dev/null
grep -F 'COPY_POLICY=norsrc,noextattr,noacl,noqtn' "$output.phase3-angle-manifest.evidence/copy-policy.txt" >/dev/null
grep -F -- 'ditto --norsrc --noextattr --noacl --noqtn SOURCE_APP OUTPUT_APP' "$output.phase3-angle-manifest.evidence/copy-command.txt" >/dev/null
test -f "$output.phase3-angle-manifest.evidence/libraries-source-baseline.txt"
test -f "$output.phase3-angle-manifest.evidence/libraries-source-baseline.sha256"
test -f "$output.phase3-angle-manifest.evidence/libraries-copy-baseline.txt"
test -f "$output.phase3-angle-manifest.evidence/libraries-copy-baseline.sha256"
test -f "$output.phase3-angle-manifest.evidence/libraries-post-install.txt"
test -f "$output.phase3-angle-manifest.evidence/libraries-post-install.sha256"
for inventory in source-baseline copy-baseline post-install; do
  LC_ALL=C sort "$output.phase3-angle-manifest.evidence/libraries-$inventory.txt" |
    cmp - "$output.phase3-angle-manifest.evidence/libraries-$inventory.txt"
done
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
zero_source="$fixture/Zero Libraries Source.app"
cp -R "$source_app" "$zero_source"
zero_libraries="$zero_source/Contents/Frameworks/Google Chrome Framework.framework/Libraries"
find -P "$zero_libraries" -mindepth 1 -depth -exec rm -rf {} +
zero_snapshot="$fixture/zero-source-snapshot"
cp -R "$zero_source" "$zero_snapshot"
zero_output="$fixture/zero baseline/Google Chrome 154 ANGLE Test.app"
mkdir -p "$(dirname "$zero_output")"
"$prepare" "$zero_source" "$artifact" "$zero_output"
diff -qr "$zero_source" "$zero_snapshot"
zero_post="$zero_output.phase3-angle-manifest.evidence/libraries-post-install.txt"
test "$(wc -l < "$zero_post" | tr -d ' ')" = 2
grep -F $'libEGL.dylib\tfile\t' "$zero_post" >/dev/null
grep -F $'libGLESv2.dylib\tfile\t' "$zero_post" >/dev/null
expect_fail "$run" CASE_B "$output" "$fixture/run-unsigned"
expect_fail "$sign" "$source_app" "$fixture/sign-original" --dry-run
expect_fail "$sign" "$output" "$fixture/sign-no-confirm" --identity "$PHASE3_FIXTURE_APPLE_DEVELOPMENT_ID"
printf '' > "$PHASE3_FIXTURE_LOG"
"$sign" "$output" "$fixture/sign-dry-run" --dry-run --identity "$PHASE3_FIXTURE_APPLE_DEVELOPMENT_ID"
test ! -s "$PHASE3_FIXTURE_LOG"
expect_fail "$sign" "$output" "$fixture/sign-invalid-identity" --dry-run --identity 0000000000000000000000000000000000000000
manifest="$output.phase3-angle-manifest"
manifest_hash="$manifest.sha256"
for old_schema in phase3-angle-test-copy-v2 phase3-angle-test-copy-v3 phase3-angle-test-copy-v4; do
  chmod u+w "$manifest" "$manifest_hash"
  sed "s/^SCHEMA=.*/SCHEMA=$old_schema/" "$manifest" > "$manifest.new"
  mv "$manifest.new" "$manifest"
  printf '%s  %s\n' "$(shasum -a 256 "$manifest" | awk '{print $1}')" "$(basename "$manifest")" > "$manifest_hash"
  chmod 0444 "$manifest" "$manifest_hash"
  expect_fail "$sign" "$output" "$fixture/sign-$old_schema" --dry-run --identity "$PHASE3_FIXTURE_APPLE_DEVELOPMENT_ID"
  chmod u+w "$manifest" "$manifest_hash"
  sed 's/^SCHEMA=.*/SCHEMA=phase3-angle-test-copy-v6/' "$manifest" > "$manifest.new"
  mv "$manifest.new" "$manifest"
  printf '%s  %s\n' "$(shasum -a 256 "$manifest" | awk '{print $1}')" "$(basename "$manifest")" > "$manifest_hash"
  chmod 0444 "$manifest" "$manifest_hash"
done
chmod u+w "$manifest" "$manifest_hash"
awk 'BEGIN { FS = OFS = "=" } $1 == "COPY_POLICY" { $2 = "unexpected" } { print }' "$manifest" > "$manifest.new"
mv "$manifest.new" "$manifest"
printf '%s  %s\n' "$(shasum -a 256 "$manifest" | awk '{print $1}')" "$(basename "$manifest")" > "$manifest_hash"
chmod 0444 "$manifest" "$manifest_hash"
expect_fail "$sign" "$output" "$fixture/sign-policy-mismatch" --dry-run --identity "$PHASE3_FIXTURE_APPLE_DEVELOPMENT_ID"
chmod u+w "$manifest" "$manifest_hash"
awk 'BEGIN { FS = OFS = "=" } $1 == "COPY_POLICY" { $2 = "norsrc,noextattr,noacl,noqtn" } { print }' "$manifest" > "$manifest.new"
mv "$manifest.new" "$manifest"
printf '%s  %s\n' "$(shasum -a 256 "$manifest" | awk '{print $1}')" "$(basename "$manifest")" > "$manifest_hash"
chmod 0444 "$manifest" "$manifest_hash"

mkdir -p "$(dirname "$output_after_tamper")"
"$prepare" "$source_app" "$artifact" "$output_after_tamper"
printf 'unexpected\n' > "$output_after_tamper/Contents/Frameworks/Google Chrome Framework.framework/Libraries/unexpected.dylib"
expect_fail "$sign" "$output_after_tamper" "$fixture/sign-unexpected" --dry-run --identity "$PHASE3_FIXTURE_APPLE_DEVELOPMENT_ID"
manifest="$output_after_tamper.phase3-angle-manifest"
chmod 0644 "$manifest"
printf 'tampered\n' >> "$manifest"
expect_fail "$sign" "$output_after_tamper" "$fixture/sign-tampered" --dry-run --identity "$PHASE3_FIXTURE_APPLE_DEVELOPMENT_ID"
output_no_manifest="$fixture/output no manifest/Google Chrome 154 ANGLE Test.app"
mkdir -p "$(dirname "$output_no_manifest")"
cp -R "$output" "$output_no_manifest"
expect_fail "$run" CASE_B "$output_no_manifest" "$fixture/run-missing-manifest"
output_signed="$fixture/output signed/Google Chrome 154 ANGLE Test.app"
mkdir -p "$(dirname "$output_signed")"
"$prepare" "$source_app" "$artifact" "$output_signed"
"$sign" "$output_signed" "$fixture/sign-confirmed" --identity "$PHASE3_FIXTURE_APPLE_DEVELOPMENT_ID" --confirm-apple-development-signing
signed_inventory="$output_signed.phase3-angle-signing-receipt.evidence/libraries-post-sign.txt"
test -f "$signed_inventory"
! cmp "$output_signed.phase3-angle-manifest.evidence/libraries-post-install.txt" "$signed_inventory"
test ! -e "$output_signed/Contents/Frameworks/Google Chrome Framework.framework/Versions/$PHASE3_FIXTURE_PREVIOUS_VERSION"
grep -F "Versions/$PHASE3_FIXTURE_VERSION" "$PHASE3_FIXTURE_LOG" >/dev/null
! grep -F -- '--bundle-version=' "$PHASE3_FIXTURE_LOG" >/dev/null
mkdir "$output_signed/Contents/Frameworks/Google Chrome Framework.framework/Versions/$PHASE3_FIXTURE_PREVIOUS_VERSION"
expect_fail "$sign" "$output_signed" "$fixture/sign-reintroduced-version" --dry-run --identity "$PHASE3_FIXTURE_APPLE_DEVELOPMENT_ID"
expect_fail "$run" CASE_B "$output_signed" "$fixture/run-reintroduced-version"
expect_fail "$collect" "$output_signed" "$fixture/collect-reintroduced-version"
rmdir "$output_signed/Contents/Frameworks/Google Chrome Framework.framework/Versions/$PHASE3_FIXTURE_PREVIOUS_VERSION"
inventory="$output_signed.phase3-angle-manifest.evidence/libraries-copy-baseline.txt"
cp "$inventory" "$inventory.backup"
chmod u+w "$inventory"
printf 'tampered\n' >> "$inventory"
expect_fail "$sign" "$output_signed" "$fixture/sign-inventory-tampered" --dry-run --identity "$PHASE3_FIXTURE_APPLE_DEVELOPMENT_ID"
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

printf 'tampered after signing\n' >> "$output_signed/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libEGL.dylib"
expect_fail "$run" CASE_B "$output_signed" "$fixture/case-signed-inventory-tampered"
mkdir "$fixture/collect-signed-inventory-tampered"
expect_fail "$collect" "$output_signed" "$fixture/collect-signed-inventory-tampered"

run_evidence_receipt_policy_group
sign_script="$repo_root/scripts/sign-chrome-angle-test-copy.sh"
grep -F 'phase3_sign_current_framework' "$sign_script" >/dev/null
grep -F 'phase3_validate_current_only_framework "$framework"' "$sign_script" >/dev/null
grep -F 'phase3_sign_target "$codesign_executable" "$identity" "$framework"' "$sign_script" >/dev/null
! grep -F -- '--bundle-version=' "$sign_script" >/dev/null
grep -F 'SIGNING_METHOD=apple-development-current-framework' "$sign_script" >/dev/null
grep -F 'SCHEMA=phase3-angle-signing-receipt-v3' "$sign_script" >/dev/null
grep -F -- '--confirm-apple-development-signing' "$sign_script" >/dev/null
grep -F "'runtime,kill,restrict'" "$sign_script" >/dev/null
! grep -F -- '--preserve-metadata=entitlements' "$sign_script" >/dev/null
grep -F 'SIGNED_LIBRARIES_INVENTORY_SHA256=' "$sign_script" >/dev/null
! grep -F "codesign --force --sign - --deep" "$sign_script" >/dev/null
printf 'phase3b fixture tests passed\n'
