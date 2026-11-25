"""Sha256-gated, same-length byte patches on shipped XIII files.

Shared by the three patch scripts in this directory and by install.py. A file
is patched only when it is the exact known build: its sha256 is checked before
and after, and the result is written atomically. Any other copy is left alone.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

ORIGINAL = "original"
PATCHED = "patched"
UNKNOWN = "unknown"
MISSING = "missing"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FilePatch:
    """One file: its original and patched sha256 and the byte edits between
    them, as (file offset, original bytes, patched bytes)."""

    def __init__(self, filename: str, original_sha256: str, patched_sha256: str,
                 edits: tuple, size: int = 0):
        for off, old, new in edits:
            if len(old) != len(new):
                raise ValueError(f"{filename}: edit at {off:#x} changes the length")
        self.filename = filename
        self.original_sha256 = original_sha256
        self.patched_sha256 = patched_sha256
        self.edits = tuple(edits)
        self.size = size

    @property
    def bytes_changed(self) -> int:
        return sum(sum(1 for a, b in zip(old, new) if a != b) for _, old, new in self.edits)

    def state(self, data: bytes) -> str:
        return {self.original_sha256: ORIGINAL,
                self.patched_sha256: PATCHED}.get(sha256(data), UNKNOWN)

    def _swap(self, data: bytes, forward: bool) -> bytes:
        want, result = ((self.original_sha256, self.patched_sha256) if forward
                        else (self.patched_sha256, self.original_sha256))
        if sha256(data) != want:
            raise ValueError(f"not the expected {self.filename}")
        out = bytearray(data)
        for off, old, new in self.edits:
            src, dst = (old, new) if forward else (new, old)
            if out[off:off + len(src)] != src:
                raise ValueError(f"unexpected bytes at {off:#x} in {self.filename}")
            out[off:off + len(dst)] = dst
        if sha256(bytes(out)) != result:
            raise ValueError(f"{self.filename}: result hash mismatch")
        return bytes(out)

    def apply(self, data: bytes) -> bytes:
        """The patched file from the original. Pure; ValueError otherwise."""
        return self._swap(data, forward=True)

    def revert(self, data: bytes) -> bytes:
        """The original file from the patched one. Pure; ValueError otherwise."""
        return self._swap(data, forward=False)


def write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(str(tmp), str(path))


def backup_path(path: Path) -> Path:
    return path.with_name(path.name + ".orig")


def cli(argv: list, patches: tuple, doc: str, unknown_note: str) -> int:
    """check | apply | revert <XIII>/System for `patches`, in that order for
    apply and in reverse order for revert. Exit codes: 0 done (or nothing to
    do), 1 an unknown file (nothing changed), 2 usage or a file missing."""
    if len(argv) != 2 or argv[0] not in ("check", "apply", "revert"):
        print(doc.split("Usage:")[1].split("Exit codes")[0].rstrip())
        return 2
    action, system = argv[0], Path(argv[1])
    states = {}
    for p in patches:
        path = system / p.filename
        if not path.is_file():
            print(f"{path}: not found")
            return 2
        data = path.read_bytes()
        states[p.filename] = p.state(data)
        print(f"{path}: {states[p.filename]} (sha256 {sha256(data)})")
    if UNKNOWN in states.values():
        print(f"Not the known build: left untouched. {unknown_note}")
        return 1
    order = patches if action == "apply" else tuple(reversed(patches))
    changed = False
    for p in order:
        path = system / p.filename
        current = states[p.filename]
        if action == "apply" and current == ORIGINAL:
            data = path.read_bytes()
            backup = backup_path(path)
            if not backup.exists():
                backup.write_bytes(data)
            write_atomic(path, p.apply(data))
            print(f"{p.filename}: patched; original kept as {backup.name}")
            changed = True
        elif action == "revert" and current == PATCHED:
            write_atomic(path, p.revert(path.read_bytes()))
            print(f"{p.filename}: reverted to the original")
            changed = True
    if action != "check" and not changed:
        print("nothing to do")
    return 0
