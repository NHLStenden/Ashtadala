import argparse
import ast
import json
import tempfile
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tokyoadwaita as t


SHELL_SOURCE = ('#panel { background-color: #36363a; color: #ffffff; }\n'
                '.sample { background-color: st-mix(-st-accent-color, #28282c, 9%); '\
                'color: -st-accent-fg-color; border-color: #3584e4; }\n'
                '.other { background-color: #2e2e32; }\n'
                '.quick-settings .quick-toggle:checked { background-color: -st-accent-color; }\n'
                '.quick-settings .quick-toggle-has-menu .quick-toggle-menu-button:checked { background-color: st-mix(-st-accent-color, #ffffff, 85%); }\n') * 28


class ColorTests(unittest.TestCase):
    def test_palette_and_accent(self):
        self.assertEqual(t.accent_valid('#FF9E64'), '#ff9e64')
        self.assertEqual(t.PALETTE['BG'], '#1a1b26')
        for color in ['#ff9e64', '#ffffff', '#000000', '#7aa2f7', '#ff0000', '#0000ff']:
            self.assertGreaterEqual(t.contrast(color, t.accent_foreground(color)), 4.49)
        self.assertEqual(t.accent_foreground('#ff9e64'), '#16161e')

    def test_mid_brightness_custom_accent_is_accessible(self):
        # Old chooser returned #16161e at just 4.24:1 for this accent.
        for color in ('#7e69dd', '#7d7d7d', '#808080', '#ff9e64'):
            self.assertGreaterEqual(t.contrast(color, t.accent_foreground(color)), 4.5)
        self.assertEqual(t.accent_foreground('#7e69dd'), '#000000')
        self.assertEqual(t.accent_foreground('#ff9e64'), '#16161e')

    def test_gtk4_user_overlay_does_not_inject_light_mode_aliases(self):
        user_css = t.gtk4_override('#ff9e64')
        self.assertIn('@media (prefers-color-scheme: dark)', user_css)
        self.assertIn('--accent-fg-color: #16161e;', user_css)
        self.assertNotIn('@define-color', user_css)
        # Legacy aliases are kept in the explicit dark GTK4 theme layer.
        theme_css = t.theme_files('#ff9e64', SHELL_SOURCE)[0]['gtk-4.0/gtk.css'].decode()
        self.assertIn('@define-color accent_bg_color #ff9e64;', theme_css)

    def test_gtk3_suggested_buttons_do_not_show_adwaita_blue_gradient(self):
        gtk3 = t.expand('gtk3.css', t.tokens('#ff9e64'))
        self.assertIn('button.suggested-action:active', gtk3)
        self.assertIn('button.suggested-action:hover', gtk3)
        self.assertIn('background-image: none;', gtk3)
        self.assertIn('color: #16161e;', gtk3)

    def test_gtk3_filechooser_focus_and_sidebar_selection(self):
        # GTK3 Adwaita's focused treeview rules can otherwise keep its blue.
        # PlacesSidebar child labels and images can separately force white.
        for accent in ('#ff9e64', '#bc83ff', '#7e69dd'):
            gtk3 = t.expand('gtk3.css', t.tokens(accent))
            self.assertIn('treeview.view:selected:focus,', gtk3)
            self.assertIn('iconview.view:selected:focus,', gtk3)
            self.assertIn('placessidebar.sidebar row:selected:hover {', gtk3)
            self.assertIn('placessidebar.sidebar row:selected label,', gtk3)
            self.assertIn('placessidebar.sidebar row:selected image {', gtk3)
            self.assertIn('background-color: ' + accent + ';', gtk3)
            self.assertIn('color: ' + t.accent_foreground(accent) + ';', gtk3)
            self.assertGreaterEqual(t.contrast(accent, t.accent_foreground(accent)), 4.5)
            # No stale original Adwaita blue in the selection template.
            self.assertNotIn('#15539e', gtk3)
            self.assertNotIn('#215d9c', gtk3)

    def test_sampled_accent_contrast_and_dark_surface_contrast(self):
        # Sample the RGB space; keep the foreground algorithm valid beyond
        # the shipped peach and a few hand-picked alternate accents.
        for r in range(0, 256, 32):
            for g in range(0, 256, 32):
                for b in range(0, 256, 32):
                    color = f'#{r:02x}{g:02x}{b:02x}'
                    self.assertGreaterEqual(t.contrast(color, t.accent_foreground(color)), 4.5)
        for key in ('BG', 'DEEP', 'PANEL', 'SURFACE', 'HOVER'):
            self.assertGreaterEqual(t.contrast(t.PALETTE[key], '#ffffff'), 7.0)

    def test_invalid_accents_rejected(self):
        for color in ['red', '#123', '#12345678', 'ffffff', '#abcdef;/*bad*/', '#g0abba']:
            with self.assertRaises(t.ThemeError):
                t.accent_valid(color)

    def test_gtk_css_layers(self):
        files, m = t.theme_files('#ff9e64', SHELL_SOURCE)
        self.assertEqual(set(files), {'gtk-3.0/gtk.css', 'gtk-3.0/gtk-dark.css',
                           'gtk-4.0/gtk.css', 'gtk-4.0/gtk-dark.css',
                           'gnome-shell/gnome-shell.css', 'index.theme', 'palette.json'})
        gtk3 = files['gtk-3.0/gtk.css'].decode()
        gtk4 = files['gtk-4.0/gtk.css'].decode()
        self.assertIn('resource:///org/gtk/libgtk/theme/Adwaita/gtk-dark.css', gtk3)
        self.assertIn('resource:///org/gtk/libgtk/theme/Default/gtk-dark.css', gtk4)
        self.assertIn('--accent-bg-color: #ff9e64', gtk4)
        self.assertIn('--window-bg-color: #1a1b26', gtk4)
        self.assertIn('window, dialog, popover {', gtk4)
        self.assertNotIn('--window-fg-color:', gtk4)
        self.assertNotIn('rgba(22, 22, 30, 0.96)', files['gnome-shell/gnome-shell.css'].decode())
        self.assertEqual(files['gtk-3.0/gtk.css'], files['gtk-3.0/gtk-dark.css'])
        self.assertEqual(files['gtk-4.0/gtk.css'], files['gtk-4.0/gtk-dark.css'])
        self.assertEqual(json.loads(files['palette.json'])['ACCENT'], '#ff9e64')
        self.assertIn('@media (prefers-color-scheme: dark)', t.gtk4_override('#ff9e64'))
        self.assertNotIn('userChrome', t.gtk4_override('#ff9e64'))
        self.assertGreater(m['shell_replacements']['-st-accent-color'], 0)

    def test_shell_reuses_original_selectors_and_color_functions(self):
        css, changes = t.shell_recolor(SHELL_SOURCE, '#bc83ff')
        self.assertIn('st-mix(#bc83ff, #1a1b26, 9%)', css)
        self.assertIn('background-color: #24283b', css)
        self.assertIn('color: #ffffff;', css)  # Blur My Shell contrast must stay white
        self.assertNotIn('color: #c0caf5', css)
        self.assertNotIn('-st-accent-color', css)
        self.assertNotIn('-st-accent-fg-color', css)
        self.assertEqual(changes['-st-accent-color'], 84)

    def test_quick_settings_checked_tiles_use_custom_accent_and_readable_fg(self):
        for accent in ('#ff9e64', '#bc83ff', '#7aa2f7'):
            css, _ = t.shell_recolor(SHELL_SOURCE, accent)
            quick = css.split('TokyoAdwaita Night managed Quick Settings')[1]
            self.assertIn('background-color: ' + accent + ';', quick)
            self.assertIn('color: ' + t.accent_foreground(accent) + ';', quick)
            self.assertIn('st-mix(' + accent + ', #ffffff, 85%)', quick)
            self.assertIn('.quick-toggle-menu-button:checked:hover', quick)
            self.assertIn('.quick-toggle:checked:focus', quick)
            self.assertNotIn('#6f8396', quick)
            self.assertNotIn('#ed5b00', quick)
            self.assertNotIn('!important', quick)
            self.assertNotIn('#c0caf5', quick)
            # Each selected button must have readable text, not white on peach.
            self.assertGreaterEqual(t.contrast(accent, t.accent_foreground(accent)), 4.5)
            self.assertLess(t.contrast(accent, '#ffffff'), 4.5) if accent == '#ff9e64' else None

    def test_quick_settings_installed_css_structural_check(self):
        css, _ = t.shell_recolor(SHELL_SOURCE, '#ff9e64')
        t.check_quick_settings_css(css, '#ff9e64')
        with self.assertRaisesRegex(t.ThemeError, 'missing expected CSS'):
            t.check_quick_settings_css(css, '#bc83ff')
        with self.assertRaisesRegex(t.ThemeError, 'lacks the managed'):
            t.check_quick_settings_css(SHELL_SOURCE, '#ff9e64')

    def test_quick_settings_refuses_nonmatching_shell_source(self):
        source = SHELL_SOURCE.replace('quick-toggle-menu-button', 'other-button')
        with self.assertRaisesRegex(t.ThemeError, 'Quick Settings selectors'):
            t.shell_recolor(source, '#ff9e64')

    def test_reconfigure_updates_shell_tiles_not_only_gtk(self):
        first, _ = t.theme_files('#ff9e64', SHELL_SOURCE)
        second, _ = t.theme_files('#bc83ff', SHELL_SOURCE)
        s1 = first['gnome-shell/gnome-shell.css'].decode().split('TokyoAdwaita Night managed Quick Settings')[1]
        s2 = second['gnome-shell/gnome-shell.css'].decode().split('TokyoAdwaita Night managed Quick Settings')[1]
        self.assertIn('background-color: #ff9e64;', s1)
        self.assertIn('background-color: #bc83ff;', s2)
        self.assertNotIn('#ff9e64', s2)
        self.assertNotEqual(s1, s2)
        self.assertEqual(first['gtk-4.0/gtk.css'].decode().count('--accent-bg-color: #ff9e64'), 1)
        self.assertEqual(second['gtk-4.0/gtk.css'].decode().count('--accent-bg-color: #bc83ff'), 1)

    def test_empty_gvariant_array(self):
        self.assertEqual(t.parse_gvariant_array('@as []'), [])
        self.assertEqual(t.parse_gvariant_array("['a@x']"), ['a@x'])

    def test_bad_shell_resource_fails_closed(self):
        for source in ['', '#panel { color: pink; }', 'a' * 3000]:
            with self.assertRaises(t.ThemeError):
                t.theme_files('#ff9e64', source)

    def test_marked_import_preserves_user_data(self):
        original = '@import url("other.css");\nbutton { border-radius: 20px; }\n'
        managed = t.insert_import(original)
        self.assertTrue(managed.startswith(t.START))
        self.assertEqual(t.remove_import(managed), original)
        self.assertEqual(t.remove_import(t.insert_import(managed)), original)
        with self.assertRaises(t.ThemeError):
            t.remove_import(managed.replace(t.IMPORT, 'bad'))


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='tokyo-tests-')
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.paths = {'user_theme': base / 'data/themes' / t.THEME,
                      'gtk_css': base / 'config/gtk-4.0/gtk.css',
                      'gtk_override': base / 'config/gtk-4.0/tokyoadwaita-night.css',
                      'state': base / 'state/tokyoadwaita/state.json'}
        self.paths['gtk_css'].parent.mkdir(parents=True)
        self.prior_css = ('@import url("not-ours.css");\n'
                          ':root { --custom-user-var: #abcdef; }\n').encode()
        self.paths['gtk_css'].write_bytes(self.prior_css)
        self.settings = {('org.gnome.desktop.interface','gtk-theme'): repr('Adwaita'),
                         ('org.gnome.desktop.interface','color-scheme'): repr('default'),
                         ('org.gnome.desktop.interface','accent-color'): repr('blue'),
                         ('org.gnome.shell.extensions.user-theme','name'): repr(''),
                         ('org.gnome.shell','enabled-extensions'): repr(['example@test.org'])}
        self.patches = [
            mock.patch.object(t, 'paths', return_value=self.paths),
            mock.patch.object(t, 'native_preflight', return_value=None),
            mock.patch.object(t, 'stock_shell_resource', return_value=(SHELL_SOURCE, Path('/mock.gresource'))),
            mock.patch.object(t, 'hook_run'),
            mock.patch.object(t, 'flatpak_present', return_value=False),
            mock.patch.object(t, 'gget', side_effect=lambda s,k: self.settings[(s,k)]),
            mock.patch.object(t, 'gset', side_effect=lambda s,k,v: self.settings.__setitem__((s,k),v)),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def install(self, accent='#ff9e64'):
        t.install(argparse.Namespace(accent=accent))

    def test_user_install_and_uninstall_exact_restore(self):
        self.install()
        state = t.read_state(self.paths['state'])
        self.assertEqual(state['format'], 4)
        self.assertTrue((self.paths['user_theme']/'gnome-shell/gnome-shell.css').is_file())
        self.assertEqual(self.settings[('org.gnome.desktop.interface', 'accent-color')], "'slate'")
        self.assertIn(t.EXTENSION, ast.literal_eval(self.settings[('org.gnome.shell','enabled-extensions')]))
        self.assertIn(b'--accent-bg-color: #ff9e64', self.paths['gtk_override'].read_bytes())
        self.assertEqual(t.remove_import(self.paths['gtk_css'].read_text()).encode(), self.prior_css)
        # User tweaks AFTER installation must survive uninstallation.
        with self.paths['gtk_css'].open('a') as f: f.write('button { outline-width: 9px; }\n')
        t.uninstall(argparse.Namespace())
        self.assertFalse(self.paths['user_theme'].exists())
        self.assertFalse(self.paths['gtk_override'].exists())
        self.assertFalse(self.paths['state'].exists())
        self.assertEqual(self.paths['gtk_css'].read_bytes(), self.prior_css + b'button { outline-width: 9px; }\n')
        self.assertEqual(self.settings[('org.gnome.desktop.interface', 'accent-color')], "'blue'")
        self.assertEqual(self.settings[('org.gnome.shell','enabled-extensions')], "['example@test.org']")

    def test_uninstall_restores_absence_of_original_gtk_css(self):
        self.paths['gtk_css'].unlink()
        self.install()
        self.assertFalse(t.read_state(self.paths['state'])['gtk_css_existed'])
        self.assertTrue(self.paths['gtk_css'].exists())
        t.uninstall(argparse.Namespace())
        self.assertFalse(self.paths['gtk_css'].exists())

    def test_added_extensions_survive_uninstall(self):
        self.install()
        self.settings[('org.gnome.shell','enabled-extensions')] = repr(['example@test.org', t.EXTENSION, 'newuser@extension'])
        t.uninstall(argparse.Namespace())
        self.assertEqual(self.settings[('org.gnome.shell','enabled-extensions')], repr(['example@test.org', 'newuser@extension']))

    def test_platform_accent_remains_slate_when_reconfiguring(self):
        self.install('#ff9e64')
        state = t.read_state(self.paths['state'])
        self.assertEqual(state['accent'], '#ff9e64')
        self.install('#9141ac')
        new = t.read_state(self.paths['state'])
        self.assertEqual(new['accent'], '#9141ac')
        self.assertEqual(self.settings[('org.gnome.desktop.interface', 'accent-color')], "'slate'")
        t.uninstall(argparse.Namespace())

    def test_reconfigure_and_upgrade_preserves_original_settings(self):
        self.install('#ff9e64')
        self.install('#bc83ff')
        state = t.read_state(self.paths['state'])
        self.assertEqual(state['settings']['org.gnome.desktop.interface/accent-color']['old'], "'blue'")
        self.assertEqual(state['accent'], '#bc83ff')
        self.assertIn('--accent-bg-color: #bc83ff', self.paths['gtk_override'].read_text())
        t.uninstall(argparse.Namespace())
        self.assertEqual(self.settings[('org.gnome.desktop.interface','gtk-theme')], "'Adwaita'")

    def test_in_place_rebuild_and_rollback_state(self):
        self.install('#ff9e64')
        old = t.read_state(self.paths['state'])
        old_theme = (self.paths['user_theme'] / 'gnome-shell/gnome-shell.css').read_text()
        self.install('#bc83ff')
        new = t.read_state(self.paths['state'])
        new_theme = (self.paths['user_theme'] / 'gnome-shell/gnome-shell.css').read_text()
        self.assertEqual(old['format'], new['format'])
        self.assertEqual(old['settings']['org.gnome.desktop.interface/gtk-theme']['old'],
                         new['settings']['org.gnome.desktop.interface/gtk-theme']['old'])
        self.assertNotEqual(old_theme, new_theme)
        t.check_quick_settings_css(new_theme, '#bc83ff')
        t.uninstall(argparse.Namespace())
        self.assertEqual(self.settings[('org.gnome.desktop.interface', 'accent-color')], "'blue'")

    def test_uninstaller_refuses_modified_theme_and_does_not_erase(self):
        self.install()
        f = self.paths['user_theme'] / 'gtk-3.0/gtk.css'
        f.write_text('user modified stylesheet')
        with self.assertRaises(t.ThemeError):
            t.uninstall(argparse.Namespace())
        self.assertTrue(f.exists())
        self.assertTrue(self.paths['state'].exists())

    def test_user_modified_settings_are_preserved(self):
        self.install()
        self.settings[('org.gnome.desktop.interface', 'accent-color')] = "'green'"
        t.uninstall(argparse.Namespace())
        self.assertEqual(self.settings[('org.gnome.desktop.interface', 'accent-color')], "'green'")

    def test_install_collision_fails_before_change(self):
        self.paths['user_theme'].mkdir(parents=True)
        (self.paths['user_theme']/'my-own-file.txt').write_text('keep')
        with self.assertRaises(t.ThemeError):
            self.install()
        self.assertEqual(self.paths['gtk_css'].read_bytes(), self.prior_css)
        self.assertFalse(self.paths['state'].exists())
        self.assertTrue((self.paths['user_theme']/'my-own-file.txt').exists())

    def test_rejects_old_state_without_mutation(self):
        self.install()
        state = t.read_state(self.paths['state'])
        state['format'] = 3
        self.paths['state'].write_text(json.dumps(state))
        with self.assertRaisesRegex(t.ThemeError, 'Older installation'):
            self.install('blue')
        self.assertTrue(self.paths['user_theme'].exists())

    def test_flatpak_global_override_restores_exactly_and_preserves_local_apps(self):
        self.paths['flatpak_fake'] = self.paths['state'].parent / 'flatpak-global'
        original = b'[Context]\nfilesystems=xdg-download;\n'
        self.paths['flatpak_fake'].parent.mkdir(parents=True, exist_ok=True)
        self.paths['flatpak_fake'].write_bytes(original)
        def fake_apply():
            self.paths['flatpak_fake'].write_bytes(b'[Context]\nfilesystems=xdg-download;xdg-config/gtk-4.0:ro;xdg-data/themes:ro;\n')
        with mock.patch.object(t, 'flatpak_present', return_value=True), mock.patch.object(t, 'flatpak_preflight'), mock.patch.object(t, 'flatpak_path', return_value=self.paths['flatpak_fake']), mock.patch.object(t, 'flatpak_apply', side_effect=fake_apply):
            args = argparse.Namespace(accent='#ff9e64')
            t.install(args)
            self.assertTrue(t.read_state(self.paths['state'])['flatpak_enabled'])
            t.uninstall(argparse.Namespace())
        self.assertEqual(self.paths['flatpak_fake'].read_bytes(), original)

    def test_flatpak_modified_after_install_is_preserved_on_uninstall(self):
        fp = self.paths['state'].parent / 'flatpak-global'
        fp.parent.mkdir(parents=True, exist_ok=True)
        def fake_apply():
            fp.write_text('[Context]\nfilesystems=xdg-config/gtk-4.0:ro;\n')
        with mock.patch.object(t, 'flatpak_present', return_value=True), mock.patch.object(t, 'flatpak_preflight'), mock.patch.object(t, 'flatpak_path', return_value=fp), mock.patch.object(t, 'flatpak_apply', side_effect=fake_apply):
            t.install(argparse.Namespace(accent='#ff9e64'))
            fp.write_text('[Context]\nfilesystems=xdg-config/gtk-4.0:ro;xdg-download;\n')
            t.uninstall(argparse.Namespace())
        self.assertIn('xdg-download', fp.read_text())

    def test_flatpak_failure_after_change_rolls_back(self):
        fp = self.paths['state'].parent / 'flatpak-global'
        fp.parent.mkdir(parents=True, exist_ok=True)
        before = b'[Context]\nfilesystems=xdg-download;\n'
        fp.write_bytes(before)
        def partial_fail():
            fp.write_text('[Context]\nfilesystems=xdg-config/gtk-4.0:ro;\n')
            raise t.ThemeError('Simulated Flatpak command failing after write')
        with mock.patch.object(t, 'flatpak_present', return_value=True), mock.patch.object(t, 'flatpak_preflight'), mock.patch.object(t, 'flatpak_path', return_value=fp), mock.patch.object(t, 'flatpak_apply', side_effect=partial_fail):
            with self.assertRaises(t.ThemeError):
                t.install(argparse.Namespace(accent='#ff9e64'))
        self.assertEqual(fp.read_bytes(), before)
        self.assertEqual(self.paths['gtk_css'].read_bytes(), self.prior_css)
        self.assertFalse(self.paths['user_theme'].exists())
        self.assertFalse(self.paths['state'].exists())

    def test_flatpak_reconfigure_keeps_original_snapshot(self):
        fp = self.paths['state'].parent / 'flatpak-global'
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text('[Context]\nfilesystems=xdg-download;\n')
        def apply():
            fp.write_text('[Context]\nfilesystems=xdg-config/gtk-4.0:ro;xdg-download;\n')
        with mock.patch.object(t, 'flatpak_present', return_value=True), mock.patch.object(t, 'flatpak_preflight'), mock.patch.object(t, 'flatpak_path', return_value=fp), mock.patch.object(t, 'flatpak_apply', side_effect=apply):
            t.install(argparse.Namespace(accent='#ff9e64'))
            t.install(argparse.Namespace(accent='#bc83ff'))
            self.assertTrue(t.read_state(self.paths['state'])['flatpak_enabled'])
            t.uninstall(argparse.Namespace())
        self.assertEqual(fp.read_text(), '[Context]\nfilesystems=xdg-download;\n')

    def test_failure_during_settings_write_rolls_back_files(self):
        original_set = t.gset
        calls = 0
        def fail_after_one(schema,key,value):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise t.ThemeError('Simulated GSettings failure')
            return original_set(schema,key,value)
        with mock.patch.object(t, 'gset', side_effect=fail_after_one):
            with self.assertRaises(t.ThemeError):
                self.install()
        self.assertFalse(self.paths['state'].exists())
        self.assertFalse(self.paths['user_theme'].exists())
        self.assertFalse(self.paths['gtk_override'].exists())
        self.assertEqual(self.paths['gtk_css'].read_bytes(), self.prior_css)


if __name__ == '__main__':
    unittest.main()
