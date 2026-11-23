# TokyoAdwaita Night

[![TokyoAdwaita Night](assets/TokyoAdwaita-Night-preview.svg)](assets/TokyoAdwaita-Night-preview.svg)

An Adwaita Dark theme for Fedora 45 with GNOME, with TokyoNight Night backgrounds and a
configurable accent (TokyoNight `blue` / `#7aa2f7` by default). Adwaita's layout, icons, light foregrounds and
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

TokyoNight's canonical `blue` (`#7aa2f7`) is the default: balanced against the Night background,
with an ordinary UI selection color rather than a warm warning-like accent. Other supported names:

| Name | Hex | Name | Hex |
| --- | --- | --- | --- |
| **blue (default)** | `#7aa2f7` | `cyan` | `#7dcfff` |
| `purple` | `#9d7cd8` | `magenta` | `#bb9af7` |
| `green` | `#9ece6a` | `teal` | `#1abc9c` |
| `yellow` | `#e0af68` | `peach` | `#ff9e64` |
| `red` | `#f7768e` | | |

```sh
./install.sh --list-accents
./configure.sh --accent magenta
./configure.sh --accent peach
./configure.sh --accent '#f6a879'  # custom colors still supported
```

Named colors resolve to an exact hex throughout GTK3, GTK4 and Shell CSS. Button and selection
foregrounds are automatically chosen for contrast.

GNOME's native accent preference accepts nine GNOME names, not arbitrary hex values. The theme
uses `slate` as the system preference by default; the custom stylesheet uses your TokyoNight accent.
Without the optional native detour below, Shell-native widgets and some Settings illustrations may
still show GNOME's slate. To change GNOME's named fallback:

```sh
./configure.sh --system-accent orange
./configure.sh --system-accent auto
```

`auto` picks the nearest named GNOME accent. It does not change the system API's available colors.

## Optional native GNOME Shell accent detour (advanced)

If you want GNOME Shell's **native** slate-based highlights to match GTK/Shell CSS exactly, opt in
to a bundled, user-local `LD_PRELOAD` hook. This is the previously proven
`cogl_color_from_string()` detour, installed for `org.gnome.Shell@user.service`. It does **not** edit
`libst-51.so`, require root, or hook GTK/libadwaita applications. It is disabled by default because
it injects code into the Wayland compositor.

New install:

```sh
./install.sh --scope user --accent blue --native-detour
```

For an existing TokyoAdwaita-Night installation (including an existing standalone v2 detour):

```sh
./configure.sh --accent blue --native-detour
./configure.sh --accent magenta  # updates theme + managed native detour together
./diagnose.sh
bash native-detour/scripts/gnome-slate-detour.sh status
bash native-detour/scripts/gnome-slate-detour.sh logs
```

The hook requires `--system-accent slate`, GNOME Shell 51, `cc`, `readelf` and a user systemd session.
`./install.sh --check --native-detour` can run compatibility checks before installation.
**Log out and back in** after activation or accent changes; never restart your live Wayland Shell.

Disable only the integrated hook:

```sh
./configure.sh --no-native-detour
```

If you had a standalone v2 detour before enabling integration, its previous accent is saved and
restored when you disable integration or uninstall the theme; otherwise the managed hook is removed.
If the hook causes a login loop, use Ctrl+Alt+F3 to enter a TTY and remove **only**
`~/.config/systemd/user/org.gnome.Shell@user.service.d/80-gnome-slate-detour.conf`, then
`systemctl --user daemon-reload` and reboot. Do not delete the entire service drop-in directory.
The native hook may need revalidation after GNOME updates. GNOME Settings illustrations and
GTK/libadwaita native accent consumers remain governed by the GNOME named preference.

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

The normal theme does not modify application binaries, GDM or browser profiles; the optional
native detour injects a shared library into the current user's GNOME Shell only. Applications with their
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
