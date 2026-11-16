#!/usr/bin/env python3
"""Compile TwoHoursCtl/Classes/*.uc into TwoHoursCtl.u.

The XIII dedicated-server archive cannot compile UnrealScript: its Core.u and
Engine.u ship without source text, and XIII's `UCC make` re-parses every
loaded class from its source text. So the build borrows the CLIENT toolchain
from the community patch (UCC.exe, the DLLs and the .u files with source
text), the same files every XIII player installs:

  Classic_XIII___Patch_by_Arthur_v1.4.2.1_2019-09-04.exe   (NSIS installer)
  https://xiii.opaquit.com/downloads-2020/Classic_XIII___Patch_by_Arthur_v1.4.2.1_2019-09-04.exe
  sha256 4cd267d92353ffd99894d65794fc8f50b8a387476b2cac3dfd42d2f78866d0c7
  unpack with `7zz x <exe>`: the game's System files land in Dir/

Even the client's IpDrv.u is stripped, so stubs/*.uc (declaration-only text
matching the compiled classes) are injected into a SCRATCH copy of IpDrv.u
(upkg.py). Nothing from the patch is shipped: the output is our own
TwoHoursCtl.u, which imports Core/Engine/IpDrv by name and runs against the
server's own packages.

A few runtime files the patch lacks come from the server's System dir
(--server-system): the MSVC 7.0 runtime, binkw32.dll, DefUser.ini and the
.int files.

Run it where Wine (32-bit prefix) and 7-Zip are:

  python3 build/build_ctl.py --client-dir <patch>/Dir --server-system <server>/System \
      --work /tmp/xiii-ctl-build --out dist/TwoHoursCtl.u

The make log is printed; the build fails unless UCC reports success and the .u
exists. The .u carries its own source text, so `--verify dist/TwoHoursCtl.u`
(no Wine needed) checks a package was built from the current .uc.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from upkg import inject_script_text  # noqa: E402

PACKAGE = "TwoHoursCtl"
PATCH_SHA256 = "4cd267d92353ffd99894d65794fc8f50b8a387476b2cac3dfd42d2f78866d0c7"
# Load order for `UCC make`: our package needs Core, Engine (wUtils comes
# before Engine in the shipped list) and IpDrv.
EDIT_PACKAGES = ("Core", "wUtils", "Engine", "IpDrv", PACKAGE)
# Runtime files the client patch does not carry, taken from the server.
FROM_SERVER = ("msvci70.dll", "msvcr70.dll", "binkw32.dll", "DefUser.ini",
               "Core.int", "Editor.int", "IpDrv.int")
IPDRV_STUBS = ("InternetLink", "UdpLink", "TcpLink", "UdpBeacon", "UdpServerQuery",
               "ClientBeaconReceiver", "XBOXServerBeacon", "XBOXClientBeaconReceiver",
               "RegisterServerToUbiCom")


def make_ini(default_ini: str, packages=EDIT_PACKAGES) -> str:
    """Default.ini with its EditPackages list replaced by `packages` (at the
    position of the first EditPackages line). CRLF, like the shipped ini."""
    out, done = [], False
    for line in default_ini.replace("\r\n", "\n").split("\n"):
        if line.startswith("EditPackages="):
            if not done:
                out.extend(f"EditPackages={p}" for p in packages)
                done = True
            continue
        out.append(line)
    if not done:
        out += ["[Editor.EditorEngine]"] + [f"EditPackages={p}" for p in packages]
    return "\r\n".join(out)


def stub_texts(stub_dir: Path = HERE / "stubs") -> dict[str, str]:
    return {name: (stub_dir / f"{name}.uc").read_text() for name in IPDRV_STUBS}


def prepare(client_dir: Path, server_system: Path, work: Path) -> Path:
    """Lay out the build tree; return its System dir."""
    if work.exists():
        shutil.rmtree(work)
    system = work / "System"
    shutil.copytree(client_dir, system,
                    ignore=shutil.ignore_patterns("._*", ".DS_Store"))
    for name in FROM_SERVER:
        if not (system / name).exists():
            shutil.copy2(server_system / name, system / name)
    ipdrv = system / "IpDrv.u"
    ipdrv.write_bytes(inject_script_text(ipdrv.read_bytes(), stub_texts()))
    (system / "XIII.ini").write_text(
        make_ini((system / "Default.ini").read_text(encoding="latin-1")),
        encoding="latin-1", newline="")
    classes = work / PACKAGE / "Classes"
    shutil.copytree(HERE.parent / PACKAGE / "Classes", classes)
    stale = system / f"{PACKAGE}.u"
    stale.unlink(missing_ok=True)
    return system


def run_make(system: Path) -> str:
    env = {**os.environ, "WINEDEBUG": "-all"}
    env.setdefault("WINEPREFIX", "/wine")
    r = subprocess.run(["wine", "UCC.exe", "make", "-silent"], cwd=system, env=env,
                       capture_output=True, text=True, errors="replace", timeout=600)
    log = (r.stdout + r.stderr).replace("\r", "")
    if r.returncode != 0 or "Success - 0 error(s)" not in log:
        raise SystemExit(f"UCC make failed (exit {r.returncode}):\n{log}")
    return log


def verify(package: Path) -> None:
    """Fail unless `package` was compiled from the current Classes/*.uc.
    UCC stores each class source as ScriptText, minus defaultproperties."""
    from upkg import Package
    pkg = Package(package.read_bytes())
    for path in sorted((HERE.parent / PACKAGE / "Classes").glob("*.uc")):
        embedded = pkg.script_text(path.stem).replace("\r\n", "\n")
        src = path.read_text()
        if embedded.rstrip() != src[:src.index("defaultproperties")].rstrip():
            raise SystemExit(f"{package} was NOT built from the current {path.name}")
        print(f"{package}: {path.stem} built from the current {path.name}")
    print(f"{package}: sha256 {hashlib.sha256(package.read_bytes()).hexdigest()}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verify", type=Path, metavar="PACKAGE",
                    help="only check that PACKAGE was built from the current .uc, then exit")
    ap.add_argument("--client-dir", type=Path,
                    help="Dir/ unpacked from the 1.4.2.1 patch installer")
    ap.add_argument("--server-system", type=Path,
                    help="System/ of the XIII server archive")
    ap.add_argument("--work", type=Path, help="scratch build dir (wiped)")
    ap.add_argument("--out", type=Path, default=HERE.parent / "dist" / f"{PACKAGE}.u",
                    help="where to write the built .u (default dist/TwoHoursCtl.u)")
    ap.add_argument("--patch-exe", type=Path,
                    help="optional: the patch .exe, checked against the pinned sha256")
    a = ap.parse_args(argv)
    if a.verify:
        verify(a.verify)
        return
    if not (a.client_dir and a.server_system and a.work):
        ap.error("--client-dir, --server-system and --work are required to build")
    if a.patch_exe:
        got = hashlib.sha256(a.patch_exe.read_bytes()).hexdigest()
        if got != PATCH_SHA256:
            raise SystemExit(f"patch sha256 {got} != pinned {PATCH_SHA256}")
    system = prepare(a.client_dir, a.server_system, a.work)
    log = run_make(system)
    print(log)
    built = system / f"{PACKAGE}.u"
    if not built.is_file():
        raise SystemExit(f"{built} was not produced")
    raw = built.read_bytes()
    shutil.copy2(built, a.out)
    print(f"{a.out}: sha256 {hashlib.sha256(raw).hexdigest()} ({len(raw)} bytes)")


if __name__ == "__main__":
    main()
