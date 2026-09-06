"""Privacy-safe, provider-neutral token and tool-call observability.

Only dimensions and sizes are persisted. Prompt text, message content, tool
arguments/results, URLs, and provider error messages are never written.
"""

from __future__ import annotations

import atexit
import hashlib
import hmac
import logging
import os
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Mapping, Sequence


LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = 3
DEFAULT_RETENTION_DAYS = 30

PROMPT_COMPONENT_TYPES = {
    "base_system",
    "context",
    "skills",
    "memory",
    "volatile",
    "runtime",
    "ephemeral_context",
}


def _non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if number >= 0 else None


def _safe_identifier(value: Any, *, maximum: int = 255) -> str:
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if not value:
        return ""
    return value[:maximum]


def _json_size(value: Any, *, depth: int = 0) -> int:
    """Estimate compact JSON characters without materializing content copies."""
    if depth > 32:
        return 0
    if value is None:
        return 4
    if isinstance(value, bool):
        return 4 if value else 5
    if isinstance(value, str):
        return len(value) + 2
    if isinstance(value, (bytes, bytearray)):
        return len(value) + 2
    if isinstance(value, Mapping):
        # Braces, one colon per entry, and commas between entries.
        return 2 + max(0, len(value) - 1) + sum(
            _json_size(str(key), depth=depth + 1)
            + 1
            + _json_size(item, depth=depth + 1)
            for key, item in value.items()
        )
    if isinstance(value, Sequence):
        return 2 + max(0, len(value) - 1) + sum(
            _json_size(item, depth=depth + 1) for item in value
        )
    if isinstance(value, (int, float)):
        return len(str(value))
    # Avoid invoking arbitrary __str__ implementations on provider objects.
    return len(type(value).__name__) + 2


def _message_role(message: Any) -> str:
    if isinstance(message, Mapping):
        return str(message.get("role") or "other").strip().lower()
    role = getattr(message, "role", None)
    return str(role or "other").strip().lower()


def _contains_tool_result(message: Any) -> bool:
    if _message_role(message) in {"tool", "function"}:
        return True
    if not isinstance(message, Mapping):
        return False
    content = message.get("content")
    if not isinstance(content, Sequence) or isinstance(content, (str, bytes, bytearray)):
        return False
    return any(
        isinstance(block, Mapping)
        and str(block.get("type") or "").lower() in {"tool_result", "function_call_output"}
        for block in content
    )


def _request_body(request: Any) -> Mapping[str, Any]:
    if not isinstance(request, Mapping):
        return {}
    body = request.get("body")
    return body if isinstance(body, Mapping) else request


def context_sizes(event: Mapping[str, Any]) -> dict[str, int]:
    """Calculate non-content request composition metrics.

    ``request_messages`` is used only in memory for complete size accounting;
    none of its values are persisted. The sanitized ``request`` payload is the
    fallback and the source for provider-specific system/tool fields.
    """
    body = _request_body(event.get("request"))
    messages = event.get("request_messages")
    if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes, bytearray)):
        messages = body.get("messages") or body.get("input") or []
    if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes, bytearray)):
        messages = []

    sizes = {
        "system_chars": 0,
        "user_chars": 0,
        "assistant_chars": 0,
        "tool_result_chars": 0,
        "other_message_chars": 0,
        "tool_schema_chars": 0,
    }
    for message in messages:
        size = _json_size(message)
        role = _message_role(message)
        if _contains_tool_result(message):
            sizes["tool_result_chars"] += size
        elif role == "system":
            sizes["system_chars"] += size
        elif role == "user":
            sizes["user_chars"] += size
        elif role == "assistant":
            sizes["assistant_chars"] += size
        else:
            sizes["other_message_chars"] += size

    # Anthropic/Bedrock commonly carry system instructions outside messages.
    if body.get("system") is not None and not any(
        _message_role(message) == "system" for message in messages
    ):
        sizes["system_chars"] += _json_size(body.get("system"))

    tools = body.get("tools")
    if tools is None:
        tools = body.get("functions")
    if tools is not None:
        sizes["tool_schema_chars"] = _json_size(tools)
    return sizes


def prompt_component_rows(
    event: Mapping[str, Any], dimensions: Mapping[str, int]
) -> list[tuple[str, str, int, int]]:
    """Return size-only prompt component rows from enriched or legacy hooks."""
    request = event.get("request")
    observer_metadata = (
        request.get("_token_observer") if isinstance(request, Mapping) else None
    )
    if not isinstance(observer_metadata, Mapping):
        observer_metadata = {}

    rows: list[tuple[str, str, int, int]] = []
    runtime_components = observer_metadata.get("prompt_components")
    has_runtime_components = isinstance(runtime_components, Mapping)
    if has_runtime_components:
        for component_type in PROMPT_COMPONENT_TYPES:
            chars = _non_negative_int(runtime_components.get(component_type))
            if chars:
                rows.append((component_type, "", chars, 1))
    elif dimensions.get("system_chars"):
        rows.append(("system", "combined", int(dimensions["system_chars"]), 1))

    for component_type, field in (
        ("user_messages", "user_chars"),
        ("assistant_history", "assistant_chars"),
        ("tool_results", "tool_result_chars"),
        ("other_history", "other_message_chars"),
    ):
        chars = int(dimensions.get(field) or 0)
        if chars:
            rows.append((component_type, "", chars, 1))

    tool_components = observer_metadata.get("tool_components")
    if isinstance(tool_components, Sequence) and not isinstance(
        tool_components, (str, bytes, bytearray)
    ):
        merged: dict[tuple[str, str], tuple[int, int]] = {}
        for item in tool_components:
            if not isinstance(item, Mapping):
                continue
            name = _safe_identifier(item.get("name"), maximum=255) or "unknown"
            chars = _non_negative_int(item.get("chars"))
            if not chars:
                continue
            component_type = "mcp_schema" if name.startswith("mcp__") else "tool_schema"
            key = (component_type, name)
            previous_chars, previous_count = merged.get(key, (0, 0))
            merged[key] = (previous_chars + chars, previous_count + 1)
        rows.extend(
            (component_type, name, chars, count)
            for (component_type, name), (chars, count) in merged.items()
        )
    elif dimensions.get("tool_schema_chars"):
        rows.append(("tool_schema", "combined", int(dimensions["tool_schema_chars"]), 1))
    return rows


def normalize_usage(usage: Any) -> dict[str, int | None]:
    """Normalize Hermes CanonicalUsage summaries and common provider shapes."""
    if not isinstance(usage, Mapping):
        return {
            "input_tokens": None,
            "output_tokens": None,
            "cache_read_tokens": None,
            "cache_write_tokens": None,
            "reasoning_tokens": None,
        }

    def first(*keys: str) -> int | None:
        for key in keys:
            if key in usage:
                value = _non_negative_int(usage.get(key))
                if value is not None:
                    return value
        return None

    cache_read = first("cache_read_tokens", "cache_read_input_tokens", "cached_tokens")
    cache_write = first(
        "cache_write_tokens", "cache_creation_input_tokens", "cache_creation_tokens"
    )
    input_tokens = first("input_tokens")
    if input_tokens is None:
        prompt_total = first("prompt_tokens")
        if prompt_total is not None:
            # OpenAI-style prompt totals include cached input. Hermes's
            # canonical summary does not, so keep the database contract stable.
            input_tokens = max(0, prompt_total - (cache_read or 0) - (cache_write or 0))
    return {
        "input_tokens": input_tokens,
        "output_tokens": first("output_tokens", "completion_tokens"),
        "cache_read_tokens": cache_read,
        "cache_write_tokens": cache_write,
        "reasoning_tokens": first("reasoning_tokens"),
    }


class ObserverStore:
    """Small, thread-safe SQLite store with process-safe WAL locking."""

    def __init__(self, db_path: Path, *, retention_days: int = DEFAULT_RETENTION_DAYS):
        self.db_path = db_path
        self.retention_days = max(1, retention_days)
        self._lock = threading.RLock()
        self._connection: sqlite3.Connection | None = None
        self._last_prune = 0.0
        self._active_calls: dict[tuple[str, str], int] = {}
        self._salt = self._load_or_create_salt()
        self._connect()
        self._initialize_schema()
        self.prune_if_due(force=True)

    def _load_or_create_salt(self) -> bytes:
        self.db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.db_path.parent, 0o700)
        except OSError:
            pass
        salt_path = self.db_path.with_suffix(self.db_path.suffix + ".salt")
        try:
            return salt_path.read_bytes()
        except FileNotFoundError:
            salt = secrets.token_bytes(32)
            try:
                descriptor = os.open(
                    salt_path,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
            except FileExistsError:
                return salt_path.read_bytes()
            with os.fdopen(descriptor, "wb") as target:
                target.write(salt)
            return salt

    def _connect(self) -> sqlite3.Connection:
        if self._connection is None:
            connection = sqlite3.connect(
                self.db_path,
                timeout=5.0,
                check_same_thread=False,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("PRAGMA busy_timeout=5000")
            connection.execute("PRAGMA foreign_keys=ON")
            self._connection = connection
            try:
                os.chmod(self.db_path, 0o600)
            except OSError:
                pass
        return self._connection

    def _initialize_schema(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ai_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_request_key TEXT NOT NULL,
            attempt_index INTEGER NOT NULL,
            session_key TEXT NOT NULL,
            task_key TEXT NOT NULL,
            turn_key TEXT NOT NULL,
            platform TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            response_model TEXT NOT NULL DEFAULT '',
            api_mode TEXT NOT NULL,
            api_call_count INTEGER,
            retry_count INTEGER,
            started_at REAL NOT NULL,
            ended_at REAL,
            latency_ms INTEGER,
            status TEXT NOT NULL,
            finish_reason TEXT NOT NULL DEFAULT '',
            http_status INTEGER,
            error_type TEXT NOT NULL DEFAULT '',
            retryable INTEGER,
            message_count INTEGER,
            tool_count INTEGER,
            approx_input_tokens INTEGER,
            request_char_count INTEGER,
            max_output_tokens INTEGER,
            system_chars INTEGER NOT NULL DEFAULT 0,
            system_chars_inferred INTEGER NOT NULL DEFAULT 0,
            user_chars INTEGER NOT NULL DEFAULT 0,
            assistant_chars INTEGER NOT NULL DEFAULT 0,
            tool_result_chars INTEGER NOT NULL DEFAULT 0,
            other_message_chars INTEGER NOT NULL DEFAULT 0,
            tool_schema_chars INTEGER NOT NULL DEFAULT 0,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cache_read_tokens INTEGER,
            cache_write_tokens INTEGER,
            reasoning_tokens INTEGER,
            non_message_prompt_tokens_estimate INTEGER,
            assistant_content_chars INTEGER,
            assistant_tool_call_count INTEGER,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            UNIQUE(api_request_key, attempt_index)
        );

        CREATE INDEX IF NOT EXISTS idx_ai_calls_started_at ON ai_calls(started_at);
        CREATE INDEX IF NOT EXISTS idx_ai_calls_session ON ai_calls(session_key, started_at);
        CREATE INDEX IF NOT EXISTS idx_ai_calls_model ON ai_calls(provider, model, started_at);

        CREATE TABLE IF NOT EXISTS tool_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            occurred_at REAL NOT NULL,
            session_key TEXT NOT NULL,
            task_key TEXT NOT NULL,
            turn_key TEXT NOT NULL,
            api_request_key TEXT NOT NULL,
            tool_call_key TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            status TEXT NOT NULL,
            error_type TEXT NOT NULL DEFAULT '',
            duration_ms INTEGER,
            args_chars INTEGER NOT NULL,
            args_key_count INTEGER NOT NULL,
            result_chars INTEGER NOT NULL,
            created_at REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_tool_calls_occurred_at ON tool_calls(occurred_at);
        CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls(session_key, occurred_at);
        CREATE INDEX IF NOT EXISTS idx_tool_calls_name ON tool_calls(tool_name, occurred_at);

        CREATE TABLE IF NOT EXISTS prompt_components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ai_call_id INTEGER NOT NULL REFERENCES ai_calls(id) ON DELETE CASCADE,
            component_type TEXT NOT NULL,
            component_name TEXT NOT NULL DEFAULT '',
            char_count INTEGER NOT NULL,
            item_count INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL,
            UNIQUE(ai_call_id, component_type, component_name)
        );

        CREATE INDEX IF NOT EXISTS idx_prompt_components_call
            ON prompt_components(ai_call_id);
        """
        with self._lock:
            connection = self._connect()
            connection.executescript(schema)
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(ai_calls)")
            }
            if "system_chars_inferred" not in columns:
                connection.execute(
                    "ALTER TABLE ai_calls ADD COLUMN system_chars_inferred INTEGER NOT NULL DEFAULT 0"
                )
            if "non_message_prompt_tokens_estimate" not in columns:
                connection.execute(
                    "ALTER TABLE ai_calls ADD COLUMN non_message_prompt_tokens_estimate INTEGER"
                )
            # Backfill rows written by schema v1. Both calculations retain an
            # explicit estimate marker and never reconstruct message content.
            connection.execute(
                """
                UPDATE ai_calls
                SET system_chars = request_char_count - user_chars - assistant_chars
                    - tool_result_chars - other_message_chars,
                    system_chars_inferred = 1
                WHERE system_chars = 0
                  AND request_char_count IS NOT NULL
                  AND request_char_count > user_chars + assistant_chars
                      + tool_result_chars + other_message_chars
                """
            )
            connection.execute(
                """
                UPDATE ai_calls
                SET non_message_prompt_tokens_estimate = MAX(
                    0,
                    COALESCE(input_tokens, 0) + COALESCE(cache_read_tokens, 0)
                      + COALESCE(cache_write_tokens, 0) - approx_input_tokens
                )
                WHERE non_message_prompt_tokens_estimate IS NULL
                  AND approx_input_tokens IS NOT NULL
                  AND input_tokens IS NOT NULL
                """
            )
            connection.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            connection.commit()

    def pseudonym(self, value: Any) -> str:
        raw = str(value or "").encode("utf-8", errors="replace")
        if not raw:
            return ""
        return hmac.new(self._salt, raw, hashlib.sha256).hexdigest()[:24]

    def _identity(self, event: Mapping[str, Any]) -> tuple[str, str, str]:
        return (
            self.pseudonym(event.get("session_id")),
            self.pseudonym(event.get("task_id")),
            self.pseudonym(event.get("turn_id")),
        )

    def begin_call(self, event: Mapping[str, Any]) -> None:
        request_id = _safe_identifier(event.get("api_request_id"), maximum=512) or "anonymous"
        request_key = self.pseudonym(request_id)
        session_key, task_key, turn_key = self._identity(event)
        started_at = float(event.get("started_at") or time.time())
        dimensions = context_sizes(event)
        request_char_count = _non_negative_int(event.get("request_char_count"))
        system_chars_inferred = 0
        if not dimensions["system_chars"] and request_char_count:
            attributed = sum(
                dimensions[field]
                for field in (
                    "user_chars", "assistant_chars", "tool_result_chars", "other_message_chars"
                )
            )
            if request_char_count > attributed:
                # Bedrock extracts system messages before the hook's legacy
                # request_messages field, and large sanitized payloads can be
                # truncated. Hermes's request_char_count remains available as
                # a rough whole-message measure, so preserve the unattributed
                # remainder and mark it explicitly as inferred.
                dimensions["system_chars"] = request_char_count - attributed
                system_chars_inferred = 1
        with self._lock:
            connection = self._connect()
            row = connection.execute(
                "SELECT COALESCE(MAX(attempt_index), -1) + 1 FROM ai_calls WHERE api_request_key = ?",
                (request_key,),
            ).fetchone()
            attempt_index = int(row[0])
            cursor = connection.execute(
                """
                INSERT INTO ai_calls (
                    api_request_key, attempt_index, session_key, task_key, turn_key,
                    platform, provider, model, api_mode, api_call_count, retry_count,
                    started_at, status, message_count, tool_count, approx_input_tokens,
                    request_char_count, max_output_tokens, system_chars, system_chars_inferred, user_chars,
                    assistant_chars, tool_result_chars, other_message_chars,
                    tool_schema_chars, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'started', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_key,
                    attempt_index,
                    session_key,
                    task_key,
                    turn_key,
                    _safe_identifier(event.get("platform"), maximum=64),
                    _safe_identifier(event.get("provider"), maximum=128),
                    _safe_identifier(event.get("model")),
                    _safe_identifier(event.get("api_mode"), maximum=128),
                    _non_negative_int(event.get("api_call_count")),
                    _non_negative_int(event.get("retry_count")),
                    started_at,
                    _non_negative_int(event.get("message_count")),
                    _non_negative_int(event.get("tool_count")),
                    _non_negative_int(event.get("approx_input_tokens")),
                    request_char_count,
                    _non_negative_int(event.get("max_tokens")),
                    dimensions["system_chars"],
                    system_chars_inferred,
                    dimensions["user_chars"],
                    dimensions["assistant_chars"],
                    dimensions["tool_result_chars"],
                    dimensions["other_message_chars"],
                    dimensions["tool_schema_chars"],
                    time.time(),
                    time.time(),
                ),
            )
            call_id = int(cursor.lastrowid)
            for component_type, component_name, char_count, item_count in prompt_component_rows(
                event, dimensions
            ):
                connection.execute(
                    """
                    INSERT OR REPLACE INTO prompt_components (
                        ai_call_id, component_type, component_name, char_count,
                        item_count, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        call_id,
                        component_type,
                        component_name,
                        char_count,
                        item_count,
                        time.time(),
                    ),
                )
            self._active_calls[(session_key, request_id)] = call_id
            connection.commit()
        self.prune_if_due()

    def _active_call_id(self, event: Mapping[str, Any]) -> int | None:
        request_id = _safe_identifier(event.get("api_request_id"), maximum=512) or "anonymous"
        session_key = self.pseudonym(event.get("session_id"))
        row_id = self._active_calls.get((session_key, request_id))
        if row_id is not None:
            return row_id
        row = self._connect().execute(
            """
            SELECT id FROM ai_calls
            WHERE api_request_key = ? AND session_key = ? AND status = 'started'
            ORDER BY id DESC LIMIT 1
            """,
            (self.pseudonym(request_id), session_key),
        ).fetchone()
        return int(row[0]) if row else None

    def finish_call(self, event: Mapping[str, Any], *, status: str) -> None:
        usage = normalize_usage(event.get("usage"))
        ended_at = float(event.get("ended_at") or time.time())
        duration = event.get("api_duration")
        try:
            latency_ms = max(0, round(float(duration) * 1000)) if duration is not None else None
        except (TypeError, ValueError, OverflowError):
            latency_ms = None
        error = event.get("error") if isinstance(event.get("error"), Mapping) else {}
        error_type = _safe_identifier(
            event.get("error_type") or error.get("type"), maximum=128
        )
        request_id = _safe_identifier(event.get("api_request_id"), maximum=512) or "anonymous"
        session_key = self.pseudonym(event.get("session_id"))
        with self._lock:
            connection = self._connect()
            row_id = self._active_call_id(event)
            if row_id is None:
                # Terminal-only events are retained rather than silently lost.
                self.begin_call({**event, "started_at": event.get("started_at") or ended_at})
                row_id = self._active_call_id(event)
            if row_id is None:
                return
            current = connection.execute(
                "SELECT approx_input_tokens FROM ai_calls WHERE id = ?", (row_id,)
            ).fetchone()
            approx_messages = _non_negative_int(current[0]) if current else None
            prompt_tokens = sum(
                int(usage[field] or 0)
                for field in ("input_tokens", "cache_read_tokens", "cache_write_tokens")
            )
            non_message_estimate = (
                max(0, prompt_tokens - approx_messages)
                if approx_messages is not None and prompt_tokens
                else None
            )
            connection.execute(
                """
                UPDATE ai_calls SET
                    ended_at = ?, latency_ms = ?, status = ?, finish_reason = ?,
                    response_model = ?, http_status = ?, error_type = ?, retryable = ?,
                    retry_count = COALESCE(?, retry_count), input_tokens = ?,
                    output_tokens = ?, cache_read_tokens = ?, cache_write_tokens = ?,
                    reasoning_tokens = ?, non_message_prompt_tokens_estimate = ?, assistant_content_chars = ?,
                    assistant_tool_call_count = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    ended_at,
                    latency_ms,
                    status,
                    _safe_identifier(event.get("finish_reason"), maximum=128),
                    _safe_identifier(event.get("response_model")),
                    _non_negative_int(event.get("status_code")),
                    error_type,
                    int(bool(event.get("retryable"))) if event.get("retryable") is not None else None,
                    _non_negative_int(event.get("retry_count")),
                    usage["input_tokens"],
                    usage["output_tokens"],
                    usage["cache_read_tokens"],
                    usage["cache_write_tokens"],
                    usage["reasoning_tokens"],
                    non_message_estimate,
                    _non_negative_int(event.get("assistant_content_chars")),
                    _non_negative_int(event.get("assistant_tool_call_count")),
                    time.time(),
                    row_id,
                ),
            )
            self._active_calls.pop((session_key, request_id), None)
            connection.commit()

    def record_tool_call(self, event: Mapping[str, Any]) -> None:
        session_key, task_key, turn_key = self._identity(event)
        args = event.get("args")
        args_key_count = len(args) if isinstance(args, Mapping) else 0
        now = time.time()
        result = event.get("result")
        duration_ms = _non_negative_int(event.get("duration_ms"))
        tool_call_id = _safe_identifier(event.get("tool_call_id"), maximum=512)
        if tool_call_id:
            tool_call_key = self.pseudonym(tool_call_id)
        else:
            # No stable provider ID is available on a few cancellation paths.
            tool_call_key = self.pseudonym(f"{task_key}:{turn_key}:{now}:{secrets.token_hex(8)}")
        with self._lock:
            connection = self._connect()
            connection.execute(
                """
                INSERT INTO tool_calls (
                    occurred_at, session_key, task_key, turn_key, api_request_key,
                    tool_call_key, tool_name, status, error_type, duration_ms,
                    args_chars, args_key_count, result_chars, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    session_key,
                    task_key,
                    turn_key,
                    self.pseudonym(event.get("api_request_id")),
                    tool_call_key,
                    _safe_identifier(event.get("tool_name"), maximum=255) or "unknown",
                    _safe_identifier(event.get("status"), maximum=64) or "unknown",
                    _safe_identifier(event.get("error_type"), maximum=128),
                    duration_ms,
                    _json_size(args),
                    args_key_count,
                    _json_size(result),
                    now,
                ),
            )
            connection.commit()
        self.prune_if_due()

    def prune_if_due(self, *, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_prune < 86400:
            return
        cutoff = now - self.retention_days * 86400
        with self._lock:
            connection = self._connect()
            connection.execute("DELETE FROM ai_calls WHERE started_at < ?", (cutoff,))
            connection.execute("DELETE FROM tool_calls WHERE occurred_at < ?", (cutoff,))
            connection.commit()
            self._last_prune = now

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None


class TokenObserver:
    """Fail-open Hermes hook callbacks."""

    def __init__(self, store: ObserverStore):
        self.store = store

    @staticmethod
    def _safely(callback, event: Mapping[str, Any]) -> None:
        try:
            callback(event)
        except Exception as error:
            # Do not include payloads or provider/tool error messages in logs.
            LOGGER.warning("token observer write failed (%s)", type(error).__name__)

    def on_pre_api_request(self, **kwargs: Any) -> None:
        self._safely(self.store.begin_call, kwargs)

    def on_post_api_request(self, **kwargs: Any) -> None:
        self._safely(lambda event: self.store.finish_call(event, status="ok"), kwargs)

    def on_api_request_error(self, **kwargs: Any) -> None:
        self._safely(lambda event: self.store.finish_call(event, status="error"), kwargs)

    def on_post_tool_call(self, **kwargs: Any) -> None:
        self._safely(self.store.record_tool_call, kwargs)


_OBSERVER: TokenObserver | None = None
_OBSERVER_LOCK = threading.Lock()


def default_db_path() -> Path:
    configured = os.getenv("HERMES_TOKEN_OBSERVER_DB")
    if configured:
        return Path(configured).expanduser()
    hermes_home = Path(os.getenv("HERMES_HOME", "~/.hermes")).expanduser()
    return hermes_home / "observability" / "ai-calls.sqlite3"


def get_observer() -> TokenObserver:
    global _OBSERVER
    with _OBSERVER_LOCK:
        if _OBSERVER is None:
            try:
                retention = int(
                    os.getenv("HERMES_TOKEN_OBSERVER_RETENTION_DAYS", str(DEFAULT_RETENTION_DAYS))
                )
            except ValueError:
                retention = DEFAULT_RETENTION_DAYS
            _OBSERVER = TokenObserver(ObserverStore(default_db_path(), retention_days=retention))
            atexit.register(_OBSERVER.store.close)
        return _OBSERVER
