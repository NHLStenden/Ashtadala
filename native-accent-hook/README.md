# Native accent hook

GNOME Shell 51 hard-codes `#6f8396` as its slate accent. This hook intercepts
`cogl_color_from_string()` via `LD_PRELOAD` and swaps just that color for your
chosen accent. Everything else passes through.

The installer builds `libaccent-hook.so` and adds a user-systemd drop-in for
`org.gnome.Shell@user.service`. It doesn't patch system libraries.

Recovery steps are in the main [README](../README.md). Technique based on
[saturation_gnome-wayland](https://github.com/ajirezk/saturation_gnome-wayland).
