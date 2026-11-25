#!/usr/bin/env python3
"""A minimal XIII (Unreal Engine 2, build 829) network client for lab tests.

Not a game client: it speaks just enough of the UDP protocol to JOIN a server
as a player, so the server holds a real TcpipConnection PlayerController (what
our lab's fake controllers never had, and what crashed the first live map
change with a real client, 2026-11-18). It then keeps the connection alive by
acknowledging every packet, and reports what the server sends:

  - the control channel text (HELLO / CHALLENGE / LOGIN / WELCOME / USES / JOIN),
  - any travel the server orders: a packet that carries the travel URL is found
    by searching every bit offset of the received payload for the map name
    (actor-channel RPCs are bit-packed, not byte-aligned).

Packet format (UE1/early UE2, UnConn.cpp): bits LSB first; a packet ends with
a single 1 bit (the highest set bit of the last byte). PacketId =
ReadInt(MAX_PACKETID); then items until the end: IsAck bit -> AckPacketId,
else a bunch: bControl, [bOpen, bClose], bReliable, ChIndex =
ReadInt(MAX_CHANNELS), [ChSequence = ReadInt(MAX_CHSEQUENCE)], [ChType =
ReadInt(CHTYPE_MAX)], BunchDataBits = ReadInt(MaxPacket*8), data. Control
channel data = FStrings (compact-index length, ANSI bytes with NUL).

It can also FOLLOW travels like a game client (--follow MAP[,MAP...]): when
the server's travel to the next listed map arrives, it opens a new connection
to the same address with the merged URL (that map + its own options), sending
HELLO every second until the server answers (a restarting server answers when
it is back: the client's InitialConnectTimeout is 60 s). Each follow prints
"followed to MAP: Join sent N s after the travel". Detection is the same bit
search as --watch, so list maps in the order the test changes to them.

Usage (on the server host or the LAN):
  python3 xiii_netclient.py --server 127.0.0.1:7777 --name labclient \\
      [--password <admin pw>] [--seconds 120] [--watch DM_Banque] \\
      [--follow DM_Banque,CTF_Base,DM_Amos]
"""
from __future__ import annotations

import argparse
import random
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))
from upkg import write_ci  # noqa: E402

MAX_PACKETID = 16384
MAX_CHANNELS = 1023
MAX_CHSEQUENCE = 1024
CHTYPE_MAX = 8
CHTYPE_CONTROL = 1
MAX_PACKET = 512


class BitWriter:
    def __init__(self):
        self.bits = []

    def bit(self, b):
        self.bits.append(1 if b else 0)

    def int_(self, value, vmax):
        new, mask = 0, 1
        while new + mask < vmax and mask:
            if value & mask:
                self.bit(1)
                new += mask
            else:
                self.bit(0)
            mask <<= 1

    def byte(self, v):
        for i in range(8):
            self.bit((v >> i) & 1)

    def extend(self, bits):
        self.bits.extend(bits)

    def packet(self) -> bytes:
        bits = self.bits + [1]  # end marker
        out = bytearray((len(bits) + 7) // 8)
        for i, b in enumerate(bits):
            if b:
                out[i >> 3] |= 1 << (i & 7)
        return bytes(out)


class BitReader:
    def __init__(self, data: bytes):
        last = data[-1] if data else 0
        if not last:
            self.size = 0
        else:
            size = len(data) * 8 - 1
            while not last & 0x80:
                last = (last << 1) & 0xFF
                size -= 1
            self.size = size
        self.data, self.pos = data, 0

    def at_end(self):
        return self.pos >= self.size

    def bit(self):
        if self.pos >= self.size:
            raise EOFError
        b = (self.data[self.pos >> 3] >> (self.pos & 7)) & 1
        self.pos += 1
        return b

    def int_(self, vmax):
        value, mask = 0, 1
        while value + mask < vmax and mask:
            if self.bit():
                value |= mask
            mask <<= 1
        return value

    def bits(self, n):
        return [self.bit() for _ in range(n)]


def compact_index_bits(v: int) -> list:
    """FArchive compact index (upkg.write_ci), as 8-bit bytes in the bit stream."""
    w = BitWriter()
    for c in write_ci(v):
        w.byte(c)
    return w.bits


def fstring_bits(text: str) -> list:
    raw = text.encode("latin-1") + b"\0"
    w = BitWriter()
    w.extend(compact_index_bits(len(raw)))
    for c in raw:
        w.byte(c)
    return w.bits


def read_fstrings(bits: list) -> list:
    """Control channel bunch data -> its strings."""
    def take_byte(i):
        return sum(bits[i + k] << k for k in range(8)), i + 8
    out, i = [], 0
    while i + 8 <= len(bits):
        b0, i = take_byte(i)
        n = b0 & 0x3F
        if b0 & 0x40:
            shift = 6
            for _ in range(4):
                bx, i = take_byte(i)
                n |= (bx & 0x7F) << shift
                shift += 7
                if not bx & 0x80:
                    break
        if b0 & 0x80:  # unicode
            raw = bytes(take_byte(i + 16 * k)[0] for k in range(n))
            i += 16 * n
        else:
            raw = bytearray()
            for _ in range(n):
                c, i = take_byte(i)
                raw.append(c)
        out.append(bytes(raw).rstrip(b"\0").decode("latin-1", "replace"))
    return out


def challenge_response(challenge: int) -> int:
    """UGameEngine::ChallengeResponse in Engine.dll (VA 0x10377cc0):
    (c*237) ^ (c >> 16, arithmetic) ^ (c << 16) ^ 0x93fe92ce, as int32."""
    m = 0xFFFFFFFF
    c = challenge & m
    sar = (challenge >> 16) & m          # Python >> on a negative int is arithmetic
    r = ((c * 0xED) & m) ^ sar ^ ((c << 16) & m) ^ 0x93FE92CE
    return r - (1 << 32) if r & 0x80000000 else r


def bits_to_bytes(bits: list, offset: int) -> bytes:
    out = bytearray()
    for i in range(offset, len(bits) - 7, 8):
        out.append(sum(bits[i + k] << k for k in range(8)))
    return bytes(out)


class Client:
    def __init__(self, server, *, log=print):
        self.server = server
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.2)
        self.out_packet = random.randint(1, 1000)
        self.out_reliable = 0          # control channel sequence
        self.in_reliable = 0
        self.pending_acks = []
        self.log = log
        self.control = []              # control strings received
        self.raw = []                  # (time, payload bits) of every packet

    def send(self, items_bits=None):
        w = BitWriter()
        self.out_packet = (self.out_packet + 1) % MAX_PACKETID
        w.int_(self.out_packet, MAX_PACKETID)
        for ack in self.pending_acks:
            w.bit(1)
            w.int_(ack, MAX_PACKETID)
        self.pending_acks = []
        if items_bits:
            w.extend(items_bits)
        self.sock.sendto(w.packet(), self.server)

    def control_bunch(self, *texts, open_=False):
        self.out_reliable += 1
        w = BitWriter()
        w.bit(0)                      # not an ack
        w.bit(1)                      # bControl
        w.bit(1 if open_ else 0)      # bOpen
        w.bit(0)                      # bClose
        w.bit(1)                      # bReliable
        w.int_(0, MAX_CHANNELS)
        w.int_(self.out_reliable % MAX_CHSEQUENCE, MAX_CHSEQUENCE)
        w.int_(CHTYPE_CONTROL, CHTYPE_MAX)
        data = []
        for t in texts:
            data += fstring_bits(t)
        w.int_(len(data), MAX_PACKET * 8)
        w.extend(data)
        self.log(f">> {' | '.join(texts)}")
        self.send(w.bits)

    def pump(self, seconds):
        """Receive for `seconds`, ack everything, collect control text."""
        end = time.time() + seconds
        got = []
        while time.time() < end:
            try:
                data, _ = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            r = BitReader(data)
            try:
                pid = r.int_(MAX_PACKETID)
                self.pending_acks.append(pid)
                payload_start = r.pos
                while not r.at_end():
                    if r.bit():
                        r.int_(MAX_PACKETID)
                        continue
                    b_control = r.bit()
                    b_open = r.bit() if b_control else 0
                    b_close = r.bit() if b_control else 0
                    b_rel = r.bit()
                    ch = r.int_(MAX_CHANNELS)
                    seq = r.int_(MAX_CHSEQUENCE) if b_rel else None
                    ctype = r.int_(CHTYPE_MAX) if (b_rel or b_open) else None
                    nbits = r.int_(MAX_PACKET * 8)
                    bits = r.bits(nbits)
                    if ch == 0:
                        texts = read_fstrings(bits)
                        self.control += texts
                        got += texts
                        for t in texts:
                            self.log(f"<< {t}")
                    self.raw.append((time.time(), ch, b_open, b_close, bits))
            except EOFError:
                pass
            self.send()  # ack it
        return got

    def find_text(self, needle: bytes):
        """[(time, channel)] of received bunches whose bits hold `needle` at
        any bit offset."""
        hits = []
        for t, ch, _, _, bits in self.raw:
            for off in range(8):
                if needle in bits_to_bytes(bits, off):
                    hits.append((t, ch))
                    break
        return hits


def follow_url(login_url: str, map_file: str) -> str:
    """The URL a client logs in with after a relative travel to `map_file`:
    the new map, the player's own options kept. Pure."""
    m = map_file if map_file.lower().endswith(".unr") else f"{map_file}.unr"
    q = login_url.find("?")
    return m + (login_url[q:] if q >= 0 else "")


def connect(server, url: str, *, ver: int, minver: int, retry_s: float = 0.0, log=print):
    """HELLO (resent each second for up to retry_s), LOGIN, JOIN. Returns the
    joined Client or None."""
    deadline = time.time() + retry_s
    while True:
        c = Client(server, log=log)
        c.control_bunch(f"HELLO REVISION=0 MINVER={minver or ver} VER={ver}", open_=True)
        got = c.pump(1 if retry_s else 3)
        challenge = next((t for t in got if t.startswith("CHALLENGE")), None)
        if any(t.startswith("UPGRADE") for t in got):
            print("server wants another version:", [t for t in got if t.startswith("UPGRADE")])
            return None
        if challenge:
            break
        c.sock.close()
        if time.time() >= deadline:
            print("no CHALLENGE from the server")
            return None
    c.control_bunch("NETSPEED 10000")
    value = int(challenge.split("CHALLENGE=")[1].split()[0])
    c.control_bunch(f"LOGIN RESPONSE={challenge_response(value)} URL={url}?Checksum=NoChecksum")
    got = c.pump(3)
    if not any(t.startswith("WELCOME") for t in got):
        print("no WELCOME from the server")
        return None
    c.pump(1)
    c.control_bunch("JOIN")
    return c


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--server", default="127.0.0.1:7777")
    ap.add_argument("--name", default="labclient")
    ap.add_argument("--password", default="")
    ap.add_argument("--ver", type=int, default=829)
    ap.add_argument("--minver", type=int, default=0)
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--watch", default="", help="report bunches whose bits hold this text")
    ap.add_argument("--dump", default="", help="at the end, print every bunch holding this text")
    ap.add_argument("--follow", default="", help="follow travels to these maps, in order (comma list)")
    ap.add_argument("--retry", type=float, default=60.0,
                    help="seconds a follow keeps sending HELLO (the client's InitialConnectTimeout)")
    a = ap.parse_args(argv)
    host, port = a.server.rsplit(":", 1)
    server = (host, int(port))
    url = f"Index.unr?Name={a.name}?Team=255?Class=XIII.XIIIPlayerPawn"
    if a.password:
        url += f"?Password={a.password}"
    c = connect(server, url, ver=a.ver, minver=a.minver)
    if c is None:
        return 1
    print("joined; holding the connection", flush=True)
    follows = [m.strip() for m in a.follow.split(",") if m.strip()]
    history = []   # packets of the connections a follow closed (for --dump)
    start = time.time()
    while time.time() - start < a.seconds:
        c.pump(1)
        if a.watch:
            hits = c.find_text(a.watch.encode())
            if hits:
                print(f"server sent '{a.watch}' on channel(s) {sorted({h[1] for h in hits})} "
                      f"{time.time() - start:.1f}s after JOIN", flush=True)
                a.watch = ""
        if follows and c.find_text(follows[0].encode()):
            target = follows.pop(0)
            seen = time.time()
            print(f"travel to {target} received {seen - start:.1f}s after JOIN; following",
                  flush=True)
            c.sock.close()
            history += c.raw
            url = follow_url(url, target)
            nxt = connect(server, url, ver=a.ver, minver=a.minver, retry_s=a.retry)
            if nxt is None:
                print(f"follow to {target} FAILED", flush=True)
                return 1
            c = nxt
            print(f"followed to {target}: Join sent {time.time() - seen:.1f}s after the travel",
                  flush=True)
    if a.dump:
        for t, ch, b_open, b_close, bits in history + c.raw:
            for off in range(8):
                blob = bits_to_bytes(bits, off)
                if a.dump.encode() in blob:
                    i = blob.index(a.dump.encode())
                    print(f"t+{t - start:.1f}s ch{ch} open={b_open} close={b_close}: "
                          f"{blob[max(0, i - 40):i + 120]!r}")
                    break
    print("last control text:", c.control[-5:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
