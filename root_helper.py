#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Restricted helper for system-scope theme installation and removal.

Only /usr/local/share/themes/TokyoAdwaita-Night is writable.
Updates and removals check file hashes before proceeding.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

DEST = Path('/usr/local/share/themes/TokyoAdwaita-Night')


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def paths(dirpath):
    if dirpath.is_symlink() or not dirpath.is_dir():
        raise ValueError('Not an ordinary directory: ' + str(dirpath))
    found = {}
    for item in dirpath.rglob('*'):
        if item.is_symlink():
            raise ValueError('Unexpected symlink: ' + str(item))
        if item.is_dir():
            continue
        if not item.is_file():
            raise ValueError('Unexpected special path: ' + str(item))
        found[item.relative_to(dirpath).as_posix()] = digest(item.read_bytes())
    return found


def main(args):
    if os.geteuid() != 0:
        raise ValueError('This helper must be run with sudo')
    if len(args) not in (3, 4, 5):
        raise ValueError('Usage: root_helper.py apply DEST SOURCE EXPECTED | remove DEST EXPECTED')
    op = args[1]
    dest = Path(args[2])
    if dest != DEST:
        raise ValueError('System theme destination restricted to ' + str(DEST))
    if op == 'apply' and len(args) == 5:
        src = Path(args[3])
        expected = json.loads(args[4])
        source_hashes = paths(src)
        if not source_hashes or not (src / 'gnome-shell/gnome-shell.css').is_file():
            raise ValueError('Incomplete theme build source')
        if dest.exists() or dest.is_symlink():
            if expected is None or paths(dest) != expected:
                raise ValueError('Installed theme does not match owned files; refusing to replace')
        elif expected is not None:
            raise ValueError('Owned theme disappeared')
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.tokyoadwaita-root-', dir=dest.parent) as t:
            tmp = Path(t)
            staged = tmp / 'staged'
            shutil.copytree(src, staged, symlinks=False)
            if paths(staged) != source_hashes:
                raise ValueError('Files changed during privileged copy')
            if dest.exists():
                old = tmp / 'old'
                dest.rename(old)
                try:
                    staged.rename(dest)
                except Exception:
                    old.rename(dest)
                    raise
            else:
                staged.rename(dest)
    elif op == 'remove' and len(args) == 4:
        expected = json.loads(args[3])
        if not isinstance(expected, dict) or not expected:
            raise ValueError('No owner manifest passed')
        if paths(dest) != expected:
            raise ValueError('Theme was edited; refusing deletion')
        shutil.rmtree(dest)
    else:
        raise ValueError('Invalid operation/arguments')


if __name__ == '__main__':
    try:
        main(sys.argv)
    except Exception as e:
        print('ROOT HELPER ERROR:', e, file=sys.stderr)
        sys.exit(1)
