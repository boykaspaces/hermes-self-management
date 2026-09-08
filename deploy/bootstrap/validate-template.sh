#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ruby -e 'require "yaml"; ARGV.each { |path| YAML.parse_file(path) }' \
  "$script_dir/artifacts-cloudformation.yaml" \
  "$script_dir/network-cloudformation.yaml"

rg -F -q 'VersioningConfiguration:' "$script_dir/artifacts-cloudformation.yaml"
rg -F -q 'Status: Enabled' "$script_dir/artifacts-cloudformation.yaml"
rg -F -q 'BlockPublicPolicy: true' "$script_dir/artifacts-cloudformation.yaml"
rg -F -q 'SSEAlgorithm: AES256' "$script_dir/artifacts-cloudformation.yaml"
rg -F -q 'aws:SecureTransport: false' "$script_dir/artifacts-cloudformation.yaml"
rg -F -q 'DeletionPolicy: Retain' "$script_dir/artifacts-cloudformation.yaml"

rg -F -q 'MapPublicIpOnLaunch: true' "$script_dir/network-cloudformation.yaml"
rg -F -q 'DestinationCidrBlock: 0.0.0.0/0' "$script_dir/network-cloudformation.yaml"
rg -F -q 'GatewayId: !Ref InternetGateway' "$script_dir/network-cloudformation.yaml"
if rg -q 'AWS::EC2::SecurityGroupIngress|CidrIp:' "$script_dir/network-cloudformation.yaml"; then
  echo 'bootstrap network template must not create ingress rules' >&2
  exit 1
fi

if rg -n 'aws (cloudformation|ec2|s3|ssm|secretsmanager) (create|delete|deploy|execute|put|start|stop|update)' \
  "$script_dir/discover-environment.sh"; then
  echo 'environment discovery must remain read-only' >&2
  exit 1
fi

echo 'bootstrap-template-validation-ok'
