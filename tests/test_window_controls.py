"""Window controls retain fixed Ashtadala roles across user accents."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import ashtadala as t
from test_theme import SHELL_SOURCE


class WindowControlTests(unittest.TestCase):
    def test_generated_styles(self):
        for accent in ('#90aafa', '#fb996c'):
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
                rest = block.split(prefix + 'close:not(:disabled)' + suffix + ' {', 1)[1].split('}', 1)[0]
                self.assertIn('background-color: #ddb63e;', rest)
                self.assertIn('background-image: none;', rest)
                self.assertIn('color: #13161e;', rest)
                for color in ('#ddb63e', '#eec651', '#c7a01e'):
                    self.assertIn('background-color: ' + color + ';', block)
                self.assertIn('background-color: #2a3249;', block)
                self.assertIn('background-color: #90aafa;', block)
                self.assertNotIn('@ERROR@', block)
            shell = files['gnome-shell/gnome-shell.css'].decode()
            for state, color in (('', '#ddb63e'), (':hover', '#eec651'), (':active', '#c7a01e')):
                self.assertIn('.window-close' + state + ' {background-color: ' + color, shell)
            self.assertIn('@media (prefers-color-scheme: dark)', t.gtk4_override(accent))

    def test_control_contrast(self):
        v = t.tokens('#fb996c')
        for fg, bg in (('#becdf6', v['HOVER']), (v['LINK_HOVER'], v['BORDER']),
                       (v['DEEP'], v['LINK']), *((v['DEEP'], v[k]) for k in ('CLOSE', 'CLOSE_HOVER', 'CLOSE_ACTIVE'))):
            self.assertGreaterEqual(t.contrast(fg, bg), 4.5)
