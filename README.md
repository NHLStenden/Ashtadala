# TokyoAdwaita Night

Adwaita, in TokyoNight's Night palette. For Fedora 45 and GNOME 51.

![TokyoAdwaita Night preview](assets/TokyoAdwaita-Night-preview.svg)

## Install

Run as your desktop user:

```sh
./install.sh                # blue accent, purple Papirus folders
./install.sh peach cyan     # peach accent, cyan folders
./configure.sh purple       # change accent, preserve folder color
./uninstall.sh
```

The first color sets the desktop accent; the second sets Papirus folders. Omit
it to preserve the previous folder color (purple by default; cyan when the
primary is purple). Use `--random-folders` to explicitly pick a new color.
Colors: `blue`, `cyan`, `purple`, `magenta`, `green`, `teal`, `yellow`, `peach`,
`red`, or any `#RRGGBB`.

GTK 3, GTK 4 and GNOME Shell are themed together. A small `LD_PRELOAD` hook
handles Shell's native accent without patching system libraries. Papirus folder
colors and Flatpak GTK access are set up only if those apps are installed.

Missing Fedora packages (`gcc`, `binutils`, User Themes) can be installed with
`sudo dnf` after you confirm. Log out and back in to load Shell changes;
restart Files if folder icons stay cached.

## License

This project is licensed under the MIT License.