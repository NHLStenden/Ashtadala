"""Generate a Papirus folder-color overlay without editing the installed icon theme."""
from __future__ import annotations

import colorsys
import os
from pathlib import Path
import re
import secrets

from tokyonight_colors import ACCENTS, resolve

ICON_THEME = 'TokyoAdwaita-Night-Papirus'
PAPIRUS = ('Papirus-Dark', 'Papirus', 'Papirus-Light')
SIZES = ('16x16', '22x22', '24x24', '32x32', '48x48', '64x64')
ANCHOR_SIZES = ('48x48', '64x64', '32x32', '24x24', '22x22', '16x16')
HEX = re.compile(r'#[0-9a-fA-F]{8}(?![\da-fA-F])|#[0-9a-fA-F]{6}(?![\da-fA-F])|#[0-9a-fA-F]{3,4}(?![\da-fA-F])')


class IconError(Exception):
    pass


def roots() -> list[Path]:
    home = Path.home()
    result = [home / '.icons', Path(os.environ.get('XDG_DATA_HOME') or home / '.local/share') / 'icons']
    for data_dir in (os.environ.get('XDG_DATA_DIRS') or '/usr/local/share:/usr/share').split(':'):
        if data_dir:
            result.append(Path(data_dir) / 'icons')
    return result


def sources(theme: Path) -> list[Path]:
    found = []
    for size in SIZES:
        place = theme / size / 'places'
        for kind in ('folder-blue', 'user-blue'):
            for source in sorted(place.glob(kind + '*.svg')):
                if (source.name == kind + '.svg' or source.name.startswith(kind + '-')) and source.is_file():
                    found.append(source)
    return found


def find_papirus(preferred: str | None = None) -> tuple[str, Path] | None:
    names = (preferred,) if preferred else PAPIRUS
    for name in names:
        if name not in PAPIRUS:
            raise IconError('Unsupported Papirus theme: ' + str(name))
        for root in roots():
            theme = root / name
            if (theme / 'index.theme').is_file() and sources(theme):
                return name, theme
    return None


def pick_color(accent: str, previous: str | None = None) -> str:
    previous_hex = resolve(previous) if previous else None
    options = [name for name, value in ACCENTS.items()
               if value != accent.lower() and value != previous_hex]
    if not options:
        raise IconError('No folder colors available')
    return secrets.choice(options)


def parse_rgb(value: str) -> tuple[float, float, float]:
    token = value[1:]
    if len(token) in (3, 4):
        token = ''.join(c * 2 for c in token)
    return tuple(int(token[i:i + 2], 16) / 255 for i in (0, 2, 4))


def is_blue(h: float, l: float, s: float) -> bool:
    return 0.47 <= h <= 0.77 and s >= 0.12 and l > 0.035


def anchor_color(files: list[Path]) -> tuple[float, float, float]:
    normal = [f for f in files if f.name == 'folder-blue.svg']
    normal.sort(key=lambda p: ANCHOR_SIZES.index(p.parent.parent.name)
                if p.parent.parent.name in ANCHOR_SIZES else len(ANCHOR_SIZES))
    for file in normal:
        colors = []
        raw = file.read_text(encoding='utf-8')
        for m in HEX.finditer(raw):
            if raw[max(0, m.start() - 4):m.start()].lower() == 'url(':
                continue
            h, l, s = colorsys.rgb_to_hls(*parse_rgb(m.group()))
            if is_blue(h, l, s):
                score = abs(l - .58) + .3 * abs(s - .65) + .2 * abs(h - .59)
                colors.append((score, (h, l, s)))
        if colors:
            return min(colors, key=lambda v: v[0])[1]
    raise IconError('Papirus folder-blue.svg contains no blue fills')


def recolor(svg: str, target: str, anchor: tuple[float, float, float]) -> tuple[str, int]:
    target_h, target_l, target_s = colorsys.rgb_to_hls(*parse_rgb(target))
    anchor_h, anchor_l, anchor_s = anchor
    changed = 0

    def change(m: re.Match[str]) -> str:
        nonlocal changed
        token = m.group()
        if m.string[max(0, m.start() - 4):m.start()].lower() == 'url(':
            return token
        h, l, s = colorsys.rgb_to_hls(*parse_rgb(token))
        if not is_blue(h, l, s):
            return token
        hue = (target_h + (h - anchor_h) * .12) % 1
        light = max(.035, min(.96, target_l + (l - anchor_l) * .84))
        sat = max(.16, min(1., target_s * (s / max(anchor_s, .1)) ** .50))
        rgb = colorsys.hls_to_rgb(hue, light, sat)
        mapped = '#{:02x}{:02x}{:02x}'.format(*(round(v * 255) for v in rgb))
        if len(token) == 9:
            mapped += token[7:9]
        elif len(token) == 5:
            mapped += token[4] * 2
        changed += mapped.lower() != token.lower()
        return mapped

    return HEX.sub(change, svg), changed


def build_overlay(theme_name: str, theme: Path, color: str) -> dict[str, bytes]:
    if theme_name not in PAPIRUS or theme.name != theme_name or not (theme / 'index.theme').is_file():
        raise IconError('Papirus theme is missing or unsupported')
    color = resolve(color)
    files = sources(theme)
    if not files:
        raise IconError('Papirus has no blue folder SVG sources')
    anchor = anchor_color(files)
    rendered = {}
    changed = 0
    dirs = []
    for source in files:
        rel = source.relative_to(theme)
        dest_name = rel.name.replace('-blue', '', 1)
        dest = rel.with_name(dest_name).as_posix()
        svg, n = recolor(source.read_text(encoding='utf-8'), color, anchor)
        if dest in rendered:
            raise IconError('Duplicate Papirus destination: ' + dest)
        rendered[dest] = svg.encode('utf-8')
        changed += n
        folder = rel.parent.as_posix()
        if folder not in dirs:
            dirs.append(folder)
    if not changed or not any(name.endswith('/places/folder.svg') for name in rendered):
        raise IconError('Papirus folder source has no usable blue fills or standard folder icon')
    index = ('[Icon Theme]\nName=TokyoAdwaita Night Papirus\n'
             f'Inherits={theme_name}\nDirectories={",".join(dirs)}\n\n')
    for folder in dirs:
        size = int(folder.split('x', 1)[0])
        index += f'[{folder}]\nSize={size}\nType=Fixed\nContext=Places\n\n'
    rendered['index.theme'] = index.encode()
    return rendered
