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

stack_status_error="$(mktemp)"
cleanup() {
  rm -f -- "$stack_status_error"
}
trap cleanup EXIT

if stack_status="$(aws cloudformation describe-stacks \
  --region "$region" \
  --stack-name "$stack_name" \
  --query 'Stacks[0].StackStatus' \
  --output text 2>"$stack_status_error")"; then
  :
elif rg -q 'does not exist' "$stack_status_error"; then
  stack_status=DOES_NOT_EXIST
else
  cat "$stack_status_error" >&2
  echo 'unable to determine the existing Stack status; no Change Set was created' >&2
  exit 1
fi

case "$stack_status" in
  DOES_NOT_EXIST)
    change_set_type=CREATE
    waiter=stack-create-complete
    description='Initial Hermes deployment prepared from public, consumer-neutral inputs'
    failure_resources_preserved=on-stack-failure-do-nothing
    ;;
  CREATE_FAILED|UPDATE_FAILED)
    if [ "$change_set_name" = hermes-initial-deployment ]; then
      echo 'set HERMES_CHANGE_SET_NAME to a new recovery-specific name; no Change Set was created' >&2
      exit 1
    fi
    change_set_type=UPDATE
    waiter=stack-update-complete
    description='Hermes first-deployment recovery prepared after operator diagnosis'
    failure_resources_preserved=execute-disable-rollback-required
    ;;
  REVIEW_IN_PROGRESS)
    echo "Stack $stack_name is REVIEW_IN_PROGRESS; review or delete its existing unexecuted Change Set first; no Change Set was created" >&2
    exit 1
    ;;
  CREATE_IN_PROGRESS|ROLLBACK_IN_PROGRESS|DELETE_IN_PROGRESS|UPDATE_IN_PROGRESS|UPDATE_COMPLETE_CLEANUP_IN_PROGRESS|UPDATE_ROLLBACK_IN_PROGRESS|UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS)
    echo "Stack $stack_name is $stack_status; wait for the current operation before retrying; no Change Set was created" >&2
    exit 1
    ;;
  ROLLBACK_COMPLETE|ROLLBACK_FAILED|DELETE_FAILED|UPDATE_ROLLBACK_FAILED)
    echo "Stack $stack_name is $stack_status and requires the explicit recovery runbook; no Change Set was created" >&2
    exit 1
    ;;
  CREATE_COMPLETE|UPDATE_COMPLETE|UPDATE_ROLLBACK_COMPLETE)
    echo "Stack $stack_name is healthy ($stack_status); this first-deployment helper refuses a normal Stack update, so no Change Set was created" >&2
    exit 1
    ;;
  *)
    echo "Stack $stack_name has unsupported status $stack_status; no Change Set was created" >&2
    exit 1
    ;;
esac

change_set_args=(
  cloudformation create-change-set
  --region "$region"
  --stack-name "$stack_name"
  --change-set-name "$change_set_name"
  --change-set-type "$change_set_type"
  --template-url "$template_url"
  --parameters "file://$parameter_path"
  --capabilities CAPABILITY_IAM
  --description "$description"
  --query Id
  --output text
)

if [ "$change_set_type" = CREATE ]; then
  change_set_id="$(aws "${change_set_args[@]}" --on-stack-failure DO_NOTHING)"
else
  change_set_id="$(aws "${change_set_args[@]}")"
fi

printf 'StackStatusBefore=%s\n' "$stack_status"
printf 'ChangeSetType=%s\n' "$change_set_type"
printf 'FailureResourcesPreserved=%s\n' "$failure_resources_preserved"
printf 'Waiter=%s\n' "$waiter"
printf 'ChangeSetId=%s\n' "$change_set_id"
printf 'Review with:\n'
printf 'aws cloudformation describe-change-set --region %q --change-set-name %q\n' "$region" "$change_set_id"
printf 'This helper does not execute the Change Set.\n'
