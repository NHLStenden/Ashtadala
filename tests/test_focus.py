"""Fixed cyan focus, independent of accent and existing semantic roles."""
import re
import unittest
from test_theme import t, SHELL_SOURCE

NATIVE_RING = 'box-shadow: inset 0 0 0 2px st-transparentize(-st-accent-color, 0.2) !important;'
FOCUS_SOURCE = SHELL_SOURCE + '\n' + '\n'.join([
    '.button:focus, StEntry:focus { ' + NATIVE_RING + ' background-color: st-mix(-st-accent-color, #28282c, 5%); }',
    '.button:focus:hover { ' + NATIVE_RING + ' }',
    '.button:checked:focus { ' + NATIVE_RING + ' }',
    '.button:focus, .button:hover { ' + NATIVE_RING + ' }',
    '.button:hover { ' + NATIVE_RING + ' }',
    '.lock-entry:focus { box-shadow: inset 0 0 0 2px rgba(255, 255, 255, 0.6) !important; }',
])


class FocusTests(unittest.TestCase):
    def test_existing_cyan_and_contrast_all_variants(self):
        for accent in (*t.ACCENTS.values(), '#000000', '#ffffff', '#777777', '#7e69dd'):
            with self.subTest(accent=accent):
                v = t.tokens(accent)
                self.assertEqual(v['FOCUS'], t.ACCENTS['cyan'])
                self.assertEqual(v['ACCENT'], accent)
                self.assertEqual(v['SELECTION'], t.ACCENTS['red'])
                self.assertEqual(v['LEVEL'], t.ACCENTS['green'])
                self.assertEqual(v['TAB'], t.ACCENTS['purple'])
                for name in ('BG', 'DEEP', 'PANEL', 'SURFACE', 'HOVER', 'BORDER'):
                    self.assertGreaterEqual(t.contrast(v['FOCUS'], v[name]), 3)
                for name in ('ACCENT', 'ACCENT_HOVER', 'ACCENT_ACTIVE', 'SELECTION'):
                    self.assertGreaterEqual(t.contrast(v[name], v[name + '_FG']), 4.5)
                split = '#' + ''.join(f'{round(int(accent[i:i+2], 16)*.85+255*.15):02x}' for i in (1,3,5))
                self.assertGreaterEqual(t.contrast(split, v['FOCUS_SPLIT']), 4.5)

    def test_gtk_focus_is_scoped_and_present_in_both_layers(self):
        for accent in t.ACCENTS.values():
            with self.subTest(accent=accent):
                files, _ = t.theme_files(accent, FOCUS_SOURCE)
                gtk3 = files['gtk-3.0/gtk.css'].decode()
                self.assertIn('outline-color: #45bde7;', gtk3)
                self.assertIn('box-shadow: inset 0 0 0 1px #45bde7;', gtk3)
                self.assertIn('entry:focus:not(.error):not(.warning)', gtk3)
                self.assertIn('outline-color: currentColor;', gtk3)
                self.assertNotIn(':focus-visible', gtk3.split('/* Fixed cyan focus')[0])
                for css in (files['gtk-4.0/gtk.css'].decode(), t.gtk4_override(accent)):
                    block = css.split('/* Fixed cyan keyboard focus', 1)[1]
                    self.assertIn('@media (prefers-contrast: no-preference)', block)
                    self.assertIn('button:focus:focus-visible:not(:disabled):not(:backdrop)', block)
                    self.assertIn('entry:focus-within:not(.error):not(.warning)', block)
                    self.assertIn('outline-color: #45bde7;', block)
                    self.assertIn('outline-offset: 1px;', block)
                    self.assertIn('outline-color: #13161e;', block)
                    self.assertNotIn('background-color:', block.split('/* Compatibility colors')[0])

    def test_shell_only_recolors_native_neutral_focus_ring(self):
        for accent in t.ACCENTS.values():
            with self.subTest(accent=accent):
                css, counts = t.shell_recolor(FOCUS_SOURCE, accent)
                self.assertEqual(counts['focus_ring'], 2)
                self.assertIn('.button:focus, StEntry:focus { box-shadow: inset 0 0 0 2px #45bde7 !important;', css)
                self.assertIn('.button:focus:hover { box-shadow: inset 0 0 0 2px #45bde7 !important;', css)
                old_ring = NATIVE_RING.replace('-st-accent-color', accent)
                for selector in ('.button:checked:focus', '.button:focus, .button:hover', '.button:hover'):
                    self.assertIn(selector + ' { ' + old_ring, css)
                self.assertIn('background-color: st-mix(' + accent + ', #181c29, 5%);', css)
                self.assertIn('rgba(255, 255, 255, 0.6) !important;', css)
                v = t.tokens(accent)
                for selector, color in (('.quick-toggle:checked:focus', v['ACCENT_FG']), ('.quick-toggle-menu-button:checked:focus', v['FOCUS_SPLIT'])):
                    rule = re.search(re.escape(selector) + r'\s*\{([^}]+)\}', css.split('Ashtadala Night managed Quick Settings',1)[1])[1]
                    self.assertIn('box-shadow: inset 0 0 0 2px ' + color + ' !important;', rule)

    def test_shell_without_matching_native_focus_rule_is_unchanged(self):
        _, counts = t.shell_recolor(SHELL_SOURCE, t.ACCENTS['peach'])
        self.assertEqual(counts['focus_ring'], 0)


if __name__ == '__main__':
    unittest.main()
