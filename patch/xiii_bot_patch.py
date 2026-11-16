#!/usr/bin/env python3
"""Let the XIII dedicated server run bots: one byte in XIIIMP.u, 32 bytes in XIIIMP.dll.

Stock XIII adds bots only offline, and a bot on a dedicated server crashes it.
Two edits fix both:

  1. XIIIMP.u, file offset 98449: in XIIIMPGameInfo.StartMatch, the test
     `Level.NetMode == NM_StandAlone` is the int `==` native (byte 9A). It
     becomes the int `!=` native (9B), so a dedicated server adds
     Level.BotNumber bots at the start of a match.
  2. XIIIMP.dll, file offset 0x3A90 (VA 0x11D03A90, DllMain and its padding):
     DllMain also calls the DLL's own export XIIIMPInitNativePackage() on
     DLL_PROCESS_ATTACH. That function registers the names the bot code calls
     back into script (AddDefaultOrders, LogOrderList, ...). The game client
     (XIII.exe) calls it; UCC.exe never does, so on a server the names stay
     None and the first bot crashes: "Failed to find function None in
     BotController" from ABotController::execAddOrder.

        11d03a90 mov eax, [esp+4]           ; unchanged
        11d03a94 mov [0x11d0b30c], eax      ; unchanged (hInstance; its relocation stays valid)
        11d03a99 cmp dword ptr [esp+8], 1   ; DLL_PROCESS_ATTACH?
        11d03a9e jne 11d03aa5
        11d03aa0 call 11d03ab0              ; XIIIMPInitNativePackage
        11d03aa5 mov eax, 1
        11d03aaa ret 0xc

Only the exact known files are touched (sha256 checked before and after). The
DLL is patched first; XIIIMP.u only when the DLL is patched, because bots on an
unpatched DLL crash the server. Originals are kept as <file>.orig.

Usage:
  python3 xiii_bot_patch.py check  <XIII>/System
  python3 xiii_bot_patch.py apply  <XIII>/System
  python3 xiii_bot_patch.py revert <XIII>/System

Exit codes: 0 done (or nothing to do), 1 an unknown file, 2 a file missing.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

# (file, original sha256, patched sha256, ((offset, original, patched), ...))
FILES = (
    ("XIIIMP.dll",
     "a504c2e3ccbe5fbfeb92a8b33c1caa4a5490172a2c22e77a80dbbbd3fec04a9b",
     "58ca02dc8036b2390b655b917c9cdcf847086cadddda0026b1a8a1e6fe4ef35e",
     ((0x3A90,
       bytes.fromhex("8b442404a30cb3d011b801000000c20c00") + b"\x90" * 15,
       bytes.fromhex("8b442404a30cb3d011837c2408017505e80b000000b801000000c20c00909090")),)),
    ("XIIIMP.u",
     "6f5f07f13b5fadd61abfaf9622e8dd15f91675f36a6525d7bd14de715a2c3450",
     "d4771d0002c4a324bfef6f8891958e2a3fb2c5d17b38294c2673493b69ac5e1e",
     ((98449, b"\x9a", b"\x9b"),)),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def swap(data: bytes, spec, forward: bool) -> bytes:
    name, orig, patched, edits = spec
    want, result = (orig, patched) if forward else (patched, orig)
    if sha256(data) != want:
        raise ValueError(f"not the expected {name}")
    out = bytearray(data)
    for off, old, new in edits:
        src, dst = (old, new) if forward else (new, old)
        if out[off:off + len(src)] != src:
            raise ValueError(f"unexpected bytes at {off:#x} in {name}")
        out[off:off + len(dst)] = dst
    if sha256(bytes(out)) != result:
        raise ValueError(f"{name}: result hash mismatch")
    return bytes(out)


def state(data: bytes, spec) -> str:
    _, orig, patched, _ = spec
    return {orig: "original", patched: "patched"}.get(sha256(data), "unknown")


def _write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("check", "apply", "revert"):
        print(__doc__.split("Usage:")[1].split("Exit codes")[0].rstrip())
        return 2
    action, system = argv[0], Path(argv[1])
    states = {}
    for spec in FILES:
        path = system / spec[0]
        if not path.is_file():
            print(f"{path}: not found")
            return 2
        data = path.read_bytes()
        states[spec[0]] = state(data, spec)
        print(f"{path}: {states[spec[0]]} (sha256 {sha256(data)})")
    if "unknown" in states.values():
        print("Not the known build: left untouched. Bots stay off on this server.")
        return 1
    # apply: DLL first, then the .u; revert: the .u first, then the DLL.
    order = FILES if action == "apply" else tuple(reversed(FILES))
    for spec in order:
        path = system / spec[0]
        current = states[spec[0]]
        if action == "apply" and current == "original":
            backup = system / (spec[0] + ".orig")
            if not backup.exists():
                backup.write_bytes(path.read_bytes())
            _write_atomic(path, swap(path.read_bytes(), spec, forward=True))
            print(f"{spec[0]}: patched; original kept as {backup.name}")
        elif action == "revert" and current == "patched":
            _write_atomic(path, swap(path.read_bytes(), spec, forward=False))
            print(f"{spec[0]}: reverted to the original")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
