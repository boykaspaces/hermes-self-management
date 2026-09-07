#!/bin/bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
region="${AWS_REGION:?set AWS_REGION}"
bucket="${HERMES_RUNTIME_ARTIFACT_BUCKET:?set HERMES_RUNTIME_ARTIFACT_BUCKET}"
work_dir="$(mktemp -d)"
bundle="$work_dir/runtime-bundle.tar.gz"
trap 'rm -rf "$work_dir"' EXIT

python3 "$script_dir/build_runtime_bundle.py" --check
python3 "$script_dir/build_runtime_bundle.py" --output "$bundle"
digest="$(shasum -a 256 "$bundle" | awk '{print $1}')"
key="hermes-self-management/runtime/$digest.tar.gz"

version_id="$(aws s3api put-object \
  --region "$region" \
  --bucket "$bucket" \
  --key "$key" \
  --body "$bundle" \
  --metadata "sha256=$digest" \
  --checksum-algorithm SHA256 \
  --query VersionId \
  --output text)"
case "$version_id" in
  None|null) version_id="" ;;
esac

remote_size="$(aws s3api head-object \
  --region "$region" \
  --bucket "$bucket" \
  --key "$key" \
  --query ContentLength \
  --output text)"
local_size="$(wc -c <"$bundle" | tr -d ' ')"
if [ "$remote_size" != "$local_size" ]; then
  echo "Uploaded runtime bundle size mismatch: local=$local_size remote=$remote_size" >&2
  exit 1
fi

printf 'RuntimeBundleArtifactS3Bucket=%s\n' "$bucket"
printf 'RuntimeBundleArtifactS3Key=%s\n' "$key"
printf 'RuntimeBundleArtifactS3ObjectVersion=%s\n' "$version_id"
printf 'RuntimeBundleArtifactSHA256=%s\n' "$digest"
