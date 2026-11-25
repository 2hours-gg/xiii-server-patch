"""The published hashes agree with the code, and the text follows the house style."""
import unittest

from _helpers import ROOT

import install
import xiii_bot_patch
import xiii_clienttravel_patch
import xiii_engine_patch
from binpatch import sha256

TEXT_SUFFIXES = {".md", ".py", ".uc", ".yml", ".txt"}


def text_files():
    skip = {".git", "__pycache__"}
    for p in sorted(ROOT.rglob("*")):
        if p.is_file() and p.suffix in TEXT_SUFFIXES and not skip & set(p.parts):
            yield p


class DocsTest(unittest.TestCase):
    def setUp(self):
        self.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    def test_readme_lists_every_pinned_hash(self):
        for p in xiii_engine_patch.PATCHES + xiii_clienttravel_patch.PATCHES + xiii_bot_patch.PATCHES:
            self.assertIn(p.original_sha256, self.readme, p.filename)
            self.assertIn(p.patched_sha256, self.readme, p.filename)
            self.assertIn(f"`{p.filename}` ({p.size})", self.readme)

    def test_addon_hash_everywhere(self):
        dist = (ROOT / "dist" / "TwoHoursCtl.u").read_bytes()
        self.assertEqual(sha256(dist), install.ADDON_SHA256)
        self.assertIn(install.ADDON_SHA256, self.readme)
        self.assertIn(install.ADDON_SHA256, self.changelog)
        self.assertIn(f"`TwoHoursCtl.u` ({len(dist)})", self.readme)

    def test_no_dashes_and_no_old_name(self):
        for p in text_files():
            text = p.read_text(encoding="utf-8")
            for ch in (chr(0x2013), chr(0x2014)):
                self.assertNotIn(ch, text, f"{p.name} has an en or em dash")
            self.assertNotIn("xiii-server-" + "mapchange", text, p.name)


if __name__ == "__main__":
    unittest.main()
