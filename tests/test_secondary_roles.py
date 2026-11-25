"""Verify that Ashtadala's folder identity is independent of semantic and link colors."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import ashtadala as t
from test_theme import SHELL_SOURCE


class SecondaryRoleTests(unittest.TestCase):
    def test_user_gtk4_override_keeps_blue_links_in_dark_mode(self):
        first = t.gtk4_override('#fb996c')
        second = t.gtk4_override('#90c970')
        for css in (first, second):
            self.assertIn('label link:not(:disabled), button.link:not(:disabled) {color: #90aafa;}', css)
            self.assertIn('link:visited:not(:disabled)', css)
            self.assertIn('link:hover:not(:disabled)', css)
            self.assertIn('@media (prefers-color-scheme: dark)', css)
            self.assertNotIn('@define-color', css)

    def test_dimmed_label_keeps_link_ink_independent_of_text_opacity(self):
        files, _ = t.theme_files('#fb996c', SHELL_SOURCE)
        gtk3 = files['gtk-3.0/gtk.css'].decode()
        gtk4 = t.gtk4_override('#fb996c')
        self.assertIn('label.dim-label:not(:disabled) {\n  opacity: 1;\n  color: alpha(currentColor, 0.55);', gtk3)
        self.assertIn('label.dimmed:not(:disabled), label.dim-label:not(:disabled) {\n  opacity: 1;', gtk4)
        self.assertIn('currentColor var(--dim-opacity, 55%), transparent', gtk4)
        self.assertNotIn('\n.dimmed {', gtk4)  # Do not undim containers or disabled widgets.
        values = t.tokens('#fb996c')
        for role in ('LINK', 'LINK_VISITED', 'LINK_HOVER'):
            red, green, blue = (int(values[role][i:i+2], 16) for i in (1, 3, 5))
            self.assertGreater(blue, green)
            self.assertGreater(green, red)
            self.assertGreaterEqual(t.contrast(values[role], values['BG']), 4.5)

    def test_shell_does_not_override_calendar_text_for_selected_or_today(self):
        with_events = SHELL_SOURCE + '\n.calendar-day-with-events { color: #eeeeee; }\n'
        css, counts = t.shell_recolor(with_events, '#fb996c')
        self.assertEqual(css.count('.calendar-day-with-events'), 1)
        self.assertNotIn('secondary_calendar_event_days', counts)
        self.assertIn('.quick-toggle:checked', css)

    def test_link_states_are_legible_on_dark_surfaces(self):
        values = t.tokens('#fb996c')
        for role in ('LINK', 'LINK_VISITED', 'LINK_HOVER'):
            for surface in ('BG', 'DEEP', 'PANEL', 'SURFACE', 'HOVER'):
                self.assertGreaterEqual(t.contrast(values[role], values[surface]), 4.5)
        self.assertGreaterEqual(t.contrast(values['SELECTION'], values['SELECTION_FG']), 4.5)

    def test_ashtadala_semantic_roles_are_fixed_and_contrast_safe(self):
        first, _ = t.theme_files('#fb996c', SHELL_SOURCE)
        second, _ = t.theme_files('#90aafa', SHELL_SOURCE)
        for item in (first, second):
            gtk = item['gtk-4.0/gtk.css'].decode()
            gtk3 = item['gtk-3.0/gtk.css'].decode()
            for name, color in [('success', '#90c970'), ('warning', '#ddb63e'), ('error', '#ee8dac')]:
                self.assertIn('--' + name + '-bg-color: ' + color + ';', gtk)
                self.assertIn('@define-color ' + name + '_color ' + color + ';', gtk3)
                self.assertGreaterEqual(t.contrast(color, t.accent_foreground(color)), 4.5)
            self.assertIn('--destructive-bg-color: #ee8dac', gtk)

    def test_information_is_fixed_and_contrast_safe(self):
        for accent in (*t.ACCENTS.values(), '#000000', '#ffffff', '#777777'):
            with self.subTest(accent=accent):
                v = t.tokens(accent)
                self.assertEqual(v['INFO'], t.ACCENTS['blue'])
                self.assertEqual(v['LINK'], v['INFO'])
                self.assertEqual(v['ACCENT'], accent)
                for role in ('BG', 'DEEP', 'PANEL', 'SURFACE', 'HOVER', 'BORDER'):
                    self.assertGreaterEqual(t.contrast(v['INFO'], v[role]), 3)
                for amount in (.25, .30):
                    tint = '#' + ''.join(f"{round(int(v['INFO'][i:i+2], 16)*amount + int(v['BG'][i:i+2], 16)*(1-amount)):02x}" for i in (1, 3, 5))
                    self.assertGreaterEqual(t.contrast(v['INFO'], tint), 3)
                    self.assertGreaterEqual(t.contrast('#eeeeec', tint), 4.5)

    def test_information_gtk_rules_are_scoped_to_explicit_info_type(self):
        for accent in (*t.ACCENTS.values(), '#000000', '#ffffff', '#777777'):
            with self.subTest(accent=accent):
                files, _ = t.theme_files(accent, SHELL_SOURCE)
                selector = 'infobar.info:not(:disabled):not(:backdrop) > revealer > box'
                gtk3 = files['gtk-3.0/gtk.css'].decode()
                self.assertIn(selector + ' {\n  background-color: mix(#181c29, #90aafa, 0.25);\n  border-bottom-color: #90aafa;\n}', gtk3)
                for gtk4 in (files['gtk-4.0/gtk.css'].decode(), t.gtk4_override(accent)):
                    self.assertIn('@media (prefers-color-scheme: dark)', gtk4)
                    self.assertIn('@media (prefers-contrast: no-preference) {\n  ' + selector, gtk4)
                    self.assertIn('background-color: color-mix(in srgb, #90aafa 25%, #181c29);', gtk4)
                    self.assertIn('box-shadow: inset 0 -1px #90aafa;', gtk4)
                    self.assertIn('infobar.info.action:hover:not(:disabled):not(:backdrop)', gtk4)
                for css in (gtk3, gtk4):
                    for other in ('infobar.warning', 'infobar.error', 'infobar.question', 'banner {', 'toast {'):
                        self.assertNotIn(other, css)

    def test_shell_unseen_indicator_only_and_transparent_panel_fallback(self):
        selector = '.panel-button.clock-display .messages-indicator'
        for accent in (*t.ACCENTS.values(), '#000000', '#ffffff', '#777777'):
            with self.subTest(accent=accent):
                css, _ = t.shell_recolor(SHELL_SOURCE, accent)
                self.assertIn('#panel ' + selector + ' {color: #90aafa;}', css)
                for state in ('overview', 'unlock-screen', 'login-screen'):
                    self.assertIn('#panel:' + state + ' ' + selector, css)
                self.assertIn('#panel:login-screen ' + selector + ' {color: inherit;}', css)
                self.assertNotIn('.message-source-icon', css)
                self.assertNotIn('.privacy-indicator', css)

    def test_folder_color_is_fixed(self):
        data = t.tokens('#90aafa')
        self.assertEqual(data['SECONDARY_ACCENT'], '#cb96e2')
        self.assertNotEqual(data['LINK'], data['SECONDARY_ACCENT'])


if __name__ == '__main__':
    unittest.main()
