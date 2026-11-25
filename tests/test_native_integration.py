"""One-path installer and native accent hook lifecycle."""
import argparse
import tempfile
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import ashtadala as t
from ashtadala_colors import ACCENTS, resolve
from test_theme import SHELL_SOURCE


class NativeAccentTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='ashtadala-hook-')
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.p = {
            'user_theme': root / 'themes' / t.THEME,
            'icon_theme': root / 'icons' / t.papirus_icons.ICON_THEME,
            'gtk_css': root / 'gtk-4.0/gtk.css',
            'gtk_override': root / 'gtk-4.0/ashtadala-night.css',
            'state': root / 'state/state.json',
        }
        self.p['gtk_css'].parent.mkdir(parents=True)
        self.p['gtk_css'].write_text('/* unrelated user CSS */\n')
        self.settings = {
            ('org.gnome.desktop.interface', 'gtk-theme'): "'Adwaita'",
            ('org.gnome.desktop.interface', 'icon-theme'): "'Adwaita'",
            ('org.gnome.desktop.interface', 'color-scheme'): "'default'",
            ('org.gnome.desktop.interface', 'accent-color'): "'blue'",
            ('org.gnome.shell.extensions.user-theme', 'name'): "''",
            ('org.gnome.shell', 'enabled-extensions'): '[]',
        }
        mocks = [
            mock.patch.object(t, 'paths', return_value=self.p),
            mock.patch.object(t, 'native_preflight'),
            mock.patch.object(t, 'stock_shell_resource', return_value=(SHELL_SOURCE, Path('fake'))),
            mock.patch.object(t, 'gget', side_effect=lambda a,b: self.settings[a,b]),
            mock.patch.object(t, 'gset', side_effect=lambda a,b,v: self.settings.__setitem__((a,b),v)),
            mock.patch.object(t, 'flatpak_present', return_value=False),
            mock.patch.object(t.papirus_icons, 'find_papirus', return_value=None),
            mock.patch.object(t, 'hook_run'),
        ]
        started = [item.start() for item in mocks]
        for item in mocks: self.addCleanup(item.stop)
        self.hook = started[-1]

    def test_palette_names_no_orange_alias(self):
        self.assertEqual(ACCENTS['blue'], '#8fa9fd')
        self.assertEqual(ACCENTS['peach'], '#ef9369')
        self.assertNotIn('orange', ACCENTS)
        with self.assertRaises(ValueError): resolve('orange')
        for name, hexcode in ACCENTS.items():
            self.assertEqual(resolve(name), hexcode)
            self.assertEqual(t.accent_choice(name), hexcode)

    def test_hook_installs_and_reconfigures_with_theme(self):
        t.install(argparse.Namespace(accent='blue'))
        self.hook.assert_any_call('check')
        self.hook.assert_any_call('install', '#8fa9fd')
        self.assertEqual(t.read_state(self.p['state'])['format'], 4)
        self.assertEqual(self.settings[('org.gnome.desktop.interface','accent-color')], "'slate'")
        self.hook.reset_mock()
        t.install(argparse.Namespace(accent='peach'))
        self.hook.assert_any_call('install', '#ef9369')
        self.assertIn('background-color: #ef9369', (self.p['user_theme'] / 'gnome-shell/gnome-shell.css').read_text())
        self.hook.reset_mock()
        t.uninstall(argparse.Namespace())
        self.hook.assert_called_once_with('uninstall')
        self.assertEqual(self.settings[('org.gnome.desktop.interface','accent-color')], "'blue'")

    def test_install_without_color_preserves_existing_selection(self):
        t.install(argparse.Namespace(accent='peach'))
        self.hook.reset_mock()
        t.install(argparse.Namespace(accent=None))
        self.assertEqual(t.read_state(self.p['state'])['accent'], '#ef9369')
        self.hook.assert_any_call('install', '#ef9369')

    def test_hook_failure_rolls_back_all_managed_files(self):
        def fail(*args):
            if args == ('install', '#8fa9fd'):
                raise t.ThemeError('simulated hook failure')
        self.hook.side_effect = fail
        with self.assertRaisesRegex(t.ThemeError, 'simulated hook failure'):
            t.install(argparse.Namespace(accent='blue'))
        self.hook.assert_any_call('uninstall')
        self.assertFalse(self.p['user_theme'].exists())
        self.assertFalse(self.p['state'].exists())
        self.assertEqual(self.p['gtk_css'].read_text(), '/* unrelated user CSS */\n')
        self.assertEqual(self.settings[('org.gnome.desktop.interface','accent-color')], "'blue'")

    def test_preflight_failure_never_writes_files(self):
        self.hook.side_effect = t.ThemeError('conflicting LD_PRELOAD')
        with self.assertRaisesRegex(t.ThemeError, 'conflicting'):
            t.install(argparse.Namespace(accent='green'))
        self.assertFalse(self.p['user_theme'].exists())


if __name__ == '__main__':
    unittest.main()
