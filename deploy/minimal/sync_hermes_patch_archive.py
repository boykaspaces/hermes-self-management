#!/usr/bin/env python3
"""Build the deterministic, version-pinned Hermes source patch archive."""

from __future__ import annotations

import argparse
import base64
import gzip
import io
import tarfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PATCH_SET = "hermes-v0.21.0-29112bef"
INCLUDED_FILES = (
    "apply-hermes-patches.sh",
    f"patches/{PATCH_SET}/commit.txt",
    f"patches/{PATCH_SET}/P-002-browser-private-url.patch",
    f"patches/{PATCH_SET}/P-003-podman-reuse.patch",
    f"patches/{PATCH_SET}/P-005-egress-allowlist-only.patch",
    f"patches/{PATCH_SET}/PATCHED_SHA256SUMS",
)


def archive_bytes() -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0, filename="") as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for filename in INCLUDED_FILES:
                source = SCRIPT_DIR / filename
                data = source.read_bytes()
                member = tarfile.TarInfo(f"managed-patches/{filename}")
                member.size = len(data)
                member.mode = 0o755 if filename.endswith(".sh") else 0o644
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
        expected = {f"managed-patches/{name}" for name in INCLUDED_FILES}
        if set(archive.getnames()) != expected:
            raise SystemExit("managed Hermes patch archive members do not match the allowlist")
        for member in archive.getmembers():
            if not member.isfile():
                raise SystemExit(f"archive member is not a regular file: {member.name}")


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
        print("hermes-patch-archive-ok")
    if not (args.output or args.check):
        parser.error("specify --output or --check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
