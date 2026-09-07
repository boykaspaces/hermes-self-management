#!/bin/bash
set -euo pipefail

: "${AWS_REGION:?AWS_REGION is required}"
: "${AWS_CLI:?AWS_CLI is required}"
: "${HERMES_HOME:?HERMES_HOME is required}"
: "${HERMES_BIN:?HERMES_BIN is required}"
: "${HERMES_PYTHON:?HERMES_PYTHON is required}"
: "${MCP_SECRET_ARN:=}"
: "${MCP_URL:=}"
: "${TELEGRAM_SECRET_ARN:=}"
: "${TELEGRAM_STATE_PARAMETER:?TELEGRAM_STATE_PARAMETER is required}"
: "${OPENAI_CODEX_MODEL:?OPENAI_CODEX_MODEL is required}"
: "${GIT_CODING_ENABLED:?GIT_CODING_ENABLED is required}"
: "${CREDENTIAL_LEASE_URL:=}"
: "${CREDENTIAL_PROFILE_ID:=}"
: "${CREDENTIAL_ARTIFACT_BUCKET:=}"
: "${CREDENTIAL_ARTIFACT_KEY:=}"
: "${CREDENTIAL_ARTIFACT_VERSION:=}"
: "${CREDENTIAL_ARTIFACT_SHA256:=}"
: "${CODING_BASE_IMAGE:=}"
: "${HERMES_RUNTIME_BUNDLE_DIR:?HERMES_RUNTIME_BUNDLE_DIR is required}"

MANAGED_PATCH_ARCHIVE="$HERMES_RUNTIME_BUNDLE_DIR/managed-patches.tar.gz"
TOKEN_OBSERVER_ARCHIVE="$HERMES_RUNTIME_BUNDLE_DIR/token-observer.tar.gz"
test -f "$MANAGED_PATCH_ARCHIVE"
test -f "$TOKEN_OBSERVER_ARCHIVE"

cd "$HERMES_HOME/hermes-agent"
"$HERMES_PYTHON" - "$MANAGED_PATCH_ARCHIVE" "$HERMES_HOME/managed-patches" <<'PY'
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

archive = Path(sys.argv[1])
target = Path(sys.argv[2])
target.parent.mkdir(parents=True, exist_ok=True)
staging = Path(tempfile.mkdtemp(prefix=".managed-patches-", dir=target.parent))
backup = target.with_name(".managed-patches.previous")
required = {
    "apply-hermes-patches.sh",
    "patches/hermes-v0.21.0-29112bef/commit.txt",
    "patches/hermes-v0.21.0-29112bef/P-002-browser-private-url.patch",
    "patches/hermes-v0.21.0-29112bef/P-003-podman-reuse.patch",
    "patches/hermes-v0.21.0-29112bef/P-005-egress-allowlist-only.patch",
    "patches/hermes-v0.21.0-29112bef/PATCHED_SHA256SUMS",
}
try:
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        actual = set()
        for member in members:
            name = PurePosixPath(member.name)
            if (
                name.is_absolute()
                or ".." in name.parts
                or member.issym()
                or member.islnk()
                or member.isdev()
                or not member.isfile()
                or not name.parts
                or name.parts[0] != "managed-patches"
            ):
                raise SystemExit(f"unsafe managed patch archive member: {member.name}")
            actual.add(str(PurePosixPath(*name.parts[1:])))
        if actual != required:
            raise SystemExit("managed patch archive is incomplete or contains unexpected files")
        source.extractall(staging, members=members, filter="data")
    candidate = staging / "managed-patches"
    if backup.exists():
        shutil.rmtree(backup)
    if target.exists():
        os.replace(target, backup)
    os.replace(candidate, target)
    if backup.exists():
        shutil.rmtree(backup)
finally:
    shutil.rmtree(staging, ignore_errors=True)
PY
env \
  HERMES_REPO="$HERMES_HOME/hermes-agent" \
  HERMES_PATCH_SET="$HERMES_HOME/managed-patches/patches/hermes-v0.21.0-29112bef" \
  HERMES_PYTHON="$HERMES_PYTHON" \
  "$HERMES_HOME/managed-patches/apply-hermes-patches.sh" apply

if [ "$GIT_CODING_ENABLED" = true ]; then
  CREDENTIAL_RUNTIME="$HERMES_HOME/runtime/credential-agent"
  install -d -m 0700 "$HERMES_HOME/runtime" "$CREDENTIAL_RUNTIME"
  CREDENTIAL_ARCHIVE="$(mktemp)"
  if [ -n "$CREDENTIAL_ARTIFACT_VERSION" ]; then
    "$AWS_CLI" s3api get-object \
      --bucket "$CREDENTIAL_ARTIFACT_BUCKET" \
      --key "$CREDENTIAL_ARTIFACT_KEY" \
      --version-id "$CREDENTIAL_ARTIFACT_VERSION" \
      --region "$AWS_REGION" \
      "$CREDENTIAL_ARCHIVE" >/dev/null
  else
    "$AWS_CLI" s3api get-object \
      --bucket "$CREDENTIAL_ARTIFACT_BUCKET" \
      --key "$CREDENTIAL_ARTIFACT_KEY" \
      --region "$AWS_REGION" \
      "$CREDENTIAL_ARCHIVE" >/dev/null
  fi
  printf '%s  %s\n' "$CREDENTIAL_ARTIFACT_SHA256" "$CREDENTIAL_ARCHIVE" | sha256sum -c -
  rm -rf "$CREDENTIAL_RUNTIME/staging"
  install -d -m 0700 "$CREDENTIAL_RUNTIME/staging"
  unzip -q "$CREDENTIAL_ARCHIVE" -d "$CREDENTIAL_RUNTIME/staging"
  rm -f "$CREDENTIAL_ARCHIVE"
  test -f "$CREDENTIAL_RUNTIME/staging/hermes-credential-provisioner"
  test -f "$CREDENTIAL_RUNTIME/staging/git-credential-hermes"
  HERMES_BIN_DIR="$(dirname "$HERMES_BIN")"
  install -d -m 0755 "$HERMES_BIN_DIR"
  install -m 0755 "$CREDENTIAL_RUNTIME/staging/hermes-credential-provisioner" \
    "$HERMES_BIN_DIR/hermes-credential-provisioner"

  CREDENTIAL_IMAGE=localhost/hermes-coding:managed
  CURRENT_IMAGE_DIGEST="$(HERMES_DOCKER_BINARY=/usr/bin/podman podman image inspect \
    --format '{{ index .Labels "org.hermes.credential-agent.sha256" }}' \
    "$CREDENTIAL_IMAGE" 2>/dev/null || true)"
  if [ "$CURRENT_IMAGE_DIGEST" != "$CREDENTIAL_ARTIFACT_SHA256" ]; then
    install -m 0755 "$CREDENTIAL_RUNTIME/staging/git-credential-hermes" \
      "$CREDENTIAL_RUNTIME/git-credential-hermes"
    cat >"$CREDENTIAL_RUNTIME/Containerfile" <<CONTAINERFILE
FROM $CODING_BASE_IMAGE
COPY git-credential-hermes /usr/local/bin/git-credential-hermes
RUN chmod 0755 /usr/local/bin/git-credential-hermes \\
    && git config --system credential.helper hermes \\
    && git config --system credential.useHttpPath true \\
    && git config --system credential.interactive false
ENV HERMES_CREDENTIAL_DIR=/run/hermes/credentials
ENV GIT_TERMINAL_PROMPT=0
LABEL org.hermes.credential-agent.sha256=$CREDENTIAL_ARTIFACT_SHA256
CONTAINERFILE
    HERMES_DOCKER_BINARY=/usr/bin/podman podman build \
      --pull=always \
      --tag "$CREDENTIAL_IMAGE" \
      "$CREDENTIAL_RUNTIME"
  fi
  rm -rf "$CREDENTIAL_RUNTIME/staging"

  HERMES_UID="$(id -u)"
  USER_UNIT_DIR="$HOME/.config/systemd/user"
  install -d -m 0700 "$USER_UNIT_DIR/default.target.wants"
  cat >"$USER_UNIT_DIR/hermes-credential-provisioner.service" <<EOF
[Unit]
Description=Hermes short-lived credential provisioner
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=HOME=$HOME
ExecStart=$HERMES_BIN_DIR/hermes-credential-provisioner --endpoint $CREDENTIAL_LEASE_URL --region $AWS_REGION --profile $CREDENTIAL_PROFILE_ID --output %t/hermes-credentials/$CREDENTIAL_PROFILE_ID.json --refresh-before 10m
Restart=always
RestartSec=10
RuntimeDirectory=hermes-credentials
RuntimeDirectoryMode=0700
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=%t/hermes-credentials
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
LockPersonality=true

[Install]
WantedBy=default.target
EOF
  chmod 0600 "$USER_UNIT_DIR/hermes-credential-provisioner.service"
  ln -sfn ../hermes-credential-provisioner.service \
    "$USER_UNIT_DIR/default.target.wants/hermes-credential-provisioner.service"

  env \
    CREDENTIAL_MOUNT="/run/user/$HERMES_UID/hermes-credentials:/run/hermes/credentials:ro" \
    CREDENTIAL_IMAGE="$CREDENTIAL_IMAGE" \
    "$HERMES_PYTHON" -c '
import os
import yaml
from utils import atomic_yaml_write

path = "/home/hermes/.hermes/config.yaml"
with open(path, encoding="utf-8") as source:
    config = yaml.safe_load(source) or {}

terminal = config.setdefault("terminal", {})
terminal["backend"] = "docker"
terminal["docker_image"] = os.environ["CREDENTIAL_IMAGE"]
terminal["docker_network"] = True
terminal["docker_forward_env"] = []
terminal["docker_extra_args"] = []
volumes = [
    item for item in terminal.get("docker_volumes", [])
    if not str(item).split(":", 1)[-1].startswith("/run/hermes/credentials")
]
volumes.append(os.environ["CREDENTIAL_MOUNT"])
terminal["docker_volumes"] = volumes

proxy = config.setdefault("proxy", {})
proxy.update({
    "enabled": True,
    "auto_install": True,
    "credential_source": "env",
    "enforce_on_docker": True,
    "allow_env_fallback": False,
    "upstream_deny_cidrs": None,
    "extra_allowed_hosts": [
        "github.com",
        "api.github.com",
        "objects.githubusercontent.com",
        "raw.githubusercontent.com",
        "codeload.github.com",
        "github-releases.githubusercontent.com",
        "proxy.golang.org",
        "sum.golang.org",
        "storage.googleapis.com",
        "registry.npmjs.org",
    ],
})
config.setdefault("checkpoints", {})["enabled"] = True
config.setdefault("skills", {}).update({
    "guard_agent_created": True,
    "write_approval": False,
})
config.setdefault("memory", {})["write_approval"] = False
approvals = config.setdefault("approvals", {})
approvals["mode"] = "smart"
approvals["denial_breaker_threshold"] = 3
deny = list(approvals.get("deny", []))
for pattern in ("git push --force*", "git push *--force*"):
    if pattern not in deny:
        deny.append(pattern)
approvals["deny"] = deny
git_policy = (
    "APPROVE ordinary git commit and non-force git push commands when the "
    "current branch starts with hermes/. ESCALATE attempts to update main, "
    "other branch namespaces, tags, remotes, credentials, or live host "
    "configuration outside the coding worktree."
)
current_policy = str(approvals.get("smart_policy", "")).strip()
if git_policy not in current_policy:
    approvals["smart_policy"] = "\n\n".join(filter(None, (current_policy, git_policy)))
atomic_yaml_write(path, config)
  '
  "$HERMES_BIN" egress install
  "$HERMES_BIN" egress setup --allowlist-only --no-bitwarden --no-restart
  "$HERMES_BIN" egress restart
fi

if [ ! -f "$HERMES_HOME/.env" ]; then
  install -m 0600 /dev/null "$HERMES_HOME/.env"
fi

if [ -n "$MCP_SECRET_ARN" ]; then
  MCP_PERSONAL_TOOLS_API_KEY="$("$AWS_CLI" secretsmanager get-secret-value \
    --secret-id "$MCP_SECRET_ARN" \
    --region "$AWS_REGION" \
    --query SecretString \
    --output text)"
  test -n "$MCP_PERSONAL_TOOLS_API_KEY"
  case "$MCP_PERSONAL_TOOLS_API_KEY" in
    *[!A-Za-z0-9_-]*) echo "Personal Tools client token contains unsupported dotenv characters" >&2; exit 1 ;;
  esac
  sed -i '/^MCP_PERSONAL_TOOLS_API_KEY=/d' "$HERMES_HOME/.env"
  printf 'MCP_PERSONAL_TOOLS_API_KEY=%s\n' "$MCP_PERSONAL_TOOLS_API_KEY" >>"$HERMES_HOME/.env"
  unset MCP_PERSONAL_TOOLS_API_KEY
  env MCP_URL="$MCP_URL" "$HERMES_PYTHON" -c '
import os
import yaml
from utils import atomic_yaml_write

path = "/home/hermes/.hermes/config.yaml"
with open(path, encoding="utf-8") as source:
    config = yaml.safe_load(source) or {}
config.setdefault("mcp_servers", {})["personal_tools"] = {
    "url": os.environ["MCP_URL"],
    "connect_timeout": 15,
    "headers": {
        "X-Hermes-Gateway-Token": "Bearer ${MCP_PERSONAL_TOOLS_API_KEY}",
    },
}
atomic_yaml_write(path, config)
'
fi

TELEGRAM_ENABLED="$("$AWS_CLI" ssm get-parameter \
  --name "$TELEGRAM_STATE_PARAMETER" \
  --region "$AWS_REGION" \
  --query Parameter.Value \
  --output text)"
case "$TELEGRAM_ENABLED" in
  true|false) ;;
  *) echo "Invalid Telegram desired state" >&2; exit 1 ;;
esac
"$HERMES_BIN" config set platforms.telegram.enabled "$TELEGRAM_ENABLED"
"$HERMES_BIN" config set platforms.telegram.reactions true
"$HERMES_BIN" config set display.platforms.telegram.streaming true
"$HERMES_BIN" config set display.platforms.telegram.tool_progress all
"$HERMES_BIN" config set display.platforms.telegram.tool_progress_grouping accumulate
"$HERMES_BIN" config set display.platforms.telegram.long_running_notifications true
"$HERMES_BIN" config set display.platforms.telegram.cleanup_progress true
"$HERMES_BIN" config set agent.gateway_notify_interval 60
"$HERMES_BIN" config set skills.write_approval false
"$HERMES_BIN" config set memory.write_approval false
sed -i \
  -e '/^TELEGRAM_BOT_TOKEN=/d' \
  -e '/^TELEGRAM_ALLOWED_USERS=/d' \
  -e '/^TELEGRAM_HOME_CHANNEL=/d' \
  -e '/^TELEGRAM_HOME_CHANNEL_THREAD_ID=/d' \
  "$HERMES_HOME/.env"

if [ "$TELEGRAM_ENABLED" = true ]; then
  test -n "$TELEGRAM_SECRET_ARN"
  TELEGRAM_SECRET_JSON="$("$AWS_CLI" secretsmanager get-secret-value \
    --secret-id "$TELEGRAM_SECRET_ARN" \
    --region "$AWS_REGION" \
    --query SecretString \
    --output text)"
  TELEGRAM_BOT_TOKEN="$(printf '%s' "$TELEGRAM_SECRET_JSON" | jq -er '.TELEGRAM_BOT_TOKEN | select(type == "string" and length > 0)')"
  TELEGRAM_ALLOWED_USERS="$(printf '%s' "$TELEGRAM_SECRET_JSON" | jq -er '.TELEGRAM_ALLOWED_USERS | select(type == "string" and length > 0)')"
  TELEGRAM_HOME_CHANNEL="$(printf '%s' "$TELEGRAM_SECRET_JSON" | jq -er '.TELEGRAM_HOME_CHANNEL | select(type == "string" and length > 0)')"
  TELEGRAM_HOME_CHANNEL_THREAD_ID="$(printf '%s' "$TELEGRAM_SECRET_JSON" | jq -er '.TELEGRAM_HOME_CHANNEL_THREAD_ID // "" | select(type == "string")')"
  case "$TELEGRAM_BOT_TOKEN" in *[!A-Za-z0-9:_-]*) echo "Invalid Telegram token format" >&2; exit 1 ;; esac
  case "$TELEGRAM_ALLOWED_USERS" in *[!0-9,-]*) echo "Invalid Telegram allowed-users format" >&2; exit 1 ;; esac
  case "$TELEGRAM_HOME_CHANNEL" in *[!0-9-]*) echo "Invalid Telegram home-channel format" >&2; exit 1 ;; esac
  case "$TELEGRAM_HOME_CHANNEL_THREAD_ID" in *[!0-9]*) echo "Invalid Telegram thread-id format" >&2; exit 1 ;; esac
  {
    printf 'TELEGRAM_BOT_TOKEN=%s\n' "$TELEGRAM_BOT_TOKEN"
    printf 'TELEGRAM_ALLOWED_USERS=%s\n' "$TELEGRAM_ALLOWED_USERS"
    printf 'TELEGRAM_HOME_CHANNEL=%s\n' "$TELEGRAM_HOME_CHANNEL"
    if [ -n "$TELEGRAM_HOME_CHANNEL_THREAD_ID" ]; then
      printf 'TELEGRAM_HOME_CHANNEL_THREAD_ID=%s\n' "$TELEGRAM_HOME_CHANNEL_THREAD_ID"
    fi
  } >>"$HERMES_HOME/.env"
  unset TELEGRAM_SECRET_JSON TELEGRAM_BOT_TOKEN TELEGRAM_ALLOWED_USERS TELEGRAM_HOME_CHANNEL TELEGRAM_HOME_CHANNEL_THREAD_ID
fi

chmod 0600 "$HERMES_HOME/.env"

sed -i \
  -e '/^OPENAI_API_KEY=/d' \
  -e '/^OPENAI_BASE_URL=/d' \
  "$HERMES_HOME/.env"
env OPENAI_CODEX_MODEL="$OPENAI_CODEX_MODEL" "$HERMES_PYTHON" -c '
import os
import yaml
from utils import atomic_yaml_write

path = "/home/hermes/.hermes/config.yaml"
with open(path, encoding="utf-8") as source:
    config = yaml.safe_load(source) or {}

model = config.setdefault("model", {})
if not isinstance(model, dict):
    model = {}
    config["model"] = model
model.update({
    "provider": "openai-codex",
    "default": os.environ["OPENAI_CODEX_MODEL"],
    "base_url": "https://chatgpt.com/backend-api/codex",
})
model.pop("api_key", None)
model.pop("api_key_env", None)

auxiliary = config.setdefault("auxiliary", {})
if isinstance(auxiliary, dict):
    for task in auxiliary.values():
        if not isinstance(task, dict):
            continue
        task["provider"] = "main"
        for key in ("model", "base_url", "api_key", "api_key_env", "fallback_chain"):
            task.pop(key, None)

config.pop("fallback_providers", None)
config.pop("fallback_model", None)
config.pop("bedrock", None)
config.setdefault("prompt_caching", {})["cache_ttl"] = "off"
atomic_yaml_write(path, config)
'
if [ -f "$HERMES_HOME/auth.json" ]; then
  chmod 0600 "$HERMES_HOME/auth.json"
fi

"$HERMES_PYTHON" - "$TOKEN_OBSERVER_ARCHIVE" "$HERMES_HOME/plugins/observability/token_observer" <<'PY'
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

archive = Path(sys.argv[1])
target = Path(sys.argv[2])
target.parent.mkdir(parents=True, exist_ok=True)
staging = Path(tempfile.mkdtemp(prefix=".token-observer-", dir=target.parent))
backup = target.with_name(".token_observer.previous")
try:
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        for member in members:
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts or member.issym() or member.islnk() or member.isdev():
                raise SystemExit(f"unsafe token observer archive member: {member.name}")
        source.extractall(staging, members=members, filter="data")
    candidate = staging / "token_observer"
    required = {
        "plugin.yaml", "__init__.py", "observer.py", "runtime_instrumentation.py", "report.py", "viewer.py",
        "hermes-token-observer-viewer.service", "web",
    }
    if not candidate.is_dir() or not required.issubset({item.name for item in candidate.iterdir()}):
        raise SystemExit("token observer archive is incomplete")
    if backup.exists():
        shutil.rmtree(backup)
    if target.exists():
        os.replace(target, backup)
    os.replace(candidate, target)
    if backup.exists():
        shutil.rmtree(backup)
finally:
    shutil.rmtree(staging, ignore_errors=True)
PY
chmod 0755 \
  "$HERMES_HOME/plugins/observability/token_observer/report.py" \
  "$HERMES_HOME/plugins/observability/token_observer/viewer.py"
VIEWER_UNIT_DIR=/home/hermes/.config/systemd/user
install -d -m 0700 "$VIEWER_UNIT_DIR" "$VIEWER_UNIT_DIR/default.target.wants"
install -m 0600 \
  "$HERMES_HOME/plugins/observability/token_observer/hermes-token-observer-viewer.service" \
  "$VIEWER_UNIT_DIR/hermes-token-observer-viewer.service"
ln -sfn ../hermes-token-observer-viewer.service \
  "$VIEWER_UNIT_DIR/default.target.wants/hermes-token-observer-viewer.service"
if [ -n "${XDG_RUNTIME_DIR:-}" ] && [ -S "${XDG_RUNTIME_DIR}/bus" ]; then
  systemctl --user daemon-reload
  systemctl --user restart hermes-token-observer-viewer.service
fi
"$HERMES_BIN" plugins enable observability/token_observer --no-allow-tool-override
"$HERMES_BIN" config set browser.backend off
"$HERMES_BIN" config check
