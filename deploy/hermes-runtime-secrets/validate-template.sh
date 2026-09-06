#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ruby -e 'require "yaml"; YAML.parse_file(ARGV.fetch(0))' "$script_dir/cloudformation.yaml"
ruby -rjson -e '
  values = {
    "${AWS_ACCOUNT_ID}" => "123456789012",
    "${AWS_REGION}" => "us-east-1",
    "${RUNTIME_SECRET_STACK_NAME}" => "example-runtime-secrets",
    "${TELEGRAM_SECRET_NAME}" => "example-hermes-telegram"
  }
  ARGV.each do |path|
    body = File.read(path)
    values.each { |from, to| body = body.gsub(from, to) }
    JSON.parse(body)
  end
' "$script_dir"/policies/*.json.tmpl
rg -F -q 'SecretString: "{}"' "$script_dir/cloudformation.yaml"
rg -F -q 'DeletionPolicy: RetainExceptOnCreate' "$script_dir/cloudformation.yaml"
echo 'runtime-secret-template-validation-ok'
