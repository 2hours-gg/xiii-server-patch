#!/usr/bin/env python3
"""Install the XIII server patch: live map changes, bots and admin commands.

  python3 install.py check     <XIII dir>
  python3 install.py install   [--dry-run] <XIII dir>
  python3 install.py uninstall [--dry-run] <XIII dir>

<XIII dir> is the server folder (the one holding System/) or System/ itself.

check      identifies every file this patch touches by its sha256 (original,
           patched or unknown) and prints what install would change.
install    patches Engine.dll, Engine.u, XIIIMP.dll and XIIIMP.u, copies
           TwoHoursCtl.u and adds the XIII.ini lines the add-on needs. Each
           original is kept as <file>.orig. It refuses to touch anything when
           one file is unknown. Running it twice is safe. It ends by printing
           each file's sha256 next to the expected one.
uninstall  puts the original files back, removes TwoHoursCtl.u and the
           add-on's XIII.ini lines.

--dry-run prints what install or uninstall would do and changes nothing.

Exit codes: 0 done, 1 an unknown file (nothing was changed), 2 a missing
file or folder, 3 a file does not have the expected sha256 after install.

Python 3.8 or newer, standard library only. Works on Windows and on Linux.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import secrets
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "patch"))
import binpatch  # noqa: E402
from binpatch import MISSING, ORIGINAL, PATCHED, UNKNOWN, FilePatch, sha256  # noqa: E402

ADDON_FILE = "TwoHoursCtl.u"
# dist/TwoHoursCtl.u of this release. install refuses a dist file that does
# not match (a broken download), so this pin and the README must agree.
ADDON_SHA256 = "07a89bdba247df37fbf439038be83175560f5c8aa4c072cd5d8bae91fda4cedf"
# Earlier builds of TwoHoursCtl.u (published in this repository before v1.0.0):
# install replaces them, uninstall removes them.
OLD_ADDON_SHA256 = (
    "65dafa6384134f4e1b94aee878fdcb87481f0a6415f661b1e90e558d61609dfc",
    "b8973532b6d315d40f78ca6b29634f8a7ffda9ef2ba500454bfe1a3ca1f76fd8",
    "876506e6211751f39a549f8b144fe50e8763e7a3db634d4361e440087ec57089",
    "3f4e692915cc1abdd69104afce7f45b6be1dbde19b60f703b6be1f430735647f",
)

INI_FILE = "XIII.ini"
DEFAULT_INI = "Default.ini"
GAME_ENGINE = "Engine.GameEngine"
ACTOR_LINE = "ServerActors=TwoHoursCtl.TwoHoursCtl"
# The add-on's line goes right after this one (it is in the shipped ini).
ANCHOR_LINE = "ServerActors=IpDrv.UdpServerQuery"
CTL_SECTION = "TwoHoursCtl.TwoHoursCtl"
CTL_PORT = 7098


class Spec:
    """What this release installs. Tests build their own with synthetic files."""

    def __init__(self, patches, addon_data: bytes, addon_sha256: str, old_addons=()):
        self.patches = tuple(patches)
        self.addon_data = addon_data
        self.addon_sha256 = addon_sha256
        self.old_addons = tuple(old_addons)

    def addon_state(self, data: bytes) -> str:
        sha = sha256(data)
        if sha == self.addon_sha256:
            return "current"
        if sha in self.old_addons:
            return "older"
        return UNKNOWN


def default_spec() -> Spec:
    import xiii_bot_patch
    import xiii_clienttravel_patch
    import xiii_engine_patch
    patches = (xiii_engine_patch.PATCHES + xiii_clienttravel_patch.PATCHES
               + xiii_bot_patch.PATCHES)
    dist = HERE / "dist" / ADDON_FILE
    if not dist.is_file():
        raise SystemExit(f"{dist}: not found (run install.py from the unpacked release)")
    data = dist.read_bytes()
    if sha256(data) != ADDON_SHA256:
        raise SystemExit(f"{dist}: sha256 {sha256(data)} is not {ADDON_SHA256}; "
                         "download the release again")
    return Spec(patches, data, ADDON_SHA256, OLD_ADDON_SHA256)


# XIII.ini
# The shipped ini is CRLF, with comments and repeated keys (ServerActors=).
# Every edit below keeps every other byte, and install then uninstall gives
# the same file back.

def _nl(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _section(lines: list, name: str):
    """(header index, end index) of [name], or None."""
    head = f"[{name}]".lower()
    start = next((i for i, l in enumerate(lines) if l.strip().lower() == head), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("[")),
               len(lines))
    return start, end


def get_ini_key(text: str, section: str, key: str):
    """The first live value of `key` in [section], or None. Pure."""
    lines = text.split(_nl(text))
    span = _section(lines, section)
    if span is None:
        return None
    for line in lines[span[0] + 1:span[1]]:
        k, sep, v = line.partition("=")
        if sep and not line.lstrip().startswith(";") and k.strip().lower() == key.lower():
            return v
    return None


def set_ini_key(text: str, section: str, key: str, value: str) -> str:
    """Set key=value in [section]: the first live key line is replaced, a
    missing key goes after the section's last non-blank line, a missing
    section is appended. Pure."""
    if any(c in value for c in "\r\n"):
        raise ValueError(f"ini value for {key} contains a line break")
    nl = _nl(text)
    lines = text.split(nl)
    span = _section(lines, section)
    if span is None:
        body = text if not text or text.endswith(nl) else text + nl
        return f"{body}{nl if body else ''}[{section}]{nl}{key}={value}{nl}"
    start, end = span
    for i in range(start + 1, end):
        k, sep, _ = lines[i].partition("=")
        if sep and not lines[i].lstrip().startswith(";") and k.strip().lower() == key.lower():
            lines[i] = f"{k}={value}"
            return nl.join(lines)
    last = max((i for i in range(start + 1, end) if lines[i].strip()), default=start)
    lines.insert(last + 1, f"{key}={value}")
    return nl.join(lines)


def _is_actor_line(line: str) -> bool:
    return line.strip().lstrip(";").strip().lower() == ACTOR_LINE.lower()


def add_actor_line(text: str) -> str:
    """[Engine.GameEngine] loads the add-on: a live ServerActors line right
    after the UdpServerQuery one (else after the section's last line). A
    commented-out copy is switched back on. Pure, idempotent."""
    nl = _nl(text)
    lines = text.split(nl)
    span = _section(lines, GAME_ENGINE)
    if span is None:
        return set_ini_key(text, GAME_ENGINE, "ServerActors", "TwoHoursCtl.TwoHoursCtl")
    start, end = span
    found = [i for i in range(start + 1, end) if _is_actor_line(lines[i])]
    if found:
        for i in found:
            lines[i] = ACTOR_LINE
        return nl.join(lines)
    anchor = next((i for i in range(start + 1, end)
                   if lines[i].strip().lower() == ANCHOR_LINE.lower()), None)
    if anchor is None:
        anchor = max((i for i in range(start + 1, end) if lines[i].strip()), default=start)
    lines.insert(anchor + 1, ACTOR_LINE)
    return nl.join(lines)


def remove_actor_line(text: str) -> str:
    """Drop every ServerActors=TwoHoursCtl.TwoHoursCtl line (live or
    commented) from [Engine.GameEngine]. Pure."""
    nl = _nl(text)
    lines = text.split(nl)
    span = _section(lines, GAME_ENGINE)
    if span is None:
        return text
    start, end = span
    keep = [l for i, l in enumerate(lines) if not (start < i < end and _is_actor_line(l))]
    return nl.join(keep)


def remove_section(text: str, section: str) -> str:
    """Drop [section] and its lines, plus the blank line right before it. Pure."""
    nl = _nl(text)
    lines = text.split(nl)
    span = _section(lines, section)
    if span is None:
        return text
    start, end = span
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1   # the blank lines after it stay
    if start > 0 and not lines[start - 1].strip():
        start -= 1
    return nl.join(lines[:start] + lines[end:])


def install_ini(text: str, new_key=None) -> str:
    """XIII.ini with the add-on loaded and configured. An existing CtlKey is
    kept; otherwise a new random one (letters and digits) is set. The admin
    password from [Engine.AccessControl] is copied for TwoHoursLogin (the
    game keeps its own copy private to UnrealScript). Pure but for the key."""
    out = add_actor_line(text)
    key = get_ini_key(out, CTL_SECTION, "CtlKey")
    if not key or not key.strip().isalnum():
        key = new_key or secrets.token_hex(16)
    out = set_ini_key(out, CTL_SECTION, "CtlPort", get_ini_key(out, CTL_SECTION, "CtlPort")
                      or str(CTL_PORT))
    out = set_ini_key(out, CTL_SECTION, "CtlKey", key.strip())
    out = set_ini_key(out, CTL_SECTION, "LabInject", "False")
    admin = get_ini_key(out, "Engine.AccessControl", "AdminPassword") or ""
    out = set_ini_key(out, CTL_SECTION, "AdminPassword", admin.strip())
    return out


def uninstall_ini(text: str) -> str:
    return remove_section(remove_actor_line(text), CTL_SECTION)


def ini_installed(text: str) -> bool:
    lines = text.split(_nl(text))
    span = _section(lines, GAME_ENGINE)
    live = span is not None and any(
        lines[i].strip().lower() == ACTOR_LINE.lower() for i in range(span[0] + 1, span[1]))
    key = get_ini_key(text, CTL_SECTION, "CtlKey")
    return live and bool(key and key.strip().isalnum())


# The server folder

def find_system(path: Path) -> Path:
    path = Path(path)
    if (path / "System").is_dir():
        return path / "System"
    if path.is_dir() and ((path / "UCC.exe").exists() or (path / "Engine.dll").exists()):
        return path
    raise FileNotFoundError(f"{path}: no System folder with the XIII server files")


def read_ini(system: Path):
    """(text, source file name) of XIII.ini, or of Default.ini when the
    server has not created XIII.ini yet (UCC copies it on first run)."""
    for name in (INI_FILE, DEFAULT_INI):
        p = system / name
        if p.is_file():
            return p.read_bytes().decode("latin-1"), name
    return None, None


def inspect(system: Path, spec: Spec) -> list:
    """[(file name, state, sha256 or '')] for every patched file and the add-on."""
    rows = []
    for p in spec.patches:
        path = system / p.filename
        if not path.is_file():
            rows.append((p.filename, MISSING, ""))
            continue
        data = path.read_bytes()
        rows.append((p.filename, p.state(data), sha256(data)))
    addon = system / ADDON_FILE
    if addon.is_file():
        data = addon.read_bytes()
        rows.append((ADDON_FILE, spec.addon_state(data), sha256(data)))
    else:
        rows.append((ADDON_FILE, "absent", ""))
    return rows


def _blocking(rows: list) -> int:
    """Exit code for the rows: 2 when a game file is missing, 1 when one is
    unknown, else 0."""
    if any(s == MISSING for _, s, _ in rows):
        return 2
    if any(s == UNKNOWN for _, s, _ in rows):
        return 1
    return 0


def _print_rows(rows: list, spec: Spec, action: str) -> None:
    what = {
        ("install", ORIGINAL): "will be patched (original kept as .orig)",
        ("install", PATCHED): "already patched, left as is",
        ("install", "absent"): "will be copied",
        ("install", "older"): "older build, will be replaced",
        ("install", "current"): "already installed",
        ("uninstall", ORIGINAL): "already original, left as is",
        ("uninstall", PATCHED): "will be restored to the original",
        ("uninstall", "absent"): "not installed",
        ("uninstall", "older"): "will be removed",
        ("uninstall", "current"): "will be removed",
    }
    for name, state, sha in rows:
        if state == UNKNOWN:
            note = "UNKNOWN build: refused, nothing will be changed"
        elif state == MISSING:
            note = "MISSING"
        else:
            note = what[(action, state)]
        print(f"  {name:<14} {state:<9} {sha or '-':<64}  {note}")


def _ini_plan(system: Path, action: str):
    """(path to write, current text, new text) for XIII.ini, or None."""
    text, source = read_ini(system)
    if text is None:
        return None
    new = install_ini(text) if action == "install" else uninstall_ini(text)
    if action == "uninstall" and source != INI_FILE:
        return None
    return system / INI_FILE, (text if source == INI_FILE else None), new


def _print_ini(plan, action: str) -> None:
    if plan is None:
        print(f"  {INI_FILE}: not found" + (", nothing to do" if action == "uninstall" else
                                            " (neither XIII.ini nor Default.ini)"))
        return
    path, old, new = plan
    if old is None:
        print(f"  {INI_FILE}: will be created from {DEFAULT_INI} with the add-on lines")
    elif old == new:
        print(f"  {INI_FILE}: " + ("add-on lines already in place" if action == "install"
                                   else "no add-on lines"))
    elif action == "install":
        print(f"  {INI_FILE}: will get [{GAME_ENGINE}] {ACTOR_LINE} and a [{CTL_SECTION}] "
              f"section (CtlPort, CtlKey, LabInject, AdminPassword); "
              f"original kept as {INI_FILE}.orig")
    else:
        print(f"  {INI_FILE}: the {ACTOR_LINE} line and the [{CTL_SECTION}] section "
              "will be removed")


def check(system: Path, spec: Spec) -> int:
    rows = inspect(system, spec)
    print(f"{system}:")
    _print_rows(rows, spec, "install")
    _print_ini(_ini_plan(system, "install"), "install")
    code = _blocking(rows)
    if code == 1:
        print("An unknown file is not the build this patch was made for. install will refuse.")
    elif code == 2:
        print("A server file is missing. install will refuse.")
    return code


def install(system: Path, spec: Spec, dry_run: bool = False) -> int:
    rows = inspect(system, spec)
    print(f"{system}:")
    _print_rows(rows, spec, "install")
    ini = _ini_plan(system, "install")
    _print_ini(ini, "install")
    code = _blocking(rows)
    if code:
        print("Refused: nothing was changed.")
        return code
    if ini is None:
        print(f"Refused: no {INI_FILE} or {DEFAULT_INI} in {system}. Nothing was changed.")
        return 2
    if dry_run:
        print("Dry run: nothing was changed.")
        return 0
    for p in spec.patches:   # in order: XIIIMP.dll before XIIIMP.u
        path = system / p.filename
        data = path.read_bytes()
        if p.state(data) != ORIGINAL:
            continue
        backup = binpatch.backup_path(path)
        if not backup.exists():
            backup.write_bytes(data)
        binpatch.write_atomic(path, p.apply(data))
    addon = system / ADDON_FILE
    if not addon.is_file() or sha256(addon.read_bytes()) != spec.addon_sha256:
        binpatch.write_atomic(addon, spec.addon_data)
    path, old, new = ini
    if old is None or old != new:
        backup = path.with_name(INI_FILE + ".orig")
        if old is not None and not backup.exists():
            backup.write_bytes(old.encode("latin-1"))
        binpatch.write_atomic(path, new.encode("latin-1"))
    return verify(system, spec)


def verify(system: Path, spec: Spec) -> int:
    """Print each file's sha256 next to the expected one. 0 when all match."""
    print("\nResult (sha256):")
    bad = 0
    expected = [(p.filename, p.patched_sha256) for p in spec.patches]
    expected.append((ADDON_FILE, spec.addon_sha256))
    for name, want in expected:
        path = system / name
        got = sha256(path.read_bytes()) if path.is_file() else "missing"
        ok = got == want
        bad += not ok
        print(f"  {name:<14} {got:<64}  {'OK' if ok else 'EXPECTED ' + want}")
    text, source = read_ini(system)
    ok = source == INI_FILE and ini_installed(text)
    bad += not ok
    print(f"  {INI_FILE:<14} {'add-on lines in place' if ok else 'add-on lines MISSING'}")
    if not bad:
        key = get_ini_key(text, CTL_SECTION, "CtlKey")
        print(f"\nInstalled. The add-on listens on UDP 127.0.0.1:{CTL_PORT} with the CtlKey "
              f"in {INI_FILE} [{CTL_SECTION}].")
        print(f"Try it once the server runs: python3 tools/xiii_ctl.py --key {key} status")
    return 3 if bad else 0


def uninstall(system: Path, spec: Spec, dry_run: bool = False) -> int:
    rows = inspect(system, spec)
    print(f"{system}:")
    _print_rows(rows, spec, "uninstall")
    ini = _ini_plan(system, "uninstall")
    _print_ini(ini, "uninstall")
    if any(s == UNKNOWN for n, s, _ in rows if n != ADDON_FILE):
        print("Refused: an unknown file cannot be restored. Nothing was changed.")
        return 1
    if dry_run:
        print("Dry run: nothing was changed.")
        return 0
    for p in reversed(spec.patches):   # XIIIMP.u before XIIIMP.dll
        path = system / p.filename
        if not path.is_file() or p.state(path.read_bytes()) != PATCHED:
            continue
        backup = binpatch.backup_path(path)
        if backup.is_file() and sha256(backup.read_bytes()) == p.original_sha256:
            os.replace(str(backup), str(path))
        else:
            binpatch.write_atomic(path, p.revert(path.read_bytes()))
    addon = system / ADDON_FILE
    if addon.is_file():
        if spec.addon_state(addon.read_bytes()) == UNKNOWN:
            print(f"  {ADDON_FILE}: unknown build, left in place")
        else:
            addon.unlink()
    if ini is not None:
        path, old, new = ini
        if old != new:
            binpatch.write_atomic(path, new.encode("latin-1"))
    print("\nResult (sha256):")
    code = 0
    for p in spec.patches:
        path = system / p.filename
        got = sha256(path.read_bytes()) if path.is_file() else "missing"
        ok = got == p.original_sha256
        code = code or (0 if ok else 3)
        print(f"  {p.filename:<14} {got:<64}  {'OK' if ok else 'EXPECTED ' + p.original_sha256}")
    print(f"  {ADDON_FILE:<14} {'still present' if addon.exists() else 'removed'}")
    return code


def main(argv=None, spec: Spec = None) -> int:
    ap = argparse.ArgumentParser(
        description="XIII server patch: live map changes, bots and admin commands.",
        epilog="Exit codes: 0 done, 1 unknown file, 2 missing file, 3 wrong sha256 after.")
    ap.add_argument("action", choices=("check", "install", "uninstall"))
    ap.add_argument("xiii_dir", type=Path, help="the server folder, or its System folder")
    ap.add_argument("--dry-run", action="store_true", help="print what would change, change nothing")
    a = ap.parse_args(argv)
    try:
        system = find_system(a.xiii_dir)
    except FileNotFoundError as e:
        print(e)
        return 2
    spec = spec or default_spec()
    if a.action == "check":
        return check(system, spec)
    if a.action == "install":
        return install(system, spec, a.dry_run)
    return uninstall(system, spec, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
