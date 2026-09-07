#!/bin/bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
template="$script_dir/cloudformation.yaml"
runtime_template="$script_dir/../hermes-runtime-secrets/cloudformation.yaml"
user_data_file="$(mktemp)"
runtime_script_file="$(mktemp)"
rendered_user_data_file="$(mktemp)"
rendered_runtime_script_file="$(mktemp)"
trap 'rm -f "$user_data_file" "$runtime_script_file" "$rendered_user_data_file" "$rendered_runtime_script_file"' EXIT

python3 "$script_dir/sync_token_observer_archive.py" --check
python3 "$script_dir/sync_hermes_patch_archive.py" --check

ruby -e 'require "yaml"; ARGV.each { |path| YAML.parse_file(path) }' \
  "$template" "$runtime_template"

awk '
  active && /^      Tags:/ { exit }
  /      UserData:/ { active=1; next }
  active { sub(/^          /, ""); print }
' "$template" | sed '1,2d' >"$user_data_file"

user_data_bytes="$(wc -c <"$user_data_file" | tr -d ' ')"
template_bytes="$(wc -c <"$template" | tr -d ' ')"
if [ "$user_data_bytes" -gt 16384 ]; then
  echo "EC2 User Data is $user_data_bytes bytes; the raw limit is 16384" >&2
  exit 1
fi

awk '
  active && /^      [A-Za-z0-9_]+:/ { exit }
  /^        Fn::Sub: \|$/ { active=1; next }
  active { sub(/^          /, ""); print }
' "$template" >"$runtime_script_file"

perl -pe 's/\$\{![^}]+\}/LITERAL_ENV/g; s/\$\{[^}]+\}/CFN_VALUE/g' \
  "$user_data_file" >"$rendered_user_data_file"
perl -pe 's/\$\{![^}]+\}/LITERAL_ENV/g; s/\$\{[^}]+\}/CFN_VALUE/g' \
  "$runtime_script_file" >"$rendered_runtime_script_file"

bash -n "$rendered_user_data_file"
bash -n "$rendered_runtime_script_file"

jq empty \
  "$script_dir/stack-policy.json"

ruby -rjson -e '
  replacements = {
    "${AWS_ACCOUNT_ID}" => "123456789012",
    "${AWS_REGION}" => "us-east-1",
    "${ARTIFACT_BUCKET}" => "example-artifact-bucket",
    "${TEMPLATE_PREFIX}" => "hermes-self-management/cloudformation",
    "${HERMES_STACK_NAME}" => "example-hermes",
    "${HERMES_ROLE_PREFIX}" => "example-hermes-",
    "${HERMES_INSTANCE_ID}" => "i-0123456789abcdef0",
    "${PROJECT_TAG}" => "hermes-self-management"
  }
  ARGV.each do |path|
    body = File.read(path)
    replacements.each { |from, to| body = body.gsub(from, to) }
    JSON.parse(body)
  end
' "$script_dir"/policies/*.json.tmpl

if rg -n 'bedrock:InvokeModel|bedrock:InvokeModelWithResponseStream|HermesBedrockRuntime' "$template"; then
  echo "The Hermes template must not grant Bedrock model invocation permissions" >&2
  exit 1
fi

rg -q 'provider": "openai-codex"' "$template"
rg -q 'config.pop\("fallback_providers", None\)' "$template"
rg -q 'task\["provider"\] = "main"' "$template"
rg -q 'Default: 29112bef099274229cadff79cdff7bf7b99c4b77' "$template"
rg -q 'ManagedHermesPatchArchive' "$template"
rg -q 'apply-hermes-patches.sh" apply' "$template"
rg -q 'terminal\["docker_network"\] = True' "$template"
rg -q '"enforce_on_docker": True' "$template"
rg -q 'hermes-credential-provisioner.service' "$template"
rg -q '/run/hermes/credentials:ro' "$template"
rg -q 'config set platforms.telegram.reactions true' "$template"
rg -q 'config set display.platforms.telegram.streaming true' "$template"
rg -q 'config set display.platforms.telegram.tool_progress all' "$template"
rg -q 'config set display.platforms.telegram.cleanup_progress true' "$template"
rg -q 'config set agent.gateway_notify_interval 60' "$template"
rg -q 'config set skills.write_approval false' "$template"
rg -q 'config set memory.write_approval false' "$template"

if rg -n '/var/run/docker.sock|/run/podman/podman.sock|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY' "$template"; then
  echo "The coding container must not receive a container-engine socket or static AWS credentials" >&2
  exit 1
fi

if rg -n 'config set model\.provider bedrock|amazon\.nova|pre-nova-cache-fix' "$template"; then
  echo "Retired Bedrock/Nova bootstrap or P-001 patch logic must not return" >&2
  exit 1
fi

if [ "${1:-}" = "--aws" ]; then
  region="${2:?usage: validate-template.sh --aws AWS_REGION}"
  if [ "$template_bytes" -le 51200 ]; then
    aws cloudformation validate-template \
      --region "$region" \
      --template-body "file://$template" >/dev/null
  else
    if [ -z "${HERMES_TEMPLATE_URL:-}" ]; then
      echo "Template is $template_bytes bytes; set HERMES_TEMPLATE_URL from publish-template.sh for AWS validation" >&2
      exit 1
    fi
    aws cloudformation validate-template \
      --region "$region" \
      --template-url "$HERMES_TEMPLATE_URL" >/dev/null
  fi
  aws cloudformation validate-template \
    --region "$region" \
    --template-body "file://$runtime_template" >/dev/null
fi

echo "template-validation-ok template_bytes=$template_bytes user_data_bytes=$user_data_bytes"
