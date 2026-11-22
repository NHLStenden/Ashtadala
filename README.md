# TokyoAdwaita Night

An Adwaita Dark theme for Fedora 45 with GNOME, with TokyoNight Night backgrounds and a
configurable accent (`#ff9e64` by default). Adwaita's layout, icons, light foregrounds and
transparency remain in place.

The theme covers GTK3, GTK4/libadwaita and GNOME Shell. It builds its Shell stylesheet from the
version installed on the machine.

## Requirements

- Fedora 45 with GNOME Shell
- Python 3, `gsettings`, `gresource`, `gnome-shell` and `gnome-extensions`
- GNOME User Themes extension (`gnome-shell-extension-user-theme`)
- Flatpak, if using the optional Flatpak integration

## Install

Run from the extracted source directory, as your desktop user:

```sh
./install.sh --check
./install.sh --scope user --install-extension
```

`--check` inspects the host without installing anything. Omit `--install-extension` if User Themes
is already installed; otherwise it may invoke `sudo dnf`.

To install the theme files for all local users:

```sh
./install.sh --scope system --install-extension
```

System scope installs files under `/usr/local/share/themes` and may prompt for sudo. GTK settings
and the GTK4 CSS import are still configured only for the current user.

Flatpak integration is optional:

```sh
./configure.sh --flatpak
```

This sets a user-wide Flatpak override giving sandboxed applications read access to the GTK4
configuration and theme directories. See [Flatpak access](docs/ARCHITECTURE.md#flatpak-access)
before enabling it.

Log out and back in to reload GNOME Shell. Restart open applications to pick up GTK changes.

## Change the accent

```sh
./configure.sh --accent '#f6a879'
./configure.sh --accent '#ff9e64'  # default
```

The color accepts any six-digit `#RRGGBB` value. Button and selection foregrounds are chosen for
contrast with the configured accent.

GNOME's native accent preference accepts named colors, not arbitrary hex values. The installer
uses `slate` by default because GNOME's `orange` does not match the TokyoNight peach. GTK and
Shell CSS use the exact chosen color; some Settings illustrations and other native-accent
consumers will still use slate. To change that fallback:

```sh
./configure.sh --system-accent orange
./configure.sh --system-accent auto
```

`auto` picks the nearest named GNOME accent. It does not change the system API's available colors.

## Update and remove

```sh
./configure.sh --refresh    # rebuild from the installed GNOME Shell stylesheet
./diagnose.sh               # show theme settings and possible conflicts
./validate.sh               # run unit tests
./validate.sh --runtime     # check the installed theme on Fedora
./uninstall.sh              # remove managed files and restore previous settings
```

To update an existing v3 installation, unpack the new release and run `./configure.sh --refresh`.
If installing again, use the same `--scope` as the previous installation. The installer tracks its
files and settings; it will stop rather than replace a managed file that has been edited since
installation.

## Compatibility

The theme does not modify application binaries, GDM or browser profiles. Applications with their
own rendering or color settings may not follow the GTK palette. GNOME's native accent colors and
some artwork in Settings are separate from GTK and Shell CSS. Blur My Shell controls transparency
and blur independently.

Implementation details and upstream references are in [Architecture](docs/ARCHITECTURE.md). Test
commands and release checks are in [Development](docs/DEVELOPMENT.md).

When reporting a problem, include your Fedora and GNOME versions, installation scope and
reproduction steps. `./diagnose.sh` can help; check its output for personal information before
posting it.

## License

Source code and theme templates are licensed under [MIT](LICENSE). See [NOTICE](NOTICE) for
TokyoNight attribution and upstream licensing information. GNOME Shell CSS is generated from the
system-installed resources and is not distributed in this repository.
