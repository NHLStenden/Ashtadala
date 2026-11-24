#!/usr/bin/env bash
# GNOME Shell 51 native accent override via ELF symbol interposition.
set -Eeuo pipefail

UNIT='org.gnome.Shell@user.service'
SLATE='#6f8396'
MARKER='# Managed by Ashtadala Night native accent hook'
DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/ashtadala-night"
LIB="$DATA/libaccent-hook.so"
DROPIN_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/$UNIT.d"
DROPIN="$DROPIN_DIR/80-ashtadala-accent.conf"
LEGACY_DROPIN="$DROPIN_DIR/80-tokyoadwaita-accent.conf"
LEGACY_LIB="${XDG_DATA_HOME:-$HOME/.local/share}/tokyoadwaita-night/libaccent-hook.so"
LIBST="${ASHTADALA_LIBST:-/usr/lib64/gnome-shell/libst-51.so}"
SYSTEMCTL="${ASHTADALA_SYSTEMCTL:-systemctl}"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || fail "Missing command: $1"; }
owned() { [[ -f "$DROPIN" && ! -L "$DROPIN" ]] && grep -Fxq -- "$MARKER" "$DROPIN"; }
# Recognize only the exact configuration emitted by the previous installer.
legacy_owned() {
  [[ -f "$LEGACY_DROPIN" && ! -L "$LEGACY_DROPIN" ]] || return 1
  python3 - "$LEGACY_DROPIN" "$LEGACY_LIB" <<'PYTHON'
import re, sys
from pathlib import Path
lines = Path(sys.argv[1]).read_text().splitlines()
valid = (len(lines) == 5 and lines[:3] == [
    '# Managed by TokyoAdwaita Night native accent hook', '[Service]',
    f'Environment="LD_PRELOAD={sys.argv[2]}"']
    and re.fullmatch(r'Environment="TOKYOADWAITA_ACCENT_COLOR=#[0-9a-fA-F]{6}"', lines[3])
    and lines[4] == 'Environment="TOKYOADWAITA_ACCENT_LOG=1"')
sys.exit(0 if valid else 1)
PYTHON
}
preload_value() {
  python3 -c 'import shlex, sys
values = [v.split("=", 1)[1] for v in shlex.split(sys.stdin.read()) if v.startswith("LD_PRELOAD=")]
if len(values) > 1:
    sys.exit(1)
print(values[0] if values else "")'
}
paths_ok() {
  # LD_PRELOAD treats space/colon as separators; systemd parses % and quotes.
  case "$LIB" in *' '*|*$'\t'*|*$'\n'*|*$'\r'*|*':'*|*'%'*|*'"'*|*'\'* ) fail 'Unsafe path for LD_PRELOAD';; esac
}
check() {
  (( EUID != 0 )) || fail 'Run as your desktop user, never sudo.'
  need cc; need readelf; need python3; need "$SYSTEMCTL"
  paths_ok
  [[ -f "$LIBST" ]] || fail "GNOME Shell library not found: $LIBST"
  readelf -rW "$LIBST" | grep -E 'JUMP_SLOT.*cogl_color_from_string' >/dev/null || \
      fail 'GNOME Shell no longer exposes the expected Cogl PLT symbol'
  grep -aFq -- "$SLATE" "$LIBST" || \
      fail 'Native slate literal missing: restore any earlier binary patch first'
  "$SYSTEMCTL" --user cat "$UNIT" >/dev/null 2>&1 || fail "GNOME service missing: $UNIT"
  if [[ -e "$DROPIN" || -L "$DROPIN" ]] && ! owned; then
      fail "Refusing to replace unmanaged drop-in: $DROPIN"
  fi
  local env preload
  env="$("$SYSTEMCTL" --user show "$UNIT" -p Environment --value)" || fail 'Cannot read Shell service environment'
  preload="$(printf '%s' "$env" | preload_value)" || fail 'Cannot parse Shell service environment'
  if [[ -e "$LEGACY_DROPIN" || -L "$LEGACY_DROPIN" ]] && ! legacy_owned; then
      fail "Refusing to replace unmanaged legacy drop-in: $LEGACY_DROPIN"
  fi
  if [[ -n "$preload" && "$preload" != "$LIB" ]]; then
      if [[ "$preload" != "$LEGACY_LIB" ]] || ! legacy_owned; then
          fail 'Another Shell LD_PRELOAD is active; remove it first (including older standalone hooks)'
      fi
  fi
}
install_hook() {
  [[ "$#" -eq 1 && "$1" =~ ^#[[:xdigit:]]{6}$ ]] || fail 'Expected exactly one #RRGGBB color'
  local color="${1,,}"
  check
  local tmp
  mkdir -p -- "$DATA"
  tmp="$(mktemp -d "$DATA/.build.XXXXXX")"
  trap 'rm -rf -- "${tmp:-}"' EXIT
  cc -O2 -std=c11 -Wall -Wextra -Werror -fPIC -shared -fvisibility=hidden \
    -o "$tmp/libaccent-hook.so" "$DIR/src/accent_hook.c" -ldl -pthread
  readelf -Ws "$tmp/libaccent-hook.so" | grep -E 'GLOBAL.*cogl_color_from_string' >/dev/null || \
      fail 'Hook does not export cogl_color_from_string'
  mkdir -p -- "$DATA" "$DROPIN_DIR"
  install -m 0755 "$tmp/libaccent-hook.so" "$tmp/library"
  {
    printf '%s\n[Service]\n' "$MARKER"
    printf 'Environment="LD_PRELOAD=%s"\n' "$LIB"
    printf 'Environment="ASHTADALA_ACCENT_COLOR=%s"\n' "$color"
    printf 'Environment="ASHTADALA_ACCENT_LOG=1"\n'
  } > "$tmp/config"
  install -m 0644 "$tmp/config" "$tmp/dropin"
  # The old filename sorts after the new one and would override LD_PRELOAD.
  if owned; then cp -- "$DROPIN" "$tmp/previous-dropin"; fi
  if [[ -e "$LIB" || -L "$LIB" ]]; then cp -P -- "$LIB" "$tmp/previous-library"; fi
  mv -f -- "$tmp/library" "$LIB"
  mv -f -- "$tmp/dropin" "$DROPIN"
  if legacy_owned; then
    mv -- "$LEGACY_DROPIN" "$tmp/legacy-dropin"
  fi
  local effective
  if ! "$SYSTEMCTL" --user daemon-reload ||
     ! effective="$("$SYSTEMCTL" --user show "$UNIT" -p Environment --value | preload_value)" ||
     [[ "$effective" != "$LIB" ]]; then
    if [[ -f "$tmp/previous-dropin" ]]; then
      mv -f -- "$tmp/previous-dropin" "$DROPIN"
    else
      rm -f -- "$DROPIN"
    fi
    if [[ -f "$tmp/legacy-dropin" ]]; then
      mv -- "$tmp/legacy-dropin" "$LEGACY_DROPIN"
    fi
    if [[ -e "$tmp/previous-library" || -L "$tmp/previous-library" ]]; then
      mv -f -- "$tmp/previous-library" "$LIB"
    else
      rm -f -- "$LIB"
    fi
    "$SYSTEMCTL" --user daemon-reload || true
    fail 'Cannot activate native hook; previous configuration restored'
  fi
  if [[ -f "$tmp/legacy-dropin" ]]; then
    printf 'Migrated previous TokyoAdwaita native accent hook (takes effect next login)\n'
  fi
  rm -rf -- "$tmp"
  printf 'Native accent hook: %s -> %s (takes effect next login)\n' "$SLATE" "$color"
}
uninstall_hook() {
  (( EUID != 0 )) || fail 'Run as your desktop user, never sudo.'
  local was_owned=0
  if [[ -e "$DROPIN" || -L "$DROPIN" ]]; then
    owned || fail "Unmanaged drop-in; refusing removal: $DROPIN"
    was_owned=1
  elif [[ -f "$LIB" ]]; then
    fail "Orphan hook library exists; inspect manually: $LIB"
  fi
  if (( was_owned )); then
    # Check whether another service/drop-in also references our library.
    rm -- "$DROPIN"
    "$SYSTEMCTL" --user daemon-reload || fail 'systemd user daemon-reload failed'
    if "$SYSTEMCTL" --user cat "$UNIT" 2>/dev/null | grep -Fq -- "$LIB"; then
      fail 'Hook library is still referenced; leave it in place'
    fi
    [[ ! -e "$LIB" && ! -L "$LIB" ]] || rm -- "$LIB"
  else
    "$SYSTEMCTL" --user daemon-reload || fail 'systemd user daemon-reload failed'
  fi
  rmdir -- "$DROPIN_DIR" "$DATA" 2>/dev/null || true
  printf 'Native accent hook removed (takes effect next login)\n'
}
status() {
  printf 'Hook: %s\n' "$LIB"
  if owned; then
    sed -n '/ASHTADALA_ACCENT_COLOR=/p' "$DROPIN"
  else
    printf 'Not installed\n'
  fi
  local pid
  pid="$("$SYSTEMCTL" --user show "$UNIT" -p MainPID --value 2>/dev/null || true)"
  if [[ "$pid" =~ ^[1-9][0-9]*$ && -r "/proc/$pid/maps" ]] && grep -Fq "$LIB" "/proc/$pid/maps"; then
    printf 'Runtime: loaded in GNOME Shell (pid %s)\n' "$pid"
  else
    printf 'Runtime: not loaded (or log out/in required)\n'
  fi
}
case "${1:-}" in
 check) [[ $# -eq 1 ]] || fail 'check takes no arguments'; check ;;
 install) [[ $# -eq 2 ]] || fail 'install requires #RRGGBB'; install_hook "$2" ;;
 uninstall) [[ $# -eq 1 ]] || fail 'uninstall takes no arguments'; uninstall_hook ;;
 status) [[ $# -eq 1 ]] || fail 'status takes no arguments'; status ;;
 *) fail 'Internal usage: accent-hook.sh check|install HEX|uninstall|status' ;;
esac
