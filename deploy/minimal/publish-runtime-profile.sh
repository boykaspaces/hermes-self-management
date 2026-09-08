#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
profile="${HERMES_RUNTIME_PROFILE_FILE:?set HERMES_RUNTIME_PROFILE_FILE to a private profile outside this clone}"
parameter_name="${HERMES_RUNTIME_PROFILE_PARAMETER:?set HERMES_RUNTIME_PROFILE_PARAMETER to an absolute SSM parameter name}"
region="${AWS_REGION:?set AWS_REGION}"

command -v aws >/dev/null 2>&1 || { echo 'aws CLI is required' >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo 'jq is required' >&2; exit 1; }
[[ "$parameter_name" =~ ^/[A-Za-z0-9_.\/-]+$ ]] || {
  echo 'HERMES_RUNTIME_PROFILE_PARAMETER must be an absolute SSM parameter name' >&2
  exit 1
}
test -f "$profile" || { echo "runtime profile not found: $profile" >&2; exit 1; }

repo_root="$(cd "$script_dir/../.." && pwd)"
profile_path="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$profile")"
case "$profile_path" in
  "$repo_root"/*)
    echo 'refusing to publish a consumer profile stored inside the public clone' >&2
    exit 1
    ;;
esac

python3 "$script_dir/validate_runtime_profile.py" "$profile"
digest="$(shasum -a 256 "$profile" | awk '{print $1}')"
bytes="$(wc -c <"$profile" | tr -d ' ')"

if [[ "${1:-}" == "--check" ]]; then
  printf 'runtime-profile-validation-ok bytes=%s sha256=%s\n' "$bytes" "$digest"
  exit 0
fi
if [[ $# -ne 0 ]]; then
  echo 'usage: publish-runtime-profile.sh [--check]' >&2
  exit 2
fi

request_file="$(mktemp)"
remote_file="$(mktemp)"
trap 'rm -f "$request_file" "$remote_file"' EXIT

jq -n \
  --arg name "$parameter_name" \
  --rawfile value "$profile" \
  '{Name:$name,Description:"Validated non-secret Hermes runtime profile",Type:"String",Value:$value,Overwrite:true,Tier:"Standard",DataType:"text"}' \
  >"$request_file"

version="$(aws ssm put-parameter \
  --region "$region" \
  --cli-input-json "file://$request_file" \
  --query Version \
  --output text)"
aws ssm get-parameter \
  --region "$region" \
  --name "$parameter_name" \
  --output json | jq -rj '.Parameter.Value' >"$remote_file"

remote_digest="$(shasum -a 256 "$remote_file" | awk '{print $1}')"
if [[ "$remote_digest" != "$digest" ]]; then
  echo 'published Runtime Profile digest mismatch' >&2
  exit 1
fi

printf 'RuntimeProfileParameterName=%s\n' "$parameter_name"
printf 'RuntimeProfileParameterVersion=%s\n' "$version"
printf 'RuntimeProfileSHA256=%s\n' "$digest"
