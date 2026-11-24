"""Verify that fixed widget hues do not replace the configurable accents."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tokyoadwaita as t
from test_theme import SHELL_SOURCE


class WidgetRoleTests(unittest.TestCase):
    def test_roles_are_independent_of_user_accents(self):
        for primary, secondary in [('#ff9e64', '#9d7cd8'), ('#7aa2f7', '#1abc9c')]:
            values = t.tokens(primary, secondary)
            self.assertEqual(values['ACCENT'], primary)
            self.assertEqual(values['SECONDARY_ACCENT'], secondary)
            for name, color in [('SELECTION', '#f7768e'), ('LEVEL', '#9ece6a'),
                                ('PROGRESS', '#9ece6a'), ('TAB', '#bb9af7')]:
                self.assertEqual(values[name], color)
                self.assertGreaterEqual(t.contrast(color, values['PANEL']), 4.5)
            self.assertGreaterEqual(t.contrast(values['SELECTION'], values['SELECTION_FG']), 4.5)

    def test_gtk4_sidebar_is_opaque_and_has_matching_ink(self):
        css = t.gtk4_override('#ff9e64', '#9d7cd8')
        self.assertIn('.navigation-sidebar > row:selected:not(:disabled)', css)
        self.assertIn('background-color: #f7768e;\n  color: #16161e;', css)
        self.assertIn('.navigation-sidebar > row:selected:not(:disabled) label', css)
        self.assertNotIn('--window-fg-color:', css)
        self.assertIn('--accent-bg-color: #ff9e64;', css)
        self.assertIn('scale:not(.color) {\n  --accent-bg-color: #9ece6a;', css)
        self.assertIn('progressbar {\n  --accent-bg-color: #9ece6a;', css)
        self.assertIn('notebook > header > tabs > tab {\n  --accent-bg-color: #bb9af7;', css)
        self.assertIn('tabbar tabbox:not(.single-tab) tab:selected', css)
        self.assertIn('entry:not(:disabled) text selection', css)
        self.assertIn('.navigation-sidebar > flowboxchild:selected:not(:disabled)', css)
        self.assertIn('color-mix(in srgb, #f7768e 92%, white)', css)
        self.assertIn('color-mix(in srgb, #f7768e 90%, black)', css)
        self.assertIn('--accent-fg-color: #16161e;', css)

    def test_stock_gtk4_fallbacks_are_not_in_libadwaita_user_overlay(self):
        files, _ = t.theme_files('#ff9e64', SHELL_SOURCE, '#9d7cd8')
        stock = files['gtk-4.0/gtk.css'].decode()
        user = t.gtk4_override('#ff9e64', '#9d7cd8')
        for rule in ('window.background {background-color: #1a1b26;}',
                     'button.suggested-action:not(.flat):not(:disabled)',
                     'switch:checked:not(:disabled),'):
            self.assertIn(rule, stock)
            self.assertNotIn(rule, user)

    def test_gtk3_and_shell_roles(self):
        files, _ = t.theme_files('#ff9e64', SHELL_SOURCE, '#9d7cd8')
        gtk = files['gtk-3.0/gtk.css'].decode()
        shell = files['gnome-shell/gnome-shell.css'].decode()
        gtk4 = files['gtk-4.0/gtk.css'].decode()
        self.assertIn('scale:not(.color):not(:disabled) > trough > highlight', gtk4)
        self.assertIn('progressbar:not(:disabled) > trough:not(.empty) > progress', gtk4)
        self.assertIn('@define-color theme_selected_bg_color #f7768e;', gtk)
        self.assertIn('switch:checked:not(:disabled), check:checked:not(:disabled), radio:checked:not(:disabled) {background-color: #ff9e64;', gtk)
        self.assertIn('scale:not(.color):not(:disabled) highlight {background-image: none; background-color: #9ece6a;', gtk)
        self.assertIn('progressbar:not(:disabled) trough:not(.empty) progress {background-image: none; background-color: #9ece6a;', gtk)
        self.assertIn('.quick-settings .slider {\n  -barlevel-active-background-color: #9ece6a;', shell)
        self.assertIn('.app-grid-running-dot {\n  background-color: #9ece6a;', shell)
        self.assertNotIn('.app-well-app-running-dot', shell)
        for offset in ('0 -4px', '0 4px', '-4px 0', '4px 0'):
            self.assertIn(f'box-shadow: inset {offset} #bb9af7;', gtk)
        t.check_quick_settings_css(shell, '#ff9e64')


if __name__ == '__main__':
    unittest.main()
