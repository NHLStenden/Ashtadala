# TokyoAdwaita Night

Dark Adwaita styling with the TokyoNight Night palette. For Fedora 45 and GNOME 51.

## Install

Run as your desktop user, without `sudo`:

```sh
./install.sh                 # blue accent, random Papirus folder color
./install.sh peach cyan      # peach accent, cyan folders
./configure.sh purple       # purple accent, new random folder color
./configure.sh blue magenta  # blue accent, magenta folders
./uninstall.sh
```

The first color controls GTK3, GTK4, GNOME Shell and its native accent hook.
The second color controls Papirus folders. Without a second color, a new random
TokyoNight color is selected, excluding the main accent and the previous folder
color. Both colors accept a name or `#RRGGBB`.

Available names: `blue` (default), `cyan`, `purple`, `magenta`, `green`,
`teal`, `yellow`, `peach`, `red`.

If Papirus is installed, the installer creates a user-local icon theme that
inherits `Papirus`, `Papirus-Dark` or `Papirus-Light`. The original icons are
not modified. If Papirus is missing, icon setup is skipped.

GTK and GNOME Shell themes, the native accent hook and Flatpak GTK access are
installed together. Flatpak support is skipped when Flatpak is not installed.
The hook uses `LD_PRELOAD` symbol interposition; it never edits Fedora libraries.

Missing Fedora dependencies (`gcc`, `binutils`, User Themes) are installed via
`sudo dnf` after a confirmation prompt. Log out and back in after installing
or uninstalling to reload GNOME Shell. Restart Files if folder icons remain cached.

## Checks

```sh
./diagnose.sh
./validate.sh
make -C native-accent-hook test
```

Uninstallation restores the original settings and Flatpak permissions, provided
they haven't been changed by another program. User CSS outside the managed
import is left in place. Modified theme files are not overwritten or deleted.

If GNOME Shell fails to start, switch to a TTY (`Ctrl+Alt+F3`), remove
`~/.config/systemd/user/org.gnome.Shell@user.service.d/80-tokyoadwaita-accent.conf`,
run `systemctl --user daemon-reload`, and reboot.

## License

Project code: MIT. TokyoNight palette: [TokyoNight](https://github.com/folke/tokyonight.nvim),
Apache 2.0 (see `licenses/`). Papirus icons are generated from the installed
Papirus theme and are not included in this repository.
