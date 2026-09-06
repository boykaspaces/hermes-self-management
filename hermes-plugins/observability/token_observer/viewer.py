#!/usr/bin/env python3
"""Local-only, read-only web viewer for Token Observer metrics."""

from __future__ import annotations

import argparse
import ipaddress
import json
import logging
import os
import sqlite3
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

try:
    from .report import default_db_path, query_agent_runs, query_recent_calls, query_report
except ImportError:
    from report import default_db_path, query_agent_runs, query_recent_calls, query_report


LOGGER = logging.getLogger("token_observer.viewer")
PLUGIN_DIR = Path(__file__).resolve().parent
WEB_ROOT = PLUGIN_DIR / "web"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


def _bounded_integer(
    query: dict[str, list[str]], name: str, default: int, minimum: int, maximum: int
) -> int:
    raw = query.get(name, [str(default)])[0]
    try:
        value = int(raw)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be an integer") from error
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


class ViewerApplication:
    def __init__(self, db_path: Path, state_db: Path | None, web_root: Path = WEB_ROOT):
        self.db_path = db_path
        self.state_db = state_db
        self.web_root = web_root

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            f"file:{self.db_path.resolve()}?mode=ro", uri=True, timeout=5.0
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def health(self) -> dict[str, str]:
        with self.connect() as connection:
            connection.execute("SELECT 1").fetchone()
        return {"status": "ok"}

    def report(self, *, days: int) -> dict[str, Any]:
        with self.connect() as connection:
            return query_report(connection, days=days, hermes_state_db=self.state_db)

    def calls(
        self, *, days: int, limit: int, before_id: int | None
    ) -> dict[str, Any]:
        with self.connect() as connection:
            return query_recent_calls(
                connection, days=days, limit=limit, before_id=before_id
            )

    def runs(self, *, days: int, limit: int) -> dict[str, Any]:
        with self.connect() as connection:
            return query_agent_runs(connection, days=days, limit=limit)


class ViewerServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], application: ViewerApplication):
        self.application = application
        super().__init__(address, ViewerRequestHandler)


class ViewerRequestHandler(BaseHTTPRequestHandler):
    server: ViewerServer
    server_version = "TokenObserverViewer/0.1"
    sys_version = ""

    def log_message(self, message: str, *args: Any) -> None:
        LOGGER.info("%s %s", self.address_string(), message % args)

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'none'",
        )

    def _send_bytes(
        self, status: HTTPStatus, body: bytes, content_type: str, *, cache: str = "no-store"
    ) -> None:
        self.send_response(status)
        self._security_headers()
        self.send_header("Cache-Control", cache)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: HTTPStatus, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._send_json(status, {"error": message})

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query, keep_blank_values=True)
        try:
            if parsed.path == "/healthz":
                self._send_json(HTTPStatus.OK, self.server.application.health())
                return
            if parsed.path == "/api/report":
                days = _bounded_integer(query, "days", 7, 1, 365)
                self._send_json(
                    HTTPStatus.OK, self.server.application.report(days=days)
                )
                return
            if parsed.path == "/api/calls":
                days = _bounded_integer(query, "days", 7, 1, 365)
                limit = _bounded_integer(query, "limit", 50, 1, 200)
                cursor_raw = query.get("cursor", [""])[0]
                before_id = None
                if cursor_raw:
                    try:
                        before_id = max(1, int(cursor_raw))
                    except ValueError as error:
                        raise ValueError("cursor must be an integer") from error
                self._send_json(
                    HTTPStatus.OK,
                    self.server.application.calls(
                        days=days, limit=limit, before_id=before_id
                    ),
                )
                return
            if parsed.path == "/api/runs":
                days = _bounded_integer(query, "days", 7, 1, 365)
                limit = _bounded_integer(query, "limit", 25, 1, 100)
                self._send_json(
                    HTTPStatus.OK,
                    self.server.application.runs(days=days, limit=limit),
                )
                return
            static = STATIC_FILES.get(parsed.path)
            if static:
                filename, content_type = static
                body = (self.server.application.web_root / filename).read_bytes()
                self._send_bytes(
                    HTTPStatus.OK, body, content_type, cache="no-cache, max-age=0"
                )
                return
            self._error(HTTPStatus.NOT_FOUND, "not found")
        except ValueError as error:
            self._error(HTTPStatus.BAD_REQUEST, str(error))
        except FileNotFoundError:
            self._error(HTTPStatus.SERVICE_UNAVAILABLE, "viewer assets unavailable")
        except sqlite3.Error:
            LOGGER.exception("database query failed")
            self._error(HTTPStatus.SERVICE_UNAVAILABLE, "metrics database unavailable")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9120)
    parser.add_argument("--db", type=Path, default=default_db_path())
    parser.add_argument(
        "--state-db",
        type=Path,
        default=Path(os.getenv("HERMES_HOME", "~/.hermes")).expanduser() / "state.db",
    )
    arguments = parser.parse_args(argv)
    try:
        address = ipaddress.ip_address(arguments.host)
    except ValueError as error:
        parser.error(f"--host must be a loopback IP address: {error}")
    if not address.is_loopback:
        parser.error("--host must be a loopback IP address")
    if not 1 <= arguments.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if not arguments.db.exists():
        parser.error(f"database does not exist: {arguments.db}")
    return arguments


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    state_db = arguments.state_db if arguments.state_db.exists() else None
    server = ViewerServer(
        (arguments.host, arguments.port),
        ViewerApplication(arguments.db, state_db),
    )
    LOGGER.info("listening on http://%s:%s", arguments.host, arguments.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
