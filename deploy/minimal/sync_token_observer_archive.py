#!/usr/bin/env python3
"""Build the deterministic Token Observer archive."""

from __future__ import annotations

import argparse
import ast
import base64
import gzip
import io
import tarfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parents[1]
SOURCE_DIR = REPOSITORY_ROOT / "hermes-plugins" / "observability" / "token_observer"
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


def archive_bytes() -> bytes:
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
    return buffer.getvalue()


def archive_base64() -> str:
    return base64.b64encode(archive_bytes()).decode("ascii")


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the generated archive")
    parser.add_argument("--output", type=Path, help="write the archive to this path")
    args = parser.parse_args()

    payload = archive_bytes()
    verify_archive(base64.b64encode(payload).decode("ascii"))
    if args.output:
        args.output.write_bytes(payload)
    if args.check:
        print("token-observer-archive-ok")
    if not (args.output or args.check):
        parser.error("specify --output or --check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
