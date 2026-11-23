#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""TokyoAdwaita Night theme builder and installer for Fedora 45 / GNOME 51."""
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

from tokyonight_colors import ACCENTS as TOKYONIGHT_ACCENTS, DEFAULT as DEFAULT_ACCENT_NAME, resolve as resolve_tokyonight_accent

ROOT = Path(__file__).resolve().parent
THEME = 'TokyoAdwaita-Night'
EXTENSION = 'user-theme@gnome-shell-extensions.gcampax.github.com'
STATE_NAME = 'tokyoadwaita-night'
START = '/* BEGIN TOKYOADWAITA-NIGHT: managed GTK4 import */'
END = '/* END TOKYOADWAITA-NIGHT */'
IMPORT = '@import url("tokyoadwaita-night.css");'
ACCENT_DEFAULT = TOKYONIGHT_ACCENTS[DEFAULT_ACCENT_NAME]
# Replace dark surfaces without changing Adwaita's light foregrounds.
PALETTE = {
    'BG': '#1a1b26',
    'DEEP': '#16161e',
    'PANEL': '#1f2335',
    'SURFACE': '#24283b',
    'HOVER': '#292e42',
    'BORDER': '#414868',
}
# Known dark grays in GNOME 51 Shell CSS. Leave light colors and alpha values alone.
STOCK_DARK = {
    '#1d1d20': 'DEEP', '#222226': 'BG',
    '#252529': 'BG', '#28282c': 'BG',
    '#29292d': 'PANEL', '#2e2e32': 'PANEL',
    '#36363a': 'SURFACE', '#39393d': 'SURFACE',
    '#3f3f43': 'HOVER', '#424246': 'HOVER',
}
SYSTEM_ACCENTS = {
    'blue': '#3584e4', 'teal': '#2190a4', 'green': '#3a944a',
    'yellow': '#c88800', 'orange': '#ed5b00', 'red': '#e62d42',
    'pink': '#d56199', 'purple': '#9141ac', 'slate': '#6f8396',
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


def accent_valid(value: str) -> str:
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        raise ThemeError('The accent must be a six-digit #RRGGBB hexadecimal color')
    return value.lower()


def accent_choice(value: str) -> str:
    """Accept official TokyoNight color names or a custom #RRGGBB."""
    try:
        return resolve_tokyonight_accent(value)
    except ValueError as e:
        raise ThemeError(str(e)) from e


def detour_file() -> Path:
    return ROOT / 'native-detour/scripts/gnome-slate-detour.sh'


def detour_run(action: str, color: str | None = None) -> None:
    """Delegate lifecycle to the separately reversible, user-only v2 installer."""
    argv = ['bash', str(detour_file()), action]
    if color is not None:
        argv.append(color)
    result = run(argv, check=False)
    if result.returncode:
        details = (result.stderr or result.stdout or b'').decode(errors='replace').strip()
        raise ThemeError(f'Native GNOME accent detour {action} failed: {details}')
    output = result.stdout.decode(errors='replace').strip()
    if output:
        print(output)


def detour_existing_color() -> str | None:
    """Snapshot only our known v2 drop-in for transactional rollback."""
    config = Path(os.environ.get('XDG_CONFIG_HOME') or str(Path.home() / '.config'))
    dropin = config / 'systemd/user/org.gnome.Shell@user.service.d/80-gnome-slate-detour.conf'
    if dropin.is_symlink():
        raise ThemeError('Native accent drop-in is a symlink; refusing modification')
    if not dropin.exists():
        return None
    data = dropin.read_text(encoding='utf-8')
    if '# Managed by gnome-slate-detour v2' not in data.splitlines():
        raise ThemeError('An unmanaged GNOME accent drop-in exists; refusing to adopt it')
    matches = re.findall(r'^Environment="GNOME_SLATE_DETOUR_COLOR=(#[0-9a-fA-F]{6})"$', data, re.M)
    if len(matches) != 1:
        raise ThemeError('Managed native accent drop-in has an unexpected color definition')
    return matches[0].lower()


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


def oklab(color: str) -> tuple[float, float, float]:
    """Convert an sRGB hex color to Oklab."""
    rgb = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
    l = (.4122214708*r + .5363325363*g + .0514459929*b)**(1/3)
    m = (.2119034982*r + .6806995451*g + .1073969566*b)**(1/3)
    s = (.0883024619*r + .2817188376*g + .6299787005*b)**(1/3)
    return (.2104542553*l + .793617785*m - .0040720468*s,
            1.9779984951*l - 2.4285922050*m + .4505937099*s,
            .0259040371*l + .7827717662*m - .8086757660*s)


def nearest_system_accent(color: str) -> str:
    """Find the closest named GNOME accent, weighted toward hue."""
    import math
    L, a, b = oklab(color)
    hue = math.atan2(b, a)
    chroma = math.hypot(a, b)
    def distance(item):
        L2, a2, b2 = oklab(item[1])
        hue2 = math.atan2(b2, a2)
        dh = abs(math.atan2(math.sin(hue-hue2), math.cos(hue-hue2))) / math.pi
        # Hue has little significance at low chroma.
        hue_weight = min(chroma / .055, 1.0)
        return 1.7 * hue_weight * dh**2 + .65 * (L-L2)**2 + .45 * (chroma-math.hypot(a2,b2))**2
    return min(SYSTEM_ACCENTS.items(), key=distance)[0]


def tokens(accent: str) -> dict[str, str]:
    return dict(PALETTE, ACCENT=accent, ACCENT_FG=accent_foreground(accent))


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
    css += '\n/* TokyoAdwaita Night v3.1: original native foreground/alpha preserved. */\n'
    css += expand('shell-extra.css', values)
    return css, counts


def check_quick_settings_css(shell_css: str, accent: str) -> None:
    """Check expected selectors and colors in the generated Shell CSS."""
    marker = 'TokyoAdwaita Night 3.1'
    if marker not in shell_css:
        raise ThemeError('Installed Shell CSS lacks the v3.1 Quick Settings accent patch')
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
    return ('/* TokyoAdwaita Night: dark-only libadwaita palette. */\n'
            '@media (prefers-color-scheme: dark) {\n'
            + expand('gtk4-vars.css', values) + '\n}\n')


def theme_files(accent: str, shell_original: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    values = tokens(accent)
    shell, counts = shell_recolor(shell_original, accent)
    check_quick_settings_css(shell, accent)
    gtk3 = expand('gtk3.css', values)
    gtk4 = ('@import url("resource:///org/gtk/libgtk/theme/Default/gtk-dark.css");\n'
            + '@media (prefers-color-scheme: dark) {\n'
            + expand('gtk4-vars.css', values) + '}\n'
            + expand('gtk4-legacy.css', values))
    meta = f'''[Desktop Entry]\nType=X-GNOME-Metatheme\nName=TokyoAdwaita Night\nComment=GTK3, GTK4, GNOME Shell: Adwaita design with TokyoNight Night palette\n[X-GNOME-Metatheme]\nGtkTheme={THEME}\nMetacityTheme=Adwaita\nIconTheme=Adwaita\nCursorTheme=Adwaita\n'''
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


def native_preflight(need_shell=True, install_extension=False):
    if os.geteuid() == 0:
        raise ThemeError('Run as your desktop account, not with sudo. System theme copy elevates itself.')
    try:
        osr = Path('/etc/os-release').read_text()
    except FileNotFoundError:
        raise ThemeError('Fedora /etc/os-release not found')
    version = re.search(r'^VERSION_ID="?([^"\n]+)"?', osr, re.M)
    distro = re.search(r'^ID="?([^"\n]+)"?', osr, re.M)
    if not version or version.group(1) != '45' or not distro or distro.group(1) != 'fedora':
        raise ThemeError('This installer specifically requires Fedora Linux 45')
    needed = ['gsettings', 'gnome-shell', 'gnome-extensions', 'gresource', 'python3']
    missing = [c for c in needed if not shutil.which(c)]
    if missing:
        raise ThemeError('Missing Fedora dependencies: ' + ', '.join(missing))
    v = run(['gnome-shell', '--version']).stdout.decode(errors='replace')
    if not re.search(r'\b51(?:\.\d+)?\b', v):
        raise ThemeError(f'GNOME Shell 51 required; received {v.strip()}')
    if need_shell:
        stock_shell_resource()
    if setting_exists('org.gnome.desktop.a11y.interface', 'high-contrast') and \
            gget('org.gnome.desktop.a11y.interface', 'high-contrast') == 'true':
        raise ThemeError('High Contrast accessibility mode is enabled. This non-high-contrast theme would reduce accessibility; refusing installation.')
    if setting_exists('org.gnome.shell', 'disable-user-extensions') and \
            gget('org.gnome.shell', 'disable-user-extensions') == 'true':
        raise ThemeError('GNOME Shell user extensions are globally disabled. Enable them before using User Themes.')
    if not gschema_exists('org.gnome.shell.extensions.user-theme'):
        if install_extension:
            if not shutil.which('sudo') or not shutil.which('dnf'):
                raise ThemeError('Need sudo and dnf to install the official User Themes extension')
            print('Installing official Fedora GNOME 51 User Themes package...')
            run(['sudo', 'dnf', 'install', '-y', 'gnome-shell-extension-user-theme'], capture=False)
        if not gschema_exists('org.gnome.shell.extensions.user-theme'):
            raise ThemeError('User Themes extension not installed. Run: sudo dnf install gnome-shell-extension-user-theme, or use --install-extension')
    for schema, key, _ in SCHEMAS:
        if not setting_exists(schema, key):
            raise ThemeError(f'Missing GNOME setting {schema} {key}')
    if not setting_exists('org.gnome.shell', 'enabled-extensions'):
        raise ThemeError('GNOME Shell enabled-extensions setting missing')
    if not setting_exists('org.gnome.desktop.interface', 'accent-color'):
        raise ThemeError('GNOME system accent-color setting is unavailable')


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
    p = run(['gsettings', 'list-schemas'], check=False)
    return p.returncode == 0 and schema in p.stdout.decode().splitlines()


def setting_exists(schema: str, key: str) -> bool:
    p = run(['gsettings', 'list-keys', schema], check=False)
    return p.returncode == 0 and key in p.stdout.decode().splitlines()


def gget(schema: str, key: str) -> str:
    return run(['gsettings', 'get', schema, key]).stdout.decode().strip()


def gset(schema: str, key: str, value: str) -> None:
    run(['gsettings', 'set', schema, key, value])


def paths() -> dict[str, Path]:
    home = Path.home()
    data = Path(os.environ.get('XDG_DATA_HOME') or str(home / '.local/share'))
    config = Path(os.environ.get('XDG_CONFIG_HOME') or str(home / '.config'))
    state = Path(os.environ.get('XDG_STATE_HOME') or str(home / '.local/state'))
    return {'user_theme': data / 'themes' / THEME,
            'system_theme': Path('/usr/local/share/themes') / THEME,
            'gtk_css': config / 'gtk-4.0/gtk.css',
            'gtk_override': config / 'gtk-4.0/tokyoadwaita-night.css',
            'state': state / STATE_NAME / 'state.json'}


def read_state(statefile: Path) -> dict[str, Any] | None:
    if not statefile.exists():
        return None
    data = json.loads(statefile.read_text(encoding='utf-8'))
    if data.get('format') not in (2, 3):
        raise ThemeError('Found state file of unexpected format, refusing to modify installation')
    return data


def atomic_write(path: Path, content: bytes, mode=0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.tokyoadwaita-', dir=path.parent)
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


def root_action(action: str, directory: Path, generated: Path | None = None, expected=None) -> None:
    args = ['sudo', 'python3', str(ROOT / 'root_helper.py'), action, str(directory)]
    if generated is not None:
        args.append(str(generated))
    if expected is not None:
        args.append(json.dumps(expected, sort_keys=True))
    run(args, capture=False)


def stage_theme(directory: Path, files: dict[str, bytes], expected: dict[str, str] | None, scope: str) -> None:
    if scope == 'system':
        with tempfile.TemporaryDirectory(prefix='tokyoadwaita-build-') as temp:
            generated = Path(temp) / THEME
            create_tree(files, generated)
            root_action('apply', directory, generated, expected)
        return
    directory.parent.mkdir(parents=True, exist_ok=True)
    if directory.exists() or directory.is_symlink():
        if expected is None:
            raise ThemeError('A theme with this name already exists and is not owned by this installer')
        assert_owned_theme(directory, expected)
    elif expected is not None:
        raise ThemeError('Previously installed theme directory disappeared; refusing overwrite')
    with tempfile.TemporaryDirectory(prefix='.tokyoadwaita-', dir=directory.parent) as temp:
        generated = Path(temp) / THEME
        create_tree(files, generated)
        if directory.exists():
            old = Path(temp) / 'old'
            directory.rename(old)
            try:
                generated.rename(directory)
            except Exception:
                old.rename(directory)
                raise
        else:
            generated.rename(directory)


def delete_theme(directory: Path, expected: dict[str, str], scope: str) -> None:
    if scope == 'system':
        root_action('remove', directory, expected=expected)
    else:
        assert_owned_theme(directory, expected)
        shutil.rmtree(directory)


# The Flatpak override is user-wide. Save its original bytes for uninstall.
# GTK_THEME is not set because it can interfere with libadwaita applications.
def flatpak_path() -> Path:
    d = Path(os.environ.get('XDG_DATA_HOME') or str(Path.home() / '.local/share'))
    return d / 'flatpak/overrides/global'


def flatpak_snapshot() -> bytes | None:
    return file_snapshot(flatpak_path())


def flatpak_preflight() -> None:
    if not shutil.which('flatpak'):
        raise ThemeError('--flatpak requested but Flatpak is not installed')
    if Path(os.environ.get('XDG_CONFIG_HOME') or str(Path.home() / '.config')) != Path.home() / '.config':
        raise ThemeError('--flatpak expects the standard ~/.config path; custom XDG_CONFIG_HOME cannot be safely shared')
    flatpak_snapshot()  # rejects symlinks


def flatpak_apply() -> None:
    run(['flatpak', 'override', '--user',
         '--filesystem=xdg-config/gtk-4.0:ro',
         '--filesystem=xdg-data/themes:ro'], capture=False)


def restore_flatpak_snapshot(raw: bytes | None) -> None:
    restore_snapshot(flatpak_path(), raw)


def file_snapshot(path: Path):
    if path.is_symlink():
        raise ThemeError('Refusing to change symlink: ' + str(path))
    return path.read_bytes() if path.exists() else None


def restore_snapshot(path: Path, raw: bytes | None):
    if raw is None:
        if path.exists():
            path.unlink()
    else:
        atomic_write(path, raw)


def get_last_state() -> tuple[dict[str, Any] | None, dict[str, Path]]:
    p = paths()
    return read_state(p['state']), p


def check_conflicts(state: dict[str, Any] | None, p: dict[str, Path], directory: Path):
    if state:
        if directory.as_posix() != state['theme_path']:
            raise ThemeError('Changing install scope requires ./uninstall.sh first')
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
        if raw and (START in raw.decode('utf-8') or END in raw.decode('utf-8')):
            raise ThemeError('Unmanaged theme markers exist in GTK4 user CSS')


def install(args):
    if args.check:
        native_preflight(install_extension=False)
        state, p = get_last_state()
        directory = p['system_theme'] if args.scope == 'system' else p['user_theme']
        check_conflicts(state, p, directory)
        source, _ = stock_shell_resource()
        files, metrics = theme_files(accent_choice(args.accent), source)
        detour_enabled = getattr(args, 'native_detour', None)
        if detour_enabled is None:
            detour_enabled = bool(state and state.get('native_detour_enabled', False))
        if detour_enabled:
            if args.system_accent != 'slate':
                raise ThemeError('--native-detour requires --system-accent slate')
            detour_existing_color()  # fail on unmanaged drop-ins before any changes
            detour_run('check')
        if args.flatpak: flatpak_preflight()
        print(f'Preflight OK: {args.scope} -> {directory}; shell theme size {len(files["gnome-shell/gnome-shell.css"])} B')
        print('Shell accent replacements:', metrics['shell_replacements'])
        return
    native_preflight(install_extension=args.install_extension)
    state, p = get_last_state()
    if state and state.get('flatpak_enabled'):
        args.flatpak = True  # Never silently abandon control of an existing override.
    directory = p['system_theme'] if args.scope == 'system' else p['user_theme']
    if args.scope == 'system' and '/usr/local/share' not in \
            os.environ.get('XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':'):
        raise ThemeError('Your session does not search /usr/local/share for themes. Use --scope user instead.')
    accent = accent_choice(args.accent)
    if args.flatpak:
        flatpak_preflight()
    sys_accent = nearest_system_accent(accent) if args.system_accent == 'auto' else args.system_accent
    detour_enabled = getattr(args, 'native_detour', None)
    if detour_enabled is None:
        detour_enabled = bool(state and state.get('native_detour_enabled', False))
    if detour_enabled and sys_accent != 'slate':
        raise ThemeError('--native-detour requires --system-accent slate')
    check_conflicts(state, p, directory)
    previous_detour = None
    if detour_enabled or (state and state.get('native_detour_enabled', False)):
        previous_detour = detour_existing_color()
    if detour_enabled:
        detour_run('check')
    # Preserve an already-installed standalone v2 detour, rather than claiming
    # or removing it when the theme is later disabled/uninstalled.
    if state and state.get('native_detour_enabled', False):
        original_detour_color = state.get('native_detour_original_color')
    else:
        original_detour_color = previous_detour if detour_enabled else None
    source, _ = stock_shell_resource()
    files, metrics = theme_files(accent, source)
    previous_gtk = file_snapshot(p['gtk_css'])
    previous_override = file_snapshot(p['gtk_override'])
    old_settings = copy.deepcopy(state['settings']) if state else {}
    new_state = {
        'format': 3, 'scope': args.scope, 'theme_path': directory.as_posix(),
        'accent': accent, 'system_accent': sys_accent,
        'system_accent_mode': args.system_accent,
        'files': {name: sha(data) for name, data in files.items()},
        'gtk_override_sha': sha(gtk4_override(accent)),
        'shell_source_sha': metrics['source_sha256'],
        'gtk_css_existed': state.get('gtk_css_existed', True) if state else previous_gtk is not None,
        'flatpak_enabled': args.flatpak,
        'native_detour_enabled': bool(detour_enabled),
        'native_detour_original_color': original_detour_color if detour_enabled else None,
        'flatpak_old': state.get('flatpak_old') if state else None,
        'flatpak_written_sha': state.get('flatpak_written_sha') if state else None,
        'settings': old_settings,
    }
    # Capture state before writing any managed files.
    old_css = previous_gtk.decode('utf-8') if previous_gtk is not None else ''
    new_css = insert_import(old_css)
    new_override = gtk4_override(accent)
    prev_theme_files = None
    if state:
        prev_theme_files = {k: (directory / k).read_bytes() for k in state['files']}
    changed_settings: list[tuple[str, str, str]] = []
    theme_applied = False
    flatpak_before = flatpak_snapshot() if args.flatpak else None
    flatpak_changed = False
    detour_touched = False
    try:
        stage_theme(directory, files, state['files'] if state else None, args.scope)
        theme_applied = True
        atomic_write(p['gtk_override'], new_override.encode('utf-8'))
        atomic_write(p['gtk_css'], new_css.encode('utf-8'))
        if args.flatpak:
            if state and state.get('flatpak_enabled'):
                if state.get('flatpak_written_sha') != sha(flatpak_before or b''):
                    raise ThemeError('Flatpak override changed after the previous installation; refusing to overwrite')
            else:
                new_state['flatpak_old'] = flatpak_before.decode('utf-8') if flatpak_before is not None else None
            flatpak_changed = True
            flatpak_apply()
            new_state['flatpak_written_sha'] = sha(flatpak_snapshot() or b'')
        current_extensions = parse_gvariant_array(gget('org.gnome.shell', 'enabled-extensions'))
        desired_extensions = list(current_extensions)
        if EXTENSION not in desired_extensions:
            desired_extensions.append(EXTENSION)
        settings_to_apply = SCHEMAS + [
            ('org.gnome.desktop.interface', 'accent-color', sys_accent),
            ('org.gnome.shell', 'enabled-extensions', desired_extensions)]
        for schema, key, new_value in settings_to_apply:
            skey = schema + '/' + key
            old = old_settings[skey]['old'] if skey in old_settings else gget(schema, key)
            last = gget(schema, key)
            encoded = repr(new_value)
            if last != encoded:
                gset(schema, key, encoded)
                changed_settings.append((schema, key, last))
            new_state['settings'][skey] = {'old': old, 'set': gget(schema, key)}
        if detour_enabled:
            detour_touched = True  # rollback even if the helper exits mid-install
            detour_run('install', accent)
        elif state and state.get('native_detour_enabled', False):
            detour_touched = True
            if original_detour_color:
                detour_run('install', original_detour_color)
            else:
                detour_run('uninstall')
        atomic_write(p['state'], (json.dumps(new_state, sort_keys=True, indent=2) + '\n').encode())
    except Exception:
        if detour_touched:
            try:
                if previous_detour:
                    detour_run('install', previous_detour)
                else:
                    detour_run('uninstall')
            except Exception as err:
                print('ROLLBACK warning (native detour):', err, file=sys.stderr)
        # Restore settings and files changed by this attempt.
        for schema, key, previous in reversed(changed_settings):
            try: gset(schema, key, previous)
            except Exception as err: print('ROLLBACK warning:', err, file=sys.stderr)
        try:
            if flatpak_changed:
                restore_flatpak_snapshot(flatpak_before)
            restore_snapshot(p['gtk_css'], previous_gtk)
            restore_snapshot(p['gtk_override'], previous_override)
            if theme_applied:
                if state:
                    stage_theme(directory, prev_theme_files, new_state['files'], args.scope)
                else:
                    delete_theme(directory, new_state['files'], args.scope)
        except Exception as err:
            print('ROLLBACK FAILED; inspect state and installed theme:', err, file=sys.stderr)
        raise
    print(f'Installed {THEME} ({args.scope}) — accent {accent} (CSS) / {sys_accent} (system API).')
    print('GNOME Shell colors updated:', metrics['shell_replacements'])
    if args.flatpak: print('Flatpak: granted read-only theme/config access for sandboxed GTK applications')
    if detour_enabled: print(f'Native GNOME Shell accent: detour enabled ({accent}); applies after re-login')
    print('Log out and back in to load the GNOME Shell theme and new extension.')
    print('User Themes is enabled in the GNOME Shell settings; re-login may be required to load it.')


def uninstall(args):
    state, p = get_last_state()
    if not state:
        print('No theme installation owned by this tool was found.')
        return
    directory = Path(state['theme_path'])
    # Verify ownership before removing any managed files.
    assert_owned_theme(directory, state['files'])
    owned_file(p['gtk_override'], state['gtk_override_sha'], 'GTK4 override')
    css = file_snapshot(p['gtk_css'])
    if css is None:
        raise ThemeError('GTK4 CSS was removed; refusing partial uninstallation')
    new_css = remove_import(css.decode('utf-8'))
    # Preserve settings changed since installation.
    restores = []
    for entry, setting in reversed(list(state['settings'].items())):
        schema, key = entry.rsplit('/', 1)
        current = gget(schema, key)
        if current == setting['set']:
            restores.append((schema, key, setting['old']))
        elif entry == 'org.gnome.shell/enabled-extensions':
            try:
                before = parse_gvariant_array(setting['old'])
                now = parse_gvariant_array(current)
                if isinstance(before, list) and isinstance(now, list) and EXTENSION not in before:
                    restores.append((schema, key, repr([e for e in now if e != EXTENSION])))
                    print('Removing only theme extension; retaining new user extensions')
            except (SyntaxError, ValueError, ThemeError):
                print('Warning: could not safely update changed extension list', file=sys.stderr)
        else:
            print('Keeping user-modified setting:', entry)
    # Do not overwrite Flatpak permissions changed after installation.
    flatpak_restore = False
    if state.get('flatpak_enabled'):
        fp_raw = flatpak_snapshot()
        flatpak_restore = sha(fp_raw or b'') == state.get('flatpak_written_sha')
        if not flatpak_restore:
            print('WARNING: Flatpak override was modified after install; leaving it untouched')
    # Remove the optional native hook only when explicitly managed by this theme.
    # Abort uninstallation if the hook refuses removal; don't strand it unexpectedly.
    if state.get('native_detour_enabled', False):
        if state.get('native_detour_original_color'):
            detour_run('install', state['native_detour_original_color'])
        else:
            detour_run('uninstall')
    # System-scope removal uses the restricted privileged helper.
    delete_theme(directory, state['files'], state['scope'])
    if not state.get('gtk_css_existed', True) and not new_css.strip():
        p['gtk_css'].unlink()
    else:
        atomic_write(p['gtk_css'], new_css.encode('utf-8'))
    p['gtk_override'].unlink()
    if flatpak_restore:
        restore_flatpak_snapshot(state.get('flatpak_old').encode('utf-8') if state.get('flatpak_old') is not None else None)
    for schema, key, old in restores:
        try:
            gset(schema, key, old)
        except Exception as err:
            print('Warning restoring setting:', schema, key, err, file=sys.stderr)
    p['state'].unlink()
    print('Uninstalled TokyoAdwaita Night. Existing CSS outside our import preserved.')
    print('Log out and back in to fully return to the previous GNOME Shell style.')


def do_validate(args):
    from unittest import defaultTestLoader, TextTestRunner
    suite = defaultTestLoader.discover(str(ROOT / 'tests'), pattern='test_*.py')
    result = TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise ThemeError('Offline tests did not all pass')
    if args.runtime:
        native_preflight()
        state, p = get_last_state()
        if not state:
            raise ThemeError('Theme not installed: install first, then test --runtime')
        directory = Path(state['theme_path'])
        assert_owned_theme(directory, state['files'])
        owned_file(p['gtk_override'], state['gtk_override_sha'], 'GTK4 override')
        check_quick_settings_css((directory / 'gnome-shell/gnome-shell.css').read_text(), state['accent'])
        css = file_snapshot(p['gtk_css'])
        if not css or START not in css.decode():
            raise ThemeError('GTK4 import not active')
        if state.get('native_detour_enabled', False):
            print('Native detour was enabled with theme; inspect ./diagnose.sh and native-detour helper status')
        if state.get('flatpak_enabled') and sha(flatpak_snapshot() or b'') != state.get('flatpak_written_sha'):
            print('NOTICE: Flatpak override changed since install')
        if EXTENSION not in parse_gvariant_array(gget('org.gnome.shell', 'enabled-extensions')):
            raise ThemeError('Official User Themes GNOME Shell extension is not enabled')
        stock, _ = stock_shell_resource()
        if sha(stock) != state['shell_source_sha']:
            print('WARNING: Fedora updated GNOME Shell CSS since install. Run ./configure.sh --refresh.')
        for schema, key, value in SCHEMAS + [('org.gnome.desktop.interface', 'accent-color', state['system_accent'])]:
            current = gget(schema, key)
            if current != repr(value):
                print(f'NOTICE: {schema}/{key} is {current}, expected {value!r}')
        print('Runtime file and installed GNOME-version checks: PASS')
        print('Note: this is not a live screenshot/render verification of GTK and GNOME Shell.')
    else:
        print('Static and isolated tests: PASS; runtime check requires Fedora 45 GNOME 51.')


def diagnose():
    """Read-only checks for theme state and common GTK/Flatpak conflicts."""
    print('TokyoAdwaita diagnostic (read-only)')
    print('GTK_THEME=', os.environ.get('GTK_THEME') or '(unset)')
    if os.environ.get('GTK_THEME') is not None:
        print('WARNING: GTK_THEME is set; forcing it for libadwaita/Flatpaks can cause mismatched appearance')
    for schema, key in [*[(s, k) for s, k, _ in SCHEMAS],
                        ('org.gnome.desktop.interface', 'accent-color')]:
        try: print(f'{schema}/{key} = {gget(schema,key)}')
        except Exception as e: print('UNAVAILABLE:', schema, key, e)
    state, p = get_last_state()
    if not state:
        print('No managed theme installed')
    else:
        print('Managed theme format:', state['format'], 'accent:', state['accent'],
              'system accent:', state['system_accent'])
        try:
            check_quick_settings_css((Path(state['theme_path']) / 'gnome-shell/gnome-shell.css').read_text(), state['accent'])
            print('Quick Settings exact CSS accent:', state['accent'], 'structural check PASS')
        except (ThemeError, OSError) as e:
            print('Quick Settings exact CSS accent: NOT VERIFIED:', e)
        print('GTK4 user import present:', p['gtk_css'].is_file() and START in p['gtk_css'].read_text())
        print('GTK4 managed color CSS present:', p['gtk_override'].is_file())
        print('Flatpak integration enabled:', state.get('flatpak_enabled', False))
        print('Native Shell detour enabled:', state.get('native_detour_enabled', False))
        if state.get('native_detour_enabled', False):
            try:
                print('Native detour configured color:', detour_existing_color() or '(not installed)')
            except ThemeError as e:
                print('Native detour check:', e)
    if shutil.which('flatpak'):
        q = run(['flatpak', 'override', '--user', '--show'], check=False)
        print('Flatpak user overrides (summary):')
        print(q.stdout.decode(errors='replace').strip() or '(none)')
        q = run(['flatpak', 'list', '--app', '--columns=application'], check=False)
        print('Flatpak application IDs:', q.stdout.decode(errors='replace').strip() or '(none)')
        print('Check whether Extension Manager is a Flatpak above; if so restart it after --flatpak')
    print('For live GTK CSS parsing errors, run a GTK4 app with GTK_DEBUG=css and inspect its stderr.')


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    cmd = parser.add_subparsers(dest='command', required=True)
    p = cmd.add_parser('install', help='Create theme, activate GTK3 + GNOME Shell + GTK4 overrides')
    p.add_argument('--scope', choices=['user', 'system'], default='user')
    p.add_argument('--accent', default=DEFAULT_ACCENT_NAME, help='TokyoNight name or #RRGGBB (default: blue)')
    p.add_argument('--system-accent', choices=['auto', *SYSTEM_ACCENTS], default='slate',
                   help='GNOME native accent: slate (default), or auto (nearest named color)')
    p.add_argument('--flatpak', action='store_true', help='Allow user Flatpaks to read GTK CSS and theme directories')
    p.add_argument('--install-extension', action='store_true', help='Allow sudo dnf to install Fedora User Themes extension')
    p.add_argument('--check', action='store_true', help='Read-only compatibility and conflict preflight')
    p.add_argument('--list-accents', action='store_true', help='Show supported TokyoNight accent names')
    dg = p.add_mutually_exclusive_group()
    dg.add_argument('--native-detour', action='store_true', default=None,
                    help='Opt in to native Shell accent via user-local LD_PRELOAD (requires re-login)')
    dg.add_argument('--no-native-detour', dest='native_detour', action='store_false',
                    help='Disable a previously managed native detour')
    cmd.add_parser('uninstall', help='Restore settings and remove only our own files')
    c = cmd.add_parser('configure', help='Rebuild in place with a new accent and current Shell stylesheet')
    c.add_argument('--accent', default=None, help='TokyoNight name or #RRGGBB')
    c.add_argument('--list-accents', action='store_true', help='Show supported TokyoNight accent names')
    dg = c.add_mutually_exclusive_group()
    dg.add_argument('--native-detour', action='store_true', default=None,
                    help='Enable native Shell accent hook')
    dg.add_argument('--no-native-detour', dest='native_detour', action='store_false',
                    help='Disable managed native Shell accent hook')
    c.add_argument('--system-accent', choices=['auto', *SYSTEM_ACCENTS], default=None)
    c.add_argument('--flatpak', action='store_true', help='Enable GTK CSS access for Flatpak applications')
    c.add_argument('--refresh', action='store_true', help='Regenerate after a Fedora/GNOME update')
    cmd.add_parser('diagnose', help='Read-only report of platform accent, GTK4 and Flatpak integration')
    v = cmd.add_parser('validate', help='Run offline tests, optionally check Fedora runtime')
    v.add_argument('--runtime', action='store_true')
    return parser.parse_args()


def main():
    args = parse_args()
    if getattr(args, 'list_accents', False):
        print('TokyoNight Night accents (default: blue):')
        for name, color in TOKYONIGHT_ACCENTS.items():
            print(f'  {name:8s} {color}')
        return 0
    try:
        if args.command == 'install':
            install(args)
        elif args.command == 'configure':
            state, _ = get_last_state()
            if not state:
                raise ThemeError('Nothing installed; start with ./install.sh')
            if args.accent is None and args.system_accent is None and not args.refresh and not args.flatpak and args.native_detour is None:
                raise ThemeError('Choose --accent NAME/#RRGGBB, --native-detour, --no-native-detour, --system-accent NAME, --flatpak, or --refresh')
            args.scope = state['scope']
            args.accent = args.accent or state['accent']
            args.system_accent = args.system_accent or state.get('system_accent_mode', 'auto')
            args.install_extension = False
            args.flatpak = args.flatpak or state.get('flatpak_enabled', False)
            args.check = False
            install(args)
        elif args.command == 'uninstall':
            uninstall(args)
        elif args.command == 'validate':
            do_validate(args)
        elif args.command == 'diagnose':
            diagnose()
    except ThemeError as e:
        print('ERROR:', e, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
