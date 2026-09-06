from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_DIR))

import runtime_instrumentation as instrumentation


class RuntimeInstrumentationTest(unittest.TestCase):
    def test_component_sizes_split_cache_tiers_memory_and_runtime(self):
        agent = types.SimpleNamespace(valid_tool_names=[])
        parts = {
            "stable": "base instructions",
            "context": "workspace context",
            "volatile": "remember this\n\nConversation started: Friday",
        }
        sizes = instrumentation._component_sizes(agent, parts)
        self.assertEqual(sizes["base_system"], len(parts["stable"]))
        self.assertEqual(sizes["context"], len(parts["context"]))
        self.assertEqual(sizes["memory"], len("remember this"))
        self.assertEqual(sizes["runtime"], len("Conversation started: Friday"))

    def test_request_wrapper_adds_size_only_sidecar_and_is_idempotent(self):
        class FakeAgent:
            ephemeral_system_prompt = "temporary"
            _token_observer_prompt_components = {"base_system": 100}

            def _api_request_payload_for_hook(self, api_kwargs):
                return {"_truncated": True}

        previous = sys.modules.get("run_agent")
        sys.modules["run_agent"] = types.SimpleNamespace(AIAgent=FakeAgent)
        try:
            self.assertTrue(instrumentation._wrap_request_payload())
            wrapped_once = FakeAgent._api_request_payload_for_hook
            self.assertTrue(instrumentation._wrap_request_payload())
            self.assertIs(FakeAgent._api_request_payload_for_hook, wrapped_once)
            payload = FakeAgent()._api_request_payload_for_hook(
                {
                    "tools": [
                        {"type": "function", "name": "terminal", "description": "secret"},
                        {"type": "function", "name": "mcp__personal__read", "description": "secret"},
                    ]
                }
            )
        finally:
            if previous is None:
                sys.modules.pop("run_agent", None)
            else:
                sys.modules["run_agent"] = previous

        sidecar = payload["_token_observer"]
        self.assertEqual(sidecar["prompt_components"]["base_system"], 100)
        self.assertEqual(sidecar["prompt_components"]["ephemeral_context"], 9)
        self.assertEqual([item["name"] for item in sidecar["tool_components"]], [
            "terminal", "mcp__personal__read",
        ])
        self.assertNotIn("secret", str(sidecar))


if __name__ == "__main__":
    unittest.main()
