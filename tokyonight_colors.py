#!/usr/bin/env python3
"""Named accents from folke/tokyonight.nvim's Night (Storm-derived) palette."""
from __future__ import annotations
import re

# Keep names explicit: TokyoNight 'magenta' and 'purple' are different colors.
ACCENTS = {
    'blue': '#7aa2f7',
    'cyan': '#7dcfff',
    'purple': '#9d7cd8',
    'magenta': '#bb9af7',
    'green': '#9ece6a',
    'teal': '#1abc9c',
    'yellow': '#e0af68',
    'peach': '#ff9e64',
    'red': '#f7768e',
}
DEFAULT = 'blue'


def resolve(value: str) -> str:
    if value.lower() in ACCENTS:
        return ACCENTS[value.lower()]
    if re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        return value.lower()
    raise ValueError('Expected a TokyoNight accent (' + ', '.join(ACCENTS) + ') or #RRGGBB')

