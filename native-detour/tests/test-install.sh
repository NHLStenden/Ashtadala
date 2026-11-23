#!/usr/bin/env bash
# Simulates GNOME Shell 51 and user systemd without modifying the host.
set -Eeuo pipefail
if (( EUID == 0 )); then
    command -v runuser >/dev/null 2>&1 || { echo 'runuser required for unprivileged install test' >&2; exit 1; }
    exec runuser -u nobody -- bash "$0"
fi
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DIR="$(mktemp -d)"
trap 'rm -rf -- "$DIR"' EXIT
mkdir -p "$DIR/bin" "$DIR/home" "$DIR/data" "$DIR/config"
CC="${CC:-cc}"
"$CC" -shared -fPIC -o "$DIR/libst-51.so" "$ROOT/tests/fake_libst.c"
cat > "$DIR/bin/systemctl" <<'SH'
#!/usr/bin/env bash
case "$*" in
  '--user cat org.gnome.Shell@user.service') exit 0 ;;
  '--user show org.gnome.Shell@user.service -p Environment --value') exit 0 ;;
  '--user show org.gnome.Shell@user.service -p MainPID --value') echo 0; exit 0 ;;
  '--user show org.gnome.Shell@user.service -p ActiveState --value') echo inactive; exit 0 ;;
  '--user daemon-reload') exit 0 ;;
  *) echo "Unexpected mock systemctl invocation: $*" >&2; exit 2 ;;
esac
SH
cat > "$DIR/bin/gsettings" <<'SH'
#!/usr/bin/env bash
[[ "$*" == 'get org.gnome.desktop.interface accent-color' ]] || exit 2
printf "'slate'\n"
SH
chmod +x "$DIR/bin/systemctl" "$DIR/bin/gsettings"

export HOME="$DIR/home"
export XDG_DATA_HOME="$DIR/data"
export XDG_CONFIG_HOME="$DIR/config"
export GNOME_SLATE_DETOUR_LIBST="$DIR/libst-51.so"
export PATH="$DIR/bin:$PATH"
SHARED="$XDG_DATA_HOME/gnome-slate-detour/libgnome-slate-detour.so"
DROPIN="$XDG_CONFIG_HOME/systemd/user/org.gnome.Shell@user.service.d/80-gnome-slate-detour.conf"
LEGACY="$XDG_CONFIG_HOME/systemd/user/org.gnome.Shell@wayland.service.d/70-gnome-slate-detour.conf"
SCRIPT="$ROOT/scripts/gnome-slate-detour.sh"

# Simulate previous v1 installation.
mkdir -p "$(dirname "$LEGACY")"
echo '# Managed by gnome-slate-detour; do not edit (use install/uninstall).' > "$LEGACY"

bash "$SCRIPT" check
bash "$SCRIPT" install '#ff9e64'
[[ -f "$SHARED" && -f "$DROPIN" && ! -e "$LEGACY" ]]
grep -Fxq '# Managed by gnome-slate-detour v2' "$DROPIN"
grep -Fq 'GNOME_SLATE_DETOUR_COLOR=#ff9e64' "$DROPIN"
grep -Fq 'GNOME_SLATE_DETOUR_LOG=1' "$DROPIN"
grep -Fq 'LD_PRELOAD=' "$DROPIN"
bash "$SCRIPT" status
# Named colors resolve through the same palette as TokyoAdwaita's installer.
bash "$SCRIPT" install magenta
grep -Fq 'GNOME_SLATE_DETOUR_COLOR=#bb9af7' "$DROPIN"
bash "$SCRIPT" install blue
grep -Fq 'GNOME_SLATE_DETOUR_COLOR=#7aa2f7' "$DROPIN"
if bash "$SCRIPT" install not-a-color > "$DIR/invalid.log" 2>&1; then
    echo 'FAIL: accepted unknown TokyoNight color' >&2
    exit 1
fi
grep -Fq 'GNOME_SLATE_DETOUR_COLOR=#7aa2f7' "$DROPIN"
bash "$SCRIPT" uninstall
[[ ! -e "$SHARED" && ! -e "$DROPIN" ]]
bash "$SCRIPT" uninstall
printf 'PASS: v1 migration, mock install/status/uninstall, repeated uninstall\n'

# The native patch blocks install (otherwise testing the hook would be misleading).
python3 - "$DIR/libst-51.so" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1]); data = p.read_bytes()
assert data.count(b'#6f8396') == 1
data = data.replace(b'#6f8396', b'#ff9e64')
p.write_bytes(data)
PY
if bash "$SCRIPT" check > "$DIR/check.log" 2>&1; then
    echo 'FAIL: check accepted previously patched binary' >&2
    exit 1
fi
grep -Fq 'Restore your previous binary patch first' "$DIR/check.log"
printf 'PASS: old native patch detected and refused\n'
