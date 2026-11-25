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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from binpatch import FilePatch, cli  # noqa: E402

# System/Engine.dll of the community "How to Host" server archive
# (build 829, 2018 update files), 2433024 bytes. Image base 0x10300000; the
# code section maps file offset X to VA 0x10300000 + X.
ENGINE_DLL = FilePatch(
    "Engine.dll",
    "810b0c9600d06e104104f1dbf04d7989584b6d931d75e4a5ff933be598cdafdc",
    "ff6183bfdbb908a0005a8dbecc7ce9fe7de11c92c8dc321780ca7fc1aa02e864",
    (
        # 0x1037c44d: call ClearActorBindings(Client) -> 5 x nop
        (0x7C44D, bytes.fromhex("e86ec3ffff"), bytes.fromhex("9090909090")),
        # 0x1037c5c6: jmp to the GEntry->Actors loop -> jmp past it
        (0x7C5C6, bytes.fromhex("eb08"), bytes.fromhex("eb3f")),
    ),
    size=2433024,
)
PATCHES = (ENGINE_DLL,)


def main(argv: list) -> int:
    return cli(argv, PATCHES, __doc__, "Map changes will crash this server.")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
