#!/usr/bin/env python3
"""Let the XIII dedicated server change map without crashing: a 7-byte Engine.dll patch.

The stock server crashes on any in-process map change (ServerTravel), because
the map-unload code assumes a local player and an Entry level, and a dedicated
server has neither. Two edits remove those assumptions:

  1. file 0x7C44D (VA 0x1037C44D): `call ClearActorBindings(Client)`
     E8 6E C3 FF FF  ->  90 90 90 90 90   (5 x nop)
  2. file 0x7C5C6 (VA 0x1037C5C6): the jump into the GEntry->Actors loop
     EB 08           ->  EB 3F            (jump past the loop, to CollectGarbage)

Only the exact known file is touched: its sha256 is checked before and after.
Any other Engine.dll is left alone. The original is kept as Engine.dll.orig.

Usage:
  python3 xiii_engine_patch.py check  <XIII>/System
  python3 xiii_engine_patch.py apply  <XIII>/System
  python3 xiii_engine_patch.py revert <XIII>/System

Exit codes: 0 done (or nothing to do), 1 unknown Engine.dll, 2 file missing.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

FILENAME = "Engine.dll"
BACKUP = "Engine.dll.orig"
# System/Engine.dll of the community "How to Host" server archive
# (build 829, 2018 update files), 2433024 bytes.
ORIGINAL_SHA256 = "810b0c9600d06e104104f1dbf04d7989584b6d931d75e4a5ff933be598cdafdc"
PATCHED_SHA256 = "ff6183bfdbb908a0005a8dbecc7ce9fe7de11c92c8dc321780ca7fc1aa02e864"

# (file offset, original bytes, patched bytes). Image base 0x10300000; the
# code section maps file offset X to VA 0x10300000 + X.
PATCHES = (
    (0x7C44D, bytes.fromhex("e86ec3ffff"), bytes.fromhex("9090909090")),
    (0x7C5C6, bytes.fromhex("eb08"), bytes.fromhex("eb3f")),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _swap(data: bytes, want_sha: str, result_sha: str, forward: bool) -> bytes:
    if sha256(data) != want_sha:
        raise ValueError("not the expected Engine.dll")
    out = bytearray(data)
    for off, old, new in PATCHES:
        src, dst = (old, new) if forward else (new, old)
        if out[off:off + len(src)] != src:
            raise ValueError(f"unexpected bytes at {off:#x}")
        out[off:off + len(dst)] = dst
    if sha256(bytes(out)) != result_sha:
        raise ValueError("result hash mismatch")
    return bytes(out)


def patch_bytes(data: bytes) -> bytes:
    """Patched Engine.dll from the original. Pure; raises ValueError otherwise."""
    return _swap(data, ORIGINAL_SHA256, PATCHED_SHA256, forward=True)


def unpatch_bytes(data: bytes) -> bytes:
    """Original Engine.dll from the patched one. Pure; raises ValueError otherwise."""
    return _swap(data, PATCHED_SHA256, ORIGINAL_SHA256, forward=False)


def state(data: bytes) -> str:
    return {ORIGINAL_SHA256: "original", PATCHED_SHA256: "patched"}.get(sha256(data), "unknown")


def _write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("check", "apply", "revert"):
        print(__doc__.split("Usage:")[1].split("Exit codes")[0].rstrip())
        return 2
    action, system = argv[0], Path(argv[1])
    path = system / FILENAME
    if not path.is_file():
        print(f"{path}: not found")
        return 2
    data = path.read_bytes()
    current = state(data)
    print(f"{path}: {current} (sha256 {sha256(data)})")
    if current == "unknown":
        print("Not the known build: left untouched. Map changes will crash this server.")
        return 1
    if action == "apply" and current == "original":
        backup = system / BACKUP
        if not backup.exists():
            backup.write_bytes(data)
        _write_atomic(path, patch_bytes(data))
        print(f"patched; original kept as {backup.name}")
    elif action == "revert" and current == "patched":
        _write_atomic(path, unpatch_bytes(data))
        print("reverted to the original")
    elif action != "check":
        print("nothing to do")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
