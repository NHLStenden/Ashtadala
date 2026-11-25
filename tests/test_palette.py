"""Lock down the mathematical palette and cross-component default."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
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
        for role, step, chroma in [('DEEP', -1, .018), ('BG', 0, .025), ('PANEL', 1, .040), ('SURFACE', 2, .041), ('HOVER', 3, .043), ('BORDER', 6, .064)]:
            self.assertEqual(t.PALETTE[role], p.oklch(.23 + .03*step, chroma, 270))

    def test_native_default(self):
        source = (t.ROOT / 'native-accent-hook/src/accent_hook.c').read_text()
        self.assertIn(f'#define DEFAULT_ACCENT "{p.ACCENTS[p.DEFAULT]}"', source)

    def test_preview_color_roles(self):
        from xml.etree import ElementTree as ET
        preview = ET.parse(t.ROOT / 'assets/Ashtadala-preview.svg')
        by_id = {element.get('id'): element for element in preview.iter()}
        v = t.tokens(p.ACCENTS['peach'])
        for ident, role in [('rect83', 'DEEP'), ('rect195', 'PANEL'),
                            ('rect196', 'BG'), ('rect208', 'SELECTION'),
                            ('circle207', 'CLOSE'), ('rect271', 'ACCENT'),
                            ('path1856', 'SECONDARY_ACCENT'),
                            ('rect227', 'SURFACE'), ('rect233', 'SURFACE'),
                            ('rect235', 'SURFACE')]:
            self.assertEqual(by_id[ident].get('fill'), v[role])
        for ident, color in [('rect234', '#4b4c55'),
                             ('rect90', '#262730'), ('rect278', '#4a4b67'), ('text274', '#e1e5fa')]:
            self.assertEqual(by_id[ident].get('fill'), color)
        self.assertIn('fill:' + v['LEVEL'] + ';', by_id['rect268'].get('style'))
