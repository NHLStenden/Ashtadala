#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate the default GTK resource examples from the CSS templates.

The Shell stylesheet is built from GNOME resources during installation.
"""
from pathlib import Path
import json
import tokyoadwaita as t

out = Path(__file__).resolve().parent / 'resources'
values = t.tokens(t.ACCENT_DEFAULT)
static = {
    'gtk-3.0/gtk.css': t.expand('gtk3.css', values),
    'gtk-3.0/gtk-dark.css': t.expand('gtk3.css', values),
    'gtk-4.0/gtk.css': ('@import url("resource:///org/gtk/libgtk/theme/Default/gtk-dark.css");\n'
                          + '@media (prefers-color-scheme: dark) {\n' + t.expand('gtk4-vars.css', values) + '}\n' + t.expand('gtk4-legacy.css', values)),
    'gtk-4.0/gtk-dark.css': ('@import url("resource:///org/gtk/libgtk/theme/Default/gtk-dark.css");\n'
                          + '@media (prefers-color-scheme: dark) {\n' + t.expand('gtk4-vars.css', values) + '}\n' + t.expand('gtk4-legacy.css', values)),
    'gtk-4.0/user-overlay.css': t.gtk4_override(t.ACCENT_DEFAULT),
    'palette.json': json.dumps(values, sort_keys=True, indent=2) + '\n',
    'gnome-shell/BUILD-ON-FEDORA.md': (
        '# GNOME Shell stylesheet\n\n'
        '`./install.sh` extracts the dark stylesheet from Fedora 45\'s installed GNOME Shell\n'
        'GResource and writes `gnome-shell/gnome-shell.css` to the installed theme directory.\n'
        'The repository does not ship a prebuilt Shell stylesheet.\n'),
}
for name, value in static.items():
    f = out / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(value, encoding='utf-8')
print('Generated', len(static), 'default resource examples in', out)
