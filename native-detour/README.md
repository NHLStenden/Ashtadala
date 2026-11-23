# Native accent detour (optional)

This is the **working GNOME 51 / Fedora 45** `LD_PRELOAD` hook, integrated into
TokyoAdwaita-Night. It is **not** enabled by default. Prefer the main commands:

```sh
./install.sh --scope user --accent blue --native-detour
./configure.sh --accent magenta
./configure.sh --no-native-detour
./uninstall.sh
```

The hook can also be inspected independently (as the desktop user, without sudo):

```sh
bash native-detour/scripts/gnome-slate-detour.sh check
bash native-detour/scripts/gnome-slate-detour.sh status
bash native-detour/scripts/gnome-slate-detour.sh logs
make -C native-detour test
```

It replaces only GNOME Shell native slate (`#6f8396`) with the selected TokyoNight
color at `cogl_color_from_string()`. It loads through `org.gnome.Shell@user.service`,
not the older `@wayland.service`. It leaves RPM-owned files alone. The helper accepts
named colors from the main shared `tokyonight_colors.py` palette, or `#RRGGBB`.

After changes, **log out/in or reboot**. Do not restart GNOME Shell during a live
Wayland session. If a login loop occurs: at Ctrl+Alt+F3, remove only the managed
`~/.config/systemd/user/org.gnome.Shell@user.service.d/80-gnome-slate-detour.conf`,
run `systemctl --user daemon-reload`, then reboot. Avoid deleting other drop-ins.

In main-theme mode, existing standalone v2 settings are restored on disabling the
integration or uninstalling the theme. Unmanaged drop-ins are refused.

Credit: injection pattern based on the independently published
[ajirezk/saturation_gnome-wayland](https://github.com/ajirezk/saturation_gnome-wayland)
(MIT), but no saturation/drm code is included.
