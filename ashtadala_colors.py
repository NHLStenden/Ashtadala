#!/usr/bin/env python3
"""Perceptual accent ring and dark surface ramp, encoded as sRGB hex."""
from __future__ import annotations
import math
import re

ACCENT_L, ACCENT_C = .75, .125
SURFACE_L, SURFACE_C, SURFACE_H, SURFACE_STEP = .23, .025, 270, .03


def oklch(L: float, C: float, H: float) -> str:
    a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    x = (L + .3963377774*a + .2158037573*b)**3
    y = (L - .1055613458*a - .0638541728*b)**3
    z = (L - .0894841775*a - 1.291485548*b)**3
    rgb = (4.0767416621*x - 3.3077115913*y + .2309699292*z,
           -1.2684380046*x + 2.6097574011*y - .3413193965*z,
           -.0041960863*x - .7034186147*y + 1.707614701*z)
    if any(v < -1e-9 or v > 1+1e-9 for v in rgb):
        raise ValueError(f'Outside sRGB: OKLCH({L}, {C}, {H})')
    return '#' + ''.join(f'{round(255*(12.92*v if v <= .0031308 else 1.055*v**(1/2.4)-.055)):02x}' for v in rgb)


# Eight distinct names, retaining the existing semantic vocabulary where possible.
HUES = dict(zip(('red', 'peach', 'yellow', 'green', 'teal', 'cyan', 'blue', 'purple'), range(0, 360, 45)))
ACCENTS = {name: oklch(ACCENT_L, ACCENT_C, hue) for name, hue in HUES.items()}
DEFAULT = 'blue'


# Original surface roles have different tint strengths; the main background
# anchors the ramp. Do not turn the deeper neutral surfaces blue or flatten
# the richer blue panels and borders into gray.
SURFACE_CHROMA = {-1: .018, 0: SURFACE_C, 1: .040, 2: .041, 3: .043, 6: .064}


def surface(step: int) -> str:
    return oklch(SURFACE_L + SURFACE_STEP*step, SURFACE_CHROMA.get(step, SURFACE_C), SURFACE_H)


def accent_shade(name: str, lightness: float) -> str:
    return oklch(lightness, ACCENT_C, HUES[name])


def resolve(value: str) -> str:
    if value.lower() in ACCENTS:
        return ACCENTS[value.lower()]
    if re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        return value.lower()
    raise ValueError('Expected a palette accent (' + ', '.join(ACCENTS) + ') or #RRGGBB')
