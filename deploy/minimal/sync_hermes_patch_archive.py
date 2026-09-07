#!/usr/bin/env python3
"""Embed the version-pinned Hermes source patch bundle in cloudformation.yaml."""

from __future__ import annotations

import argparse
import base64
import gzip
import io
import tarfile
import textwrap
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE = SCRIPT_DIR / "cloudformation.yaml"
BEGIN = "      # HERMES_PATCH_ARCHIVE_BEGIN\n"
END = "      # HERMES_PATCH_ARCHIVE_END\n"
PATCH_SET = "hermes-v0.21.0-29112bef"
INCLUDED_FILES = (
    "apply-hermes-patches.sh",
    f"patches/{PATCH_SET}/commit.txt",
    f"patches/{PATCH_SET}/P-002-browser-private-url.patch",
    f"patches/{PATCH_SET}/P-003-podman-reuse.patch",
    f"patches/{PATCH_SET}/P-005-egress-allowlist-only.patch",
    f"patches/{PATCH_SET}/PATCHED_SHA256SUMS",
)


def archive_base64() -> str:
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
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def verify_archive(encoded: str) -> None:
    payload = base64.b64decode(encoded, validate=True)
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        expected = {f"managed-patches/{name}" for name in INCLUDED_FILES}
        if set(archive.getnames()) != expected:
            raise SystemExit("managed Hermes patch archive members do not match the allowlist")
        for member in archive.getmembers():
            if not member.isfile():
                raise SystemExit(f"archive member is not a regular file: {member.name}")


def rendered_block() -> str:
    encoded = archive_base64()
    verify_archive(encoded)
    lines = [BEGIN, "      ManagedHermesPatchArchive: |\n"]
    lines.extend(f"        {line}\n" for line in textwrap.wrap(encoded, width=100))
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
        raise SystemExit("managed Hermes patch archive markers are missing or duplicated") from error
    expected = prefix + rendered_block() + suffix
    if args.check:
        if current != expected:
            raise SystemExit("embedded Hermes patch archive is stale; run sync_hermes_patch_archive.py")
        print("hermes-patch-archive-ok")
        return 0
    TEMPLATE.write_text(expected, encoding="utf-8")
    print("hermes-patch-archive-updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
