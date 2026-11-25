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
