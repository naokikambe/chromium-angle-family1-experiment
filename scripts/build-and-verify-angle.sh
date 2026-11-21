#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  printf 'usage: %s REPOSITORY_ROOT INPUTS_JSON OUTPUT_DIRECTORY ARTIFACT_NAME\n' "$0" >&2
  exit 64
fi
repo_root=$(cd "$1" && pwd -P)
inputs_json=$2
artifact_dir=$3
artifact_name=$4
: "${GITHUB_RUN_ID:?GITHUB_RUN_ID is required}"

bash "$repo_root/scripts/build-angle-candidate.sh" "$repo_root" "$inputs_json" "$artifact_dir"
printf 'manifest-and-binary-validation\n' > "${FAILURE_STAGE_FILE:-/dev/null}"
bash "$repo_root/scripts/verify-artifact.sh" "$artifact_dir"
readarray_input=$(python3 - "$inputs_json" <<'PY'
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
print(value["chrome_version"])
print(value["architecture"])
print(value["recipe"]["macos_deployment_target"])
print(value["build_key"])
PY
)
chrome_version=$(printf '%s\n' "$readarray_input" | sed -n '1p')
architecture=$(printf '%s\n' "$readarray_input" | sed -n '2p')
deployment_target=$(printf '%s\n' "$readarray_input" | sed -n '3p')
build_key=$(printf '%s\n' "$readarray_input" | sed -n '4p')
bash "$repo_root/scripts/verify-angle-binaries.sh" "$artifact_dir" "$architecture" "$deployment_target"
python3 "$repo_root/scripts/write-angle-manifest.py" --artifact-dir "$artifact_dir" --inputs "$inputs_json" \
  --run-id "$GITHUB_RUN_ID" --artifact-name "$artifact_name" \
  --xcode-version "$(xcodebuild -version | tr '\n' ';')" \
  --sdk-version "$(xcrun --show-sdk-version)" \
  --clang-version "$(xcrun clang --version | head -n 1)" \
  --ninja-version "$(ninja --version)"
python3 "$repo_root/scripts/verify-angle-artifact.py" "$artifact_dir" \
  --version "$chrome_version" --architecture "$architecture" --build-key "$build_key"
