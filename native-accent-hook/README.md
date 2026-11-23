# Native accent hook

`LD_PRELOAD` intercepts GNOME Shell 51's `cogl_color_from_string()` and replaces
`#6f8396` with the configured accent. Other calls are forwarded unchanged.

The installer builds `libaccent-hook.so` and adds a user-systemd drop-in for
`org.gnome.Shell@user.service`. No Fedora libraries are changed.

To disable injection from a TTY, remove
`~/.config/systemd/user/org.gnome.Shell@user.service.d/80-tokyoadwaita-accent.conf`,
run `systemctl --user daemon-reload` and reboot.

Injection reference: https://github.com/ajirezk/saturation_gnome-wayland
