import unittest

from _helpers import ServerDir, quiet, synthetic_spec

import binpatch
import xiii_bot_patch
import xiii_clienttravel_patch
import xiii_engine_patch
from binpatch import ORIGINAL, PATCHED, UNKNOWN, FilePatch, sha256


class FilePatchTest(unittest.TestCase):
    def setUp(self):
        self.spec, self.orig, self.patched = synthetic_spec()
        self.engine = self.spec.patches[0]

    def test_apply_and_revert_round_trip(self):
        data = self.orig["Engine.dll"]
        out = self.engine.apply(data)
        self.assertEqual(out, self.patched["Engine.dll"])
        self.assertEqual(self.engine.state(out), PATCHED)
        self.assertEqual(self.engine.revert(out), data)
        self.assertEqual(self.engine.state(data), ORIGINAL)

    def test_unknown_file_is_refused(self):
        data = bytearray(self.orig["Engine.dll"])
        data[0] ^= 0xFF
        self.assertEqual(self.engine.state(bytes(data)), UNKNOWN)
        with self.assertRaises(ValueError):
            self.engine.apply(bytes(data))
        with self.assertRaises(ValueError):
            self.engine.revert(bytes(data))

    def test_applying_twice_is_refused(self):
        with self.assertRaises(ValueError):
            self.engine.apply(self.patched["Engine.dll"])

    def test_edit_must_keep_the_length(self):
        with self.assertRaises(ValueError):
            FilePatch("x", "0" * 64, "1" * 64, ((0, b"\x00", b"\x00\x00"),))

    def test_wrong_bytes_at_offset_detected(self):
        bad = FilePatch("Engine.dll", self.engine.original_sha256, self.engine.patched_sha256,
                        ((0x10, b"\xaa", b"\xbb"),))
        with self.assertRaises(ValueError):
            bad.apply(self.orig["Engine.dll"])


class RealTablesTest(unittest.TestCase):
    """The pinned tables for the real files: well formed, and the sizes the
    README states."""

    ALL = xiii_engine_patch.PATCHES + xiii_clienttravel_patch.PATCHES + xiii_bot_patch.PATCHES

    def test_tables_well_formed(self):
        for p in self.ALL:
            for sha in (p.original_sha256, p.patched_sha256):
                self.assertRegex(sha, r"^[0-9a-f]{64}$")
            self.assertNotEqual(p.original_sha256, p.patched_sha256)
            for off, old, new in p.edits:
                self.assertEqual(len(old), len(new))
                self.assertNotEqual(old, new)
                self.assertLess(off + len(old), p.size)

    def test_bytes_changed(self):
        got = {p.filename: (p.bytes_changed, sum(len(o) for _, o, _ in p.edits)) for p in self.ALL}
        self.assertEqual(got, {"Engine.dll": (6, 7), "Engine.u": (1, 1),
                               "XIIIMP.dll": (20, 32), "XIIIMP.u": (1, 1)})

    def test_bot_patch_order_dll_first(self):
        self.assertEqual([p.filename for p in xiii_bot_patch.PATCHES], ["XIIIMP.dll", "XIIIMP.u"])


class CliTest(unittest.TestCase):
    def setUp(self):
        self.spec, self.orig, self.patched = synthetic_spec()
        self.dir = ServerDir(self.orig)
        self.addCleanup(self.dir.cleanup)
        self.bots = self.spec.patches[2:]

    def run_cli(self, *argv):
        return quiet(binpatch.cli, list(argv), self.bots, xiii_bot_patch.__doc__, "Bots stay off.")

    def test_apply_check_revert(self):
        code, out = self.run_cli("check", str(self.dir.system))
        self.assertEqual(code, 0)
        self.assertEqual(self.dir.read("XIIIMP.u"), self.orig["XIIIMP.u"])
        code, out = self.run_cli("apply", str(self.dir.system))
        self.assertEqual(code, 0)
        for name in ("XIIIMP.dll", "XIIIMP.u"):
            self.assertEqual(self.dir.read(name), self.patched[name])
            self.assertEqual(self.dir.read(name + ".orig"), self.orig[name])
        code, out = self.run_cli("apply", str(self.dir.system))
        self.assertEqual(code, 0)
        self.assertIn("nothing to do", out)
        code, out = self.run_cli("revert", str(self.dir.system))
        self.assertEqual(code, 0)
        for name in ("XIIIMP.dll", "XIIIMP.u"):
            self.assertEqual(self.dir.read(name), self.orig[name])

    def test_unknown_exit_1_and_untouched(self):
        (self.dir.system / "XIIIMP.u").write_bytes(b"something else")
        code, out = self.run_cli("apply", str(self.dir.system))
        self.assertEqual(code, 1)
        self.assertEqual(self.dir.read("XIIIMP.dll"), self.orig["XIIIMP.dll"])
        self.assertFalse((self.dir.system / "XIIIMP.dll.orig").exists())

    def test_missing_exit_2(self):
        (self.dir.system / "XIIIMP.dll").unlink()
        code, _ = self.run_cli("check", str(self.dir.system))
        self.assertEqual(code, 2)

    def test_usage_exit_2(self):
        code, out = self.run_cli("frobnicate")
        self.assertEqual(code, 2)
        self.assertIn("apply", out)


if __name__ == "__main__":
    unittest.main()
