#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ruby -e 'require "yaml"; YAML.parse_file(ARGV.fetch(0))' "$script_dir/cloudformation.yaml"
ruby -rjson -e '
  values = {
    "${AWS_ACCOUNT_ID}" => "123456789012",
    "${BUDGET_REGION}" => "us-east-1",
    "${BUDGET_STACK_NAME}" => "example-budget",
    "${MODEL_BUDGET_NAME}" => "hermes-model-monthly",
    "${ACCOUNT_BUDGET_NAME}" => "aws-account-monthly",
    "${HERMES_ROLE_NAME}" => "example-hermes-role"
  }
  ARGV.each do |path|
    body = File.read(path)
    values.each { |from, to| body = body.gsub(from, to) }
    JSON.parse(body)
  end
' "$script_dir"/policies/*.json.tmpl
rg -q 'ApprovalModel: AUTOMATIC' "$script_dir/cloudformation.yaml"
rg -q 'Effect: Deny' "$script_dir/cloudformation.yaml"
echo 'budget-template-validation-ok'
