"""Verify that Ashtadala's folder identity is independent of semantic and link colors."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ashtadala as t
from test_theme import SHELL_SOURCE


class SecondaryRoleTests(unittest.TestCase):
    def test_user_gtk4_override_keeps_blue_links_in_dark_mode(self):
        first = t.gtk4_override('#ef9369')
        second = t.gtk4_override('#8bc06d')
        for css in (first, second):
            self.assertIn('label link:not(:disabled), button.link:not(:disabled) {color: #8fa9fd;}', css)
            self.assertIn('link:visited:not(:disabled)', css)
            self.assertIn('link:hover:not(:disabled)', css)
            self.assertIn('@media (prefers-color-scheme: dark)', css)
            self.assertNotIn('@define-color', css)

    def test_dimmed_label_keeps_link_ink_independent_of_text_opacity(self):
        files, _ = t.theme_files('#ef9369', SHELL_SOURCE)
        gtk3 = files['gtk-3.0/gtk.css'].decode()
        gtk4 = t.gtk4_override('#ef9369')
        self.assertIn('label.dim-label:not(:disabled) {\n  opacity: 1;\n  color: alpha(currentColor, 0.55);', gtk3)
        self.assertIn('label.dimmed:not(:disabled), label.dim-label:not(:disabled) {\n  opacity: 1;', gtk4)
        self.assertIn('currentColor var(--dim-opacity, 55%), transparent', gtk4)
        self.assertNotIn('\n.dimmed {', gtk4)  # Do not undim containers or disabled widgets.
        values = t.tokens('#ef9369')
        for role in ('LINK', 'LINK_VISITED', 'LINK_HOVER'):
            red, green, blue = (int(values[role][i:i+2], 16) for i in (1, 3, 5))
            self.assertGreater(blue, green)
            self.assertGreater(green, red)
            self.assertGreaterEqual(t.contrast(values[role], values['BG']), 4.5)

    def test_shell_does_not_override_calendar_text_for_selected_or_today(self):
        with_events = SHELL_SOURCE + '\n.calendar-day-with-events { color: #eeeeee; }\n'
        css, counts = t.shell_recolor(with_events, '#ef9369')
        self.assertEqual(css.count('.calendar-day-with-events'), 1)
        self.assertNotIn('secondary_calendar_event_days', counts)
        self.assertIn('.quick-toggle:checked', css)

    def test_link_states_are_legible_on_dark_surfaces(self):
        values = t.tokens('#ef9369')
        for role in ('LINK', 'LINK_VISITED', 'LINK_HOVER'):
            for surface in ('BG', 'DEEP', 'PANEL', 'SURFACE', 'HOVER'):
                self.assertGreaterEqual(t.contrast(values[role], values[surface]), 4.5)
        self.assertGreaterEqual(t.contrast(values['SELECTION'], values['SELECTION_FG']), 4.5)

    def test_ashtadala_semantic_roles_are_fixed_and_contrast_safe(self):
        first, _ = t.theme_files('#ef9369', SHELL_SOURCE)
        second, _ = t.theme_files('#8fa9fd', SHELL_SOURCE)
        for item in (first, second):
            gtk = item['gtk-4.0/gtk.css'].decode()
            gtk3 = item['gtk-3.0/gtk.css'].decode()
            for name, color in [('success', '#8bc06d'), ('warning', '#cdaa45'), ('error', '#ee8bab')]:
                self.assertIn('--' + name + '-bg-color: ' + color + ';', gtk)
                self.assertIn('@define-color ' + name + '_color ' + color + ';', gtk3)
                self.assertGreaterEqual(t.contrast(color, t.accent_foreground(color)), 4.5)
            self.assertIn('--destructive-bg-color: #ee8bab', gtk)

    def test_folder_color_is_fixed(self):
        data = t.tokens('#8fa9fd')
        self.assertEqual(data['SECONDARY_ACCENT'], '#cc95e4')
        self.assertNotEqual(data['LINK'], data['SECONDARY_ACCENT'])


if __name__ == '__main__':
    unittest.main()
