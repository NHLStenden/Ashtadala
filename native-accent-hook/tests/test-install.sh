#!/usr/bin/env bash
# Simulates a Fedora Shell library and user systemd; never touches the real session.
set -Eeuo pipefail
if (( EUID == 0 )); then
  command -v runuser >/dev/null 2>&1 || { echo 'runuser required for unprivileged test' >&2; exit 1; }
  exec runuser -u nobody -- bash "$0"
fi
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DIR="$(mktemp -d)"
trap 'rm -rf -- "$DIR"' EXIT
mkdir -p "$DIR/bin" "$DIR/home" "$DIR/data" "$DIR/config"
"${CC:-cc}" -shared -fPIC -o "$DIR/libst-51.so" "$ROOT/tests/fake_libst.c"
cat > "$DIR/bin/systemctl" <<'MOCK'
#!/usr/bin/env bash
case "$*" in
  '--user cat org.gnome.Shell@user.service') exit 0 ;;
  '--user show org.gnome.Shell@user.service -p Environment --value') printf '%s\n' "${MOCK_SYSTEMD_ENV:-}"; exit 0 ;;
  '--user show org.gnome.Shell@user.service -p MainPID --value') echo 0; exit 0 ;;
  '--user daemon-reload') exit 0 ;;
  *) echo "Unexpected mock systemctl: $*" >&2; exit 2 ;;
esac
MOCK
chmod +x "$DIR/bin/systemctl"
export HOME="$DIR/home"
export XDG_DATA_HOME="$DIR/data"
export XDG_CONFIG_HOME="$DIR/config"
export ASHTADALA_LIBST="$DIR/libst-51.so"
export ASHTADALA_SYSTEMCTL=systemctl
export PATH="$DIR/bin:$PATH"
SCRIPT="$ROOT/scripts/accent-hook.sh"
LIB="$XDG_DATA_HOME/ashtadala-night/libaccent-hook.so"
DROPIN="$XDG_CONFIG_HOME/systemd/user/org.gnome.Shell@user.service.d/80-ashtadala-accent.conf"

bash "$SCRIPT" check
bash "$SCRIPT" install '#ef9369'
[[ -f "$LIB" && -f "$DROPIN" ]]
grep -Fxq '# Managed by Ashtadala Night native accent hook' "$DROPIN"
grep -Fq 'ASHTADALA_ACCENT_COLOR=#ef9369' "$DROPIN"
grep -Fq 'LD_PRELOAD=' "$DROPIN"
bash "$SCRIPT" install '#8fa9fd'
grep -Fq 'ASHTADALA_ACCENT_COLOR=#8fa9fd' "$DROPIN"
if bash "$SCRIPT" install orange > "$DIR/error" 2>&1; then
  echo 'Invalid accent accepted' >&2; exit 1
fi
if MOCK_SYSTEMD_ENV='LD_PRELOAD=/another/foreign.so' bash "$SCRIPT" check > "$DIR/error" 2>&1; then
  echo 'Foreign preload accepted' >&2; exit 1
fi
grep -Fq 'Another Shell LD_PRELOAD' "$DIR/error"
bash "$SCRIPT" uninstall
[[ ! -e "$DROPIN" && ! -e "$LIB" ]]
bash "$SCRIPT" uninstall
# Refuse to overwrite files without the ownership marker.
mkdir -p "$(dirname "$DROPIN")"
printf '[Service]\n' > "$DROPIN"
if bash "$SCRIPT" install '#ef9369' > "$DIR/error" 2>&1; then
  echo 'Unmanaged drop-in overwritten' >&2; exit 1
fi
grep -Fq 'unmanaged drop-in' "$DIR/error"
rm "$DROPIN"
# Reject the native binary-patch method rather than masking a false-positive hook.
python3 - "$DIR/libst-51.so" <<'PYTEST'
from pathlib import Path
import sys
p=Path(sys.argv[1]); data=p.read_bytes(); assert data.count(b'#6f8396')==1
p.write_bytes(data.replace(b'#6f8396',b'#ef9369'))
PYTEST
if bash "$SCRIPT" check > "$DIR/error" 2>&1; then
  echo 'Patched binary accepted' >&2; exit 1
fi
grep -Fq 'Native slate literal missing' "$DIR/error"
printf 'PASS: native hook install/reconfigure/uninstall, preloading conflict, ownership, patched-binary checks\n'
