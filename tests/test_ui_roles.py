"""Verify that fixed widget hues do not replace the configurable accents."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import ashtadala as t
from test_theme import SHELL_SOURCE


class WidgetRoleTests(unittest.TestCase):
    def test_roles_are_independent_of_user_accents(self):
        for primary in ('#fb996c', '#90aafa', '#cb96e2'):
            values = t.tokens(primary)
            self.assertEqual(values['ACCENT'], primary)
            self.assertEqual(values['SECONDARY_ACCENT'], '#cb96e2')
            for name, color in [('SELECTION', '#ee8dac'), ('LEVEL', '#90c970'),
                                ('PROGRESS', '#90c970'), ('TAB', '#cb96e2')]:
                self.assertEqual(values[name], color)
                self.assertGreaterEqual(t.contrast(color, values['PANEL']), 4.5)
            self.assertGreaterEqual(t.contrast(values['SELECTION'], values['SELECTION_FG']), 4.5)

    def test_gtk4_sidebar_is_opaque_and_has_matching_ink(self):
        css = t.gtk4_override('#fb996c')
        self.assertIn('.navigation-sidebar > row:selected:not(:disabled)', css)
        self.assertIn('background-color: #ee8dac;\n  color: #13161e;', css)
        self.assertIn('.navigation-sidebar > row:selected:not(:disabled) label', css)
        self.assertNotIn('--window-fg-color:', css)
        self.assertIn('--accent-bg-color: #fb996c;', css)
        self.assertIn('scale:not(.color) {\n  --accent-bg-color: #90c970;', css)
        self.assertIn('progressbar {\n  --accent-bg-color: #90c970;', css)
        self.assertIn('notebook > header > tabs > tab {\n  --accent-bg-color: #cb96e2;', css)
        self.assertIn('tabbar tabbox:not(.single-tab) tab:selected', css)
        self.assertIn('entry:not(:disabled) text selection', css)
        self.assertIn('.navigation-sidebar > flowboxchild:selected:not(:disabled)', css)
        self.assertIn('color-mix(in srgb, #ee8dac 92%, white)', css)
        self.assertIn('color-mix(in srgb, #ee8dac 90%, black)', css)
        self.assertIn('--accent-fg-color: #13161e;', css)

    def test_stock_gtk4_surface_fallbacks_are_not_in_libadwaita_user_overlay(self):
        files, _ = t.theme_files('#fb996c', SHELL_SOURCE)
        stock = files['gtk-4.0/gtk.css'].decode()
        user = t.gtk4_override('#fb996c')
        for rule in ('window.background {background-color: #181c29;}',
                     'switch:checked:not(:disabled),'):
            self.assertIn(rule, stock)
            self.assertNotIn(rule, user)

    def test_gtk4_action_roles_in_both_layers(self):
        for primary in [*t.ACCENTS.values(), '#7e69dd', '#777777', '#ffffff', '#000000']:
            values = t.tokens(primary)
            files, _ = t.theme_files(primary, SHELL_SOURCE)
            for css in (t.gtk4_override(primary), files['gtk-4.0/gtk.css'].decode()):
                for cls in ('suggested-action', 'default'):
                    self.assertIn(f'button.{cls}:not(.flat):not(.destructive-action):not(:disabled)', css)
                self.assertIn(f'background-color: {primary};\n  border-color: {primary};\n  color: {values["ACCENT_FG"]};', css)
                self.assertIn('background-color: #ee8dac;\n  color: #13161e;', css)
                for state, token in (('hover', 'ACCENT_HOVER'), ('active', 'ACCENT_ACTIVE')):
                    self.assertIn(f':not(:disabled):{state}', css)
                    bg, fg = values[token], values[token + '_FG']
                    self.assertIn(f'background-image: none;\n  background-color: {bg};\n  border-color: {bg};\n  color: {fg};', css)
                    self.assertGreaterEqual(t.contrast(bg, fg), 4.5)
            stock = files['gtk-4.0/gtk.css'].decode()
            self.assertIn(f'@define-color theme_selected_bg_color {primary};', stock)
            self.assertIn(f'@define-color theme_selected_fg_color {values["ACCENT_FG"]};', stock)

    def test_gtk3_and_shell_roles(self):
        files, _ = t.theme_files('#fb996c', SHELL_SOURCE)
        gtk = files['gtk-3.0/gtk.css'].decode()
        shell = files['gnome-shell/gnome-shell.css'].decode()
        gtk4 = files['gtk-4.0/gtk.css'].decode()
        self.assertIn('scale:not(.color):not(:disabled) > trough > highlight', gtk4)
        self.assertIn('progressbar:not(:disabled) > trough:not(.empty) > progress', gtk4)
        self.assertIn('@define-color theme_selected_bg_color #ee8dac;', gtk)
        self.assertIn('switch:checked:not(:disabled), check:checked:not(:disabled), radio:checked:not(:disabled) {background-color: #fb996c;', gtk)
        self.assertIn('scale:not(.color):not(:disabled) highlight {background-image: none; background-color: #90c970;', gtk)
        self.assertIn('progressbar:not(:disabled) trough:not(.empty) progress {background-image: none; background-color: #90c970;', gtk)
        self.assertIn('.quick-settings .slider {\n  -barlevel-active-background-color: #90c970;', shell)
        self.assertIn('.app-grid-running-dot {\n  background-color: #90c970;', shell)
        self.assertNotIn('.app-well-app-running-dot', shell)
        for offset in ('0 -4px', '0 4px', '-4px 0', '4px 0'):
            self.assertIn(f'box-shadow: inset {offset} #cb96e2;', gtk)
        t.check_quick_settings_css(shell, '#fb996c')


if __name__ == '__main__':
    unittest.main()
