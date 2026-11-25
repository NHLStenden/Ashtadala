"""Papirus overlay generation and installer behavior."""
import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import papirus_icons as pi
import ashtadala as t
from test_theme import InstallationTests


NORMAL = '<svg><path fill="#5294e2"/><path fill="#7aaff5"/><path fill="#ffffff"/><path fill="url(#5294e2)"/></svg>'
USER = '<svg><path fill="#5294e2aa"/><path fill="#000000"/></svg>'


def fake_papirus(path: Path):
    root = path / 'Papirus-Dark'
    (root / 'index.theme').parent.mkdir(parents=True, exist_ok=True)
    (root / 'index.theme').write_text('[Icon Theme]\nName=Papirus-Dark\n')
    files = {
        '48x48/places/folder-blue.svg': NORMAL,
        '48x48/places/folder-blue-documents.svg': NORMAL,
        '48x48/places/user-blue.svg': USER,
        '22x22/places/folder-blue.svg': NORMAL,
    }
    for name, content in files.items():
        dest = root / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
    return root


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='papirus-overlay-')
        self.addCleanup(self.temp.cleanup)
        self.root = fake_papirus(Path(self.temp.name))

    def test_all_palette_names_and_hex(self):
        for name in t.ACCENTS:
            files = pi.build_overlay('Papirus-Dark', self.root, name)
            self.assertIn('index.theme', files)
            self.assertIn('48x48/places/folder.svg', files)
            self.assertIn('48x48/places/folder-documents.svg', files)
            self.assertIn('48x48/places/user.svg', files)
            self.assertIn('Inherits=Papirus-Dark', files['index.theme'].decode())
            self.assertIn('Directories=22x22/places,48x48/places', files['index.theme'].decode())
            self.assertIn(t.ACCENTS[name], files['48x48/places/folder.svg'].decode())
        self.assertIn(b'#123456', pi.build_overlay('Papirus-Dark', self.root, '#123456')['48x48/places/folder.svg'])

    def test_preserves_source_and_unrelated_colors(self):
        files = pi.build_overlay('Papirus-Dark', self.root, 'peach')
        folder = files['48x48/places/folder.svg'].decode()
        self.assertEqual((self.root / '48x48/places/folder-blue.svg').read_text(), NORMAL)
        self.assertIn('fill="#ffffff"', folder)
        self.assertIn('fill="url(#5294e2)"', folder)
        self.assertIn('fill="#ef9369"', folder)
        self.assertIn('fill="#ef9369aa"', files['48x48/places/user.svg'].decode())
        self.assertNotIn('folder-blue.svg', files)

    def test_missing_and_bad_sources(self):
        with self.assertRaises(pi.IconError):
            pi.build_overlay('Papirus', self.root, 'peach')
        (self.root / '48x48/places/folder-blue.svg').write_text('<svg><path fill="#ffffff"/></svg>')
        (self.root / '22x22/places/folder-blue.svg').write_text('<svg><path fill="#ffffff"/></svg>')
        with self.assertRaisesRegex(pi.IconError, 'blue fills'):
            pi.build_overlay('Papirus-Dark', self.root, 'peach')

    def test_source_lookup_uses_user_and_xdg_paths(self):
        data = Path(self.temp.name)
        root = data / 'icons'
        fake_papirus(root)
        with mock.patch.object(pi, 'roots', return_value=[root]):
            self.assertEqual(pi.find_papirus('Papirus-Dark'), ('Papirus-Dark', root/'Papirus-Dark'))
            self.assertIsNone(pi.find_papirus('Papirus-Light'))


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        InstallationTests.setUp(self)
        self.papirus_base = fake_papirus(Path(self.tmp.name))
        self.settings[('org.gnome.desktop.interface','icon-theme')] = "'Papirus-Dark'"
        self.find_papirus = mock.patch.object(pi, 'find_papirus', return_value=('Papirus-Dark', self.papirus_base))
        self.find_papirus.start()
        self.addCleanup(self.find_papirus.stop)

    def test_purple_install_and_uninstall(self):
        t.install(argparse.Namespace(accent='blue'))
        state = t.read_state(self.paths['state'])
        self.assertEqual(state['papirus']['color'], '#cc95e4')
        self.assertEqual(state['papirus']['hex'], '#cc95e4')
        self.assertEqual(self.settings[('org.gnome.desktop.interface', 'icon-theme')], repr(pi.ICON_THEME))
        self.assertIn('Inherits=Papirus-Dark', (self.paths['icon_theme']/'index.theme').read_text())
        self.assertIn('#cc95e4', (self.paths['icon_theme']/'48x48/places/folder.svg').read_text())
        self.assertEqual((self.papirus_base/'48x48/places/folder-blue.svg').read_text(), NORMAL)
        t.uninstall(argparse.Namespace())
        self.assertFalse(self.paths['icon_theme'].exists())
        self.assertEqual(self.settings[('org.gnome.desktop.interface','icon-theme')], "'Papirus-Dark'")
        self.assertEqual((self.papirus_base/'48x48/places/folder-blue.svg').read_text(), NORMAL)

    def test_purple_folders_persist_across_primary_changes(self):
        t.install(argparse.Namespace(accent='blue'))
        state = t.read_state(self.paths['state'])
        self.assertEqual(state['papirus']['hex'], '#cc95e4')
        self.assertEqual(json.loads((self.paths['user_theme'] / 'palette.json').read_text())['SECONDARY_ACCENT'], '#cc95e4')
        t.install(argparse.Namespace(accent='green'))
        self.assertEqual(t.read_state(self.paths['state'])['papirus']['hex'], '#cc95e4')
        t.uninstall(argparse.Namespace())

    def test_primary_purple_keeps_purple_folders(self):
        t.install(argparse.Namespace(accent='purple'))
        self.assertEqual(t.read_state(self.paths['state'])['papirus']['hex'], '#cc95e4')
        t.uninstall(argparse.Namespace())

    def test_old_secondary_setting_is_ignored_on_reconfigure(self):
        t.install(argparse.Namespace(accent='blue'))
        state = t.read_state(self.paths['state'])
        state['secondary_accent'] = '#3dbee9'
        state['papirus']['color'] = state['papirus']['hex'] = '#3dbee9'
        self.paths['state'].write_text(json.dumps(state))
        t.install(argparse.Namespace(accent='purple'))
        state = t.read_state(self.paths['state'])
        self.assertNotIn('secondary_accent', state)
        self.assertEqual(state['papirus']['hex'], '#cc95e4')
        t.uninstall(argparse.Namespace())

    def test_modified_overlay_refuses_uninstall(self):
        t.install(argparse.Namespace(accent='peach'))
        (self.paths['icon_theme'] / '48x48/places/folder.svg').write_text('modified')
        with self.assertRaisesRegex(t.ThemeError, 'changed outside this tool'):
            t.uninstall(argparse.Namespace())
        self.assertTrue(self.paths['state'].exists())
        self.assertTrue(self.paths['user_theme'].exists())

    def test_icon_overlay_rolls_back_after_hook_failure(self):
        def fail_hook(action, color=None):
            if action == 'install':
                raise t.ThemeError('hook failed')
        with mock.patch.object(t, 'hook_run', side_effect=fail_hook):
            with self.assertRaisesRegex(t.ThemeError, 'hook failed'):
                t.install(argparse.Namespace(accent='blue'))
        self.assertFalse(self.paths['icon_theme'].exists())
        self.assertFalse(self.paths['user_theme'].exists())
        self.assertFalse(self.paths['state'].exists())
        self.assertEqual(self.settings[('org.gnome.desktop.interface', 'icon-theme')], "'Papirus-Dark'")

    def test_upgrade_existing_install_without_icons(self):
        with mock.patch.object(pi, 'find_papirus', return_value=None):
            t.install(argparse.Namespace(accent='blue'))
        old_state = t.read_state(self.paths['state'])
        self.assertIsNone(old_state['papirus'])
        old_state.pop('papirus')  # State file from the previous release.
        self.paths['state'].write_text(json.dumps(old_state))
        t.install(argparse.Namespace(accent='purple'))
        self.assertTrue(self.paths['icon_theme'].exists())
        t.uninstall(argparse.Namespace())
        self.assertFalse(self.paths['icon_theme'].exists())

    def test_missing_papirus_before_reconfigure_keeps_install(self):
        t.install(argparse.Namespace(accent='purple'))
        with mock.patch.object(pi, 'find_papirus', return_value=None):
            with self.assertRaisesRegex(t.ThemeError, 'Papirus theme is missing'):
                t.install(argparse.Namespace(accent='green'))
        self.assertEqual(t.read_state(self.paths['state'])['accent'], '#cc95e4')

    def test_icon_file_change_blocks_reconfigure(self):
        t.install(argparse.Namespace(accent='blue'))
        file = self.paths['icon_theme'] / '48x48/places/folder.svg'
        file.write_text('custom')
        with self.assertRaisesRegex(t.ThemeError, 'changed outside this tool'):
            t.install(argparse.Namespace(accent='purple'))
        self.assertEqual(file.read_text(), 'custom')
        self.assertEqual(t.read_state(self.paths['state'])['accent'], '#8fa9fd')

    def test_overlay_build_failure_does_not_change_settings(self):
        with mock.patch.object(pi, 'build_overlay', side_effect=pi.IconError('invalid SVG')):
            with self.assertRaisesRegex(t.ThemeError, 'invalid SVG'):
                t.install(argparse.Namespace(accent='blue'))
        self.assertEqual(self.settings[('org.gnome.desktop.interface', 'icon-theme')], "'Papirus-Dark'")
        self.assertFalse(self.paths['state'].exists())
        self.assertFalse(self.paths['user_theme'].exists())

    def test_adding_papirus_after_initial_install(self):
        with mock.patch.object(pi, 'find_papirus', return_value=None):
            t.install(argparse.Namespace(accent='blue'))
        self.assertIsNone(t.read_state(self.paths['state'])['papirus'])
        t.install(argparse.Namespace(accent='purple'))
        self.assertTrue(self.paths['icon_theme'].exists())
        self.assertEqual(self.settings[('org.gnome.desktop.interface', 'icon-theme')], repr(pi.ICON_THEME))
        t.uninstall(argparse.Namespace())

    def test_source_variant_restored_after_uninstall(self):
        t.install(argparse.Namespace(accent='blue'))
        t.install(argparse.Namespace(accent='purple'))
        t.uninstall(argparse.Namespace())
        self.assertEqual(self.settings[('org.gnome.desktop.interface', 'icon-theme')], "'Papirus-Dark'")

    def test_previous_icon_setting_edited_by_user_is_not_overwritten_on_uninstall(self):
        t.install(argparse.Namespace(accent='blue'))
        self.settings[('org.gnome.desktop.interface', 'icon-theme')] = "'Adwaita'"
        t.uninstall(argparse.Namespace())
        self.assertEqual(self.settings[('org.gnome.desktop.interface', 'icon-theme')], "'Adwaita'")
