# Development

Resource generation and unit tests require Python 3 and its standard library. They can run outside
Fedora.

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q tokyoadwaita.py root_helper.py build_resources.py tests
bash -n install.sh configure.sh uninstall.sh diagnose.sh validate.sh
```

`python3 build_resources.py` regenerates the checked-in GTK examples from `templates/`. The tests
check these outputs. The GNOME Shell stylesheet must be generated on the target system from its
installed GResource; it is not included in the repository.

## Layout

- `tokyoadwaita.py` — rendering, configuration and installation state
- `root_helper.py` — restricted system installation operations
- `templates/` — GTK rules and GNOME Shell accent states
- `resources/` — generated GTK examples
- `tests/` — unit tests and simulated installation cases
- `*.sh` — command wrappers

## Release checks

CI runs the unit tests, syntax checks and resource regeneration check. It does not launch GNOME
Shell or render GTK widgets.

Before releasing, test on Fedora 45 with GNOME 51:

1. Run `./install.sh --check`, install, and run `./validate.sh --runtime`.
2. Inspect active and inactive Quick Settings tiles, GTK3 file selection, GTK4/libadwaita controls and Blur My Shell transparency.
3. Check a custom accent and restore the default.
4. Test Flatpak access if using `--flatpak`.
5. Uninstall and check that previous settings and user CSS are restored.

Keep styling changes limited to color roles and relevant widget states. Changes to selection or
accent rules should include tests for both the default and an alternate accent. Do not commit a
locally generated GNOME Shell stylesheet; it contains material from the installed GNOME package.
