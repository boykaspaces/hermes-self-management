#!/usr/bin/env python3
"""Apply a validated consumer runtime profile to Hermes config.yaml."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from validate_runtime_profile import validate_profile


BLOCKED_WEBSITE_DOMAINS = [
    "localhost",
    "127.*",
    "0.0.0.0",
    "10.*",
    "100.64.*",
    "169.254.*",
    "172.16.*",
    "172.17.*",
    "172.18.*",
    "172.19.*",
    "172.20.*",
    "172.21.*",
    "172.22.*",
    "172.23.*",
    "172.24.*",
    "172.25.*",
    "172.26.*",
    "172.27.*",
    "172.28.*",
    "172.29.*",
    "172.30.*",
    "172.31.*",
    "192.168.*",
    "instance-data.ec2.internal",
    "metadata.google.internal",
    "*.compute.internal",
    "*.ec2.internal",
    "*.local",
    "*.lan",
    "*.internal",
]


def apply_profile(
    profile: dict[str, object],
    config: dict[str, object],
    *,
    git_coding_enabled: bool,
    mcp_secret_authorized: bool,
) -> dict[str, object]:
    validate_profile(profile)

    config.setdefault("web", {})["search_backend"] = "ddgs"
    config.setdefault("browser", {}).update(
        {
            "cloud_provider": "local",
            "backend": "off",
            "inactivity_timeout": profile["browser"]["inactivity_timeout"],
            "command_timeout": profile["browser"]["command_timeout"],
            "record_sessions": False,
            "headed": False,
            "allow_private_urls": False,
            "auto_local_for_private_urls": False,
            "allow_unsafe_evaluate": False,
            "restrict_evaluate": True,
            "dialog_policy": "auto_dismiss",
        }
    )
    config.setdefault("security", {})["website_blocklist"] = {
        "enabled": True,
        "domains": BLOCKED_WEBSITE_DOMAINS,
    }

    terminal_profile = profile["terminal"]
    terminal = config.setdefault("terminal", {})
    terminal.update(
        {
            "backend": "docker",
            "docker_network": False,
            "container_memory": terminal_profile["container_memory"],
            "container_disk": terminal_profile["container_disk"],
            "docker_shm_size": terminal_profile["docker_shm_size"],
            "container_cpu": terminal_profile["container_cpu"],
            "container_persistent": terminal_profile["container_persistent"],
            "docker_mount_cwd_to_workspace": terminal_profile[
                "docker_mount_cwd_to_workspace"
            ],
            "home_mode": terminal_profile["home_mode"],
            "lifetime_seconds": terminal_profile["lifetime_seconds"],
            "timeout": terminal_profile["timeout"],
            "cwd": terminal_profile["cwd"],
            "docker_forward_env": [],
            "docker_extra_args": [],
        }
    )
    terminal["docker_volumes"] = [
        item
        for item in terminal.get("docker_volumes", [])
        if not str(item).split(":", 1)[-1].startswith("/run/hermes/credentials")
    ]
    if not git_coding_enabled:
        terminal.pop("docker_image", None)
        config.setdefault("proxy", {})["enabled"] = False

    agent_profile = profile["agent"]
    config.setdefault("agent", {}).update(
        {
            "max_turns": agent_profile["max_turns"],
            "reasoning_effort": agent_profile["reasoning_effort"],
            "verbose": agent_profile["verbose"],
            "gateway_notify_interval": profile["telegram"][
                "gateway_notify_interval"
            ],
        }
    )

    memory_profile = profile["memory"]
    config.setdefault("memory", {}).update(
        {
            "memory_enabled": memory_profile["enabled"],
            "user_profile_enabled": memory_profile["user_profile_enabled"],
            "flush_min_turns": memory_profile["flush_min_turns"],
            "memory_char_limit": memory_profile["memory_char_limit"],
            "nudge_interval": memory_profile["nudge_interval"],
            "user_char_limit": memory_profile["user_char_limit"],
            "write_approval": memory_profile["write_approval"],
        }
    )
    config.setdefault("skills", {}).update(profile["skills"])

    telegram_profile = profile["telegram"]
    telegram = config.setdefault("platforms", {}).setdefault("telegram", {})
    telegram.update(
        {
            "enabled": telegram_profile["enabled"],
            "reactions": telegram_profile["reactions"],
        }
    )
    config.setdefault("display", {}).setdefault("platforms", {})["telegram"] = {
        "streaming": telegram_profile["streaming"],
        "tool_progress": telegram_profile["tool_progress"],
        "tool_progress_grouping": telegram_profile["tool_progress_grouping"],
        "long_running_notifications": telegram_profile[
            "long_running_notifications"
        ],
        "cleanup_progress": telegram_profile["cleanup_progress"],
    }

    model = config.setdefault("model", {})
    model.update(
        {
            "provider": "openai-codex",
            "default": profile["model"]["default"],
            "base_url": "https://chatgpt.com/backend-api/codex",
        }
    )
    model.pop("api_key", None)
    model.pop("api_key_env", None)
    auxiliary = config.setdefault("auxiliary", {})
    if isinstance(auxiliary, dict):
        for task in auxiliary.values():
            if not isinstance(task, dict):
                continue
            task["provider"] = "main"
            for key in (
                "model",
                "base_url",
                "api_key",
                "api_key_env",
                "fallback_chain",
            ):
                task.pop(key, None)
    config.pop("fallback_providers", None)
    config.pop("fallback_model", None)
    config.pop("bedrock", None)
    config.setdefault("prompt_caching", {})["cache_ttl"] = "off"

    mcp_url = profile["mcp"]["personal_tools_url"]
    mcp_servers = config.setdefault("mcp_servers", {})
    if mcp_url:
        if not mcp_secret_authorized:
            raise ValueError(
                "Personal Tools URL requires the CloudFormation-authorized client Secret"
            )
        mcp_servers["personal_tools"] = {
            "url": mcp_url,
            "connect_timeout": 15,
            "headers": {
                "X-Hermes-Gateway-Token": "Bearer ${MCP_PERSONAL_TOOLS_API_KEY}",
            },
        }
    else:
        mcp_servers.pop("personal_tools", None)
    return config


def atomic_write_yaml(path: Path, config: dict[str, object]) -> None:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as target:
            yaml.safe_dump(config, target, sort_keys=False)
            target.flush()
            os.fsync(target.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    import yaml

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--git-coding-enabled", choices=("true", "false"), required=True)
    parser.add_argument("--mcp-secret-authorized", choices=("true", "false"), required=True)
    args = parser.parse_args()
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    config = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    updated = apply_profile(
        profile,
        config,
        git_coding_enabled=args.git_coding_enabled == "true",
        mcp_secret_authorized=args.mcp_secret_authorized == "true",
    )
    atomic_write_yaml(args.config, updated)
    print("runtime-profile-applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
