import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import root_helper as rh


class SystemThemeTests(unittest.TestCase):
    def test_apply_update_remove_and_cannot_touch_modified_theme(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            dest = base / 'usr/local/share/themes/TokyoAdwaita-Night'
            source = base / 'original'
            source.mkdir()
            (source/'gnome-shell').mkdir()
            (source/'gnome-shell/gnome-shell.css').write_text('valid-theme')
            (source/'gtk.css').write_text('gtk-theme')
            with mock.patch.object(rh, 'DEST', dest), mock.patch.object(rh.os, 'geteuid', return_value=0):
                rh.main(['root_helper.py','apply',str(dest),str(source),'null'])
                original_hashes = rh.paths(dest)
                self.assertEqual(original_hashes,rh.paths(source))
                (source/'gtk.css').write_text('improved-gtk-theme')
                rh.main(['root_helper.py','apply',str(dest),str(source),json.dumps(original_hashes)])
                changed_hashes = rh.paths(dest)
                self.assertNotEqual(changed_hashes, original_hashes)
                (dest/'gtk.css').write_text('other user edit')
                with self.assertRaises(ValueError):
                    rh.main(['root_helper.py','remove',str(dest),json.dumps(changed_hashes)])
                self.assertTrue(dest.exists())
                (dest/'gtk.css').write_text('improved-gtk-theme')
                rh.main(['root_helper.py','remove',str(dest),json.dumps(changed_hashes)])
                self.assertFalse(dest.exists())

    def test_privileged_destination_pinned(self):
        with mock.patch.object(rh.os,'geteuid',return_value=0):
            with self.assertRaises(ValueError):
                rh.main(['root_helper.py','remove','/etc/important', '{}'])


if __name__ == '__main__':
    unittest.main()
