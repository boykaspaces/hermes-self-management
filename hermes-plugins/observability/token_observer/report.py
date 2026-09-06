#!/usr/bin/env python3
"""Query privacy-safe token observer data without Hermes dependencies."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any


def default_db_path() -> Path:
    configured = os.getenv("HERMES_TOKEN_OBSERVER_DB")
    if configured:
        return Path(configured).expanduser()
    return Path(os.getenv("HERMES_HOME", "~/.hermes")).expanduser() / "observability" / "ai-calls.sqlite3"


def percentile(values: list[int], quantile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * quantile)
    return ordered[index]


def iso_timestamp(value: float) -> str:
    timestamp = dt.datetime.fromtimestamp(float(value), tz=dt.timezone.utc)
    return timestamp.isoformat().replace("+00:00", "Z")


def query_auxiliary(state_db: Path | None, *, days: int) -> list[dict[str, Any]]:
    """Read Hermes's aggregate-only auxiliary LLM accounting, when available."""
    if state_db is None or not state_db.exists():
        return []
    cutoff = time.time() - max(1, days) * 86400
    connection = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT u.model, u.task, u.billing_provider AS provider,
                   SUM(u.api_call_count) AS calls,
                   SUM(u.input_tokens) AS input_tokens,
                   SUM(u.output_tokens) AS output_tokens,
                   SUM(u.cache_read_tokens) AS cache_read_tokens,
                   SUM(u.cache_write_tokens) AS cache_write_tokens,
                   SUM(u.reasoning_tokens) AS reasoning_tokens,
                   COUNT(DISTINCT u.session_id) AS sessions
            FROM session_model_usage u
            JOIN sessions s ON s.id = u.session_id
            WHERE s.started_at >= ? AND u.task != ''
            GROUP BY u.model, u.task, u.billing_provider
            ORDER BY SUM(u.input_tokens) + SUM(u.cache_read_tokens) DESC
            """,
            (cutoff,),
        ).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        connection.close()


def query_recent_calls(
    connection: sqlite3.Connection,
    *,
    days: int,
    limit: int = 50,
    before_id: int | None = None,
) -> dict[str, Any]:
    """Return a bounded, privacy-safe page of recent model attempts."""
    cutoff = time.time() - max(1, days) * 86400
    page_size = min(200, max(1, int(limit)))
    where = "started_at >= ?"
    parameters: list[Any] = [cutoff]
    if before_id is not None:
        where += " AND id < ?"
        parameters.append(max(1, int(before_id)))
    parameters.append(page_size + 1)
    rows = connection.execute(
        f"""
        SELECT id, started_at, provider, model, response_model, api_mode,
               api_call_count, attempt_index, retry_count, status, finish_reason,
               latency_ms, http_status, error_type, retryable, message_count,
               tool_count, approx_input_tokens, request_char_count,
               system_chars, system_chars_inferred, user_chars, assistant_chars,
               tool_result_chars, other_message_chars, tool_schema_chars,
               input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
               reasoning_tokens, non_message_prompt_tokens_estimate,
               assistant_content_chars, assistant_tool_call_count
        FROM ai_calls
        WHERE {where}
        ORDER BY id DESC
        LIMIT ?
        """,
        parameters,
    ).fetchall()
    page = rows[:page_size]
    items = []
    for row in page:
        item = dict(row)
        item["started_at_iso"] = iso_timestamp(item["started_at"])
        items.append(item)
    return {
        "items": items,
        "next_cursor": int(page[-1]["id"]) if len(rows) > page_size and page else None,
    }


def query_agent_runs(
    connection: sqlite3.Connection,
    *,
    days: int,
    limit: int = 25,
) -> dict[str, Any]:
    """Return recent anonymous Agent turns with every model API attempt."""
    cutoff = time.time() - max(1, days) * 86400
    page_size = min(100, max(1, int(limit)))
    run_rows = connection.execute(
        """
        SELECT CASE WHEN turn_key != '' THEN turn_key ELSE api_request_key END AS run_id,
               MIN(started_at) AS started_at,
               MAX(COALESCE(ended_at, started_at)) AS ended_at,
               MAX(platform) AS platform,
               COUNT(*) AS attempt_count,
               COUNT(DISTINCT api_call_count) AS loop_count,
               MAX(api_call_count) AS max_loop,
               SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS errors
        FROM ai_calls
        WHERE started_at >= ?
        GROUP BY run_id
        ORDER BY MAX(started_at) DESC
        LIMIT ?
        """,
        (cutoff, page_size),
    ).fetchall()
    if not run_rows:
        return {"items": []}

    run_ids = [str(row["run_id"]) for row in run_rows]
    placeholders = ",".join("?" for _ in run_ids)
    rows = connection.execute(
        f"""
        SELECT id, api_request_key,
               CASE WHEN turn_key != '' THEN turn_key ELSE api_request_key END AS run_id,
               started_at, provider, model, api_call_count, attempt_index,
               retry_count, status, latency_ms, input_tokens, output_tokens,
               cache_read_tokens, cache_write_tokens, reasoning_tokens,
               tool_count, system_chars, user_chars, assistant_chars,
               tool_result_chars, other_message_chars, tool_schema_chars
        FROM ai_calls
        WHERE started_at >= ?
          AND CASE WHEN turn_key != '' THEN turn_key ELSE api_request_key END
              IN ({placeholders})
        ORDER BY started_at, attempt_index
        """,
        [cutoff, *run_ids],
    ).fetchall()

    call_ids = [int(row["id"]) for row in rows]
    components_by_call: dict[int, list[dict[str, Any]]] = {
        call_id: [] for call_id in call_ids
    }
    has_prompt_components = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'prompt_components'"
    ).fetchone()
    if call_ids and has_prompt_components:
        component_placeholders = ",".join("?" for _ in call_ids)
        component_rows = connection.execute(
            f"""
            SELECT ai_call_id, component_type, component_name, char_count, item_count
            FROM prompt_components
            WHERE ai_call_id IN ({component_placeholders})
            ORDER BY ai_call_id, char_count DESC, component_name
            """,
            call_ids,
        ).fetchall()
        for component in component_rows:
            components_by_call[int(component["ai_call_id"])].append(dict(component))

    tool_rows = connection.execute(
        f"""
        SELECT CASE WHEN turn_key != '' THEN turn_key ELSE api_request_key END AS run_id,
               api_request_key, tool_name, COUNT(*) AS calls
        FROM tool_calls
        WHERE occurred_at >= ?
          AND CASE WHEN turn_key != '' THEN turn_key ELSE api_request_key END
              IN ({placeholders})
        GROUP BY run_id, api_request_key, tool_name
        ORDER BY run_id, calls DESC, tool_name
        """,
        [cutoff, *run_ids],
    ).fetchall()
    tools_by_request: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for tool in tool_rows:
        name = str(tool["tool_name"] or "unknown")
        tools_by_request.setdefault(
            (str(tool["run_id"]), str(tool["api_request_key"])), []
        ).append(
            {
                "tool_name": name,
                "kind": "mcp" if name.startswith("mcp__") else "tool",
                "calls": int(tool["calls"] or 0),
            }
        )

    attempts_by_run: dict[str, list[dict[str, Any]]] = {
        run_id: [] for run_id in run_ids
    }
    token_fields = (
        "input_tokens", "cache_read_tokens", "cache_write_tokens",
        "output_tokens", "reasoning_tokens",
    )
    for row in rows:
        item = dict(row)
        call_id = int(item.pop("id"))
        item["started_at_iso"] = iso_timestamp(item.pop("started_at"))
        prompt_values = [
            item[field]
            for field in ("input_tokens", "cache_read_tokens", "cache_write_tokens")
            if item[field] is not None
        ]
        item["prompt_tokens"] = sum(int(value) for value in prompt_values) if prompt_values else None
        stored_components = components_by_call.get(call_id) or []
        if not stored_components:
            for component_type, field in (
                ("system", "system_chars"),
                ("user_messages", "user_chars"),
                ("assistant_history", "assistant_chars"),
                ("tool_results", "tool_result_chars"),
                ("other_history", "other_message_chars"),
                ("tool_schema", "tool_schema_chars"),
            ):
                chars = int(item.get(field) or 0)
                if chars:
                    stored_components.append(
                        {
                            "component_type": component_type,
                            "component_name": "combined" if component_type in {"system", "tool_schema"} else "",
                            "char_count": chars,
                            "item_count": 1,
                        }
                    )
        visible_estimate = 0
        components = []
        for component in stored_components:
            chars = int(component.get("char_count") or 0)
            estimated_tokens = round(chars / 4)
            visible_estimate += estimated_tokens
            components.append(
                {
                    "type": component.get("component_type") or "unknown",
                    "name": component.get("component_name") or "",
                    "chars": chars,
                    "items": int(component.get("item_count") or 1),
                    "estimated_tokens": estimated_tokens,
                }
            )
        prompt_total = int(item["prompt_tokens"] or 0)
        if prompt_total > visible_estimate:
            components.append(
                {
                    "type": "unattributed",
                    "name": "",
                    "chars": None,
                    "items": 1,
                    "estimated_tokens": prompt_total - visible_estimate,
                }
            )
        item["components"] = components
        for field in (
            "system_chars", "user_chars", "assistant_chars", "tool_result_chars",
            "other_message_chars", "tool_schema_chars",
        ):
            item.pop(field, None)
        run_id = str(item.pop("run_id"))
        item["_api_request_key"] = str(item.get("api_request_key") or "")
        item.pop("api_request_key", None)
        attempts_by_run[run_id].append(item)

    for run_id, attempts in attempts_by_run.items():
        attempts_by_request: dict[str, list[dict[str, Any]]] = {}
        for attempt in attempts:
            attempts_by_request.setdefault(attempt.pop("_api_request_key"), []).append(attempt)
        for request_key, request_attempts in attempts_by_request.items():
            recorded_tools = tools_by_request.get((run_id, request_key), [])
            target = next(
                (attempt for attempt in reversed(request_attempts) if attempt["status"] == "ok"),
                request_attempts[-1],
            )
            for attempt in request_attempts:
                attempt["tools"] = recorded_tools if attempt is target else []
                attempt["tool_call_count"] = sum(
                    item["calls"] for item in attempt["tools"] if item["kind"] == "tool"
                )
                attempt["mcp_call_count"] = sum(
                    item["calls"] for item in attempt["tools"] if item["kind"] == "mcp"
                )

    items = []
    for row in run_rows:
        run = dict(row)
        run_id = str(run["run_id"])
        attempts = attempts_by_run[run_id]
        totals = {
            field: sum(int(item[field] or 0) for item in attempts)
            for field in token_fields
        }
        totals["prompt_tokens"] = sum(int(item["prompt_tokens"] or 0) for item in attempts)
        items.append(
            {
                "run_id": run_id,
                "started_at_iso": iso_timestamp(run["started_at"]),
                "ended_at_iso": iso_timestamp(run["ended_at"]),
                "duration_ms": max(0, round((run["ended_at"] - run["started_at"]) * 1000)),
                "platform": run["platform"] or "unknown",
                "attempt_count": int(run["attempt_count"] or 0),
                "loop_count": int(run["loop_count"] or 0),
                "max_loop": int(run["max_loop"]) if run["max_loop"] is not None else None,
                "errors": int(run["errors"] or 0),
                "totals": totals,
                "attempts": attempts,
            }
        )
    return {"items": items}


def query_report(
    connection: sqlite3.Connection,
    *,
    days: int,
    hermes_state_db: Path | None = None,
) -> dict[str, Any]:
    cutoff = time.time() - max(1, days) * 86400
    calls = connection.execute(
        "SELECT * FROM ai_calls WHERE started_at >= ? ORDER BY started_at", (cutoff,)
    ).fetchall()
    tools = connection.execute(
        "SELECT * FROM tool_calls WHERE occurred_at >= ? ORDER BY occurred_at", (cutoff,)
    ).fetchall()

    successful = [row for row in calls if row["status"] == "ok"]
    latencies = [int(row["latency_ms"]) for row in successful if row["latency_ms"] is not None]

    def token_sum(field: str) -> int:
        return sum(int(row[field] or 0) for row in successful)

    model_groups: dict[tuple[str, str], dict[str, Any]] = {}
    for row in calls:
        key = (row["provider"] or "unknown", row["model"] or "unknown")
        group = model_groups.setdefault(
            key,
            {"provider": key[0], "model": key[1], "calls": 0, "errors": 0,
             "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0,
             "cache_write_tokens": 0, "latency_ms": []},
        )
        group["calls"] += 1
        if row["status"] == "error":
            group["errors"] += 1
        if row["status"] == "ok":
            for field in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"):
                group[field] += int(row[field] or 0)
            if row["latency_ms"] is not None:
                group["latency_ms"].append(int(row["latency_ms"]))

    models = []
    for group in model_groups.values():
        model_latencies = group.pop("latency_ms")
        group["p95_latency_ms"] = percentile(model_latencies, 0.95)
        models.append(group)
    models.sort(key=lambda group: group["input_tokens"] + group["cache_read_tokens"], reverse=True)

    tool_groups: dict[str, dict[str, Any]] = {}
    for row in tools:
        name = row["tool_name"] or "unknown"
        group = tool_groups.setdefault(
            name,
            {"tool_name": name, "calls": 0, "errors": 0, "duration_ms": [], "result_chars": 0},
        )
        group["calls"] += 1
        if row["status"] != "ok":
            group["errors"] += 1
        if row["duration_ms"] is not None:
            group["duration_ms"].append(int(row["duration_ms"]))
        group["result_chars"] += int(row["result_chars"] or 0)

    tool_summary = []
    for group in tool_groups.values():
        durations = group.pop("duration_ms")
        group["p95_latency_ms"] = percentile(durations, 0.95)
        group["avg_result_chars"] = round(group.pop("result_chars") / group["calls"])
        tool_summary.append(group)
    tool_summary.sort(key=lambda group: group["calls"], reverse=True)

    context_totals = {
        field: sum(int(row[field] or 0) for row in calls)
        for field in (
            "system_chars", "user_chars", "assistant_chars", "tool_result_chars",
            "other_message_chars", "tool_schema_chars",
        )
    }
    prompt_tokens = token_sum("input_tokens") + token_sum("cache_read_tokens") + token_sum("cache_write_tokens")
    cache_read = token_sum("cache_read_tokens")
    logical_requests: dict[str, set[str]] = {}
    for row in calls:
        logical_requests.setdefault(row["api_request_key"], set()).add(row["provider"])

    loop_groups: dict[int, dict[str, Any]] = {}
    for row in calls:
        if row["api_call_count"] is None:
            continue
        loop_index = int(row["api_call_count"])
        group = loop_groups.setdefault(
            loop_index,
            {"loop": loop_index, "calls": 0, "prompt_tokens": 0, "request_chars": 0,
             "system_chars": 0, "assistant_chars": 0, "tool_result_chars": 0,
             "tool_schema_chars": 0, "non_message_prompt_tokens_estimate": 0,
             "non_message_estimate_samples": 0},
        )
        group["calls"] += 1
        group["prompt_tokens"] += sum(
            int(row[field] or 0)
            for field in ("input_tokens", "cache_read_tokens", "cache_write_tokens")
        )
        for source, target in (
            ("request_char_count", "request_chars"),
            ("system_chars", "system_chars"),
            ("assistant_chars", "assistant_chars"),
            ("tool_result_chars", "tool_result_chars"),
            ("tool_schema_chars", "tool_schema_chars"),
            ("non_message_prompt_tokens_estimate", "non_message_prompt_tokens_estimate"),
        ):
            group[target] += int(row[source] or 0)
        if row["non_message_prompt_tokens_estimate"] is not None:
            group["non_message_estimate_samples"] += 1
    loops = []
    for group in loop_groups.values():
        count = group["calls"]
        averages = {
            f"avg_{field}": round(group[field] / count) for field in (
                "prompt_tokens", "request_chars", "system_chars", "assistant_chars",
                "tool_result_chars", "tool_schema_chars",
            )
        }
        samples = group["non_message_estimate_samples"]
        averages["avg_non_message_prompt_tokens_estimate"] = (
            round(group["non_message_prompt_tokens_estimate"] / samples) if samples else None
        )
        loops.append({
            "loop": group["loop"],
            "calls": count,
            "non_message_estimate_samples": samples,
            **averages,
        })
    loops.sort(key=lambda item: item["loop"])

    auxiliary = query_auxiliary(hermes_state_db, days=days)
    auxiliary_totals = {
        field: sum(int(row.get(field) or 0) for row in auxiliary)
        for field in (
            "calls", "input_tokens", "output_tokens", "cache_read_tokens",
            "cache_write_tokens", "reasoning_tokens",
        )
    }
    return {
        "window_days": max(1, days),
        "coverage": {
            "main_model_requests": "per_api_attempt",
            "tool_calls": "per_call",
            "auxiliary_model_requests": "not_in_this_database; use Hermes session_model_usage aggregates",
        },
        "totals": {
            "calls": len(calls),
            "successful_calls": len(successful),
            "error_calls": sum(1 for row in calls if row["status"] == "error"),
            "pending_calls": sum(1 for row in calls if row["status"] == "started"),
            "retried_attempts": sum(1 for row in calls if int(row["attempt_index"] or 0) > 0),
            "fallback_switches": sum(1 for providers in logical_requests.values() if len(providers) > 1),
            "input_tokens": token_sum("input_tokens"),
            "output_tokens": token_sum("output_tokens"),
            "cache_read_tokens": cache_read,
            "cache_write_tokens": token_sum("cache_write_tokens"),
            "reasoning_tokens": token_sum("reasoning_tokens"),
            "cache_read_ratio": round(cache_read / prompt_tokens, 4) if prompt_tokens else None,
            "p50_latency_ms": percentile(latencies, 0.50),
            "p95_latency_ms": percentile(latencies, 0.95),
            "tool_calls": len(tools),
        },
        "context_chars": context_totals,
        "loops": loops,
        "models": models,
        "tools": tool_summary,
        "auxiliary_totals": auxiliary_totals,
        "auxiliary_models": auxiliary,
    }


def print_human(report: dict[str, Any]) -> None:
    totals = report["totals"]
    print(f"Window: {report['window_days']} day(s)")
    print(
        "Calls: {calls} ({successful_calls} ok, {error_calls} error, {pending_calls} pending)".format(
            **totals
        )
    )
    print(
        f"Tokens: input={totals['input_tokens']:,} output={totals['output_tokens']:,} "
        f"cache_read={totals['cache_read_tokens']:,} cache_write={totals['cache_write_tokens']:,} "
        f"reasoning={totals['reasoning_tokens']:,}"
    )
    print(
        f"Latency: p50={totals['p50_latency_ms']}ms p95={totals['p95_latency_ms']}ms; "
        f"tool_calls={totals['tool_calls']}; retried_attempts={totals['retried_attempts']}; "
        f"fallback_switches={totals['fallback_switches']}"
    )
    context = report["context_chars"]
    print(
        "Context chars: "
        f"system={context['system_chars']:,} assistant={context['assistant_chars']:,} "
        f"tool_results={context['tool_result_chars']:,} tool_schema={context['tool_schema_chars']:,}"
    )
    print("\nModels:")
    for item in report["models"][:10]:
        print(
            f"  {item['provider']}/{item['model']}: calls={item['calls']} errors={item['errors']} "
            f"input={item['input_tokens']:,} output={item['output_tokens']:,} "
            f"cache_read={item['cache_read_tokens']:,}"
        )
    print("\nTools:")
    for item in report["tools"][:10]:
        print(
            f"  {item['tool_name']}: calls={item['calls']} errors={item['errors']} "
            f"p95={item['p95_latency_ms']}ms avg_result_chars={item['avg_result_chars']:,}"
        )
    if report["loops"]:
        print("\nLoop growth:")
        for item in report["loops"][:15]:
            non_message = item["avg_non_message_prompt_tokens_estimate"]
            non_message_label = f"{non_message:,}" if non_message is not None else "n/a"
            print(
                f"  loop={item['loop']} calls={item['calls']} "
                f"avg_prompt_tokens={item['avg_prompt_tokens']:,} "
                f"avg_tool_result_chars={item['avg_tool_result_chars']:,} "
                f"avg_tool_schema_chars={item['avg_tool_schema_chars']:,} "
                f"avg_non_message_tokens≈{non_message_label}"
            )
    if report["auxiliary_models"]:
        print("\nAuxiliary models (Hermes aggregate accounting):")
        for item in report["auxiliary_models"][:10]:
            print(
                f"  {item['task']} {item['provider']}/{item['model']}: calls={item['calls']} "
                f"input={item['input_tokens']:,} output={item['output_tokens']:,}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=default_db_path())
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument(
        "--hermes-state-db",
        type=Path,
        default=Path(os.getenv("HERMES_HOME", "~/.hermes")).expanduser() / "state.db",
        help="Hermes state.db used for aggregate-only auxiliary model usage",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    if not args.db.exists():
        parser.error(f"database does not exist: {args.db}")
    connection = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        report = query_report(connection, days=args.days, hermes_state_db=args.hermes_state_db)
    finally:
        connection.close()
    if args.as_json:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
