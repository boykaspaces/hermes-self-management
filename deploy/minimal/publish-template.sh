#!/bin/bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
template="$script_dir/cloudformation.yaml"
region="${AWS_REGION:?set AWS_REGION}"
bucket="${HERMES_TEMPLATE_BUCKET:?set HERMES_TEMPLATE_BUCKET}"

"$script_dir/validate-template.sh"

digest="$(shasum -a 256 "$template" | awk '{print $1}')"
key="hermes-self-management/cloudformation/$digest.yaml"
template_url="https://$bucket.s3.$region.amazonaws.com/$key"

aws s3api put-object \
  --region "$region" \
  --bucket "$bucket" \
  --key "$key" \
  --body "$template" \
  --metadata "sha256=$digest" \
  --checksum-algorithm SHA256 >/dev/null

remote_size="$(aws s3api head-object \
  --region "$region" \
  --bucket "$bucket" \
  --key "$key" \
  --query ContentLength \
  --output text)"
local_size="$(wc -c <"$template" | tr -d ' ')"
if [ "$remote_size" != "$local_size" ]; then
  echo "Uploaded template size mismatch: local=$local_size remote=$remote_size" >&2
  exit 1
fi

HERMES_TEMPLATE_URL="$template_url" "$script_dir/validate-template.sh" --aws "$region"
printf '%s\n' "$template_url"
