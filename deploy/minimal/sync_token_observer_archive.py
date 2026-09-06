#!/usr/bin/env python3
"""Embed a deterministic token-observer archive in cloudformation.yaml."""

from __future__ import annotations

import argparse
import ast
import base64
import gzip
import io
import tarfile
import textwrap
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parents[1]
SOURCE_DIR = REPOSITORY_ROOT / "hermes-plugins" / "observability" / "token_observer"
TEMPLATE = SCRIPT_DIR / "cloudformation.yaml"
BEGIN = "      # TOKEN_OBSERVER_ARCHIVE_BEGIN\n"
END = "      # TOKEN_OBSERVER_ARCHIVE_END\n"
INCLUDED_FILES = (
    "plugin.yaml",
    "__init__.py",
    "observer.py",
    "runtime_instrumentation.py",
    "report.py",
    "viewer.py",
    "hermes-token-observer-viewer.service",
    "web/index.html",
    "web/app.js",
    "web/style.css",
)


class _DocstringStripper(ast.NodeTransformer):
    """Keep the embedded artifact small while retaining readable source in git."""

    def _strip(self, node):
        self.generic_visit(node)
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            node.body.pop(0)
        return node

    visit_Module = _strip
    visit_ClassDef = _strip
    visit_FunctionDef = _strip
    visit_AsyncFunctionDef = _strip


def deploy_bytes(source: Path) -> bytes:
    data = source.read_bytes()
    if source.suffix != ".py":
        return data
    tree = ast.parse(data, filename=str(source))
    tree = _DocstringStripper().visit(tree)
    ast.fix_missing_locations(tree)
    return (ast.unparse(tree) + "\n").encode("utf-8")


def archive_base64() -> str:
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0, filename="") as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for filename in INCLUDED_FILES:
                source = SOURCE_DIR / filename
                data = deploy_bytes(source)
                member = tarfile.TarInfo(f"token_observer/{filename}")
                member.size = len(data)
                member.mode = 0o755 if filename in {"report.py", "viewer.py"} else 0o644
                member.mtime = 0
                member.uid = member.gid = 0
                member.uname = member.gname = ""
                archive.addfile(member, io.BytesIO(data))
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def verify_archive(encoded: str) -> None:
    payload = base64.b64decode(encoded, validate=True)
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        names = set(archive.getnames())
        expected = {f"token_observer/{name}" for name in INCLUDED_FILES}
        if names != expected:
            raise SystemExit(f"unexpected archive members: {sorted(names ^ expected)}")
        for member in archive.getmembers():
            extracted = archive.extractfile(member)
            if extracted is None:
                raise SystemExit(f"archive member is not a regular file: {member.name}")
            data = extracted.read()
            if member.name.endswith(".py"):
                compile(data, member.name, "exec")


def rendered_block() -> str:
    encoded = archive_base64()
    verify_archive(encoded)
    wrapped = textwrap.wrap(encoded, width=100)
    lines = [BEGIN, "      TokenObserverArchive: |\n"]
    lines.extend(f"        {line}\n" for line in wrapped)
    lines.append(END)
    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the embedded archive is stale")
    args = parser.parse_args()

    current = TEMPLATE.read_text(encoding="utf-8")
    try:
        prefix, remainder = current.split(BEGIN, 1)
        _old, suffix = remainder.split(END, 1)
    except ValueError as error:
        raise SystemExit("token observer archive markers are missing or duplicated") from error
    expected = prefix + rendered_block() + suffix
    if args.check:
        if current != expected:
            raise SystemExit("embedded token observer archive is stale; run sync_token_observer_archive.py")
        print("token-observer-archive-ok")
        return 0
    TEMPLATE.write_text(expected, encoding="utf-8")
    print("token-observer-archive-updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
