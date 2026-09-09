#!/usr/bin/env bash
set -euo pipefail

PREFLIGHT_VERSION=1
check_aws=false

usage() {
  cat <<'EOF'
Usage: ./deploy/preflight.sh [--aws]

Checks the supported local operator environment and required tool versions.
With --aws, also performs a read-only STS identity check in AWS_REGION.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --aws)
      check_aws=true
      ;;
    --version)
      printf 'hermes-deployment-preflight %s\n' "$PREFLIGHT_VERSION"
      exit 0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
  shift
done

failures=0

fail() {
  printf 'preflight-error: %s\n' "$1" >&2
  failures=$((failures + 1))
}

first_line() {
  printf '%s\n' "${1%%$'\n'*}"
}

version_at_least() {
  local actual="$1"
  local required_major="$2"
  local required_minor="$3"
  case "$actual" in
    *.*) ;;
    *) return 1 ;;
  esac
  local major="${actual%%.*}"
  local remainder="${actual#*.}"
  local minor="${remainder%%.*}"

  case "$major:$minor" in
    *[!0-9:]*|:|*:|"")
      return 1
      ;;
  esac
  [ "$major" -gt "$required_major" ] \
    || { [ "$major" -eq "$required_major" ] && [ "$minor" -ge "$required_minor" ]; }
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "$1 is required"
    return 1
  fi
  return 0
}

system_name="$(uname -s 2>/dev/null || true)"
case "$system_name" in
  Darwin|Linux)
    printf 'platform=%s\n' "$system_name"
    ;;
  *)
    fail "supported operator platforms are macOS and Linux; use WSL2 on Windows"
    ;;
esac

bash_version="${BASH_VERSION%%(*}"
printf 'bash=%s\n' "$bash_version"
version_at_least "$bash_version" 3 2 \
  || fail "Bash 3.2 or newer is required"

if require_command aws; then
  aws_raw="$(aws --version 2>&1 || true)"
  aws_line="$(first_line "$aws_raw")"
  aws_version="${aws_line#aws-cli/}"
  aws_version="${aws_version%% *}"
  printf 'aws-cli=%s\n' "$aws_version"
  version_at_least "$aws_version" 2 0 \
    || fail "AWS CLI v2 is required"
fi

if require_command session-manager-plugin; then
  plugin_raw="$(session-manager-plugin --version 2>&1 || true)"
  plugin_version="$(first_line "$plugin_raw")"
  if [ -z "$plugin_version" ]; then
    fail "Session Manager plugin version could not be read"
  else
    printf 'session-manager-plugin=%s\n' "$plugin_version"
  fi
fi

if require_command jq; then
  jq_raw="$(jq --version 2>&1 || true)"
  jq_version="$(first_line "$jq_raw")"
  jq_version="${jq_version#jq-}"
  printf 'jq=%s\n' "$jq_version"
  version_at_least "$jq_version" 1 6 \
    || fail "jq 1.6 or newer is required"
fi

if require_command python3; then
  python_raw="$(python3 --version 2>&1 || true)"
  python_version="$(first_line "$python_raw")"
  python_version="${python_version#Python }"
  printf 'python=%s\n' "$python_version"
  version_at_least "$python_version" 3 9 \
    || fail "Python 3.9 or newer is required"
fi

if require_command ruby; then
  ruby_raw="$(ruby --version 2>&1 || true)"
  ruby_version="$(first_line "$ruby_raw")"
  ruby_version="${ruby_version#ruby }"
  ruby_version="${ruby_version%%[ p]*}"
  printf 'ruby=%s\n' "$ruby_version"
  version_at_least "$ruby_version" 2 6 \
    || fail "Ruby 2.6 or newer is required"
fi

if require_command git; then
  git_raw="$(git --version 2>&1 || true)"
  git_version="$(first_line "$git_raw")"
  git_version="${git_version#git version }"
  git_version="${git_version%% *}"
  printf 'git=%s\n' "$git_version"
  version_at_least "$git_version" 2 20 \
    || fail "Git 2.20 or newer is required"
fi

if require_command rg; then
  rg_raw="$(rg --version 2>&1 || true)"
  rg_version="$(first_line "$rg_raw")"
  rg_version="${rg_version#ripgrep }"
  printf 'ripgrep=%s\n' "$rg_version"
  version_at_least "$rg_version" 12 0 \
    || fail "ripgrep 12 or newer is required"
fi

if require_command shasum; then
  shasum_raw="$(shasum --version 2>&1 || true)"
  shasum_version="$(first_line "$shasum_raw")"
  if [ -z "$shasum_version" ]; then
    fail "shasum version could not be read"
  else
    printf 'shasum=%s\n' "$shasum_version"
  fi
fi

if [ "$check_aws" = true ]; then
  if [ -z "${AWS_REGION:-}" ]; then
    fail "AWS_REGION is required with --aws"
  elif command -v aws >/dev/null 2>&1; then
    if aws sts get-caller-identity \
      --region "$AWS_REGION" \
      --query Account \
      --output text >/dev/null; then
      printf 'aws-identity=ok region=%s\n' "$AWS_REGION"
    else
      fail "AWS identity check failed in AWS_REGION=$AWS_REGION"
    fi
  fi
fi

if [ "$failures" -ne 0 ]; then
  printf 'preflight-failed failures=%s\n' "$failures" >&2
  exit 1
fi

printf 'preflight-ok version=%s\n' "$PREFLIGHT_VERSION"
