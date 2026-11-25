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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from binpatch import FilePatch, cli  # noqa: E402

ENGINE_U = FilePatch(
    "Engine.u",
    "da24040b4fca0d3ec6dd92aa3b192d3ee82b25fa358170bbeded4d8432683234",
    "019296366fe36805fbf2721cb09c365dd117d42ad05a6128f2444aa21a4af7f6",
    # PlayerController.ClientTravel FunctionFlags 0x001b3000 -> 0x00133000
    ((222008, b"\x1b", b"\x13"),),
    size=547891,
)
PATCHES = (ENGINE_U,)


def main(argv: list) -> int:
    return cli(argv, PATCHES, __doc__, "Live map changes with players will crash.")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
