# Native accent hook

The GNOME Shell 51 accent is changed through ELF symbol interposition (`LD_PRELOAD`).
`accent-hook.c` wraps `cogl_color_from_string()` and replaces exactly GNOME's native
slate (`#6f8396`) with `TOKYOADWAITA_ACCENT_COLOR`. Other calls are forwarded unchanged.

The main installer builds and configures the hook for `org.gnome.Shell@user.service`.
No RPM-owned files are modified. Use `./diagnose.sh` to inspect the installed hook.

**Recovery:** from a TTY (Ctrl+Alt+F3), remove only
`~/.config/systemd/user/org.gnome.Shell@user.service.d/80-tokyoadwaita-accent.conf`,
run `systemctl --user daemon-reload`, then reboot. Removing the drop-in stops future
injection. Other systemd Shell drop-ins are untouched.

The hook must be revalidated after GNOME Shell upgrades.
Injection pattern reference: https://github.com/ajirezk/saturation_gnome-wayland
