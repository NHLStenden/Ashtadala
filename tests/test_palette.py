"""Lock down the mathematical palette and cross-component default."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ashtadala_colors as p
import ashtadala as t


class PaletteTests(unittest.TestCase):
    def test_octagon(self):
        self.assertEqual(list(p.HUES.values()), list(range(0, 360, 45)))
        self.assertEqual(len(set(p.ACCENTS.values())), 8)
        for name, h in p.HUES.items():
            self.assertEqual(p.ACCENTS[name], p.oklch(.75, .125, h))
            self.assertGreaterEqual(t.contrast(p.ACCENTS[name], t.PALETTE['BG']), 4.5)
            self.assertGreaterEqual(t.contrast(p.ACCENTS[name], t.accent_foreground(p.ACCENTS[name])), 4.5)
        with self.assertRaises(ValueError):
            p.resolve('magenta')
        with self.assertRaises(ValueError):
            p.oklch(.75, .13, 270)

    def test_surface_ramp(self):
        for role, step in [('DEEP', -2), ('BG', 0), ('PANEL', 1), ('SURFACE', 2), ('HOVER', 3), ('BORDER', 5)]:
            self.assertEqual(t.PALETTE[role], p.oklch(.23 + .03*step, .025, 270))

    def test_native_default(self):
        source = (t.ROOT / 'native-accent-hook/src/accent_hook.c').read_text()
        self.assertIn(f'#define DEFAULT_ACCENT "{p.ACCENTS[p.DEFAULT]}"', source)
