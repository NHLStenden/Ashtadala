"""Verify that TokyoNight's second hue has narrowly scoped, visible UI roles."""
import json
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tokyoadwaita as t
from test_theme import SHELL_SOURCE


class SecondaryRoleTests(unittest.TestCase):
    def test_two_colors_change_gtk_link_ink_without_changing_primary_controls(self):
        one, _ = t.theme_files('#ff9e64', SHELL_SOURCE, '#9d7cd8')
        two, _ = t.theme_files('#ff9e64', SHELL_SOURCE, '#7dcfff')
        for gtk in ('gtk-3.0/gtk.css', 'gtk-4.0/gtk.css'):
            a, b = one[gtk].decode(), two[gtk].decode()
            self.assertNotEqual(a, b, gtk)
            self.assertIn('color: #7dcfff;', b, gtk)
            self.assertIn('color: #ff9e64;', a, gtk) if gtk.startswith('gtk-3') else self.assertIn('--accent-bg-color: #ff9e64', a)
            self.assertNotIn('link:visited', a)
            self.assertIn('link:link', a)
        for files in (one, two):
            pal = json.loads(files['palette.json'])
            self.assertEqual(pal['ACCENT'], '#ff9e64')
            self.assertGreaterEqual(t.contrast(pal['SECONDARY_TEXT'], t.PALETTE['SURFACE']), 4.5)

    def test_user_gtk4_override_gets_actual_secondary_link_styles(self):
        first = t.gtk4_override('#ff9e64', '#9d7cd8')
        second = t.gtk4_override('#ff9e64', '#7dcfff')
        self.assertNotEqual(first, second)
        self.assertIn('window label link:link', first)
        self.assertIn('color: #7dcfff;', second)
        self.assertIn('--accent-bg-color: #ff9e64', first)
        self.assertNotIn('@define-color', first)

    def test_shell_does_not_override_calendar_text_for_selected_or_today(self):
        with_events = SHELL_SOURCE + '\n.calendar-day-with-events { color: #eeeeee; }\n'
        css, counts = t.shell_recolor(with_events, '#ff9e64', '#9d7cd8')
        self.assertEqual(css.count('.calendar-day-with-events'), 1)
        self.assertNotIn('secondary_calendar_event_days', counts)
        self.assertIn('.quick-toggle:checked', css)

    def test_secondary_ink_is_legible_for_all_palette_and_dark_custom_colors(self):
        import tokyonight_colors
        for color in list(tokyonight_colors.ACCENTS.values()) + ['#101010', '#24283b', '#000000', '#ffffff']:
            result = t.secondary_text_color(color)
            self.assertGreaterEqual(t.contrast(result, t.PALETTE['SURFACE']), 4.5, color)
        self.assertEqual(t.secondary_text_color('#7dcfff'), '#7dcfff')
        self.assertNotEqual(t.secondary_text_color('#9d7cd8'), '#9d7cd8')

    def test_tokyonight_semantic_roles_are_fixed_and_contrast_safe(self):
        first, _ = t.theme_files('#ff9e64', SHELL_SOURCE, '#9d7cd8')
        second, _ = t.theme_files('#7aa2f7', SHELL_SOURCE, '#7dcfff')
        for item in (first, second):
            gtk = item['gtk-4.0/gtk.css'].decode()
            gtk3 = item['gtk-3.0/gtk.css'].decode()
            for name, color in [('success', '#9ece6a'), ('warning', '#e0af68'), ('error', '#f7768e')]:
                self.assertIn('--' + name + '-bg-color: ' + color + ';', gtk)
                self.assertIn('@define-color ' + name + '_color ' + color + ';', gtk3)
                self.assertGreaterEqual(t.contrast(color, t.accent_foreground(color)), 4.5)
            self.assertIn('--destructive-bg-color: #f7768e', gtk)

    def test_custom_secondary_stays_exact_for_folder_icons(self):
        data = t.tokens('#7aa2f7', '#292e42')
        self.assertEqual(data['SECONDARY_ACCENT'], '#292e42')
        self.assertNotEqual(data['SECONDARY_TEXT'], data['SECONDARY_ACCENT'])


if __name__ == '__main__':
    unittest.main()
