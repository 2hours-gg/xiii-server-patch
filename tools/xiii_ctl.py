#!/usr/bin/env python3
"""Send one command to the TwoHoursCtl actor of a local XIII dedicated server.

Run it ON the server machine (the actor ignores datagrams that are not from
127.0.0.1). The key is the CtlKey set in XIII.ini [TwoHoursCtl.TwoHoursCtl].

  python3 xiii_ctl.py --key <CtlKey> status
  python3 xiii_ctl.py --key <CtlKey> travel "DM_Amos.unr?MapName=FBI?NP=12?FF=0?FR=40?TI=20?Game=XIIIMP.XIIIMPGameInfo?GameIdx=0?Mutator="
  python3 xiii_ctl.py --key <CtlKey> say "map change in 10 seconds"
  python3 xiii_ctl.py --key <CtlKey> kick SomePlayer
  python3 xiii_ctl.py --key <CtlKey> ban SomePlayer
  python3 xiii_ctl.py --key <CtlKey> tell "Some Player" "only you see this"
  python3 xiii_ctl.py --key <CtlKey> poll
  python3 xiii_ctl.py --key <CtlKey> bots 6 2

`tell` sends "tell <name><TAB><text>", so a name may hold spaces. `poll` prints
the chat commands queued since the last poll, one "<name><TAB><a|p><TAB><command>"
line each (a = admin, p = player), plus "<TAB>s<TAB>#matchend" when a match
ends, and empties the queue. `bots <n> <skill>` makes bots fill the server to n
players (0 = off) at skill 0-3, from the next match start; it needs
patch/xiii_bot_patch.py.

Wire format, one UDP datagram each way:
  request  "<key> <id> <command> [args]"
  reply    "<id> <text>"          (no reply at all for a wrong key or source)
"""
from __future__ import annotations

import argparse
import random
import socket
import sys


def request(key: str, command: str, *, port: int = 7098, timeout: float = 3.0) -> str:
    req_id = str(random.randint(1, 10**9))
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.sendto(f"{key} {req_id} {command}".encode("latin-1"), ("127.0.0.1", port))
        while True:
            data, _ = sock.recvfrom(65535)
            text = data.decode("latin-1").rstrip("\n")
            got_id, _, rest = text.partition(" ")
            if got_id == req_id:
                return rest


def build_command(words: list) -> str:
    """The datagram's command part. `tell <name> <text...>` puts a tab between
    the name and the text."""
    if words and words[0].lower() == "tell":
        if len(words) < 3:
            raise SystemExit("usage: tell <name> <text>")
        return f"tell {words[1]}\t{' '.join(words[2:])}"
    return " ".join(words)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="TwoHoursCtl client (status, travel, say, kick, ban, tell, poll, bots)")
    ap.add_argument("--key", required=True, help="CtlKey from XIII.ini")
    ap.add_argument("--port", type=int, default=7098, help="CtlPort (default 7098)")
    ap.add_argument("command", nargs="+",
                    help="status | travel <url> | say <text> | kick <name> | ban <name> | "
                         "tell <name> <text> | poll | bots <n> <skill>")
    a = ap.parse_args()
    try:
        print(request(a.key, build_command(a.command), port=a.port))
    except socket.timeout:
        print("no reply: server down, map loading, wrong key, or the actor is not loaded",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
