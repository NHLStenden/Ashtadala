# TokyoAdwaita Night

Adwaita, in TokyoNight's Night palette. For Fedora 45 and GNOME 51.

![TokyoAdwaita Night preview](assets/TokyoAdwaita-Night-preview.svg)

*Illustration, not a screenshot.*

## Install

Run as your desktop user, without `sudo`:

```sh
./install.sh                # blue accent, random Papirus folders
./install.sh peach cyan     # peach accent, cyan folders
./configure.sh purple       # change accent, pick new folder color
./uninstall.sh
```

The first color sets the desktop accent; the second sets Papirus folders. Omit
it for a random folder color, different from the accent and the previous pick.
Colors: `blue`, `cyan`, `purple`, `magenta`, `green`, `teal`, `yellow`, `peach`,
`red`, or any `#RRGGBB`.

GTK 3, GTK 4 and GNOME Shell are themed together. A small `LD_PRELOAD` hook
handles Shell's native accent without patching system libraries. Papirus folder
colors and Flatpak GTK access are set up only if those apps are installed.

Missing Fedora packages (`gcc`, `binutils`, User Themes) can be installed with
`sudo dnf` after you confirm. Log out and back in to load Shell changes;
restart Files if folder icons stay cached.

## Checks

```sh
./diagnose.sh
./validate.sh
make -C native-accent-hook test
```

Uninstall restores the old settings and Flatpak permissions if they're still
unchanged. Other GTK CSS and modified theme files are left alone.

If Shell won't start, switch to a TTY (`Ctrl+Alt+F3`) and run:

```sh
rm ~/.config/systemd/user/org.gnome.Shell@user.service.d/80-tokyoadwaita-accent.conf
systemctl --user daemon-reload
reboot
```

## License

Code: MIT. [TokyoNight](https://github.com/folke/tokyonight.nvim) palette:
Apache 2.0 (`licenses/`). Papirus icons are generated locally, not bundled.
