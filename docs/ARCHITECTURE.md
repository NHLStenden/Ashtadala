# Architecture

TokyoAdwaita Night changes selected dark surfaces and accent states while keeping Adwaita's
layout, foreground colors and transparency.

## Styling layers

| Layer | Implementation |
| --- | --- |
| GTK3 | Imports the installed Adwaita Dark CSS. Named colors and selected widget states are overridden in `gtk-3.0/gtk.css`. |
| GTK4/libadwaita | Sets dark semantic color variables on windows, dialogs and popovers. A managed import is placed in the user's GTK4 CSS. Legacy named colors stay within the installed GTK4 dark theme, so they do not affect light-mode libadwaita windows. |
| GNOME Shell | Extracts the installed GNOME 51 dark stylesheet, replaces known dark surface colors and accent tokens, and adds styles for checked Quick Settings tiles and menu arrows. The official User Themes extension loads it. |
| Native accent | Sets `org.gnome.desktop.interface accent-color` to `slate` unless configured otherwise. |
| Flatpak | Optionally grants user Flatpaks read-only access to GTK4 CSS and theme directories. |

Shell stylesheet generation checks for expected GNOME 51 selectors and accent tokens. If GNOME
changes them, generation stops. Run `./configure.sh --refresh` after an update to regenerate from
the installed stylesheet.

## Colors and contrast

| Role | Default |
| --- | --- |
| Window | `#1a1b26` |
| Deep surface | `#16161e` |
| Headerbar and sidebar | `#1f2335` |
| Raised surface | `#24283b` |
| Hover surface | `#292e42` |
| Accent | `#ff9e64` |

Adwaita's light text and translucent surfaces are preserved. Text and icons on accent fills use a
foreground selected for a contrast ratio of at least 4.5:1. GTK3 suggested buttons remove the
inherited Adwaita background image when filled with the accent. Focused file-list rows and
selected places-sidebar content use explicit GTK3 selectors; those states otherwise retain
Adwaita's blue or white text.

Success, warning and destructive states keep their upstream meanings unless styled by one of the
targeted rules.

## Native accent colors

GNOME exposes nine named accent colors: `blue`, `teal`, `green`, `yellow`, `orange`, `red`,
`pink`, `purple` and `slate`. GNOME's orange is `#ed5b00`, not `#ff9e64`.

Some Settings illustrations get their accent from libadwaita's style manager. Those colors follow
GNOME's named preference and cannot be changed by a GTK stylesheet. `--system-accent orange`
selects GNOME orange; `auto` selects the nearest named color. Neither supplies a custom RGB value
to native consumers.

## Flatpak access

The optional `--flatpak` integration sets these user-wide overrides:

```sh
flatpak override --user \
  --filesystem=xdg-config/gtk-4.0:ro \
  --filesystem=xdg-data/themes:ro
```

These permissions apply to all of the user's Flatpak applications. They permit reads from the
listed directories, not changes to application preferences. The installer records the previous
global override. The uninstaller restores it only if it has not been changed since installation.
Custom `XDG_CONFIG_HOME` paths are not supported by this option.

## Files and uninstall

User installs use `$XDG_DATA_HOME/themes/TokyoAdwaita-Night`. System installs use
`/usr/local/share/themes/TokyoAdwaita-Night`. The installer stores checksums and previous settings
at `$XDG_STATE_HOME/tokyoadwaita-night/state.json`.

The privileged helper handles only the system theme directory. Existing GTK4 CSS outside the
managed import and unrelated GNOME extensions are left alone. On uninstall, a setting changed by
the user after installation is not reset. An interrupted uninstall may require manual recovery.

## References

- [TokyoNight Night palette](https://github.com/folke/tokyonight.nvim/blob/main/lua/tokyonight/colors/night.lua)
- [libadwaita CSS variables](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/main/css-variables.html)
- [libadwaita styles and appearance](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/styles-and-appearance.html)
- [GNOME Shell Quick Settings SCSS](https://github.com/GNOME/gnome-shell/blob/main/data/theme/gnome-shell-sass/widgets/_quick-settings.scss)
- [GNOME Control Center mask paintable](https://github.com/GNOME/gnome-control-center/blob/main/panels/common/cc-mask-paintable.c)
- [User Themes extension](https://extensions.gnome.org/extension/19/user-themes/)
- [Fedora User Themes package](https://packages.fedoraproject.org/pkgs/gnome-shell-extensions/gnome-shell-extension-user-theme/)
- [Flatpak command reference](https://docs.flatpak.org/en/latest/flatpak-command-reference.html)
