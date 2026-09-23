#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd -P)
ensure="$repo_root/scripts/ensure-angle-release-artifact.sh"
fixture=$(mktemp -d /private/tmp/phase3-release-artifact-fixture.XXXXXX)
printf 'release artifact fixture retained for inspection: %s\n' "$fixture"
stub_dir="$fixture/stubs"
mkdir "$stub_dir"

readonly fixture_version='154.0.8037.58'
readonly fixture_chromium='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
readonly fixture_angle='bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
readonly fixture_depot_tools='0306e4682b4ac35287c726fa35a983157a625902'

make_source_app() {
  local app=$1 version=$2
  mkdir -p "$app/Contents"
  cat > "$app/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>CFBundleShortVersionString</key><string>$version</string></dict></plist>
EOF
}

make_artifact() {
  local artifact=$1 version=$2 run_id=$3
  mkdir -p "$artifact"
  printf 'fixture egl %s\n' "$version" > "$artifact/libEGL.dylib"
  printf 'fixture gles %s\n' "$version" > "$artifact/libGLESv2.dylib"
  egl_sha=$(/usr/bin/shasum -a 256 "$artifact/libEGL.dylib" | awk '{print $1}')
  gles_sha=$(/usr/bin/shasum -a 256 "$artifact/libGLESv2.dylib" | awk '{print $1}')
  cat > "$artifact/ANGLE_RELEASE_MANIFEST" <<EOF
SCHEMA=angle-release-v1
ARTIFACT_SCHEMA=angle-artifact-v1
CHROME_VERSION=$version
CHROMIUM_REVISION=$fixture_chromium
ANGLE_REVISION=$fixture_angle
DEPOT_TOOLS_REVISION=$fixture_depot_tools
LIBEGL_SHA256=$egl_sha
LIBGLESV2_SHA256=$gles_sha
ARTIFACT_NAME=angle-macos-x86_64-chrome-${version}-angle-${fixture_angle:0:8}-${run_id}
BUILD_RUN_ID=$run_id
BUILT_AT_UTC=2026-09-23T00:00:00Z
GN_ARGS_SHA256=cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
EOF
  /usr/bin/shasum -a 256 "$artifact/ANGLE_RELEASE_MANIFEST" |
    awk '{print $1 "  ANGLE_RELEASE_MANIFEST"}' > "$artifact/ANGLE_RELEASE_MANIFEST.sha256"
}

cat > "$stub_dir/gh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'gh' >> "$PHASE3_STEP0_GH_LOG"
printf ' %q' "$@" >> "$PHASE3_STEP0_GH_LOG"
printf '\n' >> "$PHASE3_STEP0_GH_LOG"

if [[ "$1 $2" == 'workflow run' ]]; then
  touch "$PHASE3_STEP0_DISPATCHED"
  exit 0
fi
if [[ "$1 $2" == 'run list' ]]; then
  if [[ -e "$PHASE3_STEP0_DISPATCHED" ]]; then
    printf '222\n111\n'
  else
    printf '111\n'
  fi
  exit 0
fi
if [[ "$1 $2" == 'run watch' ]]; then
  [[ "${PHASE3_STEP0_FAIL_BUILD:-0}" != 1 ]]
  exit
fi
if [[ "$1" == api ]]; then
  printf '%s\n' "$PHASE3_STEP0_ARTIFACT_NAME"
  exit 0
fi
if [[ "$1 $2" == 'run download' ]]; then
  destination=''
  while [[ $# -gt 0 ]]; do
    if [[ "$1" == --dir ]]; then
      destination=$2
      break
    fi
    shift
  done
  [[ -n "$destination" ]]
  cp -R "$PHASE3_STEP0_DOWNLOAD_TEMPLATE/." "$destination/"
  exit 0
fi
printf 'unexpected gh invocation\n' >&2
exit 70
EOF
chmod +x "$stub_dir/gh"

expect_fail() {
  if "$@"; then
    printf 'expected failure: %q ' "$@" >&2
    printf '\n' >&2
    exit 1
  fi
}

export PATH="$stub_dir:$PATH"
export PHASE3_STEP0_GH_LOG="$fixture/gh.log"
export PHASE3_STEP0_DISPATCHED="$fixture/dispatched"
source_app="$fixture/Google Chrome.app"
make_source_app "$source_app" "$fixture_version"

# A single verified matching artifact is returned without any GitHub call.
reuse_cache="$fixture/reuse-cache"
mkdir "$reuse_cache"
make_artifact "$reuse_cache/artifact" "$fixture_version" 100
selected=$("$ensure" --source-app "$source_app" --artifact-cache-root "$reuse_cache")
test "$selected" = "$reuse_cache/artifact"
test ! -e "$PHASE3_STEP0_GH_LOG"

# Invalid and version-mismatched candidates are not reused. The newly
# dispatched artifact is downloaded, verified, and returned.
dispatch_cache="$fixture/dispatch-cache"
download_template="$fixture/download-template"
mkdir "$dispatch_cache"
make_artifact "$dispatch_cache/invalid" "$fixture_version" 101
printf 'tampered\n' >> "$dispatch_cache/invalid/libEGL.dylib"
make_artifact "$dispatch_cache/other-version" 154.0.8037.57 102
make_artifact "$download_template" "$fixture_version" 222
export PHASE3_STEP0_DOWNLOAD_TEMPLATE="$download_template"
export PHASE3_STEP0_ARTIFACT_NAME="angle-macos-x86_64-chrome-${fixture_version}-angle-${fixture_angle:0:8}-222"
: > "$PHASE3_STEP0_GH_LOG"
rm -f "$PHASE3_STEP0_DISPATCHED"
selected=$("$ensure" --source-app "$source_app" --artifact-cache-root "$dispatch_cache")
test "$selected" = "$dispatch_cache/run-222-artifact"
grep -F 'workflow run build-angle-macos-x64.yml' "$PHASE3_STEP0_GH_LOG" >/dev/null
grep -F "chrome_version=$fixture_version" "$PHASE3_STEP0_GH_LOG" >/dev/null
grep -F 'run watch 222' "$PHASE3_STEP0_GH_LOG" >/dev/null
grep -F 'run download 222' "$PHASE3_STEP0_GH_LOG" >/dev/null

# Ambiguous verified matches fail closed without dispatching a build.
multiple_cache="$fixture/multiple-cache"
mkdir "$multiple_cache"
make_artifact "$multiple_cache/first" "$fixture_version" 301
make_artifact "$multiple_cache/second" "$fixture_version" 302
: > "$PHASE3_STEP0_GH_LOG"
rm -f "$PHASE3_STEP0_DISPATCHED"
expect_fail "$ensure" --source-app "$source_app" --artifact-cache-root "$multiple_cache"
test ! -s "$PHASE3_STEP0_GH_LOG"

# A failed build is reported without downloading or retrying it.
failed_cache="$fixture/failed-cache"
mkdir "$failed_cache"
: > "$PHASE3_STEP0_GH_LOG"
rm -f "$PHASE3_STEP0_DISPATCHED"
export PHASE3_STEP0_FAIL_BUILD=1
expect_fail "$ensure" --source-app "$source_app" --artifact-cache-root "$failed_cache"
test ! -e "$failed_cache/run-222-artifact"
unset PHASE3_STEP0_FAIL_BUILD

ln -s "$reuse_cache" "$fixture/cache-link"
expect_fail "$ensure" --source-app "$source_app" --artifact-cache-root "$fixture/cache-link"

printf 'phase3 release artifact fixture tests passed\n'
