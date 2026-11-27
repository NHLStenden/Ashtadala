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

# The parent still substitutes the accent, but its exec'd child must not.
assert_eq "$(LD_PRELOAD="$DIR/libaccent-hook.so" "$DIR/driver" '#6f8396' exec-child)" \
    $'#fb996c\n#6f8396' 'preload does not leak to exec child'
# Do not alter another preload, including an unsupported mixed configuration.
mixed="$DIR/libaccent-hook.so:$DIR/libfakecogl.so"
assert_eq "$(LD_PRELOAD="$mixed" bash -c 'printf %s "$LD_PRELOAD"')" "$mixed" \
    'mixed preload is preserved'
assert_eq "$(LD_PRELOAD="$DIR/libfakecogl.so" bash -c 'printf %s "$LD_PRELOAD"')" \
    "$DIR/libfakecogl.so" 'foreign preload is preserved'

# Reproduce the Resources helper's stderr pipe with no reader. Python restores
# default SIGPIPE in the child (unlike Python's own ignored disposition).
python3 - "$DIR" <<'PYTEST'
import os
import socket
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
env = dict(os.environ, LD_PRELOAD=str(root / 'libaccent-hook.so'),
           ASHTADALA_ACCENT_LOG='1', ASHTADALA_ACCENT_COLOR='#fb996c')
for kind in ('pipe', 'socket', 'closed-fd'):
    if kind == 'pipe':
        reader, writer = os.pipe()
        os.close(reader)
    elif kind == 'socket':
        peer, endpoint = socket.socketpair()
        peer.close()
        writer = endpoint.detach()
    else:
        writer = None
    try:
        result = subprocess.run([str(root / 'driver'), '#6f8396'], env=env,
                                stdout=subprocess.PIPE, stderr=writer,
                                restore_signals=True,
                                preexec_fn=(lambda: os.close(2)) if writer is None else None,
                                timeout=5)
        assert result.returncode == 0, (kind, result.returncode)
        assert result.stdout == b'#fb996c\n', (kind, result.stdout)
        print(f'PASS: diagnostic logging survives {kind}')
    finally:
        if writer is not None:
            os.close(writer)
PYTEST
