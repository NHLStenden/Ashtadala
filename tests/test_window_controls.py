"""Window controls retain fixed TokyoNight roles across user accents."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tokyoadwaita as t
from test_theme import SHELL_SOURCE


class WindowControlTests(unittest.TestCase):
    def test_generated_styles(self):
        for accent in ('#7aa2f7', '#ff9e64'):
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
                self.assertIn('background-color: #e0af68;', rest)
                self.assertIn('background-image: none;', rest)
                self.assertIn('color: #16161e;', rest)
                for color in ('#e0af68', '#edc58d', '#be9558'):
                    self.assertIn('background-color: ' + color + ';', block)
                self.assertIn('background-color: #292e42;', block)
                self.assertIn('background-color: #7aa2f7;', block)
                self.assertNotIn('@ERROR@', block)
            shell = files['gnome-shell/gnome-shell.css'].decode()
            for state, color in (('', '#e0af68'), (':hover', '#edc58d'), (':active', '#be9558')):
                self.assertIn('.window-close' + state + ' {background-color: ' + color, shell)
            self.assertIn('@media (prefers-color-scheme: dark)', t.gtk4_override(accent))

    def test_control_contrast(self):
        v = t.tokens('#ff9e64')
        for fg, bg in (('#c0caf5', v['HOVER']), (v['LINK_HOVER'], v['BORDER']),
                       (v['DEEP'], v['LINK']), *((v['DEEP'], v[k]) for k in ('CLOSE', 'CLOSE_HOVER', 'CLOSE_ACTIVE'))):
            self.assertGreaterEqual(t.contrast(fg, bg), 4.5)
