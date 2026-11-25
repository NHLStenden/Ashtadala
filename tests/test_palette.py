"""Lock down the mathematical palette and cross-component default."""
import math
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
        self.assertEqual(list(p.ACCENTS.values()), [
            '#ee8dac', '#fb996c', '#ddb63e', '#90c970',
            '#3bc9b2', '#45bde7', '#90aafa', '#cb96e2',
        ])
        for name, h in p.HUES.items():
            weight = ((1 + math.sin(math.radians(h))) / 2)**3
            L, C, H = p.accent_coordinates(h)
            self.assertAlmostEqual(L, .75 + .04*weight)
            self.assertAlmostEqual(C, .12 + .02*weight)
            self.assertEqual(H, h)
            self.assertEqual(p.ACCENTS[name], p.oklch(L, C, H))
            self.assertGreaterEqual(t.contrast(p.ACCENTS[name], t.PALETTE['BG']), 7.0)
            self.assertGreaterEqual(t.contrast(p.ACCENTS[name], t.PALETTE['HOVER']), 4.5)
            self.assertGreaterEqual(t.contrast(p.ACCENTS[name], t.accent_foreground(p.ACCENTS[name])), 4.5)
        with self.assertRaises(ValueError):
            p.resolve('magenta')
        with self.assertRaises(ValueError):
            p.oklch(.75, .13, 270)

    def test_harmonic_symmetry_and_gamut(self):
        for h in range(360):
            L, C, H = p.accent_coordinates(h)
            reflected = p.accent_coordinates((180 - h) % 360)
            self.assertAlmostEqual(L, reflected[0])
            self.assertAlmostEqual(C, reflected[1])
            # The converter rejects out-of-gamut colors rather than clipping.
            p.oklch(L, C, H)
        for h, expected in [(90, (.79, .14, 90)), (270, (.75, .12, 270))]:
            for actual, target in zip(p.accent_coordinates(h), expected):
                self.assertAlmostEqual(actual, target)

    def test_logo_palette(self):
        from xml.etree import ElementTree as ET
        logo = ET.parse(t.ROOT / 'assets/Ashtadala-logo.svg')
        self.assertEqual([element.get('fill') for element in logo.iter('{http://www.w3.org/2000/svg}use')],
                         list(p.ACCENTS.values()))

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
                            ('circle207', 'CLOSE'), ('circle116', 'CLOSE'), ('rect271', 'ACCENT'),
                            ('path1856', 'SECONDARY_ACCENT'),
                            ('rect227', 'SURFACE'), ('rect233', 'SURFACE'),
                            ('rect235', 'SURFACE')]:
            self.assertEqual(by_id[ident].get('fill'), v[role])
        for ident, color in [('rect234', '#4b4c55'),
                             ('rect90', '#262730'), ('rect278', '#4a4b67')]:
            self.assertEqual(by_id[ident].get('fill'), color)
        for ident in ('rect268', 'rect270'):
            self.assertEqual(by_id[ident].get('fill'), v['LEVEL'])
            self.assertIn('fill:' + v['LEVEL'] + ';', by_id[ident].get('style'))
        for ident in ('text274', 'text275', 'text278', 'text284', 'text290',
                      'path1940', 'path1943', 'path1950', 'circle283',
                      'ref-icon-1600-228', 'ref-icon-1825-225', 'ref-icon-1599-439'):
            self.assertEqual(by_id[ident].get('fill'), v['ACCENT_FG'])
        for ident in ('path1906', 'path117'):
            self.assertEqual(by_id[ident].get('stroke'), v['DEEP'])
