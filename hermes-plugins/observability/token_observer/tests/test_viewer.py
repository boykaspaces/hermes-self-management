from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_DIR))

import observer
import viewer


class ViewerTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "ai-calls.sqlite3"
        store = observer.ObserverStore(self.db_path)
        agent = observer.TokenObserver(store)
        self.secret = "DO-NOT-RETURN-viewer-secret"
        agent.on_pre_api_request(
            api_request_id="viewer-request",
            session_id="viewer-session",
            provider="bedrock",
            model="claude",
            api_call_count=1,
            request_messages=[{"role": "user", "content": self.secret}],
        )
        agent.on_post_api_request(
            api_request_id="viewer-request",
            session_id="viewer-session",
            provider="bedrock",
            model="claude",
            usage={"input_tokens": 12, "output_tokens": 3, "cache_read_tokens": 40},
            api_duration=0.125,
        )
        store.close()
        application = viewer.ViewerApplication(self.db_path, None)
        self.server = viewer.ViewerServer(("127.0.0.1", 0), application)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tempdir.cleanup()

    def get(self, path: str):
        return urllib.request.urlopen(self.base_url + path, timeout=2)

    def test_health_and_security_headers(self):
        with self.get("/healthz") as response:
            self.assertEqual(json.load(response), {"status": "ok"})
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            self.assertEqual(response.headers["X-Frame-Options"], "DENY")
            self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])

    def test_report_and_calls_are_privacy_safe(self):
        with self.get("/api/report?days=7") as response:
            report_body = response.read()
            report = json.loads(report_body)
        with self.get("/api/calls?days=7&limit=20") as response:
            calls_body = response.read()
            calls = json.loads(calls_body)
        with self.get("/api/runs?days=7&limit=20") as response:
            runs_body = response.read()
            runs = json.loads(runs_body)
        self.assertEqual(report["totals"]["calls"], 1)
        self.assertEqual(report["totals"]["input_tokens"], 12)
        self.assertEqual(calls["items"][0]["model"], "claude")
        self.assertEqual(calls["items"][0]["latency_ms"], 125)
        self.assertEqual(len(runs["items"]), 1)
        self.assertEqual(runs["items"][0]["attempt_count"], 1)
        self.assertEqual(runs["items"][0]["attempts"][0]["prompt_tokens"], 52)
        self.assertEqual(runs["items"][0]["attempts"][0]["cache_read_tokens"], 40)
        self.assertIn(
            "unattributed",
            {item["type"] for item in runs["items"][0]["attempts"][0]["components"]},
        )
        self.assertNotIn(self.secret.encode(), report_body)
        self.assertNotIn(self.secret.encode(), calls_body)
        self.assertNotIn(self.secret.encode(), runs_body)
        self.assertNotIn(b"viewer-session", calls_body)
        self.assertNotIn(b"viewer-request", calls_body)
        self.assertNotIn(b"viewer-session", runs_body)
        self.assertNotIn(b"viewer-request", runs_body)

    def test_query_parameters_are_bounded(self):
        for path in (
            "/api/report?days=0", "/api/calls?limit=201",
            "/api/calls?cursor=x", "/api/runs?limit=101",
        ):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                self.get(path)
            self.assertEqual(caught.exception.code, 400)
            caught.exception.close()

    def test_agent_run_groups_loops_and_preserves_exact_token_breakdown(self):
        store = observer.ObserverStore(self.db_path)
        agent = observer.TokenObserver(store)
        for loop, request_id, usage in (
            (1, "chain-request-1", {
                "input_tokens": 2, "cache_read_tokens": 30,
                "cache_write_tokens": 4, "output_tokens": 5,
                "reasoning_tokens": 1,
            }),
            (2, "chain-request-2", {
                "input_tokens": 3, "cache_read_tokens": 35,
                "cache_write_tokens": 6, "output_tokens": 7,
                "reasoning_tokens": 2,
            }),
        ):
            event = {
                "api_request_id": request_id,
                "session_id": "chain-session",
                "task_id": "chain-task",
                "turn_id": "chain-turn",
                "provider": "bedrock",
                "model": "claude",
                "api_call_count": loop,
            }
            if loop == 1:
                event["request"] = {
                    "_token_observer": {
                        "prompt_components": {"base_system": 40, "memory": 20},
                        "tool_components": [{"name": "terminal", "chars": 16}],
                    }
                }
            agent.on_pre_api_request(**event)
            agent.on_post_api_request(**event, usage=usage, api_duration=0.1)
            if loop == 1:
                agent.on_post_tool_call(
                    **event,
                    tool_call_id="tool-1",
                    tool_name="terminal",
                    args={}, result="ok", status="ok",
                )
                agent.on_post_tool_call(
                    **event,
                    tool_call_id="tool-2",
                    tool_name="mcp__personal_tools__budget",
                    args={}, result="ok", status="ok",
                )
        store.close()

        with self.get("/api/runs?days=7&limit=20") as response:
            body = response.read()
            runs = json.loads(body)["items"]
        chain = next(run for run in runs if run["attempt_count"] == 2)
        self.assertEqual(chain["loop_count"], 2)
        self.assertEqual(chain["max_loop"], 2)
        self.assertEqual([item["prompt_tokens"] for item in chain["attempts"]], [36, 44])
        self.assertEqual(chain["totals"]["cache_write_tokens"], 10)
        self.assertEqual(chain["totals"]["reasoning_tokens"], 3)
        self.assertEqual(chain["attempts"][0]["tool_call_count"], 1)
        self.assertEqual(chain["attempts"][0]["mcp_call_count"], 1)
        self.assertEqual(chain["attempts"][1]["tools"], [])
        self.assertTrue(chain["attempts"][0]["components"])
        self.assertIn(
            "memory", {item["type"] for item in chain["attempts"][0]["components"]}
        )
        self.assertNotIn(b"chain-session", body)
        self.assertNotIn(b"chain-turn", body)

    def test_agent_runs_tolerate_database_before_component_migration(self):
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("DROP TABLE prompt_components")
            connection.commit()
        finally:
            connection.close()
        with self.get("/api/runs?days=7&limit=20") as response:
            runs = json.load(response)["items"]
        self.assertEqual(len(runs), 1)
        self.assertTrue(runs[0]["attempts"][0]["components"])

    def test_static_assets_are_local_and_unknown_paths_fail(self):
        with self.get("/") as response:
            index = response.read().decode()
        self.assertIn("AI 调用观测台", index)
        for filename in ("index.html", "app.js", "style.css"):
            data = (viewer.WEB_ROOT / filename).read_text()
            self.assertNotIn("https://", data)
            self.assertNotIn("http://", data)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get("/../observer.py")
        self.assertEqual(caught.exception.code, 404)
        caught.exception.close()

    def test_non_loopback_bind_is_rejected(self):
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            viewer.parse_args(["--host", "0.0.0.0", "--db", str(self.db_path)])


if __name__ == "__main__":
    unittest.main()
