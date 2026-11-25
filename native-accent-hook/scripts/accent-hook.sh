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
LIBST="${ASHTADALA_LIBST:-/usr/lib64/gnome-shell/libst-51.so}"
SYSTEMCTL="${ASHTADALA_SYSTEMCTL:-systemctl}"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || fail "Missing command: $1"; }
owned_library() {
  [[ -f "$LIB" && ! -L "$LIB" ]] && grep -aFq -- '[ashtadala-accent]' "$LIB"
}
owned() {
  [[ -f "$DROPIN" && ! -L "$DROPIN" ]] || return 1
  local -a lines=()
  mapfile -t lines < "$DROPIN"
  [[ ${#lines[@]} -eq 5 ]] &&
    [[ "${lines[0]}" == "$MARKER" && "${lines[1]}" == '[Service]' &&
       "${lines[2]}" == "Environment=\"LD_PRELOAD=$LIB\"" &&
       "${lines[4]}" == 'Environment="ASHTADALA_ACCENT_LOG=1"' ]] &&
    [[ "${lines[3]}" =~ ^Environment=\"ASHTADALA_ACCENT_COLOR=\#[[:xdigit:]]{6}\"$ ]]
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
  local env preload manager
  env="$("$SYSTEMCTL" --user show "$UNIT" -p Environment --value)" || fail 'Cannot read Shell service environment'
  preload="$(printf '%s' "$env" | preload_value)" || fail 'Cannot parse Shell service environment'
  if [[ -n "$preload" ]] && { [[ "$preload" != "$LIB" ]] || ! owned; }; then
      fail 'Another Shell LD_PRELOAD is active; remove it first'
  fi
  manager="$("$SYSTEMCTL" --user show-environment)" || fail 'Cannot read user manager environment'
  preload="$(printf '%s' "$manager" | preload_value)" || fail 'Cannot parse user manager environment'
  if [[ -n "$preload" ]]; then
      fail 'A user-manager LD_PRELOAD is active; remove it first'
  fi
  if [[ -e "$LIB" || -L "$LIB" ]] && ! owned_library; then
      fail "Refusing to replace unmanaged library: $LIB"
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
  if owned; then cp -- "$DROPIN" "$tmp/previous-dropin"; fi
  if [[ -e "$LIB" || -L "$LIB" ]]; then cp -P -- "$LIB" "$tmp/previous-library"; fi
  local effective
  if ! mv -f -- "$tmp/library" "$LIB" ||
     ! mv -f -- "$tmp/dropin" "$DROPIN" ||
     ! "$SYSTEMCTL" --user daemon-reload ||
     ! effective="$("$SYSTEMCTL" --user show "$UNIT" -p Environment --value | preload_value)" ||
     [[ "$effective" != "$LIB" ]]; then
    local restore_failed=0
    if [[ -f "$tmp/previous-dropin" ]]; then
      cp -- "$tmp/previous-dropin" "$DROPIN" || restore_failed=1
    else
      rm -f -- "$DROPIN" || restore_failed=1
    fi
    if [[ -f "$tmp/previous-library" ]]; then
      cp -- "$tmp/previous-library" "$LIB" || restore_failed=1
    else
      rm -f -- "$LIB" || restore_failed=1
    fi
    if (( restore_failed )); then
      trap - EXIT
      fail "Cannot activate or restore native hook; backups retained at $tmp"
    fi
    "$SYSTEMCTL" --user daemon-reload || fail 'Native hook files restored, but systemd reload failed; retry uninstall or installation'
    fail 'Cannot activate native hook; previous configuration restored'
  fi
  rm -rf -- "$tmp"
  printf 'Native accent hook: %s -> %s (takes effect next login)\n' "$SLATE" "$color"
}
uninstall_hook() {
  (( EUID != 0 )) || fail 'Run as your desktop user, never sudo.'
  if [[ -e "$DROPIN" || -L "$DROPIN" ]]; then
    owned || fail "Unmanaged drop-in; refusing removal: $DROPIN"
    rm -- "$DROPIN"
  fi
  # Always reload, even on retry after a previous reload failure.
  "$SYSTEMCTL" --user daemon-reload || fail 'systemd user daemon-reload failed; retry uninstall'
  local unit env manager
  unit="$("$SYSTEMCTL" --user cat "$UNIT")" || fail 'Cannot verify Shell service'
  env="$("$SYSTEMCTL" --user show "$UNIT" -p Environment --value)" || fail 'Cannot verify Shell service environment'
  manager="$("$SYSTEMCTL" --user show-environment)" || fail 'Cannot verify user manager environment'
  if [[ "$unit" == *"$LIB"* || "$env" == *"$LIB"* || "$manager" == *"$LIB"* ]]; then
    fail 'Hook library is still referenced; leave it in place'
  fi
  if [[ -e "$LIB" || -L "$LIB" ]]; then
    owned_library || fail "Unmanaged hook library; refusing removal: $LIB"
    rm -- "$LIB"
  fi
  rmdir -- "$DROPIN_DIR" "$DATA" 2>/dev/null || true
  printf 'Native accent hook removed (takes effect next login)\n'
}
status() {
  printf 'Hook: %s\n' "$LIB"
  if owned; then
    sed -n '/ASHTADALA_ACCENT_COLOR=/p' "$DROPIN"
  elif [[ -e "$DROPIN" || -L "$DROPIN" ]]; then
    printf 'Unmanaged drop-in remains: %s\n' "$DROPIN"
  elif [[ -e "$LIB" || -L "$LIB" ]]; then
    printf 'Orphaned hook library remains: %s\n' "$LIB"
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
