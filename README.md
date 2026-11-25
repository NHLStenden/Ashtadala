# Ashtadala

<p align="center">
  <img src="assets/Ashtadala-logo.svg" alt="Ashtadala logo" width="50%">
</p>

Ashtadala is a user theme for Fedora 45 and GNOME 51.

![Ashtadala preview](assets/Ashtadala-preview.svg)

## Install

Run as your desktop user:

```sh
./install.sh             # install
./uninstall.sh           # uninstall
```

Missing Fedora packages (`gcc`, `binutils`, User Themes) can be installed with `sudo dnf`. Log out and back in after installation to reload GTK styles in all running apps, Shell changes, and the native accent hook.

## Design

Ashtadala's palette is mathematically constructed in OKLCH, a perceptual color space defined by lightness (L), chroma (C), and hue (H).

The eight accents form a harmonic color ring, with hues evenly spaced at 45° intervals. Lightness and chroma vary smoothly around the ring,
peaking at gold to balance the visual intensity of warm and cool colors. Each accent follows the same mathematical formula:

- `H = 45° × n`, where `n = 0…7`
- `w = ((1 + sin(H)) / 2)³`, with H in degrees
- `L = 0.75 + 0.04 × w`
- `C = 0.12 + 0.02 × w`

The dark surfaces share a deep-blue hue of 270°, with lightness increasing in regular steps (`L = 0.23 + 0.03 × n`). Chroma varies
according to each surface's role, with `C = 0.025` for the main background, creating a subtle visual hierarchy without competing
with the accents.

Together, these two color systems balance mathematical elegance, visual harmony, and everyday readability.

## License

This project is licensed under the MIT License.
