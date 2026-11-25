#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Ashtadala Night theme builder and installer for Fedora 45 / GNOME 51."""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from ashtadala_colors import ACCENTS, DEFAULT as DEFAULT_ACCENT_NAME, resolve as resolve_accent, surface, accent_shade, oklch
import papirus_icons

ROOT = Path(__file__).resolve().parents[1]
THEME = 'Ashtadala-Night'
EXTENSION = 'user-theme@gnome-shell-extensions.gcampax.github.com'
STATE_NAME = 'ashtadala-night'
FLATPAK_GRANTS = ('xdg-config/gtk-4.0:ro', 'xdg-data/themes:ro')
START = '/* BEGIN ASHTADALA-NIGHT: managed GTK4 import */'
END = '/* END ASHTADALA-NIGHT */'
IMPORT = '@import url("ashtadala-night.css");'
FOLDER_COLOR = ACCENTS['purple']
# Replace dark surfaces without changing Adwaita's light foregrounds.
PALETTE = {
    'BG': surface(0),
    'DEEP': surface(-1),
    'PANEL': surface(1),
    'SURFACE': surface(2),
    'HOVER': surface(3),
    'BORDER': surface(6),
    'CONTROL_FG': oklch(.85, .06, 270),
    'SUCCESS': ACCENTS['green'],
    'WARNING': ACCENTS['yellow'],
    'ERROR': ACCENTS['red'],
    # A small, persistent control needs a brighter gold than the warning accent.
    'CLOSE': accent_shade('yellow', .05),
    'CLOSE_HOVER': accent_shade('yellow', .08),
    'CLOSE_ACTIVE': accent_shade('yellow', .02),
}

# Known dark grays in GNOME 51 Shell CSS. Leave light colors and alpha values alone.
STOCK_DARK = {
    '#1d1d20': 'DEEP', '#222226': 'BG',
    '#252529': 'BG', '#28282c': 'BG',
    '#29292d': 'PANEL', '#2e2e32': 'PANEL',
    '#36363a': 'SURFACE', '#39393d': 'SURFACE',
    '#3f3f43': 'HOVER', '#424246': 'HOVER',
}
SCHEMAS = [
    ('org.gnome.desktop.interface', 'gtk-theme', THEME),
    ('org.gnome.desktop.interface', 'color-scheme', 'prefer-dark'),
    ('org.gnome.shell.extensions.user-theme', 'name', THEME),
]


class ThemeError(Exception):
    pass


def sha(content: bytes | str) -> str:
    if isinstance(content, str):
        content = content.encode()
    return hashlib.sha256(content).hexdigest()


def run(args: list[str], *, check=True, capture=True) -> subprocess.CompletedProcess:
    p = subprocess.run(args, stdout=subprocess.PIPE if capture else None,
                       stderr=subprocess.PIPE if capture else None, check=False)
    if check and p.returncode:
        tail = (p.stderr or b'').decode(errors='replace').strip()
        raise ThemeError(f'{args[0]} failed ({p.returncode}): {tail}')
    return p


def accent_choice(value: str) -> str:
    """Accept generated palette color names or a custom #RRGGBB."""
    try:
        return resolve_accent(value)
    except ValueError as e:
        raise ThemeError(str(e)) from e


def hook_file() -> Path:
    return ROOT / 'native-accent-hook/scripts/accent-hook.sh'


def hook_run(action: str, color: str | None = None) -> None:
    command = ['bash', str(hook_file()), action]
    if color is not None:
        command.append(color)
    result = run(command, check=False)
    if result.returncode:
        detail = (result.stderr or result.stdout or b'').decode(errors='replace').strip()
        raise ThemeError(f'Native accent hook {action} failed: {detail}')
    if result.stdout:
        print(result.stdout.decode(errors='replace').strip())


def relative_luminance(color: str) -> float:
    rgb = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
    return sum(v * w for v, w in zip(linear, (.2126, .7152, .0722)))


def contrast(a: str, b: str) -> float:
    x, y = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (x + .05) / (y + .05)


def accent_foreground(accent: str) -> str:
    """Choose dark or white text with 4.5:1 contrast; use black at the crossover."""
    dark = PALETTE['DEEP']
    white = '#ffffff'
    preferred = dark if contrast(accent, dark) >= contrast(accent, white) else white
    return preferred if contrast(accent, preferred) >= 4.5 else '#000000'


def tokens(accent: str) -> dict[str, str]:
    selection = ACCENTS['red']
    fg = accent_foreground(accent)
    def tint(amount: float) -> str:
        return '#' + ''.join(f'{round(int(accent[i:i + 2], 16) * (1 - amount) + int(fg[i:i + 2], 16) * amount):02x}'
                             for i in (1, 3, 5))
    hover, active = tint(.10), tint(.20)
    return dict(PALETTE, ACCENT=accent, ACCENT_FG=fg,
                ACCENT_HOVER=hover, ACCENT_HOVER_FG=accent_foreground(hover),
                ACCENT_ACTIVE=active, ACCENT_ACTIVE_FG=accent_foreground(active),
                SELECTION=selection, SELECTION_FG=accent_foreground(selection),
                LEVEL=ACCENTS['green'],
                LEVEL_FG=accent_foreground(ACCENTS['green']),
                PROGRESS=ACCENTS['green'],
                PROGRESS_FG=accent_foreground(ACCENTS['green']),
                TAB=ACCENTS['purple'],
                SECONDARY_ACCENT=FOLDER_COLOR,
                LINK=ACCENTS['blue'],
                LINK_VISITED=oklch(.78, .10, 270),  # Visited links stay blue, not neutral gray.
                LINK_HOVER=oklch(.81, .09, 270),  # Lighter blue for pointer feedback.
                SUCCESS_FG=accent_foreground(PALETTE['SUCCESS']),
                WARNING_FG=accent_foreground(PALETTE['WARNING']),
                ERROR_FG=accent_foreground(PALETTE['ERROR']))


def expand(name: str, values: dict[str, str]) -> str:
    text = (ROOT / 'templates' / name).read_text(encoding='utf-8')
    result = re.sub(r'@([A-Z_]+)@', lambda m: values[m.group(1)], text)
    if re.search(r'@[A-Z_]+@', result):
        raise ThemeError('Unexpanded CSS token in ' + name)
    return result


def shell_recolor(css: str, accent: str) -> tuple[str, dict[str, int]]:
    """Recolor the installed GNOME Shell stylesheet, retaining its selectors and assets."""
    if len(css) < 2000 or '#panel' not in css:
        raise ThemeError('Shell resource is not a recognizable full GNOME dark stylesheet')
    if '.quick-toggle:checked' not in css or '.quick-toggle-menu-button:checked' not in css:
        raise ThemeError('GNOME Shell stylesheet lacks expected Quick Settings selectors; do not apply an unverified accent patch')
    values = tokens(accent)
    counts = {}
    # Replace whole accent tokens, including those inside Shell color functions.
    for key, replacement in [('-st-accent-fg-color', values['ACCENT_FG']),
                             ('-st-accent-color', values['ACCENT'])]:
        css, n = re.subn(r'(?<![\w-])' + re.escape(key) + r'(?![\w-])', replacement, css)
        counts[key] = n
    def replace(m: re.Match[str]) -> str:
        h = m.group(0).lower()
        k = STOCK_DARK.get(h)
        if k:
            counts[k] = counts.get(k, 0) + 1
            return values[k]
        return m.group(0)
    css = re.sub(r'(?<![\w-])#[0-9a-fA-F]{6}(?![\da-fA-F])', replace, css)
    if counts['-st-accent-color'] == 0:
        raise ThemeError('GNOME Shell stylesheet has no native -st-accent-color tokens; release mismatch')
    css += '\n/* Ashtadala Night: original native foreground/alpha preserved. */\n'
    css += expand('shell-extra.css', values)
    # Calendar foregrounds depend on selection state.
    return css, counts


def check_quick_settings_css(shell_css: str, accent: str) -> None:
    """Check expected selectors and colors in the generated Shell CSS."""
    marker = 'Ashtadala Night managed Quick Settings'
    if marker not in shell_css:
        raise ThemeError('Installed Shell CSS lacks the managed Quick Settings accent patch')
    extra = shell_css.split(marker, 1)[1]
    expected = (
        '.quick-settings .quick-toggle:checked',
        '.quick-settings .quick-toggle-has-menu .quick-toggle-menu-button:checked',
        f'background-color: {accent};',
        f'color: {accent_foreground(accent)};',
        f'st-mix({accent}, #ffffff, 85%)',
    )
    missing = [part for part in expected if part not in extra]
    if missing:
        raise ThemeError('Quick Settings accent patch missing expected CSS: ' + ', '.join(missing))


def gtk4_override(accent: str) -> str:
    values = tokens(accent)
    # Named color aliases belong in the installed dark theme; here they could
    # affect libadwaita windows forced into light mode.
    return ('/* Ashtadala Night: dark-only libadwaita palette. */\n'
            '@media (prefers-color-scheme: dark) {\n'
            + expand('gtk4-vars.css', values) + '\n}\n')


def gtk4_theme(accent: str) -> str:
    values = tokens(accent)
    return ('@import url("resource:///org/gtk/libgtk/theme/Default/gtk-dark.css");\n'
            + '@media (prefers-color-scheme: dark) {\n'
            + expand('gtk4-vars.css', values) + '}\n'
            + expand('gtk4-legacy.css', values))


def theme_files(accent: str, shell_original: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    values = tokens(accent)
    shell, counts = shell_recolor(shell_original, accent)
    check_quick_settings_css(shell, accent)
    gtk3 = expand('gtk3.css', values)
    gtk4 = gtk4_theme(accent)
    meta = f'''[Desktop Entry]\nType=X-GNOME-Metatheme\nName=Ashtadala Night\nComment=GTK3, GTK4, GNOME Shell: Adwaita design with generated OKLCH palette\n[X-GNOME-Metatheme]\nGtkTheme={THEME}\nMetacityTheme=Adwaita\nIconTheme=Adwaita\nCursorTheme=Adwaita\n'''
    files = {
        'index.theme': meta.encode(),
        'gtk-3.0/gtk.css': gtk3.encode(),
        'gtk-3.0/gtk-dark.css': gtk3.encode(),
        'gtk-4.0/gtk.css': gtk4.encode(),
        'gtk-4.0/gtk-dark.css': gtk4.encode(),
        'gnome-shell/gnome-shell.css': shell.encode(),
        'palette.json': (json.dumps(values, indent=2, sort_keys=True) + '\n').encode(),
    }
    return files, {'shell_replacements': counts, 'source_sha256': sha(shell_original)}


def stock_shell_resource() -> tuple[str, Path]:
    candidates = [Path('/usr/share/gnome-shell/gnome-shell-theme.gresource')]
    for path in candidates:
        if not path.is_file():
            continue
        names = run(['gresource', 'list', str(path)]).stdout.decode().splitlines()
        matched = [n.strip() for n in names if n.strip().endswith('/gnome-shell-dark.css')]
        if len(matched) != 1:
            raise ThemeError(f'Expected exactly one GNOME Shell dark stylesheet in {path}, found {matched}')
        data = run(['gresource', 'extract', str(path), matched[0]]).stdout
        try:
            return data.decode('utf-8'), path
        except UnicodeDecodeError as e:
            raise ThemeError('GNOME Shell stylesheet was not UTF-8') from e
    raise ThemeError('No GNOME Shell theme GResource in /usr/share/gnome-shell; cannot inherit Adwaita')


def native_preflight() -> None:
    if os.geteuid() == 0:
        raise ThemeError('Run as your GNOME desktop user, not sudo')
    osr = Path('/etc/os-release').read_text(encoding='utf-8')
    version = re.search(r'^VERSION_ID="?([^"\n]+)"?', osr, re.M)
    distro = re.search(r'^ID="?([^"\n]+)"?', osr, re.M)
    if not version or version.group(1) != '45' or not distro or distro.group(1) != 'fedora':
        raise ThemeError('Requires Fedora Linux 45')
    missing = [c for c in ('gsettings', 'gnome-shell', 'gnome-extensions', 'gresource', 'python3') if not shutil.which(c)]
    if missing:
        raise ThemeError('Missing dependencies: ' + ', '.join(missing))
    version_string = run(['gnome-shell', '--version']).stdout.decode(errors='replace')
    if not re.search(r'\b51(?:\.\d+)?\b', version_string):
        raise ThemeError('Requires GNOME Shell 51; found ' + version_string.strip())
    stock_shell_resource()
    if setting_exists('org.gnome.desktop.a11y.interface', 'high-contrast') and \
            gget('org.gnome.desktop.a11y.interface', 'high-contrast') == 'true':
        raise ThemeError('High Contrast is enabled; refusing to apply a non-high-contrast theme')
    if setting_exists('org.gnome.shell', 'disable-user-extensions') and \
            gget('org.gnome.shell', 'disable-user-extensions') == 'true':
        raise ThemeError('GNOME Shell extensions are disabled')
    packages = []
    if not gschema_exists('org.gnome.shell.extensions.user-theme'):
        packages.append('gnome-shell-extension-user-theme')
    if not shutil.which('cc'):
        packages.append('gcc')
    if not shutil.which('readelf'):
        packages.append('binutils')
    if packages:
        if not shutil.which('sudo') or not shutil.which('dnf'):
            raise ThemeError('Missing Fedora packages: ' + ', '.join(packages))
        print('Installing required Fedora packages:', ', '.join(packages))
        run(['sudo', 'dnf', 'install', '-y', *packages], capture=False)
    if not gschema_exists('org.gnome.shell.extensions.user-theme'):
        raise ThemeError('User Themes extension unavailable; log out/in and retry')
    if not shutil.which('cc') or not shutil.which('readelf'):
        raise ThemeError('Compiler or readelf still unavailable after installing dependencies')
    for schema, key, _ in SCHEMAS:
        if not setting_exists(schema, key):
            raise ThemeError(f'Missing GNOME setting {schema}/{key}')
    if not setting_exists('org.gnome.shell', 'enabled-extensions'):
        raise ThemeError('GNOME enabled-extensions setting unavailable')
    if not setting_exists('org.gnome.desktop.interface', 'accent-color'):
        raise ThemeError('GNOME accent-color setting unavailable')


def parse_gvariant_array(value: str) -> list[str]:
    # GSettings prints empty string arrays as '@as []' on some GLib versions.
    value = value.strip()
    if value.startswith('@as '):
        value = value[4:]
    try:
        result = ast.literal_eval(value)
    except (SyntaxError, ValueError) as error:
        raise ThemeError('Cannot parse GNOME enabled-extensions value: ' + value) from error
    if not isinstance(result, list) or any(not isinstance(v, str) for v in result):
        raise ThemeError('GNOME enabled-extensions is not a string array')
    return result


def gschema_exists(schema: str) -> bool:
    p = run(['gsettings', 'list-schemas'])
    return schema in p.stdout.decode().splitlines()


def setting_exists(schema: str, key: str) -> bool:
    p = run(['gsettings', 'list-keys', schema], check=False)
    return p.returncode == 0 and key in p.stdout.decode().splitlines()


def gget(schema: str, key: str) -> str:
    return run(['gsettings', 'get', schema, key]).stdout.decode().strip()


def gset(schema: str, key: str, value: str) -> None:
    run(['gsettings', 'set', schema, key, value])


def greset(schema: str, key: str) -> None:
    run(['gsettings', 'reset', schema, key])


def paths() -> dict[str, Path]:
    home = Path.home()
    data = Path(os.environ.get('XDG_DATA_HOME') or str(home / '.local/share'))
    config = Path(os.environ.get('XDG_CONFIG_HOME') or str(home / '.config'))
    state = Path(os.environ.get('XDG_STATE_HOME') or str(home / '.local/state'))
    return {'user_theme': data / 'themes' / THEME,
            'icon_theme': data / 'icons' / papirus_icons.ICON_THEME,
            'gtk_css': config / 'gtk-4.0/gtk.css',
            'gtk_override': config / 'gtk-4.0/ashtadala-night.css',
            'state': state / STATE_NAME / 'state.json'}


def read_state(statefile: Path) -> dict[str, Any] | None:
    if statefile.is_symlink():
        raise ThemeError('Installation state is a symlink; refusing to use it')
    if not statefile.exists():
        return None
    if not statefile.is_file():
        raise ThemeError('Installation state is not a regular file')
    data = json.loads(statefile.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('format') != 4:
        raise ThemeError('Unsupported installation state format')
    required = {'theme_path': str, 'accent': str, 'files': dict,
                'gtk_override_sha': str, 'settings': dict, 'flatpak_enabled': bool,
                'gtk_css_existed': bool}
    if any(not isinstance(data.get(key), kind) for key, kind in required.items()):
        raise ThemeError('Malformed installation state')
    if any(not isinstance(item, dict) or not isinstance(item.get('old'), str)
           or not isinstance(item.get('set'), str) or '/' not in key
           for key, item in data['settings'].items()):
        raise ThemeError('Malformed saved GNOME settings')
    if data.get('papirus') is not None and (not isinstance(data['papirus'], dict)
                                          or not isinstance(data['papirus'].get('files'), dict)):
        raise ThemeError('Malformed saved icon state')
    return data


def atomic_write(path: Path, content: bytes, mode=None) -> None:
    if path.is_symlink():
        raise ThemeError('Refusing to change symlink: ' + str(path))
    if mode is None:
        mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.ashtadala-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def insert_import(content: str) -> str:
    if (START in content) or (END in content):
        # Replace the previous managed import, if present.
        content = remove_import(content)
    return START + '\n' + IMPORT + '\n' + END + '\n\n' + content


def remove_import(content: str) -> str:
    if START not in content and END not in content:
        return content
    if content.count(START) != 1 or content.count(END) != 1:
        raise ThemeError('GTK4 user CSS has damaged or repeated theme markers; refusing edit')
    start = content.index(START)
    end = content.index(END, start) + len(END)
    if content[start:end] != START + '\n' + IMPORT + '\n' + END:
        raise ThemeError('Managed GTK4 import was modified; refusing edit')
    rest = content[:start] + content[end:]
    return rest[2:] if start == 0 and rest.startswith('\n\n') else rest


def existing_hashes(directory: Path) -> dict[str, str]:
    if directory.is_symlink() or not directory.is_dir():
        raise ThemeError(f'Expected a normal theme directory: {directory}')
    hashes = {}
    for f in directory.rglob('*'):
        if f.is_symlink():
            raise ThemeError('Theme contains a symlink: ' + str(f))
        if f.is_dir():
            continue
        if not f.is_file():
            raise ThemeError('Theme contains an unexpected special file: ' + str(f))
        hashes[f.relative_to(directory).as_posix()] = sha(f.read_bytes())
    return hashes


def assert_owned_theme(directory: Path, expected: dict[str, str]) -> None:
    actual = existing_hashes(directory)
    if actual != expected:
        changed = sorted(set(actual) ^ set(expected) | {k for k in actual.keys() & expected.keys() if actual[k] != expected[k]})
        raise ThemeError('Installed theme changed outside this tool; refusing overwrite/delete: ' + ', '.join(changed))


def create_tree(files: dict[str, bytes], directory: Path) -> None:
    for rel, data in files.items():
        dest = directory / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def owned_file(path: Path, expected: str | None, label: str) -> None:
    if expected is None:
        if path.exists() or path.is_symlink():
            raise ThemeError(f'{label} already exists but was not created by the theme: {path}')
        return
    if not path.is_file() or path.is_symlink() or sha(path.read_bytes()) != expected:
        raise ThemeError(f'{label} was modified or removed after install: {path}')


def stage_theme(directory: Path, files: dict[str, bytes], expected: dict[str, str] | None) -> None:
    directory.parent.mkdir(parents=True, exist_ok=True)
    if directory.exists() or directory.is_symlink():
        if expected is None:
            raise ThemeError('A theme with this name exists but is not owned by this installer')
        assert_owned_theme(directory, expected)
    elif expected is not None:
        raise ThemeError('Previously installed theme directory disappeared; refusing overwrite')
    temp = Path(tempfile.mkdtemp(prefix='.ashtadala-', dir=directory.parent))
    preserve = False
    try:
        generated = temp / THEME
        create_tree(files, generated)
        if directory.exists():
            old = temp / 'old'
            directory.rename(old)
            try:
                generated.rename(directory)
            except (Exception, KeyboardInterrupt):
                try:
                    old.rename(directory)
                except (Exception, KeyboardInterrupt) as err:
                    preserve = True
                    raise ThemeError(f'Cannot restore staged theme; original retained at {old}: {err}') from err
                raise
        else:
            generated.rename(directory)
    finally:
        if not preserve:
            shutil.rmtree(temp)


def delete_theme(directory: Path, expected: dict[str, str]) -> None:
    assert_owned_theme(directory, expected)
    shutil.rmtree(directory)


# The Flatpak override is user-wide. Save its original bytes for uninstall.
# GTK_THEME is not set because it can interfere with libadwaita applications.
def flatpak_present() -> bool:
    return shutil.which('flatpak') is not None


def flatpak_path() -> Path:
    d = Path(os.environ.get('XDG_DATA_HOME') or str(Path.home() / '.local/share'))
    return d / 'flatpak/overrides/global'


def flatpak_snapshot() -> bytes | None:
    return file_snapshot(flatpak_path())


def flatpak_preflight() -> None:
    if not shutil.which('flatpak'):
        raise ThemeError('Flatpak was enabled previously but flatpak is now missing')
    if Path(os.environ.get('XDG_CONFIG_HOME') or str(Path.home() / '.config')) != Path.home() / '.config':
        raise ThemeError('Flatpak requires the standard ~/.config path; custom XDG_CONFIG_HOME is unsupported')
    flatpak_snapshot()  # rejects symlinks


def flatpak_apply() -> None:
    run(['flatpak', 'override', '--user',
         *['--filesystem=' + grant for grant in FLATPAK_GRANTS]], capture=False)


def restore_flatpak_snapshot(raw: bytes | None) -> None:
    restore_snapshot(flatpak_path(), raw)


def file_snapshot(path: Path):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ThemeError('Refusing to change non-regular file: ' + str(path))
    return path.read_bytes() if path.exists() else None


def restore_snapshot(path: Path, raw: bytes | None):
    if raw is None:
        if path.is_symlink():
            raise ThemeError('Refusing to change symlink: ' + str(path))
        if path.exists():
            path.unlink()
    else:
        atomic_write(path, raw)


def get_last_state() -> tuple[dict[str, Any] | None, dict[str, Path]]:
    p = paths()
    return read_state(p['state']), p


def check_conflicts(state: dict[str, Any] | None, p: dict[str, Path], directory: Path):
    if state:
        if state.get('pending'):
            raise ThemeError('Incomplete installation; run ./uninstall.sh before installing again')
        if directory.as_posix() != state['theme_path']:
            raise ThemeError('Installed theme path differs from expected user path; uninstall first')
        assert_owned_theme(directory, state['files'])
        owned_file(p['gtk_override'], state['gtk_override_sha'], 'GTK4 override')
        raw = file_snapshot(p['gtk_css'])
        if raw is None or START not in raw.decode(encoding='utf-8'):
            raise ThemeError('GTK4 import was removed after install; refusing overwrite')
        remove_import(raw.decode('utf-8'))
    else:
        if directory.exists() or directory.is_symlink():
            raise ThemeError('Theme name already in use: ' + str(directory))
        owned_file(p['gtk_override'], None, 'GTK4 override')
        raw = file_snapshot(p['gtk_css'])
        if raw and any(part in raw.decode('utf-8') for part in (START, END, IMPORT)):
            raise ThemeError('Unmanaged theme markers exist in GTK4 user CSS')


def install(args):
    state, p = get_last_state()
    accent = accent_choice(args.accent or (state['accent'] if state else DEFAULT_ACCENT_NAME))
    directory = p['user_theme']
    check_conflicts(state, p, directory)
    previous_icons = state.get('papirus') if state else None
    current_icon = gget('org.gnome.desktop.interface', 'icon-theme').strip("'")
    preferred = previous_icons['base'] if previous_icons else (current_icon if current_icon in papirus_icons.PAPIRUS else None)
    papirus = papirus_icons.find_papirus(preferred)
    if not papirus and not previous_icons and preferred:
        papirus = papirus_icons.find_papirus()
    if previous_icons and not papirus:
        raise ThemeError('Previously used Papirus theme is missing; cannot safely reconfigure icons')
    icon_files = None
    if papirus:
        try:
            icon_files = papirus_icons.build_overlay(papirus[0], papirus[1], FOLDER_COLOR)
        except (papirus_icons.IconError, ValueError, OSError, UnicodeError) as e:
            raise ThemeError(f'Papirus: {e}') from e
        icon_dir = p['icon_theme']
        if previous_icons:
            assert_owned_theme(icon_dir, previous_icons['files'])
        elif icon_dir.exists() or icon_dir.is_symlink():
            raise ThemeError('Icon theme directory already exists: ' + str(icon_dir))
    flatpak_enabled = flatpak_present() or bool(state and state['flatpak_enabled'])
    if flatpak_enabled:
        flatpak_preflight()
    native_preflight()
    hook_run('check')  # Refuse competing preloads or an old binary patch.
    source, _ = stock_shell_resource()
    files, metrics = theme_files(accent, source)
    previous_gtk = file_snapshot(p['gtk_css'])
    previous_override = file_snapshot(p['gtk_override'])
    old_settings = copy.deepcopy(state['settings']) if state else {}
    new_state = {
        'format': 4,
        'theme_path': directory.as_posix(),
        'accent': accent,
        'files': {name: sha(data) for name, data in files.items()},
        'gtk_override_sha': sha(gtk4_override(accent)),
        'shell_source_sha': metrics['source_sha256'],
        'gtk_css_existed': state['gtk_css_existed'] if state else previous_gtk is not None,
        'flatpak_enabled': flatpak_enabled,
        'flatpak_old': state['flatpak_old'] if state else None,
        'flatpak_written_sha': state['flatpak_written_sha'] if state else None,
        'settings': old_settings,
        'papirus': ({'base': papirus[0], 'color': FOLDER_COLOR,
                     'hex': FOLDER_COLOR,
                     'files': {name: sha(data) for name, data in icon_files.items()}}
                    if icon_files is not None else None),
    }
    old_css = previous_gtk.decode('utf-8') if previous_gtk is not None else ''
    new_css = insert_import(old_css)
    prev_theme_files = {k: (directory / k).read_bytes() for k in state['files']} if state else None
    prev_icon_files = ({k: (p['icon_theme'] / k).read_bytes() for k in previous_icons['files']}
                       if previous_icons else None)
    flatpak_before = flatpak_snapshot() if flatpak_enabled else None
    if flatpak_enabled:
        if state and state['flatpak_enabled']:
            if state['flatpak_written_sha'] != sha(flatpak_before or b''):
                raise ThemeError('Flatpak override changed externally; refusing to overwrite')
        else:
            new_state['flatpak_old'] = flatpak_before.decode('utf-8') if flatpak_before is not None else None
    extensions = parse_gvariant_array(gget('org.gnome.shell', 'enabled-extensions'))
    if EXTENSION not in extensions:
        extensions.append(EXTENSION)
    settings_to_apply = SCHEMAS + [
        ('org.gnome.desktop.interface', 'accent-color', 'slate'),
        ('org.gnome.shell', 'enabled-extensions', extensions),
    ]
    if icon_files is not None:
        settings_to_apply.append(('org.gnome.desktop.interface', 'icon-theme', papirus_icons.ICON_THEME))
    planned = []
    for schema, key, value in settings_to_apply:
        skey = schema + '/' + key
        last = gget(schema, key)
        old = old_settings[skey]['old'] if skey in old_settings else last
        encoded = repr(value)
        new_state['settings'][skey] = {'old': old, 'set': encoded}
        planned.append((schema, key, last, encoded))
    previous_state = file_snapshot(p['state'])
    changed_settings: list[tuple[str, str, str]] = []
    theme_applied = icons_applied = flatpak_changed = hook_touched = False
    gtk_override_touched = gtk_css_touched = False
    # Save recovery information before changing any user resource.
    new_state['pending'] = True
    atomic_write(p['state'], (json.dumps(new_state, sort_keys=True, indent=2) + '\n').encode())
    try:
        stage_theme(directory, files, state['files'] if state else None)
        theme_applied = True
        if icon_files is not None:
            stage_theme(p['icon_theme'], icon_files, previous_icons['files'] if previous_icons else None)
            icons_applied = True
        gtk_override_touched = True
        atomic_write(p['gtk_override'], gtk4_override(accent).encode('utf-8'))
        gtk_css_touched = True
        atomic_write(p['gtk_css'], new_css.encode('utf-8'))
        if flatpak_enabled:
            flatpak_changed = True
            flatpak_apply()
            new_state['flatpak_written_sha'] = sha(flatpak_snapshot() or b'')
        for schema, key, last, encoded in planned:
            if last != encoded:
                # A command may change a setting and then report failure.
                changed_settings.append((schema, key, last))
                gset(schema, key, encoded)
            actual = gget(schema, key)
            if not setting_matches(key, actual, encoded):
                raise ThemeError(f'GNOME setting did not take effect: {schema}/{key}')
            new_state['settings'][schema + '/' + key]['set'] = actual
        hook_touched = True
        hook_run('install', accent)
        new_state.pop('pending')
        atomic_write(p['state'], (json.dumps(new_state, sort_keys=True, indent=2) + '\n').encode())
    except (Exception, KeyboardInterrupt):
        errors = []
        def rollback(label, action, *values):
            try:
                action(*values)
            except Exception as err:
                errors.append(label)
                print(f'ROLLBACK FAILED ({label}): {err}', file=sys.stderr)
        if hook_touched:
            if state:
                rollback('accent hook', hook_run, 'install', state['accent'])
            else:
                rollback('accent hook', hook_run, 'uninstall')
        for schema, key, old in reversed(changed_settings):
            rollback(schema + '/' + key, restore_setting, schema, key, old)
        if flatpak_changed:
            rollback('Flatpak', restore_flatpak_snapshot, flatpak_before)
        if gtk_css_touched:
            rollback('GTK4 CSS', restore_snapshot, p['gtk_css'], previous_gtk)
        if gtk_override_touched:
            rollback('GTK4 overlay', restore_snapshot, p['gtk_override'], previous_override)
        if theme_applied:
            if state:
                rollback('theme', stage_theme, directory, prev_theme_files, new_state['files'])
            else:
                rollback('theme', delete_theme, directory, new_state['files'])
        if icons_applied:
            if previous_icons:
                rollback('icons', stage_theme, p['icon_theme'], prev_icon_files, new_state['papirus']['files'])
            else:
                rollback('icons', delete_theme, p['icon_theme'], new_state['papirus']['files'])
        # A failed directory swap can leave a preserved original outside the
        # active path even before stage_theme returns successfully.
        if state and not directory.is_dir():
            errors.append('theme staging')
        if previous_icons and not p['icon_theme'].is_dir():
            errors.append('icon staging')
        if not errors:
            rollback('installation state', restore_snapshot, p['state'], previous_state)
        if errors:
            print('Recovery state retained; run ./uninstall.sh after resolving the errors.', file=sys.stderr)
        raise
    print(f'Installed {THEME} — {accent} (GTK, GNOME Shell, native accent hook).')
    if flatpak_enabled:
        print('Flatpak: GTK theme directories shared read-only')
    if icon_files is not None:
        print(f'Papirus folders: {FOLDER_COLOR}')
    print('Log out and back in to reload GTK styles in running apps, Shell and the native accent hook.')


# The global Flatpak override is shared with other applications. Only undo
# our two exact grants, not other permissions added after installation.
def filesystem_line(raw: bytes | None) -> tuple[str, re.Match | None, list[str]]:
    text = (raw or b'').decode('utf-8')
    sections = list(re.finditer(r'^\[([^\]\r\n]+)\][ \t]*\r?$', text, re.M))
    contexts = [i for i, m in enumerate(sections) if m[1] == 'Context']
    if len(contexts) > 1:
        raise ThemeError('Repeated Flatpak Context sections; refusing edit')
    if not contexts:
        return text, None, []
    i = contexts[0]
    end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
    pattern = re.compile(r'^(filesystems[ \t]*=[ \t]*)([^\r\n]*)', re.M)
    matches = list(pattern.finditer(text, sections[i].end(), end))
    if len(matches) > 1:
        raise ThemeError('Repeated Flatpak filesystem keys; refusing edit')
    if not matches:
        return text, None, []
    m = matches[0]
    # GLib keyfiles escape literal semicolons and backslashes.
    items = re.findall(r'(?:\\.|[^;\\])+', m[2])
    if ';'.join(items).rstrip(';') != m[2].rstrip(';'):
        raise ThemeError('Cannot safely parse Flatpak filesystem list')
    return text, m, items


def restore_flatpak_permissions(state: dict[str, Any]) -> None:
    raw = flatpak_snapshot()
    if raw is None:
        return  # Already removed by the user or an earlier uninstall.
    old = state.get('flatpak_old')
    original = old.encode('utf-8') if old is not None else None
    if sha(raw) == state.get('flatpak_written_sha'):
        restore_flatpak_snapshot(original)
        return
    text, line, current = filesystem_line(raw)
    _, _, previous = filesystem_line(original)
    if line is None:
        return
    def location(entry):
        return re.sub(r':(?:ro|rw|create)$', '', entry.lstrip('!'))
    for grant in FLATPAK_GRANTS:
        prior = [entry for entry in previous if location(entry) == location(grant)]
        now = [entry for entry in current if location(entry) == location(grant)]
        if now == [grant] and prior != now:
            pos = current.index(grant)
            current[pos:pos + 1] = prior
    replacement = ';'.join(current) + (';' if current else '')
    if replacement != line[2]:
        restore_flatpak_snapshot((text[:line.start(2)] + replacement + text[line.end(2):]).encode('utf-8'))


def setting_matches(key: str, actual: str, expected: str) -> bool:
    if key == 'enabled-extensions':
        return parse_gvariant_array(actual) == parse_gvariant_array(expected)
    return actual == expected


def restore_setting(schema: str, key: str, value: str) -> None:
    if not setting_matches(key, gget(schema, key), value):
        gset(schema, key, value)
    if not setting_matches(key, gget(schema, key), value):
        raise ThemeError(f'GNOME setting did not restore: {schema}/{key}')


def present(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def component_paths(p: dict[str, Path]) -> list[Path]:
    return [p['user_theme'], p['icon_theme'], p['gtk_override'],
            p['user_theme'].parent.parent / STATE_NAME / 'libaccent-hook.so',
            p['gtk_css'].parent.parent / 'systemd/user/org.gnome.Shell@user.service.d/80-ashtadala-accent.conf']


def retire_component(path: Path, expected, marker: str, backup_parent: Path, *, tree=False) -> None:
    if not present(path):
        return
    if path.is_symlink():
        raise ThemeError(f'Refusing to remove symlink: {path}')
    # Delete only exact recorded content. Modified or untracked but identifiable
    # theme components are moved out of active search paths instead.
    if expected is not None:
        try:
            if tree:
                assert_owned_theme(path, expected)
            else:
                owned_file(path, expected, 'GTK4 override')
        except ThemeError:
            pass
        else:
            if tree:
                shutil.rmtree(path)
            else:
                path.unlink()
            return
    else:
        check = path / 'index.theme' if tree else path
        if check.is_symlink() or not check.is_file() or marker not in check.read_text(encoding='utf-8').splitlines():
            raise ThemeError(f'Unrecognized component; inspect manually: {path}')
    backup_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix='uninstall-', dir=backup_parent)) / path.name
    shutil.move(str(path), str(destination))
    print('Preserved modified or untracked component outside active paths:', destination)


def uninstall(args):
    p = paths()
    errors = []
    def attempt(label, action, *values, **kwargs):
        try:
            action(*values, **kwargs)
        except Exception as err:
            errors.append(label)
            print(f'ERROR ({label}): {err}', file=sys.stderr)
    state = None
    try:
        state = read_state(p['state'])
    except (ThemeError, ValueError, OSError) as err:
        errors.append('installation state')
        print('ERROR (installation state):', err, file=sys.stderr)
    if state:
        state['pending'] = True
        attempt('record recovery state', atomic_write, p['state'],
                (json.dumps(state, sort_keys=True, indent=2) + '\n').encode())
    had_components = any(present(path) for path in component_paths(p))
    def remove_gtk_import():
        nonlocal had_components
        raw = file_snapshot(p['gtk_css'])
        if raw is None:
            return
        css = raw.decode('utf-8')
        new = remove_import(css)
        # An exact import can survive if a user accidentally removed its markers.
        # Ignore comments; do not rewrite arbitrary custom import syntax.
        masked = re.sub(r'/\*[\s\S]*?\*/', lambda m: re.sub(r'[^\r\n]', ' ', m[0]), new)
        for match in reversed(list(re.finditer(r'^' + re.escape(IMPORT) + r'[ \t]*(?:\r?\n|$)', masked, re.M))):
            if new[match.start():match.end()].strip() == IMPORT:
                new = new[:match.start()] + new[match.end():]
        if 'ashtadala-night.css' in re.sub(r'/\*[\s\S]*?\*/', '', new):
            raise ThemeError('Nonstandard Ashtadala CSS reference remains; inspect gtk.css')
        if new == css:
            return
        had_components = True
        if state and not state.get('gtk_css_existed', True) and not new.strip():
            p['gtk_css'].unlink()
        else:
            atomic_write(p['gtk_css'], new.encode('utf-8'), p['gtk_css'].stat().st_mode & 0o777)
    attempt('native hook', hook_run, 'uninstall')
    attempt('GTK4 import', remove_gtk_import)
    backup_parent = p['state'].parent.parent / 'ashtadala-cleanup-backups'
    if state and state.get('theme_path') != p['user_theme'].as_posix():
        errors.append('theme path')
        print('ERROR: recorded theme path differs from current XDG path; inspect original location.', file=sys.stderr)
    attempt('theme', retire_component, p['user_theme'],
            state.get('files') if state and state.get('theme_path') == p['user_theme'].as_posix() else None,
            f'GtkTheme={THEME}', backup_parent, tree=True)
    attempt('icons', retire_component, p['icon_theme'],
            (state.get('papirus') or {}).get('files') if state else None,
            'Name=Ashtadala Night Papirus', backup_parent, tree=True)
    attempt('GTK4 overlay', retire_component, p['gtk_override'],
            state.get('gtk_override_sha') if state else None,
            '/* Ashtadala Night: dark-only libadwaita palette. */', backup_parent)
    if state and state.get('flatpak_enabled'):
        attempt('Flatpak permissions', restore_flatpak_permissions, state)
    named = {('org.gnome.desktop.interface', 'gtk-theme'): THEME,
             ('org.gnome.desktop.interface', 'icon-theme'): papirus_icons.ICON_THEME,
             ('org.gnome.shell.extensions.user-theme', 'name'): THEME}
    def read_theme_setting(schema, key):
        try:
            return gget(schema, key)
        except ThemeError:
            # The optional extension package may have been uninstalled already.
            if schema == 'org.gnome.shell.extensions.user-theme' and not gschema_exists(schema):
                return None
            raise
    def restore_entry(entry, setting):
        schema, key = entry.rsplit('/', 1)
        current = read_theme_setting(schema, key)
        if current is None:
            return
        if setting_matches(key, current, setting['set']):
            if named.get((schema, key)) and setting['old'] == repr(named[schema, key]):
                greset(schema, key)
                if gget(schema, key) == repr(named[schema, key]):
                    raise ThemeError('Theme is still selected after reset')
            else:
                restore_setting(schema, key, setting['old'])
        elif entry == 'org.gnome.shell/enabled-extensions':
            before = parse_gvariant_array(setting['old'])
            now = parse_gvariant_array(current)
            if EXTENSION not in before and EXTENSION in now:
                restore_setting(schema, key, repr([e for e in now if e != EXTENSION]))
        else:
            print('Keeping user-modified setting:', entry)
    if state:
        for entry, setting in reversed(list(state.get('settings', {}).items())):
            attempt(entry, restore_entry, entry, setting)
    # Never leave our named themes selected, even with no recovery state.
    def clear_selection(schema, key, value):
        nonlocal had_components
        current = read_theme_setting(schema, key)
        if current == repr(value):
            had_components = True
            greset(schema, key)
            if gget(schema, key) == repr(value):
                raise ThemeError('Theme is still selected after reset')
    for (schema, key), value in named.items():
        attempt(schema + '/' + key, clear_selection, schema, key, value)
    if errors:
        raise ThemeError('Uninstall incomplete: ' + ', '.join(errors) + '. Resolve the errors and rerun; recovery state retained if present.')
    if state:
        p['state'].unlink()
        try:
            p['state'].parent.rmdir()
        except OSError:
            pass
        print('Uninstalled Ashtadala Night. Existing CSS outside our import preserved.')
    elif had_components:
        raise ThemeError('Identifiable theme components cleaned, but installation state is missing. '
                         'Previous accent, dark-mode, extension and Flatpak settings cannot be reconstructed. '
                         'Check them manually and log out/in.')
    else:
        print('No installation state or identifiable active components found.')
    print('Log out and back in to fully return to the previous GNOME Shell style.')


def do_validate() -> None:
    from unittest import defaultTestLoader, TextTestRunner
    suite = defaultTestLoader.discover(str(ROOT / 'tests'), pattern='test_*.py')
    result = TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise ThemeError('Tests failed')
    print('Unit tests passed. Fedora/GNOME runtime behavior requires testing on the target machine.')


def diagnose() -> None:
    print('Ashtadala Night diagnostics')
    for schema, key in [*[(s, k) for s, k, _ in SCHEMAS],
                        ('org.gnome.desktop.interface', 'accent-color'),
                        ('org.gnome.desktop.interface', 'icon-theme')]:
        try:
            print(f'{schema}/{key}: {gget(schema, key)}')
        except ThemeError as e:
            print(f'{schema}/{key}: unavailable ({e})')
    p = paths()
    try:
        state = read_state(p['state'])
    except (ThemeError, OSError, ValueError) as e:
        print('Installation state:', e)
        state = None
    if not state:
        print('Theme: no usable installation state')
        for path in component_paths(p):
            if present(path):
                print('Untracked component:', path)
        try:
            css = file_snapshot(p['gtk_css']) or b''
            if START.encode() in css or IMPORT.encode() in css or END.encode() in css:
                print('Untracked GTK4 import:', p['gtk_css'])
        except (ThemeError, OSError) as e:
            print('GTK4 CSS:', e)
        try:
            hook_run('status')
        except ThemeError as e:
            print('Native accent hook:', e)
        return
    if state.get('pending'):
        print('Incomplete installation; run ./uninstall.sh to recover.')
        hook_run('status')
        return
    print('Primary accent:', state['accent'])
    if state.get('papirus'):
        try:
            assert_owned_theme(p['icon_theme'], state['papirus']['files'])
            print('Papirus folders:', state['papirus']['color'], '(installed)')
        except ThemeError as e:
            print('Papirus icons:', e)
    print('Flatpak:', 'enabled' if state['flatpak_enabled'] else 'not installed')
    try:
        assert_owned_theme(Path(state['theme_path']), state['files'])
        print('Theme files: valid')
    except ThemeError as e:
        print('Theme files:', e)
    # Ownership hashes describe the installed release, not necessarily this source.
    # Compare generated GTK files separately so an intact older release is detected.
    accent = state['accent']
    expected_gtk3 = expand('gtk3.css', tokens(accent)).encode()
    expected_gtk4 = gtk4_theme(accent).encode()
    expected = {Path(state['theme_path']) / f'gtk-{version}.0/{name}': css
                for version, css in ((3, expected_gtk3), (4, expected_gtk4))
                for name in ('gtk.css', 'gtk-dark.css')}
    expected[p['gtk_override']] = gtk4_override(accent).encode()
    stale = [str(path) for path, css in expected.items()
             if not path.is_file() or path.read_bytes() != css]
    print('Expected close colors (normal / hover / pressed):',
          *(PALETTE[k] for k in ('CLOSE', 'CLOSE_HOVER', 'CLOSE_ACTIVE')))
    if stale:
        print('GTK styles differ from this source; run ./install.sh:')
        for path in stale:
            print('  ', path)
    else:
        print('GTK styles: current on disk (running apps may still use older CSS)')
    try:
        owned_file(p['gtk_override'], state['gtk_override_sha'], 'GTK4 override')
        user_css = p['gtk_css'].read_text(encoding='utf-8') if p['gtk_css'].is_file() else ''
        if START not in user_css:
            raise ThemeError('Managed GTK4 import missing')
        remaining = remove_import(user_css)
        print('GTK4 user import: valid')
        if remaining.strip():
            print('Additional GTK4 user CSS exists; it may override theme styles.')
    except ThemeError as e:
        print('GTK4 user CSS:', e)
    gtk3_user_css = p['gtk_css'].parent.parent / 'gtk-3.0/gtk.css'
    if gtk3_user_css.is_file():
        print('Additional GTK3 user CSS exists; it may override theme styles:', gtk3_user_css)
    try:
        hook_run('status')
    except ThemeError as e:
        print('Native accent hook:', e)
    print('If on-screen colors differ, log out and back in; disk checks cannot inspect running widgets.')


def parse_args():
    parser = argparse.ArgumentParser(description='Ashtadala Night theme installer')
    cmd = parser.add_subparsers(dest='command', required=True)
    install_cmd = cmd.add_parser('install', help='Install GTK, Shell, Flatpak and native accent hook')
    install_cmd.add_argument('accent', nargs='?', default=None,
                             help='Palette color name or #RRGGBB; default peach on first install')
    configure_cmd = cmd.add_parser('configure', help='Change the installed accent')
    configure_cmd.add_argument('accent', help='Palette color name or #RRGGBB')
    cmd.add_parser('uninstall', help='Remove the theme and restore the previous settings')
    cmd.add_parser('diagnose', help='Inspect the installed theme and hook')
    cmd.add_parser('validate', help='Run automated tests')
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        if args.command in ('install', 'configure', 'uninstall') and os.geteuid() == 0:
            raise ThemeError('Run as your GNOME desktop user, not sudo')
        if args.command == 'install':
            install(args)
        elif args.command == 'configure':
            if not get_last_state()[0]:
                raise ThemeError('Nothing installed; run ./install.sh first')
            install(args)
        elif args.command == 'uninstall':
            uninstall(args)
        elif args.command == 'diagnose':
            diagnose()
        elif args.command == 'validate':
            do_validate()
    except (ThemeError, OSError, ValueError) as e:
        print('ERROR:', e, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
