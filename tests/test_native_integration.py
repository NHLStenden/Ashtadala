"""Optional GNOME Shell detour integration and named accents."""
import argparse
import ast
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tokyoadwaita as t
from tokyonight_colors import ACCENTS, DEFAULT, resolve

SHELL_SOURCE = (
    '#panel { background-color: #36363a; color: #ffffff; }\n'
    '.quick-settings .quick-toggle:checked { background-color: -st-accent-color; color: -st-accent-fg-color; }\n'
    '.quick-settings .quick-toggle-has-menu .quick-toggle-menu-button:checked { background-color: -st-accent-color; }\n'
) * 30


class NamedAccents(unittest.TestCase):
    def test_default_is_canonical_tokyonight_blue(self):
        self.assertEqual(DEFAULT, 'blue')
        self.assertEqual(t.ACCENT_DEFAULT, '#7aa2f7')
        self.assertEqual(ACCENTS['orange'], '#ff9e64')
        self.assertEqual(ACCENTS['peach'], ACCENTS['orange'])
        self.assertNotEqual(ACCENTS['magenta'], ACCENTS['purple'])

    def test_names_and_hex(self):
        for name, value in ACCENTS.items():
            self.assertEqual(t.accent_choice(name), value)
            self.assertEqual(t.accent_choice(name.upper()), value)
        self.assertEqual(t.accent_choice('#BB9AF7'), '#bb9af7')
        for bad in ('violet', '#1234', '#ZZABCD', 'green;rm -rf /', 'red #000000'):
            with self.assertRaises(t.ThemeError):
                t.accent_choice(bad)


class IntegratedDetour(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='tokyo-integrated-')
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.p = {'user_theme': base / 'data/themes' / t.THEME,
                  'system_theme': base / 'system/themes' / t.THEME,
                  'gtk_css': base / 'config/gtk-4.0/gtk.css',
                  'gtk_override': base / 'config/gtk-4.0/tokyoadwaita-night.css',
                  'state': base / 'state/tokyoadwaita/state.json'}
        self.p['gtk_css'].parent.mkdir(parents=True)
        self.p['gtk_css'].write_text('/* unrelated user CSS */\n')
        self.settings = {('org.gnome.desktop.interface','gtk-theme'): repr('Adwaita'),
                         ('org.gnome.desktop.interface','color-scheme'): repr('default'),
                         ('org.gnome.desktop.interface','accent-color'): repr('blue'),
                         ('org.gnome.shell.extensions.user-theme','name'): repr(''),
                         ('org.gnome.shell','enabled-extensions'): repr(['extra@user.org'])}
        patches = [
            mock.patch.object(t, 'paths', return_value=self.p),
            mock.patch.object(t, 'native_preflight'),
            mock.patch.object(t, 'stock_shell_resource', return_value=(SHELL_SOURCE, Path('/fake'))),
            mock.patch.object(t, 'gget', side_effect=lambda s,k:self.settings[(s,k)]),
            mock.patch.object(t, 'gset', side_effect=lambda s,k,v:self.settings.__setitem__((s,k),v)),
            mock.patch.object(t, 'detour_existing_color', return_value=None),
            mock.patch.object(t, 'detour_run'),
        ]
        self.mocks = [p.start() for p in patches]
        for patch in patches:
            self.addCleanup(patch.stop)
        self.detour = self.mocks[-1]
        self.current_color = self.mocks[-2]

    def install(self, accent='blue', native=None, system_accent='slate', check=False):
        t.install(argparse.Namespace(check=check, install_extension=False, accent=accent,
                   scope='user', system_accent=system_accent, flatpak=False,
                   native_detour=native))

    def test_optin_and_reconfigure_keeps_css_and_native_in_sync(self):
        self.install('blue', native=True)
        state = t.read_state(self.p['state'])
        self.assertTrue(state['native_detour_enabled'])
        self.assertEqual(state['accent'], '#7aa2f7')
        self.detour.assert_any_call('check')
        self.detour.assert_any_call('install', '#7aa2f7')
        self.assertIn('background-color: #7aa2f7',
                      (self.p['user_theme'] / 'gnome-shell/gnome-shell.css').read_text())
        self.detour.reset_mock()
        self.current_color.return_value = '#7aa2f7'
        self.install('magenta', native=None)
        self.assertEqual(t.read_state(self.p['state'])['accent'], '#bb9af7')
        self.detour.assert_any_call('install', '#bb9af7')
        self.detour.reset_mock()
        self.current_color.return_value = '#bb9af7'
        t.uninstall(argparse.Namespace())
        self.detour.assert_called_once_with('uninstall')
        self.assertFalse(self.p['state'].exists())
        self.assertEqual(self.settings[('org.gnome.desktop.interface','accent-color')], "'blue'")

    def test_optout_leaves_unmanaged_standalone_hook_alone(self):
        self.install('blue', native=False)
        self.detour.assert_not_called()
        self.assertFalse(t.read_state(self.p['state'])['native_detour_enabled'])
        t.uninstall(argparse.Namespace())
        self.detour.assert_not_called()

    def test_explicit_disable_removes_managed_detour(self):
        self.install('blue', native=True)
        self.current_color.return_value = '#7aa2f7'
        self.detour.reset_mock()
        self.install('green', native=False)
        self.detour.assert_called_once_with('uninstall')
        self.assertFalse(t.read_state(self.p['state'])['native_detour_enabled'])
        self.assertEqual(t.read_state(self.p['state'])['accent'], '#9ece6a')

    def test_refuse_incompatible_system_accent_before_changes(self):
        with self.assertRaisesRegex(t.ThemeError, 'requires --system-accent slate'):
            self.install(native=True, system_accent='orange')
        self.detour.assert_not_called()
        self.assertFalse(self.p['user_theme'].exists())

    def test_failure_rolls_back_theme_settings_and_detour(self):
        def side_effect(*args):
            if args == ('install', '#7aa2f7'):
                raise t.ThemeError('simulated hook install failure')
        self.detour.side_effect = side_effect
        with self.assertRaisesRegex(t.ThemeError, 'simulated'):
            self.install('blue', native=True)
        self.detour.assert_any_call('uninstall')
        self.assertFalse(self.p['state'].exists())
        self.assertFalse(self.p['user_theme'].exists())
        self.assertEqual(self.p['gtk_css'].read_text(), '/* unrelated user CSS */\n')
        self.assertEqual(self.settings[('org.gnome.desktop.interface','accent-color')], "'blue'")

    def test_prior_standalone_v2_detour_is_restored_not_removed(self):
        self.current_color.return_value = '#ff9e64'  # user's existing v2 hook
        self.install('blue', native=True)
        state = t.read_state(self.p['state'])
        self.assertEqual(state['native_detour_original_color'], '#ff9e64')
        self.detour.reset_mock()
        t.uninstall(argparse.Namespace())
        self.detour.assert_called_once_with('install', '#ff9e64')

    def test_explicit_disable_restores_preexisting_standalone_hook(self):
        self.current_color.return_value = '#ff9e64'
        self.install('blue', native=True)
        self.current_color.return_value = '#7aa2f7'
        self.detour.reset_mock()
        self.install('orange', native=False)
        self.detour.assert_called_once_with('install', '#ff9e64')
        self.assertIsNone(t.read_state(self.p['state'])['native_detour_original_color'])

    def test_readonly_preflight_does_not_touch_theme(self):
        self.install('green', native=True, check=True)
        self.detour.assert_called_once_with('check')
        self.assertFalse(self.p['user_theme'].exists())


if __name__ == '__main__':
    unittest.main()
