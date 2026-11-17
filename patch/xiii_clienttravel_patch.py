#!/usr/bin/env python3
"""Let the XIII dedicated server change map live WITH players connected: 1 byte in Engine.u.

With xiii_engine_patch.py alone, a map change works on an empty server but
crashes as soon as a real player is connected:

  ProcessServerTravel: DM_Banque.unr?...
  Cast of TcpipConnection Transient.TcpipConnection2 to Viewport failed
  History: UGameEngine::SetClientTravel <- UObject::ProcessEvent <- ...

ProcessServerTravel tells each remote player to follow with
P.ClientTravel(URL, TRAVEL_Relative, bItems), a function replicated to the
client. XIII declares it `native static function event ClientTravel(...)`, and
a static function is never sent over the network: the native ran on the
server, whose Player object is a TcpipConnection, not a Viewport.

The fix clears the static bit (0x00080000) of that one function in the
server's Engine.u. Its serialized FunctionFlags (export
PlayerController.ClientTravel) are at file offset 222006 and read 0x001b3000:

  file 222008: 1B -> 13      (0x001b3000 -> 0x00133000)

Players keep their own Engine.u, where the native runs locally as it must.
Only the exact known file is touched (sha256 before and after). The original
is kept as Engine.u.orig.

Usage:
  python3 xiii_clienttravel_patch.py check  <XIII>/System
  python3 xiii_clienttravel_patch.py apply  <XIII>/System
  python3 xiii_clienttravel_patch.py revert <XIII>/System

Exit codes: 0 done (or nothing to do), 1 unknown Engine.u, 2 file missing.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

FILENAME = "Engine.u"
ORIGINAL_SHA256 = "da24040b4fca0d3ec6dd92aa3b192d3ee82b25fa358170bbeded4d8432683234"
PATCHED_SHA256 = "019296366fe36805fbf2721cb09c365dd117d42ad05a6128f2444aa21a4af7f6"
PATCHES = ((222008, b"\x1b", b"\x13"),)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def swap(data: bytes, forward: bool) -> bytes:
    want, result = (ORIGINAL_SHA256, PATCHED_SHA256) if forward else (PATCHED_SHA256, ORIGINAL_SHA256)
    if sha256(data) != want:
        raise ValueError("not the expected Engine.u")
    out = bytearray(data)
    for off, old, new in PATCHES:
        src, dst = (old, new) if forward else (new, old)
        if out[off:off + len(src)] != src:
            raise ValueError(f"unexpected bytes at {off}")
        out[off:off + len(dst)] = dst
    if sha256(bytes(out)) != result:
        raise ValueError("result hash mismatch")
    return bytes(out)


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
    state = {ORIGINAL_SHA256: "original", PATCHED_SHA256: "patched"}.get(sha256(data), "unknown")
    print(f"{path}: {state} (sha256 {sha256(data)})")
    if state == "unknown":
        print("Not the known build: left untouched. Live map changes with players will crash.")
        return 1
    tmp = path.with_name(path.name + ".tmp")
    if action == "apply" and state == "original":
        backup = system / (FILENAME + ".orig")
        if not backup.exists():
            backup.write_bytes(data)
        tmp.write_bytes(swap(data, forward=True))
        tmp.replace(path)
        print(f"patched; original kept as {backup.name}")
    elif action == "revert" and state == "patched":
        tmp.write_bytes(swap(data, forward=False))
        tmp.replace(path)
        print("reverted to the original")
    elif action != "check":
        print("nothing to do")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
