"""Just enough of the Unreal Engine 2 package format (XIII: version 100,
licensee 58) to put UnrealScript source text back into a stripped package.

Why: XIII's `UCC make` re-parses every superclass of a class it compiles from
the superclass's ScriptText. The shipped IpDrv.u has that text stripped (a
single space), so a class extending IpDrv.UdpLink cannot be compiled. The
build (build_ctl.py) injects declaration-only text (stubs/*.uc) into a
SCRATCH copy of IpDrv.u; the real IpDrv.u on a server is never touched.

Layout (all little endian):
  header   tag, version u16, licensee u16, flags u32, name count/offset,
           export count/offset, import count/offset (u32 each)
  export   class ci, super ci, package i32, name ci, flags u32,
           serial size ci, serial offset ci (only when size > 0)
  TextBuffer data: tagged-property terminator (name ci), Pos i32, Top i32,
           Text FString (ci length incl. NUL, bytes, NUL)
`ci` is the engine's compact index (sign + 6 bits, then 7-bit groups).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

TAG = 0x9E2A83C1
_HEADER = struct.Struct("<IHHIIIIIII")


class PackageError(Exception):
    pass


def read_ci(b: bytes, p: int) -> tuple[int, int]:
    """(value, next offset) of the compact index at p."""
    b0 = b[p]
    p += 1
    v = b0 & 0x3F
    if b0 & 0x40:
        shift = 6
        for i in range(4):
            bx = b[p]
            p += 1
            if i == 3:
                v |= bx << shift
                break
            v |= (bx & 0x7F) << shift
            shift += 7
            if not bx & 0x80:
                break
    return (-v if b0 & 0x80 else v), p


def write_ci(v: int) -> bytes:
    a = abs(int(v))
    out = bytearray([(0x80 if v < 0 else 0) | (a & 0x3F)])
    a >>= 6
    if a:
        out[0] |= 0x40
    i = 0
    while a:
        i += 1
        if i == 4:
            out.append(a & 0xFF)
            break
        b = a & 0x7F
        a >>= 7
        if a:
            b |= 0x80
        out.append(b)
    return bytes(out)


def write_fstring(text: str) -> bytes:
    raw = text.encode("latin-1") + b"\0"
    return write_ci(len(raw)) + raw


@dataclass
class Export:
    cls: int
    sup: int
    package: int
    name: int
    flags: int
    size: int
    offset: int

    def encode(self) -> bytes:
        out = (write_ci(self.cls) + write_ci(self.sup) + struct.pack("<i", self.package)
               + write_ci(self.name) + struct.pack("<I", self.flags) + write_ci(self.size))
        if self.size > 0:
            out += write_ci(self.offset)
        return out


class Package:
    def __init__(self, data: bytes):
        self.data = bytes(data)
        if len(self.data) < _HEADER.size:
            raise PackageError("file too short for a package header")
        (tag, self.version, self.licensee, self.flags, nc, no, ec, eo, ic, io) = \
            _HEADER.unpack_from(self.data, 0)
        if tag != TAG:
            raise PackageError("not an Unreal package (bad tag)")
        self.names: list[str] = []
        p = no
        for _ in range(nc):
            n, p = read_ci(self.data, p)
            self.names.append(self.data[p:p + n - 1].decode("latin-1") if n > 0 else "")
            p += max(n, 0) + 4  # string + object flags
        self.imports: list[tuple[str, str, int, str]] = []
        p = io
        for _ in range(ic):
            cp, p = read_ci(self.data, p)
            cn, p = read_ci(self.data, p)
            pk = struct.unpack_from("<i", self.data, p)[0]
            p += 4
            on, p = read_ci(self.data, p)
            self.imports.append((self.names[cp], self.names[cn], pk, self.names[on]))
        self.exports: list[Export] = []
        p = eo
        for _ in range(ec):
            cls, p = read_ci(self.data, p)
            sup, p = read_ci(self.data, p)
            pk = struct.unpack_from("<i", self.data, p)[0]
            p += 4
            on, p = read_ci(self.data, p)
            fl = struct.unpack_from("<I", self.data, p)[0]
            p += 4
            sz, p = read_ci(self.data, p)
            off = 0
            if sz > 0:
                off, p = read_ci(self.data, p)
            self.exports.append(Export(cls, sup, pk, on, fl, sz, off))
        self._export_count, self._import_count = ec, ic
        self._name_off, self._name_count, self._import_off = no, nc, io

    def class_name(self, e: Export) -> str:
        """Name of the export's class ('Class' for a UClass)."""
        if e.cls == 0:
            return "Class"
        if e.cls < 0:
            return self.imports[-e.cls - 1][3]
        return self.names[self.exports[e.cls - 1].name]

    def find(self, name: str, class_name: str, outer: str | None = None) -> int:
        """1-based export index of the object `outer.name` of class class_name."""
        for i, e in enumerate(self.exports):
            if self.names[e.name] != name or self.class_name(e) != class_name:
                continue
            if outer is not None:
                if e.package <= 0 or self.names[self.exports[e.package - 1].name] != outer:
                    continue
            return i + 1
        raise PackageError(f"no {class_name} {outer + '.' if outer else ''}{name} in package")

    def script_text(self, class_name: str) -> str:
        e = self.exports[self.find("ScriptText", "TextBuffer", class_name) - 1]
        _, p = read_ci(self.data, e.offset)  # tagged-property terminator
        p += 8  # Pos, Top
        n, p = read_ci(self.data, p)
        return self.data[p:p + n - 1].decode("latin-1") if n > 0 else ""


def inject_script_text(data: bytes, texts: dict[str, str]) -> bytes:
    """A copy of package `data` whose classes {name: source} carry that source
    as ScriptText. The new TextBuffers and a rewritten export table are
    appended; the header's export offset moves to the new table. Everything
    else (names, imports, other objects) is byte-identical."""
    pkg = Package(data)
    out = bytearray(pkg.data)
    exports = [Export(**vars(e)) for e in pkg.exports]
    for cls_name, text in texts.items():
        idx = pkg.find("ScriptText", "TextBuffer", cls_name)
        e = exports[idx - 1]
        _, p = read_ci(pkg.data, e.offset)
        prefix = pkg.data[e.offset:p + 8]  # terminator + Pos + Top, as shipped
        blob = prefix + write_fstring(text.replace("\r\n", "\n").replace("\n", "\r\n"))
        e.offset, e.size = len(out), len(blob)
        out += blob
    table_off = len(out)
    for e in exports:
        out += e.encode()
    header = list(_HEADER.unpack_from(out, 0))
    header[7] = table_off
    _HEADER.pack_into(out, 0, *header)
    return bytes(out)
