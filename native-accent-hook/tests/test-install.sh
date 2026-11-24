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
   '--user show org.gnome.Shell@user.service -p Environment --value')
    if [[ ${MOCK_SHOW_FAIL:-0} == 1 ]]; then exit 1; fi
    if [[ ${MOCK_SYSTEMD_ENV+x} ]]; then printf '%s\n' "$MOCK_SYSTEMD_ENV"; exit 0; fi
    # Last drop-in wins, just as systemd's Environment= assignment does.
    for file in "$XDG_CONFIG_HOME"/systemd/user/org.gnome.Shell@user.service.d/*.conf; do
      [[ -f "$file" ]] || continue
      value=$(sed -n 's/^Environment="LD_PRELOAD=\(.*\)"$/\1/p' "$file")
      [[ -z "$value" ]] || preload=$value
    done
    [[ -z ${preload:-} ]] || printf 'LD_PRELOAD=%s\n' "$preload"
    exit 0 ;;
  '--user show org.gnome.Shell@user.service -p MainPID --value') echo 0; exit 0 ;;
  '--user daemon-reload') [[ ${MOCK_RELOAD_FAIL:-0} != 1 ]] ;;
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
# A list containing our library AND a foreign library is not our preload.
if MOCK_SYSTEMD_ENV="LD_PRELOAD=$LIB:/another/foreign.so" bash "$SCRIPT" check > "$DIR/error" 2>&1; then
  echo 'Mixed preload accepted' >&2; exit 1
fi
if MOCK_SHOW_FAIL=1 bash "$SCRIPT" check > "$DIR/error" 2>&1; then
  echo 'Unreadable service environment accepted' >&2; exit 1
fi
bash "$SCRIPT" uninstall
[[ ! -e "$DROPIN" && ! -e "$LIB" ]]
bash "$SCRIPT" uninstall
# Reproduce the old install using its actual emitted configuration.
OLD_LIB="$XDG_DATA_HOME/tokyoadwaita-night/libaccent-hook.so"
OLD_DROPIN="$(dirname "$DROPIN")/80-tokyoadwaita-accent.conf"
mkdir -p "$(dirname "$OLD_LIB")" "$(dirname "$OLD_DROPIN")"
touch "$OLD_LIB"
printf '%s\n' '# Managed by TokyoAdwaita Night native accent hook' '[Service]' \
  "Environment=\"LD_PRELOAD=$OLD_LIB\"" 'Environment="TOKYOADWAITA_ACCENT_COLOR=#7aa2f7"' \
  'Environment="TOKYOADWAITA_ACCENT_LOG=1"' > "$OLD_DROPIN"
cp "$OLD_DROPIN" "$DIR/original-dropin"
bash "$SCRIPT" check
cmp "$OLD_DROPIN" "$DIR/original-dropin"  # Preflight is read-only.
if MOCK_RELOAD_FAIL=1 bash "$SCRIPT" install '#8fa9fd' > "$DIR/error" 2>&1; then
  echo 'Reload failure accepted' >&2; exit 1
fi
cmp "$OLD_DROPIN" "$DIR/original-dropin"
[[ ! -e "$DROPIN" && ! -e "$LIB" ]]
# A modified old drop-in is not ours to remove.
printf 'Environment="OTHER=1"\n' >> "$OLD_DROPIN"
if bash "$SCRIPT" check > "$DIR/error" 2>&1; then
  echo 'Modified legacy drop-in accepted' >&2; exit 1
fi
cp "$DIR/original-dropin" "$OLD_DROPIN"
if MOCK_SYSTEMD_ENV="LD_PRELOAD=$OLD_LIB:/another/foreign.so" bash "$SCRIPT" check > "$DIR/error" 2>&1; then
  echo 'Mixed legacy preload accepted' >&2; exit 1
fi
bash "$SCRIPT" install '#8fa9fd'
[[ ! -e "$OLD_DROPIN" && -f "$OLD_LIB" && -f "$DROPIN" && -f "$LIB" ]]
[[ $(systemctl --user show org.gnome.Shell@user.service -p Environment --value) == "LD_PRELOAD=$LIB" ]]
bash "$SCRIPT" install '#ef9369'
bash "$SCRIPT" uninstall
[[ ! -e "$DROPIN" && ! -e "$LIB" ]]
# A legacy path without its authentic drop-in is still foreign.
if MOCK_SYSTEMD_ENV="LD_PRELOAD=$OLD_LIB" bash "$SCRIPT" check > "$DIR/error" 2>&1; then
  echo 'Unowned legacy preload accepted' >&2; exit 1
fi
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
