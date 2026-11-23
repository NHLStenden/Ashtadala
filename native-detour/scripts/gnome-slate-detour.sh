#!/usr/bin/env bash
# TokyoNight GNOME Slate Detour v2. Installs without modifying RPM-owned files.
set -Eeuo pipefail

NAME=gnome-slate-detour
UNIT='org.gnome.Shell@user.service'
LEGACY_UNIT='org.gnome.Shell@wayland.service'
SLATE='#6f8396'
DEFAULT_COLOR='#7aa2f7'
MARKER='# Managed by gnome-slate-detour v2'
OLD_MARKER='# Managed by gnome-slate-detour; do not edit (use install/uninstall).'

THIS_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$THIS_DIR/.." && pwd)"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/$NAME"
LIB="$DATA_DIR/libgnome-slate-detour.so"
CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
DROPIN_DIR="$CONF_DIR/$UNIT.d"
DROPIN="$DROPIN_DIR/80-gnome-slate-detour.conf"
LEGACY_DROPIN="$CONF_DIR/$LEGACY_UNIT.d/70-gnome-slate-detour.conf"
LIBST="${GNOME_SLATE_DETOUR_LIBST:-/usr/lib64/gnome-shell/libst-51.so}"
SYSTEMCTL="${GNOME_SLATE_DETOUR_SYSTEMCTL:-systemctl}"

say() { printf '%s\n' "$*"; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
usage() {
cat <<'HELP'
GNOME Slate Detour (TokyoAdwaita) — Fedora 45 / GNOME 51

Usage: ./gnome-slate-detour.sh COMMAND [NAME|#RRGGBB]
  check                Read-only compatibility checks
  install [NAME|#RRGGBB]  Build hook, configure org.gnome.Shell@user.service
  status               Check service, loaded hook, and binary patch state
  logs                 Show recent hook events from the user's journal
  uninstall            Remove only this hook and its managed drop-in

Run without sudo. Logout/login (or reboot) after installing/uninstalling.
Restore the OLD binary patch first: the native #6f8396 must be present.
HELP
}
need_user() { (( EUID != 0 )) || die 'Run without sudo as your GNOME desktop user.'; }
need() { command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"; }
valid_hex() { [[ "$1" =~ ^#[[:xdigit:]]{6}$ ]]; }
owned() { [[ -f "$DROPIN" ]] && grep -Fxq -- "$MARKER" "$DROPIN"; }
legacy_owned() { [[ -f "$LEGACY_DROPIN" ]] && grep -Fxq -- "$OLD_MARKER" "$LEGACY_DROPIN"; }

check_paths() {
    # LD_PRELOAD uses spaces and colons as delimiters; systemd expands %.
    case "$LIB" in
        *' '*|*$'\t'*|*':'*|*'%'*|*'"'*|*'\'* )
            die 'Library path contains unsupported characters (spaces, colon, %, quotes or backslash).';;
    esac
}

check() {
    need_user
    need python3; need cc; need readelf; need grep; need "$SYSTEMCTL"; need gsettings
    check_paths
    [[ -f "$LIBST" ]] || die "GNOME Shell 51 library missing: $LIBST"
    if ! readelf -rW "$LIBST" | grep -F 'cogl_color_from_string' | grep -F 'JUMP_SLOT' >/dev/null; then
        die 'libst-51.so lacks a JUMP_SLOT for cogl_color_from_string.'
    fi
    say "OK  ELF relocation for cogl_color_from_string present: $LIBST"
    if ! grep -aFq -- "$SLATE" "$LIBST"; then
        die 'Native #6f8396 absent. Restore your previous binary patch first (or reinstall GNOME Shell).'
    fi
    say "OK  Native $SLATE literal present (binary not replaced at that location)"
    "$SYSTEMCTL" --user cat "$UNIT" >/dev/null 2>&1 || die "Systemd unit $UNIT unavailable."
    say "OK  $UNIT is available"
    local effective
    effective="$("$SYSTEMCTL" --user show "$UNIT" -p Environment --value 2>/dev/null || true)"
    if [[ "$effective" == *'LD_PRELOAD='* && "$effective" != *"LD_PRELOAD=$LIB"* ]]; then
        die "Another LD_PRELOAD is configured for $UNIT; refusing to replace it. Inspect systemctl --user cat '$UNIT'."
    fi
    local setting
    setting="$(gsettings get org.gnome.desktop.interface accent-color 2>/dev/null || true)"
    [[ "$setting" == "'slate'" ]] || warn "Accent is $setting, not 'slate'; set it with: gsettings set org.gnome.desktop.interface accent-color slate"
    if [[ -e "$LEGACY_DROPIN" ]] && ! legacy_owned; then
        warn "Unrecognized old Wayland drop-in at $LEGACY_DROPIN (will not touch)."
    fi
}

install_detour() {
    local color
    # The main installer and this helper resolve names through the same palette.
    color="$(python3 "$PROJECT_DIR/../tokyonight_colors.py" resolve "${1:-blue}")" || \
        die 'Invalid TokyoNight color name or hex.'
    valid_hex "$color" || die 'Color must resolve to #RRGGBB.'
    check
    if [[ -e "$DROPIN" ]] && ! owned; then
        die "Refusing to overwrite unmanaged drop-in: $DROPIN"
    fi
    local temp tmpso tmpconf
    temp="$(mktemp -d)"
    trap 'rm -rf -- "${temp:-}"' EXIT
    cc -O2 -std=c11 -Wall -Wextra -Werror -fPIC -shared -fvisibility=hidden \
        -o "$temp/libgnome-slate-detour.so" "$PROJECT_DIR/src/gnome_slate_detour.c" -ldl -pthread
    readelf -Ws "$temp/libgnome-slate-detour.so" | grep -E 'GLOBAL.*cogl_color_from_string' >/dev/null || \
        die 'Build did not export cogl_color_from_string.'
    mkdir -p -- "$DATA_DIR" "$DROPIN_DIR"
    tmpso="$LIB.new.$$"
    install -m 0755 -- "$temp/libgnome-slate-detour.so" "$tmpso"
    mv -f -- "$tmpso" "$LIB"
    tmpconf="$DROPIN.new.$$"
    {
        printf '%s\n' "$MARKER"
        printf '[Service]\n'
        printf 'Environment="LD_PRELOAD=%s"\n' "$LIB"
        printf 'Environment="GNOME_SLATE_DETOUR_COLOR=%s"\n' "$color"
        printf 'Environment="GNOME_SLATE_DETOUR_LOG=1"\n'
    } > "$tmpconf"
    chmod 0644 "$tmpconf"
    mv -f -- "$tmpconf" "$DROPIN"
    if legacy_owned; then
        rm -f -- "$LEGACY_DROPIN"
        rmdir -- "$(dirname -- "$LEGACY_DROPIN")" 2>/dev/null || true
        say 'Removed the old v1 @wayland drop-in (exact project marker verified).'
    fi
    "$SYSTEMCTL" --user daemon-reload || die 'Installed, but daemon-reload failed. Use uninstall from TTY if necessary.'
    say "Installed native slate detour $SLATE -> $color"
    say "User service: $UNIT"
    say "Hook: $LIB"
    say "Drop-in: $DROPIN"
    say 'Log out/in or reboot. Then run: ./gnome-slate-detour.sh status'
    say 'For loaded/replaced diagnostics: ./gnome-slate-detour.sh logs'
}

status() {
    need_user
    say "Configured GNOME Shell unit: $UNIT"
    if [[ -e "$LIB" ]]; then say "Hook file: present ($LIB)"; else say 'Hook file: absent'; fi
    if owned; then
        say "Drop-in: managed ($DROPIN)"
        grep -F 'GNOME_SLATE_DETOUR_COLOR=' "$DROPIN" || true
    elif [[ -e "$DROPIN" ]]; then warn "Unmanaged drop-in exists: $DROPIN";
    else say 'Drop-in: absent'; fi
    if [[ -e "$LEGACY_DROPIN" ]]; then warn "Old @wayland drop-in still exists: $LEGACY_DROPIN"; fi
    if [[ -e "$LIBST" ]]; then
        if grep -aFq -- "$SLATE" "$LIBST"; then
            say "Native slate literal $SLATE: present"
        else warn 'Native slate literal: missing — check previous binary patch'; fi
    fi
    local pid active env
    active="$("$SYSTEMCTL" --user show "$UNIT" -p ActiveState --value 2>/dev/null || true)"
    pid="$("$SYSTEMCTL" --user show "$UNIT" -p MainPID --value 2>/dev/null || true)"
    env="$("$SYSTEMCTL" --user show "$UNIT" -p Environment --value 2>/dev/null || true)"
    say "Service active state: ${active:-unknown}, MainPID: ${pid:-unknown}"
    if [[ "$env" == *"LD_PRELOAD=$LIB"* ]]; then
        say 'Service configuration: contains expected LD_PRELOAD'
    else
        warn 'Service configuration: expected LD_PRELOAD not effective'
    fi
    if [[ "$pid" =~ ^[1-9][0-9]*$ && -r "/proc/$pid/maps" ]]; then
        if grep -Fq -- "$LIB" "/proc/$pid/maps"; then
            say 'RUNTIME: hook library is mapped in the running Shell process'
        else
            warn 'RUNTIME: hook NOT mapped in GNOME Shell (re-login, then inspect logs)'
        fi
        if [[ -r "/proc/$pid/environ" ]]; then
            if tr '\0' '\n' < "/proc/$pid/environ" | grep -Fxq -- "LD_PRELOAD=$LIB"; then
                say 'RUNTIME: process environment contains expected LD_PRELOAD'
            else
                warn 'RUNTIME: process environment does not contain expected LD_PRELOAD'
            fi
        fi
    else
        warn 'RUNTIME: no readable GNOME Shell process for the selected unit'
    fi
    say 'Use ./gnome-slate-detour.sh logs to check for "loaded" and "replaced" messages.'
}

logs() {
    need_user; need journalctl
    journalctl --user -b --no-pager -o short-iso -u "$UNIT" | \
        grep -F '[gnome-slate-detour]' || true
}

uninstall_detour() {
    need_user
    if [[ -e "$DROPIN" ]]; then
        owned || die "Refusing to delete an unmanaged drop-in: $DROPIN"
        rm -f -- "$DROPIN"
    fi
    # If v1's drop-in remains, remove it only when it contains our v1 marker.
    if legacy_owned; then rm -f -- "$LEGACY_DROPIN"; fi
    [[ ! -f "$LIB" ]] || rm -f -- "$LIB"
    rmdir -- "$DATA_DIR" "$DROPIN_DIR" "$(dirname -- "$LEGACY_DROPIN")" 2>/dev/null || true
    "$SYSTEMCTL" --user daemon-reload || warn 'Run systemctl --user daemon-reload when available.'
    say 'Uninstalled user-local hook. Log out/in or reboot to unload it.'
    say 'No RPM-owned binary or GNOME accent setting was modified.'
}

case "${1:-help}" in
    help|-h|--help) usage ;;
    check) [[ $# == 1 ]] || die 'Usage: check'; check ;;
    install) [[ $# -le 2 ]] || die 'Usage: install [NAME|#RRGGBB]'; install_detour "${2:-$DEFAULT_COLOR}" ;;
    status) [[ $# == 1 ]] || die 'Usage: status'; status ;;
    logs) [[ $# == 1 ]] || die 'Usage: logs'; logs ;;
    uninstall) [[ $# == 1 ]] || die 'Usage: uninstall'; uninstall_detour ;;
    *) usage; exit 2 ;;
esac
