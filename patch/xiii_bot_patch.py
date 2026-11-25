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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from binpatch import FilePatch, cli  # noqa: E402

XIIIMP_DLL = FilePatch(
    "XIIIMP.dll",
    "a504c2e3ccbe5fbfeb92a8b33c1caa4a5490172a2c22e77a80dbbbd3fec04a9b",
    "58ca02dc8036b2390b655b917c9cdcf847086cadddda0026b1a8a1e6fe4ef35e",
    # DllMain (0x11d03a90) and its padding, up to XIIIMPInitNativePackage.
    ((0x3A90,
      bytes.fromhex("8b442404a30cb3d011b801000000c20c00") + b"\x90" * 15,
      bytes.fromhex("8b442404a30cb3d011837c2408017505e80b000000b801000000c20c00909090")),),
    size=53248,
)
XIIIMP_U = FilePatch(
    "XIIIMP.u",
    "6f5f07f13b5fadd61abfaf9622e8dd15f91675f36a6525d7bd14de715a2c3450",
    "d4771d0002c4a324bfef6f8891958e2a3fb2c5d17b38294c2673493b69ac5e1e",
    # XIIIMPGameInfo.StartMatch: `Level.NetMode == NM_StandAlone` -> `!=`
    ((98449, b"\x9a", b"\x9b"),),
    size=941397,
)
# Applied in this order (the DLL first: bots on an unpatched DLL crash the
# server), reverted in the reverse order.
PATCHES = (XIIIMP_DLL, XIIIMP_U)


def main(argv: list) -> int:
    return cli(argv, PATCHES, __doc__, "Bots stay off on this server.")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
