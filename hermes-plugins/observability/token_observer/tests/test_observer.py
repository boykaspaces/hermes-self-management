from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


observer_module = load_module("token_observer_test_observer", PLUGIN_DIR / "observer.py")
report_module = load_module("token_observer_test_report", PLUGIN_DIR / "report.py")


class TokenObserverTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "ai-calls.sqlite3"
        self.store = observer_module.ObserverStore(self.db_path, retention_days=30)
        self.observer = observer_module.TokenObserver(self.store)

    def tearDown(self):
        self.store.close()
        self.tempdir.cleanup()

    def rows(self, table: str):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            return connection.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
        finally:
            connection.close()

    def test_successful_call_records_tokens_and_only_context_sizes(self):
        secret = "DO-NOT-PERSIST-telegram-secret"
        base = {
            "api_request_id": "turn-1:api:1",
            "session_id": "telegram:123456",
            "task_id": "task-1",
            "turn_id": "turn-1",
            "platform": "telegram",
            "provider": "bedrock",
            "model": "claude-sonnet-4-6",
            "api_mode": "bedrock_converse",
            "api_call_count": 1,
            "retry_count": 0,
            "started_at": 1000.0,
            "message_count": 3,
            "tool_count": 1,
            "approx_input_tokens": 321,
            "request_char_count": 1234,
            "max_tokens": 4096,
            "request_messages": [
                {"role": "system", "content": "system " + secret},
                {"role": "user", "content": "user " + secret},
                {"role": "tool", "content": "result " + secret},
            ],
            "request": {
                "body": {
                    "tools": [{"name": "memory", "description": secret}],
                    "messages": [{"role": "user", "content": secret}],
                }
            },
        }
        self.observer.on_pre_api_request(**base)
        self.observer.on_post_api_request(
            **{key: value for key, value in base.items() if key not in {"request_messages", "request"}},
            ended_at=1001.25,
            api_duration=1.25,
            finish_reason="stop",
            response_model="claude-sonnet-4-6-v1",
            usage={
                "input_tokens": 100,
                "output_tokens": 20,
                "cache_read_tokens": 200,
                "cache_write_tokens": 10,
                "reasoning_tokens": 5,
            },
            assistant_content_chars=80,
            assistant_tool_call_count=0,
        )

        [row] = self.rows("ai_calls")
        self.assertEqual(row["status"], "ok")
        self.assertEqual(row["input_tokens"], 100)
        self.assertEqual(row["cache_read_tokens"], 200)
        self.assertEqual(row["latency_ms"], 1250)
        self.assertGreater(row["system_chars"], 0)
        self.assertGreater(row["tool_result_chars"], 0)
        self.assertNotEqual(row["session_key"], "telegram:123456")
        persisted = self.db_path.read_bytes()
        self.assertNotIn(secret.encode(), persisted)
        self.assertNotIn(b"telegram:123456", persisted)
        self.assertNotIn(b"turn-1:api:1", persisted)

    def test_retry_and_fallback_are_separate_attempts(self):
        base = {
            "api_request_id": "turn-2:api:1",
            "session_id": "s2",
            "task_id": "t2",
            "turn_id": "turn-2",
            "started_at": 2000.0,
            "provider": "bedrock",
            "model": "primary",
        }
        self.observer.on_pre_api_request(**base, retry_count=0)
        self.observer.on_api_request_error(
            **base,
            retry_count=0,
            ended_at=2000.1,
            api_duration=0.1,
            status_code=429,
            retryable=True,
            error={"type": "RateLimitError", "message": "secret provider body"},
        )
        fallback = {**base, "provider": "openai", "model": "fallback", "started_at": 2000.2}
        self.observer.on_pre_api_request(**fallback, retry_count=0)
        self.observer.on_post_api_request(
            **fallback,
            ended_at=2000.5,
            api_duration=0.3,
            usage={"input_tokens": 50, "output_tokens": 5},
        )

        rows = self.rows("ai_calls")
        self.assertEqual(len(rows), 2)
        self.assertEqual([row["attempt_index"] for row in rows], [0, 1])
        self.assertEqual([row["status"] for row in rows], ["error", "ok"])
        self.assertEqual(rows[0]["error_type"], "RateLimitError")
        self.assertNotIn(b"secret provider body", self.db_path.read_bytes())

    def test_bedrock_truncation_uses_explicitly_marked_estimates(self):
        self.observer.on_pre_api_request(
            api_request_id="bedrock-r1",
            session_id="s-bedrock",
            provider="bedrock",
            model="m",
            api_call_count=1,
            approx_input_tokens=200,
            request_char_count=800,
            request_messages=[{"role": "user", "content": "short"}],
            request={"_truncated": True, "preview": "not parsed or persisted"},
        )
        self.observer.on_post_api_request(
            api_request_id="bedrock-r1",
            session_id="s-bedrock",
            provider="bedrock",
            model="m",
            usage={"input_tokens": 10, "cache_write_tokens": 490, "output_tokens": 1},
        )
        [row] = self.rows("ai_calls")
        self.assertEqual(row["system_chars_inferred"], 1)
        self.assertGreater(row["system_chars"], 700)
        self.assertEqual(row["non_message_prompt_tokens_estimate"], 300)
        self.assertNotIn(b"not parsed or persisted", self.db_path.read_bytes())

    def test_schema_v1_is_migrated_in_place(self):
        self.observer.on_pre_api_request(
            api_request_id="legacy", session_id="legacy-session",
            approx_input_tokens=20, request_char_count=80,
            request_messages=[{"role": "user", "content": "x"}],
        )
        self.observer.on_post_api_request(
            api_request_id="legacy", session_id="legacy-session",
            usage={"input_tokens": 10, "cache_write_tokens": 40},
        )
        self.store.close()
        connection = sqlite3.connect(self.db_path)
        connection.execute("UPDATE ai_calls SET system_chars = 0")
        connection.execute("ALTER TABLE ai_calls DROP COLUMN system_chars_inferred")
        connection.execute("ALTER TABLE ai_calls DROP COLUMN non_message_prompt_tokens_estimate")
        connection.execute(
            "UPDATE schema_meta SET value = '1' WHERE key = 'schema_version'"
        )
        connection.commit()
        connection.close()

        self.store = observer_module.ObserverStore(self.db_path, retention_days=30)
        columns = {row[1] for row in self.store._connect().execute("PRAGMA table_info(ai_calls)")}
        self.assertIn("system_chars_inferred", columns)
        self.assertIn("non_message_prompt_tokens_estimate", columns)
        version = self.store._connect().execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()[0]
        self.assertEqual(version, "3")
        row = self.store._connect().execute(
            "SELECT system_chars, system_chars_inferred, non_message_prompt_tokens_estimate FROM ai_calls"
        ).fetchone()
        self.assertGreater(row["system_chars"], 0)
        self.assertEqual(row["system_chars_inferred"], 1)
        self.assertEqual(row["non_message_prompt_tokens_estimate"], 30)

    def test_enriched_prompt_components_store_only_sizes_and_tool_names(self):
        secret = "DO-NOT-PERSIST-component-body"
        self.observer.on_pre_api_request(
            api_request_id="components-r1",
            session_id="components-session",
            request_messages=[{"role": "user", "content": secret}],
            request={
                "_truncated": True,
                "_token_observer": {
                    "version": 1,
                    "prompt_components": {
                        "base_system": 4000,
                        "context": 800,
                        "memory": 1200,
                        "unknown_content": 9999,
                    },
                    "tool_components": [
                        {"name": "terminal", "chars": 600},
                        {"name": "mcp__personal_tools__budget", "chars": 900},
                    ],
                },
            },
        )
        rows = self.rows("prompt_components")
        self.assertEqual(
            {row["component_type"] for row in rows},
            {"base_system", "context", "memory", "user_messages", "tool_schema", "mcp_schema"},
        )
        self.assertEqual(
            next(row["char_count"] for row in rows if row["component_type"] == "memory"),
            1200,
        )
        persisted = self.db_path.read_bytes()
        self.assertNotIn(secret.encode(), persisted)
        self.assertNotIn(b"unknown_content", persisted)

    def test_tool_call_records_metadata_but_not_values(self):
        secret = "DO-NOT-PERSIST-tool-value"
        self.observer.on_post_tool_call(
            session_id="s3",
            task_id="t3",
            turn_id="turn-3",
            api_request_id="turn-3:api:1",
            tool_call_id="call-123",
            tool_name="web_search",
            args={"query": secret},
            result=json.dumps({"result": secret}),
            status="ok",
            duration_ms=45,
        )
        [row] = self.rows("tool_calls")
        self.assertEqual(row["tool_name"], "web_search")
        self.assertEqual(row["duration_ms"], 45)
        self.assertEqual(row["args_key_count"], 1)
        self.assertGreater(row["result_chars"], len(secret))
        self.assertNotIn(secret.encode(), self.db_path.read_bytes())
        self.assertNotIn(b"call-123", self.db_path.read_bytes())

    def test_plugin_registers_only_required_hooks(self):
        package_name = "token_observer_test_package"
        spec = importlib.util.spec_from_file_location(
            package_name,
            PLUGIN_DIR / "__init__.py",
            submodule_search_locations=[str(PLUGIN_DIR)],
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[package_name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)

        class Context:
            def __init__(self):
                self.hooks = {}

            def register_hook(self, name, callback):
                self.hooks[name] = callback

        context = Context()
        old_observer = module.get_observer
        module.get_observer = lambda: self.observer
        try:
            module.register(context)
        finally:
            module.get_observer = old_observer
        self.assertEqual(
            set(context.hooks),
            {"pre_api_request", "post_api_request", "api_request_error", "post_tool_call"},
        )

    def test_report_aggregates_calls_and_tools(self):
        self.observer.on_pre_api_request(
            api_request_id="r1", session_id="s", provider="bedrock", model="m"
        )
        self.observer.on_post_api_request(
            api_request_id="r1",
            session_id="s",
            provider="bedrock",
            model="m",
            usage={"input_tokens": 10, "output_tokens": 2, "cache_read_tokens": 30},
            api_duration=0.2,
        )
        self.observer.on_post_tool_call(
            session_id="s", tool_name="memory", args={}, result="ok", status="ok", duration_ms=10
        )
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            report = report_module.query_report(connection, days=7)
        finally:
            connection.close()
        self.assertEqual(report["totals"]["calls"], 1)
        self.assertEqual(report["totals"]["input_tokens"], 10)
        self.assertEqual(report["totals"]["cache_read_tokens"], 30)
        self.assertEqual(report["totals"]["tool_calls"], 1)

    def test_report_reads_auxiliary_aggregates_when_available(self):
        state_db = Path(self.tempdir.name) / "state.db"
        connection = sqlite3.connect(state_db)
        try:
            connection.executescript(
                """
                CREATE TABLE sessions (id TEXT PRIMARY KEY, started_at REAL);
                CREATE TABLE session_model_usage (
                    session_id TEXT, model TEXT, task TEXT, billing_provider TEXT,
                    api_call_count INTEGER, input_tokens INTEGER, output_tokens INTEGER,
                    cache_read_tokens INTEGER, cache_write_tokens INTEGER,
                    reasoning_tokens INTEGER
                );
                """
            )
            connection.execute("INSERT INTO sessions VALUES ('s', strftime('%s','now'))")
            connection.execute(
                "INSERT INTO session_model_usage VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("s", "nova-lite", "compression", "bedrock", 2, 100, 20, 30, 4, 0),
            )
            connection.commit()
        finally:
            connection.close()

        observer_db = sqlite3.connect(self.db_path)
        observer_db.row_factory = sqlite3.Row
        try:
            report = report_module.query_report(observer_db, days=7, hermes_state_db=state_db)
        finally:
            observer_db.close()
        self.assertEqual(report["auxiliary_totals"]["calls"], 2)
        self.assertEqual(report["auxiliary_totals"]["input_tokens"], 100)
        self.assertEqual(report["auxiliary_models"][0]["task"], "compression")

    def test_hook_failures_are_fail_open(self):
        def broken(_event):
            raise sqlite3.OperationalError("database unavailable")

        self.observer._safely(broken, {"user_message": "secret"})


if __name__ == "__main__":
    unittest.main()
