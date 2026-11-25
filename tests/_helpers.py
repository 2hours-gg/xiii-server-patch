"""Shared fixtures: synthetic stand-ins for the XIII server files.

The real files are Ubisoft's and are not in this repository, and no synthetic
file can have their sha256. So the tests build random files, derive patch
tables (FilePatch objects) whose hashes are those files' hashes, and run the
real code paths on them.
"""
from __future__ import annotations

import contextlib
import io
import random
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for sub in ("", "patch", "build", "tools"):
    p = str(ROOT / sub) if sub else str(ROOT)
    if p not in sys.path:
        sys.path.insert(0, p)

import install  # noqa: E402
from binpatch import FilePatch, sha256  # noqa: E402

CRLF_INI = (
    "[URL]\r\n"
    "Protocol=unreal\r\n"
    "Port=7777\r\n"
    "\r\n"
    "[Engine.GameEngine]\r\n"
    "CacheSizeMegs=4\r\n"
    ";ServerActors=IpDrv.UdpBeacon\r\n"
    "ServerActors=IpDrvPlus.MasterServerUplink\r\n"
    "ServerActors=IpDrv.UdpServerQuery\r\n"
    "ServerPackages=XIIIMP\r\n"
    "\r\n"
    "[Engine.AccessControl]\r\n"
    "AdminPassword=silenteagle42\r\n"
    "\r\n"
    "[Engine.GameReplicationInfo]\r\n"
    "ServerName=XIII Server\r\n"
)


def synthetic_file(seed: int, size: int, edits_at: tuple):
    """(original bytes, FilePatch) for a random file with edits at the given
    (offset, original bytes, patched bytes) places."""
    rnd = random.Random(seed)
    data = bytearray(rnd.getrandbits(8) for _ in range(size))
    for off, old, _ in edits_at:
        data[off:off + len(old)] = old
    patched = bytearray(data)
    for off, _, new in edits_at:
        patched[off:off + len(new)] = new
    return bytes(data), bytes(patched), edits_at


def synthetic_spec():
    """(Spec, {filename: original bytes}, {filename: patched bytes})."""
    files = {
        "Engine.dll": synthetic_file(1, 4096, (
            (0x44D, bytes.fromhex("e86ec3ffff"), bytes.fromhex("9090909090")),
            (0x5C6, bytes.fromhex("eb08"), bytes.fromhex("eb3f")))),
        "Engine.u": synthetic_file(2, 2048, ((1208, b"\x1b", b"\x13"),)),
        "XIIIMP.dll": synthetic_file(3, 1024, (
            (0x90, bytes.fromhex("8b442404"), bytes.fromhex("837c2408")),)),
        "XIIIMP.u": synthetic_file(4, 2048, ((449, b"\x9a", b"\x9b"),)),
    }
    patches = tuple(FilePatch(name, sha256(o), sha256(p), edits)
                    for name, (o, p, edits) in files.items())
    addon = b"synthetic TwoHoursCtl.u " + bytes(range(256))
    older = b"an older synthetic TwoHoursCtl.u"
    spec = install.Spec(patches, addon, sha256(addon), (sha256(older),))
    spec.older_bytes = older
    return (spec, {n: f[0] for n, f in files.items()}, {n: f[1] for n, f in files.items()})


class ServerDir:
    """A temporary XIII server folder with the synthetic files in System/."""

    def __init__(self, originals: dict, ini: str = CRLF_INI, ini_name: str = "XIII.ini"):
        self.root = Path(tempfile.mkdtemp(prefix="xiii-test-"))
        self.system = self.root / "System"
        self.system.mkdir()
        for name, data in originals.items():
            (self.system / name).write_bytes(data)
        (self.system / "UCC.exe").write_bytes(b"MZ")
        if ini is not None:
            (self.system / ini_name).write_bytes(ini.encode("latin-1"))

    def read(self, name: str) -> bytes:
        return (self.system / name).read_bytes()

    def snapshot(self) -> dict:
        return {p.name: p.read_bytes() for p in sorted(self.system.iterdir())}

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def quiet(fn, *args, **kwargs):
    """(return value, printed text) of fn."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rv = fn(*args, **kwargs)
    return rv, buf.getvalue()
