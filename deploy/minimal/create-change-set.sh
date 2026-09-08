#!/usr/bin/env bash
set -euo pipefail

region="${AWS_REGION:?set AWS_REGION}"
stack_name="${HERMES_STACK_NAME:?set HERMES_STACK_NAME}"
template_url="${HERMES_TEMPLATE_URL:?set HERMES_TEMPLATE_URL to the published content-addressed template}"
parameter_file="${HERMES_PARAMETER_FILE:?set HERMES_PARAMETER_FILE to a private JSON file outside this clone}"
change_set_name="${HERMES_CHANGE_SET_NAME:-hermes-initial-deployment}"

command -v aws >/dev/null 2>&1 || { echo 'aws CLI is required' >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo 'jq is required' >&2; exit 1; }
[[ "$stack_name" =~ ^[A-Za-z][A-Za-z0-9-]{0,127}$ ]] || {
  echo 'HERMES_STACK_NAME is not a valid CloudFormation stack name' >&2
  exit 1
}
[[ "$change_set_name" =~ ^[A-Za-z][A-Za-z0-9-]{0,127}$ ]] || {
  echo 'HERMES_CHANGE_SET_NAME is not valid' >&2
  exit 1
}
[[ "$template_url" =~ ^https://[^[:space:]]+$ ]] || {
  echo 'HERMES_TEMPLATE_URL must be an HTTPS URL' >&2
  exit 1
}
test -f "$parameter_file" || { echo "parameter file not found: $parameter_file" >&2; exit 1; }

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
parameter_path="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$parameter_file")"
case "$parameter_path" in
  "$repo_root"/*)
    echo 'refusing a deployment parameter file stored inside the public clone' >&2
    exit 1
    ;;
esac

jq -e '
  type == "array" and length > 0 and
  all(.[];
    type == "object" and
    (.ParameterKey | type == "string" and length > 0) and
    (.ParameterValue | type == "string") and
    ((keys - ["ParameterKey", "ParameterValue"]) | length == 0)
  )
' "$parameter_file" >/dev/null || {
  echo 'parameter file must be a non-empty CloudFormation ParameterKey/ParameterValue array' >&2
  exit 1
}

if rg -n 'REPLACE_WITH_' "$parameter_file"; then
  echo 'parameter file still contains example placeholders' >&2
  exit 1
fi

change_set_id="$(aws cloudformation create-change-set \
  --region "$region" \
  --stack-name "$stack_name" \
  --change-set-name "$change_set_name" \
  --change-set-type CREATE \
  --template-url "$template_url" \
  --parameters "file://$parameter_path" \
  --capabilities CAPABILITY_IAM \
  --description 'Initial Hermes deployment prepared from public, consumer-neutral inputs' \
  --query Id \
  --output text)"

printf 'ChangeSetId=%s\n' "$change_set_id"
printf 'Review with:\n'
printf 'aws cloudformation describe-change-set --region %q --change-set-name %q\n' "$region" "$change_set_id"
printf 'This helper does not execute the Change Set.\n'
