#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DIR="$(mktemp -d)"
trap 'rm -rf -- "$DIR"' EXIT
CC="${CC:-cc}"
"$CC" -fPIC -shared -o "$DIR/libfakecogl.so" "$ROOT/tests/fake_cogl.c"
"$CC" -o "$DIR/driver" "$ROOT/tests/call_cogl.c" \
    -L"$DIR" -lfakecogl -Wl,-rpath,"$DIR"
"$CC" -O2 -Wall -Wextra -Werror -std=c11 -fPIC -shared -fvisibility=hidden \
    -o "$DIR/libaccent-hook.so" "$ROOT/src/accent_hook.c" -ldl -pthread

assert_eq() {
    local got="$1" want="$2" desc="$3"
    if [[ "$got" != "$want" ]]; then
        printf 'FAIL: %s: expected %q; got %q\n' "$desc" "$want" "$got" >&2
        exit 1
    fi
    printf 'PASS: %s\n' "$desc"
}

assert_eq "$("$DIR/driver" '#6f8396')" '#6f8396' 'without hook original unchanged'
assert_eq "$(LD_PRELOAD="$DIR/libaccent-hook.so" "$DIR/driver" '#6f8396')" '#fb996c' 'generated default substitution'
assert_eq "$(LD_PRELOAD="$DIR/libaccent-hook.so" "$DIR/driver" '#abcdef')" '#abcdef' 'unrelated color unchanged'
assert_eq "$(ASHTADALA_ACCENT_COLOR='#AABBCC' LD_PRELOAD="$DIR/libaccent-hook.so" "$DIR/driver" '#6f8396')" '#AABBCC' 'custom color override'
assert_eq "$(ASHTADALA_ACCENT_COLOR='not-a-color' LD_PRELOAD="$DIR/libaccent-hook.so" "$DIR/driver" '#6f8396')" '#fb996c' 'invalid color falls back to generated default'
assert_eq "$(ASHTADALA_ACCENT_COLOR='#' LD_PRELOAD="$DIR/libaccent-hook.so" "$DIR/driver" '#6f8396')" '#fb996c' 'short invalid color safely falls back'
assert_eq "$(ASHTADALA_ACCENT_COLOR='' LD_PRELOAD="$DIR/libaccent-hook.so" "$DIR/driver" '#6f8396')" '#fb996c' 'empty color safely falls back'
assert_eq "$(LD_PRELOAD="$DIR/libaccent-hook.so" "$DIR/driver" '#6f8397')" '#6f8397' 'nearby but different color unchanged'

LOG_OUT="$DIR/log.txt"
ASHTADALA_ACCENT_LOG=1 LD_PRELOAD="$DIR/libaccent-hook.so" "$DIR/driver" '#6f8396' > /dev/null 2> "$LOG_OUT"
grep -Fq 'loaded' "$LOG_OUT"
grep -Fq 'replaced native slate with #fb996c' "$LOG_OUT"
printf 'PASS: runtime load and replacement diagnostics\n'
