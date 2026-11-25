"""Window controls retain fixed Ashtadala roles across user accents."""
import re
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import ashtadala as t
from test_theme import SHELL_SOURCE


class WindowControlTests(unittest.TestCase):
    def test_generated_styles(self):
        for accent in (*t.ACCENTS.values(), '#000000', '#ffffff', '#777777'):
            files, _ = t.theme_files(accent, SHELL_SOURCE)
            for css, prefix, suffix in (
                (files['gtk-3.0/gtk.css'].decode(), 'button.titlebutton.', ''),
                (files['gtk-4.0/gtk.css'].decode(), 'windowcontrols > button.', ' > image'),
                (t.gtk4_override(accent), 'windowcontrols > button.', ' > image'),
            ):
                block = css.split('/* Window controls:', 1)[1].split('/* Fixed cyan', 1)[0].split('*/', 1)[1]
                block = re.sub(r'/\*.*?\*/', '', block, flags=re.S)
                # Check the actual grouped declarations, not just color presence.
                rules = re.findall(r'([^{}]+)\{([^{}]+)\}', block)
                for role in ('minimize', 'maximize'):
                    for state, background, foreground in (
                        ('', '#2a3249', '#3bc9b2'),
                        (':hover', '#3d486d', '#3bc9b2'),
                        (':active', '#3bc9b2', '#13161e'),
                    ):
                        selector = prefix + role + ':not(:disabled)' + state + ':not(:backdrop)' + suffix
                        matching = [body for selectors, body in rules
                                    if selector in [item.strip() for item in selectors.split(',')]]
                        self.assertEqual(len(matching), 1, (accent, selector))
                        self.assertIn('background-color: ' + background + ';', matching[0])
                        self.assertIn('color: ' + foreground + ';', matching[0])
                # All minimize/maximize recoloring excludes disabled and backdrop states.
                for selectors, body in rules:
                    if '#3bc9b2' in body:
                        for selector in selectors.split(','):
                            self.assertIn(':not(:disabled)', selector)
                            self.assertIn(':not(:backdrop)', selector)
                for state, color in (('', '#eec651'), (':hover', '#f8d05c'), (':active', '#e4bc46')):
                    rule = block.split(prefix + 'close:not(:disabled)' + state + suffix + ' {', 1)[1].split('}', 1)[0]
                    self.assertIn('background-color: ' + color + ';', rule)
                    self.assertIn('background-image: none;', rule)
                    self.assertIn('color: #13161e;', rule)
                    self.assertIn('opacity: 1;', rule)
                self.assertIn('background-color: #2a3249;', block)
                self.assertNotIn('@ERROR@', block)
            shell = files['gnome-shell/gnome-shell.css'].decode()
            for state, color in (('', '#eec651'), (':hover', '#f8d05c'), (':active', '#e4bc46')):
                self.assertIn('.window-close' + state + ' {background-color: ' + color, shell)
            self.assertIn('@media (prefers-color-scheme: dark)', t.gtk4_override(accent))

    def test_control_contrast(self):
        for accent in (*t.ACCENTS.values(), '#000000', '#ffffff', '#777777'):
            v = t.tokens(accent)
            self.assertEqual(v['WINDOW_CONTROL'], t.ACCENTS['teal'])
            self.assertEqual(v['FOCUS'], t.ACCENTS['cyan'])
            self.assertEqual(v['LINK'], t.ACCENTS['blue'])
            # Symbolic icons are non-text controls (3:1), not body text (4.5:1).
            for bg in ('HOVER', 'BORDER', 'PANEL'):
                self.assertGreaterEqual(t.contrast(v['WINDOW_CONTROL'], v[bg]), 3)
            self.assertGreaterEqual(t.contrast(v['DEEP'], v['WINDOW_CONTROL']), 4.5)
            for k in ('CLOSE', 'CLOSE_HOVER', 'CLOSE_ACTIVE'):
                self.assertGreaterEqual(t.contrast(v['DEEP'], v[k]), 4.5)

    def test_close_is_brighter_than_warning_and_has_distinct_states(self):
        from ashtadala_colors import accent_shade
        v = t.tokens('#fb996c')
        self.assertEqual(v['WARNING'], '#ddb63e')
        for key, delta in (('CLOSE', .05), ('CLOSE_HOVER', .08), ('CLOSE_ACTIVE', .02)):
            self.assertEqual(v[key], accent_shade('yellow', delta))
            self.assertGreaterEqual(t.contrast(v[key], v['PANEL']), 7)
        self.assertLess(t.relative_luminance(v['WARNING']), t.relative_luminance(v['CLOSE_ACTIVE']))
        self.assertLess(t.relative_luminance(v['CLOSE_ACTIVE']), t.relative_luminance(v['CLOSE']))
        self.assertLess(t.relative_luminance(v['CLOSE']), t.relative_luminance(v['CLOSE_HOVER']))

    def test_adwaita_backdrop_filter_excludes_enabled_close(self):
        files, _ = t.theme_files('#fb996c', SHELL_SOURCE)
        for css in (files['gtk-4.0/gtk.css'].decode(), t.gtk4_override('#fb996c')):
            parent = 'headerbar:not(.flat):not(.inline):backdrop > windowhandle'
            block = css.split('/* Libadwaita dims both', 1)[1]
            reset, remainder = block.split(' {\n  filter: none;\n}', 1)
            self.assertIn(parent, reset)
            for side in ('top', 'bottom'):
                self.assertIn(f'toolbarview > .{side}-bar:backdrop > windowhandle', reset)
            selectors = remainder.split('{\n  filter: opacity(0.5);', 1)[0]
            for suffix in ('box > :nth-child(2)', 'box.start > :not(windowcontrols)',
                           'box.end > :not(windowcontrols)', 'windowcontrols > button:not(.close)',
                           'windowcontrols > button.close:disabled', 'windowcontrols > image'):
                self.assertIn(suffix, selectors)
            for side in ('start', 'end'):
                for nesting in ('', 'widget > '):
                    self.assertIn(parent + f' > box > {nesting}box.{side} > :not(windowcontrols)', selectors)
            self.assertNotIn('windowcontrols > button,', selectors)
            self.assertNotIn('> box > :not(headerbar)', remainder)
