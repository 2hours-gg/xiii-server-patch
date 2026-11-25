import contextlib
import io
import unittest

from _helpers import ROOT

import build_ctl
import upkg
import xiii_ctl
import xiii_netclient


class AddonPackageTest(unittest.TestCase):
    """dist/TwoHoursCtl.u carries the source text of every class it was
    compiled from: it must match TwoHoursCtl/Classes/*.uc."""

    def test_dist_built_from_current_sources(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            build_ctl.verify(ROOT / "dist" / "TwoHoursCtl.u")
        for cls in ("TwoHoursCtl", "TwoHoursChat", "TwoHoursLogin"):
            self.assertIn(f"{cls} built from the current {cls}.uc", buf.getvalue())

    def test_compact_index_round_trip(self):
        for v in (0, 1, 63, 64, -64, 8191, 8192, 1 << 20, -(1 << 26), (1 << 31) - 1):
            enc = upkg.write_ci(v)
            self.assertEqual(upkg.read_ci(enc, 0), (v, len(enc)), v)


class ReproducibleBuildTest(unittest.TestCase):
    def setUp(self):
        self.dist = (ROOT / "dist" / "TwoHoursCtl.u").read_bytes()

    def test_dist_is_a_reproducible_build(self):
        self.assertEqual(upkg.guid(self.dist), build_ctl.expected_guid(),
                         "dist/TwoHoursCtl.u does not carry the GUID derived from the sources")

    def test_guid_is_the_only_change(self):
        g = bytes(16)
        out = upkg.with_guid(self.dist, g)
        self.assertEqual(upkg.guid(out), g)
        diff = upkg.differences(self.dist, out)
        self.assertTrue(diff)
        self.assertTrue(all(upkg.GUID_OFFSET <= off < upkg.GUID_OFFSET + 16 for off, _, _ in diff))
        self.assertEqual(upkg.differences(self.dist, out, ignore_guid=True), [])
        pkg = upkg.Package(out)   # still a readable package
        self.assertIn("TwoHoursCtl", pkg.names)

    def test_source_guid_depends_on_every_input(self):
        classes = {"A.uc": b"class A;\r\n", "B.uc": b"class B;\n"}
        stubs = {"UdpLink": "class UdpLink;"}
        g = build_ctl.source_guid(classes, stubs)
        self.assertEqual(len(g), 16)
        self.assertEqual(g, build_ctl.source_guid(dict(reversed(list(classes.items()))), stubs))
        # LF and CRLF read the same (UCC reads CRLF)
        self.assertEqual(g, build_ctl.source_guid({"A.uc": b"class A;\n", "B.uc": b"class B;\r\n"}, stubs))
        self.assertNotEqual(g, build_ctl.source_guid({**classes, "B.uc": b"class B2;\n"}, stubs))
        self.assertNotEqual(g, build_ctl.source_guid(classes, {"UdpLink": "class UdpLink2;"}))
        self.assertNotEqual(g, build_ctl.source_guid(classes, stubs, toolchain_sha256="0" * 64))

    def test_compare_exit_codes(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            a, b, c = Path(d, "a.u"), Path(d, "b.u"), Path(d, "c.u")
            a.write_bytes(self.dist)
            b.write_bytes(upkg.with_guid(self.dist, bytes(16)))
            c.write_bytes(self.dist[:-1] + bytes([self.dist[-1] ^ 1]))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(build_ctl.compare(a, a), 0)
                self.assertEqual(build_ctl.compare(a, b), 1)
                self.assertEqual(build_ctl.compare(a, c), 2)


class CtlClientTest(unittest.TestCase):
    def test_tell_puts_a_tab_after_the_name(self):
        self.assertEqual(xiii_ctl.build_command(["tell", "Boss", "hello", "there"]),
                         "tell Boss\thello there")

    def test_other_commands_joined(self):
        self.assertEqual(xiii_ctl.build_command(["travel", "4", "DM_Pal.unr?Game=X"]),
                         "travel 4 DM_Pal.unr?Game=X")


class NetClientTest(unittest.TestCase):
    def test_follow_url_keeps_player_options(self):
        self.assertEqual(xiii_netclient.follow_url("DM_Amos.unr?Name=t?Password=lab", "DM_Pal"),
                         "DM_Pal.unr?Name=t?Password=lab")
        self.assertEqual(xiii_netclient.follow_url("DM_Amos.unr", "CTF_Base.unr"), "CTF_Base.unr")

    def test_challenge_response_is_int32(self):
        for c in (0, 1, 0x7FFFFFFF, 0x12345678):
            r = xiii_netclient.challenge_response(c)
            self.assertTrue(-(1 << 31) <= r < (1 << 31))


if __name__ == "__main__":
    unittest.main()
