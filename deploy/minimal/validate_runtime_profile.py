#!/usr/bin/env python3
"""Validate a consumer-owned Hermes runtime profile."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
from pathlib import Path
from urllib.parse import urlparse


MODEL_RE = re.compile(r"^[A-Za-z0-9._:-]+$")
PROFILE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
HOST_RE = re.compile(
    r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}$"
)

EXPECTED_KEYS_V1 = {
    "schema_version",
    "model",
    "telegram",
    "mcp",
    "credential",
    "browser",
    "terminal",
    "agent",
    "memory",
    "skills",
    "proxy",
}
EXPECTED_KEYS_V2 = EXPECTED_KEYS_V1 | {"context_workspace"}
CONTEXT_WORKSPACE_KEYS = {"enabled", "host_root", "project_access"}


def require_object(value: object, name: str, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    actual = set(value)
    if actual != keys:
        raise ValueError(
            f"{name} keys differ: missing={sorted(keys - actual)} "
            f"unexpected={sorted(actual - keys)}"
        )
    return value


def require_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def require_int(value: object, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def require_number(
    value: object, name: str, minimum: float, maximum: float
) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def require_host_root(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("context_workspace.host_root must be a string")
    if not value.startswith("/") or value.startswith("//") or value == "/":
        raise ValueError(
            "context_workspace.host_root must be an absolute non-root POSIX path"
        )
    if (
        value != posixpath.normpath(value)
        or ":" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError(
            "context_workspace.host_root must be normalized and mount-safe"
        )
    return value


def validate_profile(profile: object) -> dict[str, object]:
    if not isinstance(profile, dict):
        raise ValueError("profile must be an object")
    schema_version = profile.get("schema_version")
    if isinstance(schema_version, bool):
        raise ValueError("schema_version must be 1 or 2")
    if schema_version == 1:
        root = require_object(profile, "profile", EXPECTED_KEYS_V1)
    elif schema_version == 2:
        root = require_object(profile, "profile", EXPECTED_KEYS_V2)
    else:
        raise ValueError("schema_version must be 1 or 2")

    if schema_version == 2:
        context_workspace = require_object(
            root["context_workspace"],
            "context_workspace",
            CONTEXT_WORKSPACE_KEYS,
        )
        require_bool(context_workspace["enabled"], "context_workspace.enabled")
        require_host_root(context_workspace["host_root"])
        if context_workspace["project_access"] not in {"read-only", "read-write"}:
            raise ValueError("context_workspace.project_access is invalid")

    model = require_object(root["model"], "model", {"default"})
    if not isinstance(model["default"], str) or not MODEL_RE.fullmatch(model["default"]):
        raise ValueError("model.default is invalid")

    telegram = require_object(
        root["telegram"],
        "telegram",
        {
            "enabled",
            "reactions",
            "streaming",
            "tool_progress",
            "tool_progress_grouping",
            "long_running_notifications",
            "cleanup_progress",
            "gateway_notify_interval",
        },
    )
    for key in (
        "enabled",
        "reactions",
        "streaming",
        "long_running_notifications",
        "cleanup_progress",
    ):
        require_bool(telegram[key], f"telegram.{key}")
    if telegram["tool_progress"] not in {"off", "new", "all"}:
        raise ValueError("telegram.tool_progress is invalid")
    if telegram["tool_progress_grouping"] not in {"off", "accumulate"}:
        raise ValueError("telegram.tool_progress_grouping is invalid")
    require_int(
        telegram["gateway_notify_interval"],
        "telegram.gateway_notify_interval",
        15,
        3600,
    )

    mcp = require_object(root["mcp"], "mcp", {"personal_tools_url"})
    mcp_url = mcp["personal_tools_url"]
    if not isinstance(mcp_url, str):
        raise ValueError("mcp.personal_tools_url must be a string")
    if mcp_url:
        parsed = urlparse(mcp_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.path != "/mcp":
            raise ValueError("mcp.personal_tools_url must be an HTTPS /mcp endpoint")
        if parsed.params or parsed.query or parsed.fragment or parsed.username:
            raise ValueError("mcp.personal_tools_url must not contain credentials or extras")

    credential = require_object(root["credential"], "credential", {"profile_id"})
    profile_id = credential["profile_id"]
    if not isinstance(profile_id, str) or not PROFILE_RE.fullmatch(profile_id):
        raise ValueError("credential.profile_id is invalid")

    browser = require_object(
        root["browser"], "browser", {"inactivity_timeout", "command_timeout"}
    )
    require_int(browser["inactivity_timeout"], "browser.inactivity_timeout", 15, 3600)
    require_int(browser["command_timeout"], "browser.command_timeout", 5, 600)

    terminal = require_object(
        root["terminal"],
        "terminal",
        {
            "container_memory",
            "container_disk",
            "docker_shm_size",
            "container_cpu",
            "container_persistent",
            "docker_mount_cwd_to_workspace",
            "home_mode",
            "lifetime_seconds",
            "timeout",
            "cwd",
        },
    )
    require_int(terminal["container_memory"], "terminal.container_memory", 256, 16384)
    require_int(terminal["container_disk"], "terminal.container_disk", 0, 1024)
    shm_size = terminal["docker_shm_size"]
    if not isinstance(shm_size, str) or not re.fullmatch(r"[1-9][0-9]*(?:[kKmMgG])?", shm_size):
        raise ValueError("terminal.docker_shm_size is invalid")
    require_number(terminal["container_cpu"], "terminal.container_cpu", 0.25, 16)
    require_bool(terminal["container_persistent"], "terminal.container_persistent")
    require_bool(
        terminal["docker_mount_cwd_to_workspace"],
        "terminal.docker_mount_cwd_to_workspace",
    )
    if terminal["home_mode"] not in {"auto", "ephemeral", "persistent"}:
        raise ValueError("terminal.home_mode is invalid")
    require_int(terminal["lifetime_seconds"], "terminal.lifetime_seconds", 30, 86400)
    require_int(terminal["timeout"], "terminal.timeout", 10, 3600)
    if terminal["cwd"] != ".":
        raise ValueError("terminal.cwd must remain the workspace-relative '.'")

    agent = require_object(
        root["agent"], "agent", {"max_turns", "reasoning_effort", "verbose"}
    )
    require_int(agent["max_turns"], "agent.max_turns", 1, 500)
    if agent["reasoning_effort"] not in {
        "none",
        "minimal",
        "low",
        "medium",
        "high",
        "xhigh",
    }:
        raise ValueError("agent.reasoning_effort is invalid")
    require_bool(agent["verbose"], "agent.verbose")

    memory = require_object(
        root["memory"],
        "memory",
        {
            "enabled",
            "user_profile_enabled",
            "flush_min_turns",
            "memory_char_limit",
            "nudge_interval",
            "user_char_limit",
            "write_approval",
        },
    )
    require_bool(memory["enabled"], "memory.enabled")
    require_bool(memory["user_profile_enabled"], "memory.user_profile_enabled")
    require_int(memory["flush_min_turns"], "memory.flush_min_turns", 1, 100)
    require_int(memory["memory_char_limit"], "memory.memory_char_limit", 256, 20000)
    require_int(memory["nudge_interval"], "memory.nudge_interval", 1, 100)
    require_int(memory["user_char_limit"], "memory.user_char_limit", 128, 20000)
    require_bool(memory["write_approval"], "memory.write_approval")

    skills = require_object(
        root["skills"], "skills", {"guard_agent_created", "write_approval"}
    )
    require_bool(skills["guard_agent_created"], "skills.guard_agent_created")
    require_bool(skills["write_approval"], "skills.write_approval")

    proxy = require_object(root["proxy"], "proxy", {"extra_allowed_hosts"})
    hosts = proxy["extra_allowed_hosts"]
    if not isinstance(hosts, list) or not 1 <= len(hosts) <= 64:
        raise ValueError("proxy.extra_allowed_hosts must contain 1-64 hosts")
    if len(hosts) != len(set(hosts)):
        raise ValueError("proxy.extra_allowed_hosts must not contain duplicates")
    for host in hosts:
        if not isinstance(host, str) or not HOST_RE.fullmatch(host):
            raise ValueError(f"invalid proxy host: {host!r}")

    serialized = json.dumps(root, sort_keys=True)
    if re.search(r"(?i)(token|password|private[_-]?key|secret[_-]?value)", serialized):
        raise ValueError("runtime profile appears to contain credential material")
    if len(serialized.encode("utf-8")) > 4096:
        raise ValueError("runtime profile exceeds the SSM Standard parameter limit")
    return root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    args = parser.parse_args()
    try:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        validate_profile(profile)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit(f"runtime-profile-invalid: {error}") from error
    print("runtime-profile-ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
