#!/usr/bin/env python3
"""Is this bench ready to produce a result worth keeping?

Every check here is something that has quietly ruined a run in this repository: a
missing tool that only bites twenty minutes in, a second probe.py fighting for the
board, a host that is about to suspend, a python without pyusb.  None of them look
like a failure at the time -- they look like a board that stopped working at the
frequency under test, which is the most expensive kind of wrong answer this bench
can give.

Nothing here touches SWD, so it is safe to run at any time, including next to a
run that is already going.  The chip is identified by tools/probe.py --identify-only,
which is a different command and does touch the probe.

    preflight.py                 check, and say what is wrong
    preflight.py --json          the same, as data
    preflight.py --print-root    just print where the coremark checkout is
    preflight.py --print-python  just print the interpreter probe.py should use

Exit status is 2 if anything would stop a run, 0 otherwise; warnings do not fail.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

FAIL, WARN, OK = "FAIL", "warn", "ok"

# pico-turbo's own vocabulary for what a Pico's USB looks like, from the VID/PID
# pairs tools/probe.py matches on.
PICO_VID = 0x2E8A
BY_PID = {
    0x0003: "RP2040 bootrom (BOOTSEL)",
    0x000F: "RP2350 bootrom (BOOTSEL)",
    0x0009: "an application's stdio CDC (RP2350)",
    0x000A: "an application's stdio CDC (RP2040)",
}


def find_root():
    """Where the coremark checkout is.  It is deliberately not written down: this
    skill is meant to be copyable to ~/.claude/skills, so the checkout is looked for
    under COREMARK_DIR, then up from the working directory, then up from this file,
    then in a sibling directory called coremark."""
    candidates = []

    def add(path):
        if path:
            candidates.append(os.path.abspath(path))

    add(os.environ.get("COREMARK_DIR"))
    here = os.path.dirname(os.path.abspath(__file__))
    for start in (os.getcwd(), here):
        d = start
        while True:
            add(d)
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    # Installed at ~/.claude/skills, the walk up from here finds nothing; the
    # sibling guess is for being run from the library's own checkout, where the
    # bench is coremark/ next door.
    add(os.path.join(os.getcwd(), os.pardir, "coremark"))

    for path in candidates:
        if os.path.exists(os.path.join(path, "tools", "probe.py")):
            return path
    return None


def can_import(python, module):
    if not python or not os.path.exists(python):
        return False
    try:
        return subprocess.run([python, "-c", "import %s" % module],
                              timeout=60,
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def find_python(root):
    """probe.py's console reader imports pyusb, and pyusb does not have to be in
    the python on PATH -- in this checkout it is in .venv and nowhere else, where
    `python3 tools/probe.py` dies on the import.  probe.py starts its reader with
    sys.executable, so the interpreter chosen here is the one both processes get."""
    if not root:
        return None
    for candidate in (os.path.join(root, ".venv", "bin", "python3"),
                      sys.executable,
                      shutil.which("python3")):
        if can_import(candidate, "usb.core"):
            return candidate
    return None


def other_runs():
    """Another probe.py walking a ladder would be erasing the same flash and
    reading the same console as this one; both runs would produce evidence that
    describes neither.

    Two things are not a second run: the console reader, which is a child of a run
    rather than a run, and anything that merely mentions the file -- an editor with
    it open, or the grep someone is using to look for it.  Only a python process
    with probe.py among its arguments counts, which is what a run is."""
    if not shutil.which("pgrep"):
        return []
    try:
        out = subprocess.run(["pgrep", "-af", "probe.py"], timeout=30,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             text=True).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    runs = []
    for line in out.splitlines():
        pid, _, cmd = line.partition(" ")
        argv = cmd.split()
        if not argv or not os.path.basename(argv[0]).startswith("python"):
            continue
        if "--reader" in argv:
            continue
        if not any(os.path.basename(a) == "probe.py" for a in argv):
            continue
        if pid.isdigit() and int(pid) != os.getpid():
            runs.append(line.strip())
    return runs


def boards_on_usb(python):
    """What is on the other end of the cable, if anything.  Not fatal -- probe.py
    reaches the chip over SWD and can blank it whatever it is running -- but a
    board that is not there at all is a run that ends at the first point.

    Asked through probe.py's interpreter rather than this one: pyusb is what the
    reader needs and it is not necessarily in the python that happens to be running
    this script, so importing it here would answer a different question."""
    if not python:
        return None
    # Built by concatenation rather than %-formatting: the snippet has a format
    # specifier of its own, and one % pass would eat it.
    code = ("import usb.core\n"
            "found = usb.core.find(find_all=True, idVendor=" + hex(PICO_VID) + ") or []\n"
            "print(' '.join(hex(d.idProduct) for d in found))\n")
    try:
        out = subprocess.run([python, "-c", code], timeout=60, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return [BY_PID.get(int(pid, 16), "pid %s" % pid)
            for pid in out.stdout.split()]


def collect(root, python):
    out = []

    def check(level, name, detail):
        out.append({"level": level, "name": name, "detail": detail})

    if root:
        check(OK, "coremark checkout", root)
    else:
        check(FAIL, "coremark checkout",
              "tools/probe.py not found: set COREMARK_DIR, or run this from the "
              "checkout (or a directory under it)")

    # probe.py checks the first three itself, but only after it has identified the
    # chip; picotool is used on every point and is not checked anywhere, and
    # addr2line is what turns "it hung" into "it hung in core_stop_parallel".
    for tool, level, why in (
            ("openocd", FAIL, "every point is flashed and read back through it"),
            ("picotool", FAIL, "the write and the reboot go through the bootrom"),
            ("cmake", FAIL, ""),
            ("arm-none-eabi-gcc", FAIL, ""),
            ("arm-none-eabi-addr2line", WARN,
             "a hang would be reported without the symbol it landed in")):
        path = shutil.which(tool)
        if path:
            check(OK, tool, path)
        else:
            check(level, tool, ("not on PATH" + (": " + why if why else "")))

    if python:
        check(OK, "python with pyusb", python)
    elif root:
        check(FAIL, "python with pyusb",
              "no interpreter here can import usb.core (the reader needs it): "
              "pip install pyusb, or use the checkout's .venv")
    else:
        check(FAIL, "python with pyusb", "cannot look for one without a checkout")

    # The two below are warnings rather than failures on purpose: probe.py checks
    # both itself, in its first second, and exits with the same advice -- and either
    # can be supplied on the command line, which is something this script cannot
    # see.  A gate that refuses a run that would have worked is worse than no gate.
    sdk = os.environ.get("PICO_SDK_PATH") or os.path.expanduser("~/.pico-sdk")
    if os.path.exists(os.path.join(sdk, "pico_sdk_init.cmake")):
        check(OK, "pico-sdk", sdk)
    else:
        check(WARN, "pico-sdk",
              "nothing at %s: export PICO_SDK_PATH, or pass --sdk to probe.py "
              "(which is where this is really checked)" % sdk)

    turbo = os.environ.get("PICO_TURBO_DIR") or (
        os.path.join(os.path.dirname(root), "pico-turbo") if root else None)
    if turbo and os.path.exists(os.path.join(turbo, "CMakeLists.txt")):
        check(OK, "pico-turbo", turbo)
    else:
        check(WARN, "pico-turbo",
              "nothing at %s: export PICO_TURBO_DIR, or pass --pico-turbo"
              % (turbo or "<unset>"))

    running = other_runs()
    if running:
        check(FAIL, "no other probe.py running",
              "; ".join(running) + " -- two runs share one board and neither "
              "result describes it")
    else:
        check(OK, "no other probe.py running", "")

    boards = boards_on_usb(python)
    if boards is None:
        check(WARN, "board on USB", "could not tell: pyusb is not importable")
    elif boards:
        check(OK, "board on USB", ", ".join(boards))
    else:
        check(WARN, "board on USB",
              "no 2e8a: device.  Either the board is not plugged in, or it is "
              "running firmware with a VID/PID of its own (a WeAct RP2350A came up "
              "as 1209:0001 that way).  Neither stops a run: what the write path "
              "waits for is the bootrom at 2e8a:000f, which appears once the flash "
              "is blanked whatever the application was")

    if shutil.which("systemd-inhibit"):
        check(OK, "sleep inhibitor", "run_probe.sh will hold sleep, idle and lid")
    else:
        check(WARN, "sleep inhibitor",
              "systemd-inhibit is missing, so a suspend would drop the reader and "
              "the run would leave no score behind -- do not close the lid")

    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true", help="the checks as data")
    ap.add_argument("--print-root", action="store_true",
                    help="print the checkout and nothing else")
    ap.add_argument("--print-python", action="store_true",
                    help="print the interpreter probe.py should run under")
    args = ap.parse_args()

    root = find_root()

    if args.print_root:
        if not root:
            print("cannot find the coremark checkout: set COREMARK_DIR", file=sys.stderr)
            return 2
        print(root)
        return 0
    if args.print_python:
        python = find_python(root)
        if not python:
            print("no interpreter here can import pyusb", file=sys.stderr)
            return 2
        print(python)
        return 0

    checks = collect(root, find_python(root))
    failed = [c for c in checks if c["level"] == FAIL]
    warned = [c for c in checks if c["level"] == WARN]

    if args.json:
        # Only the data, so this can be piped; the verdict is in the document
        # rather than in prose next to it.
        json.dump({"ready": not failed, "failed": len(failed),
                   "warned": len(warned), "checks": checks}, sys.stdout, indent=1)
        print()
        return 2 if failed else 0

    width = max(len(c["name"]) for c in checks)
    for c in checks:
        print("[%-4s] %-*s  %s" % (c["level"], width, c["name"], c["detail"]))

    if failed:
        print("\n%d check(s) would stop a run.  Fix them first: a run that dies at "
              "the first point costs the build, the erase and the flash." % len(failed))
        return 2
    if warned:
        print("\nReady, with %d thing(s) worth knowing about above." % len(warned))
        return 0
    print("\nReady.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
