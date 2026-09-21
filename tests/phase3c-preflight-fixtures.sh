#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd -P)
preflight="$repo_root/scripts/run-phase3c-preflight.sh"
fixture=$(mktemp -d /private/tmp/phase3c-preflight.XXXXXX)
stub_dir="$fixture/stubs"
mkdir -p "$stub_dir"
export PATH="$stub_dir:$PATH"

cat > "$stub_dir/codesign" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
target=${!#}
case " $* " in
  *' --verify '*) exit 0 ;;
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
if [[ "${PHASE3C_SOURCE_PROCESS:-0}" == 1 ]]; then
  printf '777 %s/Contents/MacOS/Google Chrome --type=gpu-process\n' "$PHASE3C_SOURCE_APP"
fi
EOF
cat > "$stub_dir/ditto" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
source="${@: -2:1}"
output="${@: -1}"
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
printf 'baseline\n' > "$source_app/Contents/Frameworks/Google Chrome Framework.framework/Libraries/libchrome.dylib"
printf 'egl\n' > "$artifact_dir/libEGL.dylib"
printf 'gles\n' > "$artifact_dir/libGLESv2.dylib"
printf '%s\n' '72b8f72a7587ec776d7d2a57d275a6e9b1781b1d' > "$artifact_dir/ANGLE_REVISION"

expect_fail() { if "$@" >/dev/null 2>&1; then printf 'expected failure: %s\n' "$*" >&2; exit 1; fi; }
"$preflight" --help >/dev/null
expect_fail "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/retry0/out.app" --results-dir "$fixture/results-retry0"
mkdir "$fixture/existing-output.app" "$fixture/existing-results"
expect_fail "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/existing-output.app" --results-dir "$fixture/results-new"
expect_fail "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/new-output.app" --results-dir "$fixture/existing-results"
ln -s "$source_app" "$fixture/source-link.app"
expect_fail "$preflight" --source-app "$fixture/source-link.app" --artifact-dir "$artifact_dir" --output-app "$fixture/link-output.app" --results-dir "$fixture/link-results"
expect_fail env FORCE_HASH_MISMATCH=1 "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/hash-output.app" --results-dir "$fixture/hash-results"
export PHASE3C_SOURCE_APP="$source_app"
expect_fail env PHASE3C_SOURCE_PROCESS=1 "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/process-output.app" --results-dir "$fixture/process-results"
unset PHASE3C_SOURCE_PROCESS
success_log="$fixture/success-preflight.log"
if ! bash -x "$preflight" --source-app "$source_app" --artifact-dir "$artifact_dir" --output-app "$fixture/phase3c-output.app" --results-dir "$fixture/phase3c-results" > "$success_log" 2>&1; then
  cat "$success_log" >&2
  exit 1
fi
test -f "$fixture/phase3c-output.app.phase3-angle-manifest"
test -f "$fixture/phase3c-results/sign-dry-run.txt"
grep -F 'no xattr or codesign command was executed.' "$fixture/phase3c-results/sign-dry-run.txt" >/dev/null
printf '%s\n' 'phase3c preflight fixture tests passed'
