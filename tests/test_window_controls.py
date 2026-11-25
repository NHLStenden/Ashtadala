"""Window controls retain fixed Ashtadala roles across user accents."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import ashtadala as t
from test_theme import SHELL_SOURCE


class WindowControlTests(unittest.TestCase):
    def test_generated_styles(self):
        for accent in (*t.ACCENTS.values(), '#777777'):
            files, _ = t.theme_files(accent, SHELL_SOURCE)
            for css, prefix, suffix in (
                (files['gtk-3.0/gtk.css'].decode(), 'button.titlebutton.', ''),
                (files['gtk-4.0/gtk.css'].decode(), 'windowcontrols > button.', ' > image'),
                (t.gtk4_override(accent), 'windowcontrols > button.', ' > image'),
            ):
                block = css.split('/* Window controls:', 1)[1]
                for role in ('minimize', 'maximize', 'close'):
                    for state in ('', ':hover', ':active'):
                        self.assertIn(prefix + role + ':not(:disabled)' + state + ('' if role == 'close' else ':not(:backdrop)') + suffix, block)
                for state, color in (('', '#eec651'), (':hover', '#f8d05c'), (':active', '#e4bc46')):
                    rule = block.split(prefix + 'close:not(:disabled)' + state + suffix + ' {', 1)[1].split('}', 1)[0]
                    self.assertIn('background-color: ' + color + ';', rule)
                    self.assertIn('background-image: none;', rule)
                    self.assertIn('color: #13161e;', rule)
                    self.assertIn('opacity: 1;', rule)
                self.assertIn('background-color: #2a3249;', block)
                self.assertIn('background-color: #90aafa;', block)
                self.assertNotIn('@ERROR@', block)
            shell = files['gnome-shell/gnome-shell.css'].decode()
            for state, color in (('', '#eec651'), (':hover', '#f8d05c'), (':active', '#e4bc46')):
                self.assertIn('.window-close' + state + ' {background-color: ' + color, shell)
            self.assertIn('@media (prefers-color-scheme: dark)', t.gtk4_override(accent))

    def test_control_contrast(self):
        v = t.tokens('#fb996c')
        for fg, bg in (('#becdf6', v['HOVER']), (v['LINK_HOVER'], v['BORDER']),
                       (v['DEEP'], v['LINK']), *((v['DEEP'], v[k]) for k in ('CLOSE', 'CLOSE_HOVER', 'CLOSE_ACTIVE'))):
            self.assertGreaterEqual(t.contrast(fg, bg), 4.5)

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
            self.assertIn(parent + ' {\n  filter: none;\n}', css)
            # Ordinary AdwHeaderBar bins and controls retain the dim treatment;
            # neither an enabled close button nor its ancestors may be dimmed.
            selectors = css.split('filter: none;\n}', 1)[1].split('{\n  filter: opacity(0.5);', 1)[0]
            for suffix in ('widget:nth-child(2)', 'box.start > :not(windowcontrols)',
                           'box.end > :not(windowcontrols)', 'windowcontrols > button:not(.close)',
                           'windowcontrols > button.close:disabled', 'windowcontrols > image'):
                self.assertIn(suffix, selectors)
            self.assertNotIn('windowcontrols > button,', selectors)
