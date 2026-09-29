#!/usr/bin/env bash
#
# Measure a board: check the bench, hold the host awake, run tools/probe.py.
#
# The inhibitor is not decoration.  A suspended host -- a closed lid, a switched
# user session, an idle suspend -- drops the console reader's device and the run
# leaves no score behind, while the board's own state line says the clock was fine
# and the program counter sits in the timer.  That combination was once read as "the
# board hung at 420 MHz".  It was the machine.
#
# Options are tools/probe.py's; this adds nothing but the two things above.  It
# runs from the repository root whatever directory you call it from, so the output
# (probe-<board>-<stamp>, which holds a whole cmake build tree) lands in a place
# that is already gitignored rather than in whatever directory you happened to be
# in.  Pass --out to put it somewhere else.

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

root="$(python3 "$here/preflight.py" --print-root)" || {
    echo "cannot find the coremark checkout: set COREMARK_DIR" >&2
    exit 2
}
py="$(python3 "$here/preflight.py" --print-python)" || {
    echo "no interpreter here can import pyusb: pip install pyusb, or use .venv" >&2
    exit 2
}

# Hard failures stop here; warnings do not.  A missing tool or a second probe.py
# sharing the board costs a build, an erase and a flash to discover, and produces
# evidence that describes neither run -- while "no board visible on USB" is worth
# knowing and no reason to refuse.
python3 "$here/preflight.py" || { echo "stopped before touching the board."; exit 2; }

inhibit=()
if command -v systemd-inhibit >/dev/null 2>&1; then
    inhibit=(systemd-inhibit --what=sleep:idle:handle-lid-switch --mode=block
             --why="CoreMark probe run: a suspended host leaves no score behind")
fi

echo "== $py $root/tools/probe.py $*"
cd "$root"
exec "${inhibit[@]}" "$py" tools/probe.py "$@"
