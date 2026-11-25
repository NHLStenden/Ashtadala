# Ashtadala

<p align="center">
  <img src="assets/Ashtadala-logo.svg" alt="Ashtadala logo" width="50%">
</p>

Ashtadala is a user theme for Fedora 45 and GNOME 51.

![Ashtadala preview](assets/Ashtadala-preview.svg)

## Install

Run as your desktop user:

```sh
./install.sh                # blue accent
./install.sh peach          # peach accent
./configure.sh purple       # change accent
./uninstall.sh
```

The color sets the desktop accent. Colors: `blue`, `cyan`, `purple`, `green`, `teal`, `yellow`, `peach`,
`red`, or any `#RRGGBB`.

Missing Fedora packages (`gcc`, `binutils`, User Themes) can be installed with
`sudo dnf` after you confirm. Log out and back in to load Shell changes;
restart Files if folder icons stay cached.

## Design

The eight accents use OKLCH(0.75, 0.125, 45° × n); dark surfaces use
OKLCH(0.23 + 0.03 × n, C, 270°), with the main background at C = 0.025
and role-specific chroma preserving the original dark-surface hierarchy.

## License

This project is licensed under the MIT License.
