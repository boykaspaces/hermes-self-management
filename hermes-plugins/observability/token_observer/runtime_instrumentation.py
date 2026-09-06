"""Upgrade-safe, in-process Hermes prompt-size instrumentation.

The adapter deliberately avoids editing the Hermes checkout.  It wraps two
stable runtime seams when the plugin loads, adds size-only metadata to the
existing pre_api_request payload, and is installed again after every Gateway
restart.  Incompatible Hermes versions degrade to the observer's existing
coarse accounting instead of blocking model calls.
"""

from __future__ import annotations

import functools
import importlib
import inspect
import json
import logging
from typing import Any, Mapping, Sequence


LOGGER = logging.getLogger(__name__)
INSTRUMENTATION_VERSION = 1
_WRAPPED = "__token_observer_runtime_instrumentation_v1__"


def _compact_json_chars(value: Any) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str))
    except Exception:
        return 0


def _tool_name(tool: Mapping[str, Any]) -> str:
    name = tool.get("name")
    if not name and isinstance(tool.get("function"), Mapping):
        name = tool["function"].get("name")
    if not name:
        name = tool.get("type") or "unknown"
    return str(name)[:255]


def _skills_prefix(agent: Any, volatile_without_runtime: str) -> str:
    """Recreate only the cached skills index and verify it is an exact prefix."""
    valid_names = list(getattr(agent, "valid_tool_names", None) or [])
    if not any(name in valid_names for name in ("skills_list", "skill_view", "skill_manage")):
        return ""
    try:
        runtime = importlib.import_module("run_agent")
        toolsets = {
            toolset
            for toolset in (runtime.get_toolset_for_tool(name) for name in valid_names)
            if toolset
        }
        compact_categories = None
        try:
            coding = importlib.import_module("agent.coding_context")
            runtime_cwd = importlib.import_module("agent.runtime_cwd")
            compact_categories = coding.coding_compact_skill_categories(
                platform=getattr(agent, "platform", None),
                cwd=runtime_cwd.resolve_context_cwd(),
            ) or None
        except Exception:
            compact_categories = None
        rendered = runtime.build_skills_system_prompt(
            available_tools=valid_names,
            available_toolsets=toolsets,
            compact_categories=compact_categories,
        )
        candidate = str(rendered or "").strip()
        return candidate if candidate and volatile_without_runtime.startswith(candidate) else ""
    except Exception:
        return ""


def _component_sizes(agent: Any, parts: Mapping[str, Any]) -> dict[str, int]:
    stable = str(parts.get("stable") or "")
    context = str(parts.get("context") or "")
    volatile = str(parts.get("volatile") or "")

    marker = "Conversation started:"
    marker_index = volatile.rfind("\n\n" + marker)
    if marker_index >= 0:
        before_runtime = volatile[:marker_index]
        runtime = volatile[marker_index + 2 :]
    elif volatile.startswith(marker):
        before_runtime = ""
        runtime = volatile
    else:
        before_runtime = volatile
        runtime = ""

    expects_skills = any(
        name in list(getattr(agent, "valid_tool_names", None) or [])
        for name in ("skills_list", "skill_view", "skill_manage")
    )
    skills = _skills_prefix(agent, before_runtime)
    unresolved_volatile = expects_skills and bool(before_runtime) and not skills
    memory = before_runtime[len(skills) :].lstrip("\n") if skills else before_runtime
    components = {
        "base_system": len(stable),
        "context": len(context),
        "skills": len(skills),
        "memory": 0 if unresolved_volatile else len(memory),
        "volatile": len(before_runtime) if unresolved_volatile else 0,
        "runtime": len(runtime),
    }
    return {name: chars for name, chars in components.items() if chars > 0}


def _wrap_system_prompt() -> bool:
    module = importlib.import_module("agent.system_prompt")
    original = getattr(module, "build_system_prompt_parts", None)
    if not callable(original):
        return False
    if getattr(original, _WRAPPED, False):
        return True

    @functools.wraps(original)
    def wrapped(agent: Any, *args: Any, **kwargs: Any):
        parts = original(agent, *args, **kwargs)
        try:
            if isinstance(parts, Mapping):
                agent._token_observer_prompt_components = _component_sizes(agent, parts)
        except Exception:
            LOGGER.debug("prompt component instrumentation failed", exc_info=True)
        return parts

    setattr(wrapped, _WRAPPED, True)
    module.build_system_prompt_parts = wrapped
    return True


def _wrap_request_payload() -> bool:
    runtime = importlib.import_module("run_agent")
    agent_class = getattr(runtime, "AIAgent", None)
    original = getattr(agent_class, "_api_request_payload_for_hook", None)
    if not callable(original):
        return False
    if getattr(original, _WRAPPED, False):
        return True
    parameters = inspect.signature(original).parameters
    if "api_kwargs" not in parameters:
        return False

    @functools.wraps(original)
    def wrapped(self: Any, api_kwargs: Any):
        payload = original(self, api_kwargs)
        if not isinstance(payload, dict):
            payload = {"_truncated": True}
        try:
            prompt_components = dict(
                getattr(self, "_token_observer_prompt_components", None) or {}
            )
            ephemeral = getattr(self, "ephemeral_system_prompt", None)
            if isinstance(ephemeral, str) and ephemeral:
                prompt_components["ephemeral_context"] = len(ephemeral)

            tools = api_kwargs.get("tools") if isinstance(api_kwargs, Mapping) else None
            tool_components = []
            if isinstance(tools, Sequence) and not isinstance(tools, (str, bytes, bytearray)):
                for tool in tools:
                    if not isinstance(tool, Mapping):
                        continue
                    tool_components.append(
                        {"name": _tool_name(tool), "chars": _compact_json_chars(tool)}
                    )
            payload["_token_observer"] = {
                "version": INSTRUMENTATION_VERSION,
                "prompt_components": prompt_components,
                "tool_components": tool_components,
            }
        except Exception:
            LOGGER.debug("request component instrumentation failed", exc_info=True)
        return payload

    setattr(wrapped, _WRAPPED, True)
    agent_class._api_request_payload_for_hook = wrapped
    return True


def install_runtime_instrumentation() -> dict[str, Any]:
    """Install guarded wrappers and return a small health summary."""
    status = {
        "version": INSTRUMENTATION_VERSION,
        "system_prompt": False,
        "request_payload": False,
    }
    try:
        status["system_prompt"] = _wrap_system_prompt()
    except Exception:
        LOGGER.warning("Hermes system-prompt instrumentation is unavailable")
    try:
        status["request_payload"] = _wrap_request_payload()
    except Exception:
        LOGGER.warning("Hermes request instrumentation is unavailable")
    return status
