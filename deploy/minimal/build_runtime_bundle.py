#!/usr/bin/env python3
"""Build the deterministic Hermes runtime bundle consumed by EC2 Metadata."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import tarfile
from pathlib import Path, PurePosixPath

import sync_hermes_patch_archive
import sync_token_observer_archive


SCRIPT_DIR = Path(__file__).resolve().parent
MEMBERS = (
    ("runtime-config.sh", 0o755),
    ("apply_runtime_profile.py", 0o755),
    ("validate_runtime_profile.py", 0o755),
    ("managed-patches.tar.gz", 0o644),
    ("token-observer.tar.gz", 0o644),
)


def member_payloads() -> dict[str, bytes]:
    return {
        "runtime-config.sh": (SCRIPT_DIR / "runtime-config.sh").read_bytes(),
        "apply_runtime_profile.py": (SCRIPT_DIR / "apply_runtime_profile.py").read_bytes(),
        "validate_runtime_profile.py": (
            SCRIPT_DIR / "validate_runtime_profile.py"
        ).read_bytes(),
        "managed-patches.tar.gz": sync_hermes_patch_archive.archive_bytes(),
        "token-observer.tar.gz": sync_token_observer_archive.archive_bytes(),
    }


def bundle_bytes() -> bytes:
    payloads = member_payloads()
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", mtime=0, filename="") as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for name, mode in MEMBERS:
                data = payloads[name]
                member = tarfile.TarInfo(name)
                member.size = len(data)
                member.mode = mode
                member.mtime = 0
                member.uid = member.gid = 0
                member.uname = member.gname = ""
                archive.addfile(member, io.BytesIO(data))
    return output.getvalue()


def verify_bundle(payload: bytes) -> None:
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        members = archive.getmembers()
        expected = {name for name, _mode in MEMBERS}
        if {member.name for member in members} != expected:
            raise SystemExit("runtime bundle members do not match the allowlist")
        for member in members:
            path = PurePosixPath(member.name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not member.isfile()
                or member.issym()
                or member.islnk()
                or member.isdev()
            ):
                raise SystemExit(f"unsafe runtime bundle member: {member.name}")
            extracted = archive.extractfile(member)
            if extracted is None or not extracted.read():
                raise SystemExit(f"empty runtime bundle member: {member.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write the bundle to this path")
    parser.add_argument(
        "--check", action="store_true", help="verify deterministic output and members"
    )
    parser.add_argument(
        "--print-sha256", action="store_true", help="print the bundle SHA-256"
    )
    args = parser.parse_args()

    payload = bundle_bytes()
    verify_bundle(payload)
    if args.check and payload != bundle_bytes():
        raise SystemExit("runtime bundle output is not deterministic")
    if args.output:
        args.output.write_bytes(payload)
    if args.print_sha256:
        print(hashlib.sha256(payload).hexdigest())
    elif args.check:
        print(f"runtime-bundle-ok bytes={len(payload)}")
    if not (args.output or args.check or args.print_sha256):
        parser.error("specify --output, --check, or --print-sha256")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
