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
  '--user show-environment') printf '%s\n' "${MOCK_MANAGER_ENV:-}" ;;
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
bash "$SCRIPT" install '#fb996c'
[[ -f "$LIB" && -f "$DROPIN" ]]
grep -Fxq '# Managed by Ashtadala Night native accent hook' "$DROPIN"
grep -Fq 'ASHTADALA_ACCENT_COLOR=#fb996c' "$DROPIN"
grep -Fq 'LD_PRELOAD=' "$DROPIN"
bash "$SCRIPT" install '#90aafa'
grep -Fq 'ASHTADALA_ACCENT_COLOR=#90aafa' "$DROPIN"
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
# Failed install must restore both files; failed reload on uninstall must be retryable.
if MOCK_RELOAD_FAIL=1 bash "$SCRIPT" install '#90aafa' > "$DIR/error" 2>&1; then
  echo 'Reload failure accepted' >&2; exit 1
fi
[[ ! -e "$DROPIN" && ! -e "$LIB" ]]
bash "$SCRIPT" install '#90aafa'
cp "$DROPIN" "$DIR/original-dropin"
cp "$LIB" "$DIR/original-library"
if MOCK_RELOAD_FAIL=1 bash "$SCRIPT" install '#fb996c' > "$DIR/error" 2>&1; then
  echo 'Reconfigure reload failure accepted' >&2; exit 1
fi
cmp "$DROPIN" "$DIR/original-dropin"
cmp "$LIB" "$DIR/original-library"
if MOCK_RELOAD_FAIL=1 bash "$SCRIPT" uninstall > "$DIR/error" 2>&1; then
  echo 'Uninstall reload failure accepted' >&2; exit 1
fi
[[ ! -e "$DROPIN" && -f "$LIB" ]]
bash "$SCRIPT" status | grep -F 'Orphaned hook library remains' >/dev/null
if MOCK_SHOW_FAIL=1 bash "$SCRIPT" uninstall > "$DIR/error" 2>&1; then
  echo 'Unverified service environment accepted' >&2; exit 1
fi
[[ -f "$LIB" ]]
if MOCK_SYSTEMD_ENV="LD_PRELOAD=$LIB" bash "$SCRIPT" uninstall > "$DIR/error" 2>&1; then
  echo 'Referenced library removed' >&2; exit 1
fi
[[ -f "$LIB" ]]
if MOCK_MANAGER_ENV="LD_PRELOAD=$LIB" bash "$SCRIPT" uninstall > "$DIR/error" 2>&1; then
  echo 'Manager-referenced library removed' >&2; exit 1
fi
[[ -f "$LIB" ]]
bash "$SCRIPT" uninstall
[[ ! -e "$DROPIN" && ! -e "$LIB" ]]
bash "$SCRIPT" uninstall
if MOCK_MANAGER_ENV='LD_PRELOAD=/another/foreign.so' bash "$SCRIPT" check > "$DIR/error" 2>&1; then
  echo 'Foreign manager preload accepted' >&2; exit 1
fi
# A modified marked drop-in is not safe to delete.
bash "$SCRIPT" install '#90aafa'
cp "$DROPIN" "$DIR/original-dropin"
printf 'Environment="OTHER=1"\n' >> "$DROPIN"
if bash "$SCRIPT" uninstall > "$DIR/error" 2>&1; then
  echo 'Modified drop-in removed' >&2; exit 1
fi
[[ -f "$DROPIN" && -f "$LIB" ]]
cp "$DIR/original-dropin" "$DROPIN"
bash "$SCRIPT" uninstall
# A file at the dedicated library path without our marker is not ours.
mkdir -p "$(dirname "$LIB")"
printf 'foreign' > "$LIB"
if bash "$SCRIPT" uninstall > "$DIR/error" 2>&1; then
  echo 'Foreign library removed' >&2; exit 1
fi
[[ $(cat "$LIB") == foreign ]]
rm "$LIB"
# Refuse to overwrite files without the ownership marker.
mkdir -p "$(dirname "$DROPIN")"
printf '[Service]\n' > "$DROPIN"
if bash "$SCRIPT" install '#fb996c' > "$DIR/error" 2>&1; then
  echo 'Unmanaged drop-in overwritten' >&2; exit 1
fi
grep -Fq 'unmanaged drop-in' "$DIR/error"
rm "$DROPIN"
# Reject the native binary-patch method rather than masking a false-positive hook.
python3 - "$DIR/libst-51.so" <<'PYTEST'
from pathlib import Path
import sys
p=Path(sys.argv[1]); data=p.read_bytes(); assert data.count(b'#6f8396')==1
p.write_bytes(data.replace(b'#6f8396',b'#fb996c'))
PYTEST
if bash "$SCRIPT" check > "$DIR/error" 2>&1; then
  echo 'Patched binary accepted' >&2; exit 1
fi
grep -Fq 'Native slate literal missing' "$DIR/error"
printf 'PASS: native hook install/reconfigure/uninstall, preloading conflict, ownership, patched-binary checks\n'
