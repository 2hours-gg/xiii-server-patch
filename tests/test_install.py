import unittest

from _helpers import CRLF_INI, ServerDir, quiet, synthetic_spec

import install
from binpatch import sha256


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.spec, self.orig, self.patched = synthetic_spec()
        self.dir = ServerDir(self.orig)
        self.addCleanup(self.dir.cleanup)

    def run_main(self, *argv):
        return quiet(install.main, list(argv), spec=self.spec)

    def test_check_original_files(self):
        before = self.dir.snapshot()
        code, out = self.run_main("check", str(self.dir.root))
        self.assertEqual(code, 0)
        self.assertIn("will be patched", out)
        self.assertEqual(self.dir.snapshot(), before)

    def test_check_unknown_exits_1(self):
        (self.dir.system / "Engine.u").write_bytes(b"not the known build")
        code, out = self.run_main("check", str(self.dir.root))
        self.assertEqual(code, 1)
        self.assertIn("UNKNOWN", out)

    def test_check_missing_exits_2(self):
        (self.dir.system / "Engine.dll").unlink()
        code, _ = self.run_main("check", str(self.dir.system))
        self.assertEqual(code, 2)

    def test_install(self):
        code, out = self.run_main("install", str(self.dir.root))
        self.assertEqual(code, 0, out)
        for name, data in self.patched.items():
            self.assertEqual(self.dir.read(name), data, name)
            self.assertEqual(self.dir.read(name + ".orig"), self.orig[name], name)
        self.assertEqual(self.dir.read("TwoHoursCtl.u"), self.spec.addon_data)
        ini = self.dir.read("XIII.ini").decode("latin-1")
        self.assertTrue(install.ini_installed(ini))
        self.assertEqual(self.dir.read("XIII.ini.orig"), CRLF_INI.encode("latin-1"))
        self.assertNotIn("\n", ini.replace("\r\n", ""))   # still CRLF only
        self.assertEqual(install.get_ini_key(ini, "TwoHoursCtl.TwoHoursCtl", "AdminPassword"),
                         "silenteagle42")
        for name in self.patched:
            self.assertIn(f"{sha256(self.patched[name])}  OK", out)

    def test_install_is_idempotent(self):
        self.run_main("install", str(self.dir.root))
        first = self.dir.snapshot()
        code, out = self.run_main("install", str(self.dir.root))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.dir.snapshot(), first)   # the CtlKey is kept too
        self.assertIn("already patched", out)

    def test_dry_run_changes_nothing(self):
        before = self.dir.snapshot()
        code, out = self.run_main("install", "--dry-run", str(self.dir.root))
        self.assertEqual(code, 0)
        self.assertIn("Dry run", out)
        self.assertEqual(self.dir.snapshot(), before)

    def test_refuses_when_one_file_is_unknown(self):
        (self.dir.system / "XIIIMP.u").write_bytes(b"modded")
        before = self.dir.snapshot()
        code, out = self.run_main("install", str(self.dir.root))
        self.assertEqual(code, 1)
        self.assertIn("Refused", out)
        self.assertEqual(self.dir.snapshot(), before)

    def test_refuses_unknown_addon(self):
        (self.dir.system / "TwoHoursCtl.u").write_bytes(b"someone else's build")
        before = self.dir.snapshot()
        code, _ = self.run_main("install", str(self.dir.root))
        self.assertEqual(code, 1)
        self.assertEqual(self.dir.snapshot(), before)

    def test_replaces_older_addon(self):
        (self.dir.system / "TwoHoursCtl.u").write_bytes(self.spec.older_bytes)
        code, out = self.run_main("install", str(self.dir.root))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.dir.read("TwoHoursCtl.u"), self.spec.addon_data)

    def test_partly_patched_server(self):
        (self.dir.system / "Engine.dll").write_bytes(self.patched["Engine.dll"])
        code, out = self.run_main("install", str(self.dir.root))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.dir.read("Engine.dll"), self.patched["Engine.dll"])
        self.assertFalse((self.dir.system / "Engine.dll.orig").exists())

    def test_creates_xiii_ini_from_default_ini(self):
        d = ServerDir(self.orig, ini_name="Default.ini")
        self.addCleanup(d.cleanup)
        code, out = quiet(install.main, ["install", str(d.root)], spec=self.spec)
        self.assertEqual(code, 0, out)
        self.assertEqual(d.read("Default.ini"), CRLF_INI.encode("latin-1"))
        self.assertTrue(install.ini_installed(d.read("XIII.ini").decode("latin-1")))

    def test_uninstall_restores_everything(self):
        before = self.dir.snapshot()
        self.run_main("install", str(self.dir.root))
        code, out = self.run_main("uninstall", str(self.dir.root))
        self.assertEqual(code, 0, out)
        after = self.dir.snapshot()
        after.pop("XIII.ini.orig")   # the ini backup is kept
        self.assertEqual(after, before)

    def test_uninstall_without_backups_reverts_bytes(self):
        self.run_main("install", str(self.dir.root))
        for name in self.orig:
            (self.dir.system / (name + ".orig")).unlink()
        code, out = self.run_main("uninstall", str(self.dir.root))
        self.assertEqual(code, 0, out)
        for name, data in self.orig.items():
            self.assertEqual(self.dir.read(name), data)

    def test_uninstall_dry_run(self):
        self.run_main("install", str(self.dir.root))
        before = self.dir.snapshot()
        code, _ = self.run_main("uninstall", "--dry-run", str(self.dir.root))
        self.assertEqual(code, 0)
        self.assertEqual(self.dir.snapshot(), before)

    def test_uninstall_refuses_unknown(self):
        self.run_main("install", str(self.dir.root))
        (self.dir.system / "Engine.u").write_bytes(b"changed after install")
        before = self.dir.snapshot()
        code, _ = self.run_main("uninstall", str(self.dir.root))
        self.assertEqual(code, 1)
        self.assertEqual(self.dir.snapshot(), before)

    def test_not_a_server_folder(self):
        code, out = quiet(install.main, ["check", str(self.dir.root / "nope")], spec=self.spec)
        self.assertEqual(code, 2)


class ReleaseSpecTest(unittest.TestCase):
    def test_default_spec_matches_dist(self):
        spec = install.default_spec()
        self.assertEqual(sha256(spec.addon_data), install.ADDON_SHA256)
        self.assertEqual([p.filename for p in spec.patches],
                         ["Engine.dll", "Engine.u", "XIIIMP.dll", "XIIIMP.u"])


class IniTest(unittest.TestCase):
    def test_actor_line_after_the_query_actor(self):
        out = install.add_actor_line(CRLF_INI)
        self.assertIn("ServerActors=IpDrv.UdpServerQuery\r\n"
                      "ServerActors=TwoHoursCtl.TwoHoursCtl\r\n"
                      "ServerPackages=XIIIMP\r\n", out)
        self.assertEqual(install.add_actor_line(out), out)

    def test_commented_actor_line_switched_on(self):
        text = CRLF_INI.replace("ServerPackages=XIIIMP\r\n",
                                "ServerPackages=XIIIMP\r\n;ServerActors=TwoHoursCtl.TwoHoursCtl\r\n")
        out = install.add_actor_line(text)
        self.assertEqual(out.count("TwoHoursCtl.TwoHoursCtl"), 1)
        self.assertIn("\r\nServerActors=TwoHoursCtl.TwoHoursCtl\r\n", out)

    def test_install_ini_keeps_key_and_round_trips(self):
        out = install.install_ini(CRLF_INI, new_key="abc123")
        self.assertEqual(install.get_ini_key(out, "TwoHoursCtl.TwoHoursCtl", "CtlKey"), "abc123")
        self.assertEqual(install.get_ini_key(out, "TwoHoursCtl.TwoHoursCtl", "CtlPort"), "7098")
        self.assertEqual(install.get_ini_key(out, "TwoHoursCtl.TwoHoursCtl", "LabInject"), "False")
        self.assertEqual(install.install_ini(out, new_key="other"), out)
        self.assertTrue(out.endswith("\r\n"))
        self.assertEqual(install.uninstall_ini(out), CRLF_INI)

    def test_random_key_is_alphanumeric(self):
        out = install.install_ini(CRLF_INI)
        key = install.get_ini_key(out, "TwoHoursCtl.TwoHoursCtl", "CtlKey")
        self.assertTrue(key.isalnum() and len(key) >= 16)

    def test_bad_key_is_replaced(self):
        text = CRLF_INI + "\r\n[TwoHoursCtl.TwoHoursCtl]\r\nCtlKey=has space\r\n"
        out = install.install_ini(text, new_key="good1")
        self.assertEqual(install.get_ini_key(out, "TwoHoursCtl.TwoHoursCtl", "CtlKey"), "good1")

    def test_lf_ini_stays_lf(self):
        lf = CRLF_INI.replace("\r\n", "\n")
        out = install.install_ini(lf, new_key="k1")
        self.assertNotIn("\r", out)
        self.assertEqual(install.uninstall_ini(out), lf)

    def test_uninstall_keeps_bot_settings_section_out(self):
        text = install.install_ini(CRLF_INI, new_key="k1")
        text = install.set_ini_key(text, "TwoHoursCtl.TwoHoursCtl", "BotTarget", "4")
        self.assertEqual(install.uninstall_ini(text), CRLF_INI)

    def test_section_in_the_middle_removed_cleanly(self):
        text = CRLF_INI.replace("\r\n[Engine.AccessControl]",
                                "\r\n[TwoHoursCtl.TwoHoursCtl]\r\nCtlKey=k1\r\n\r\n[Engine.AccessControl]")
        self.assertEqual(install.remove_section(text, "TwoHoursCtl.TwoHoursCtl"), CRLF_INI)

    def test_no_admin_password(self):
        text = CRLF_INI.replace("AdminPassword=silenteagle42\r\n", "")
        out = install.install_ini(text, new_key="k1")
        self.assertEqual(install.get_ini_key(out, "TwoHoursCtl.TwoHoursCtl", "AdminPassword"), "")


if __name__ == "__main__":
    unittest.main()
