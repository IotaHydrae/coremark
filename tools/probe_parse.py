#!/usr/bin/env python3
"""Parse and judge the CoreMark console, with no hardware and no side effects.

`tools/probe.py` measures: it builds, flashes, reads the flash back, runs, and
collects console text.  This module is the other half -- everything that turns
that text and those records into a structured observation and a verdict.  It
touches no device, needs no `pico-sdk`, and every function is deterministic, so
the rules the bench judges by can be tested offline (`tests/`).

What lives here, and where each rule comes from:

* **The state line** -- `parse_state_line`.  The format is the one
  `rpi-pico/core_portme.c` (`portable_init`) prints: asked / configured /
  hardware-counter measured clock, vreg select, flash and clk_peri clocks, and
  whether USB came up at 48 MHz.
* **The score and the repeat banner** -- `parse_console`.  `CoreMark benchmark
  running` is printed once per boot (before the timed region); `CoreMark 1.0 :`
  once per finished run; `COREMARK-REPEAT: run N of M` once per finished run and
  `all M runs finished` once at the end (`portable_fini`).
* **`Errors detected` is not a data error** -- `parse_console()["item_errors"]`.
  CoreMark prints `[i]ERROR! <part> crc ...` when a CRC disagrees and prints
  `Errors detected` for *any* nonzero error count, including simply running for
  less than ten seconds (`core_main.c`, upstream README run rule 1).
* **The soak counter** -- `soak_count` / `soak_diagnosis`.  The counter is the
  port's: watchdog scratch slot 6 holds the magic `0x636d726b` and slot 7 the
  count (`rpi-pico/core_portme.c`, `CORE_REPEAT_MAGIC`).  Slot 4 belongs to the
  SDK and reading it returns a clean zero, which is why the magic is checked
  first.  Slot 0 starts at watchdog + 0x0C on both families.
* **The point verdict** -- `point_checks` / `point_result`.  The five checks are
  the evidence bar in `AGENTS.md`: flash read-back byte-for-byte, a score,
  `Correct operation validated`, no CoreMark errors, and the clock measured
  landing where it was asked.
* **The results file** -- `load_results` / `dump_results`.  Two layouts exist:
  an older bare mapping of point keys to records, and the current
  `{"command": ..., "results": {...}}` wrapper.  Both are read; the wrapper is
  written, with a `schema` tag so a reader can tell which version wrote it.

The score is never an input to a verdict here.  A point passes on its checks and
its record; a soak passes on the counter the *application* printed, not on the
lines a reader happened to catch.

    # offline, no board:
    python3 -m unittest discover -s tests -v
"""

import json
import os
import re

__all__ = [
    "REPEAT_MAGIC", "WATCHDOG_BASE", "SCRATCH_OFFSET", "MAGIC_SLOT", "COUNT_SLOT",
    "RESULTS_SCHEMA", "SCORE_LINE_PREFIX", "BANNER_TEXT", "KNOWN_CRC_PERFORMANCE_2K",
    "UsageError", "scratch_magic_addr", "scratch_count_addr", "parse_state_line",
    "clock_landed", "parse_console", "item_errors", "crc_values", "parse_chip_state",
    "point_checks", "point_result", "soak_count", "soak_diagnosis", "load_results",
    "dump_results", "vreg_table", "vreg_macro_of", "vreg_sel_of",
    "cflags_release", "cflags_tag", "parse_points", "toolchain_taken",
    "pll_reachable",
]

# ---------------------------------------------------------------------------
# Constants that are contracts, not choices
# ---------------------------------------------------------------------------

#: Written by `rpi-pico/core_portme.c` (`CORE_REPEAT_MAGIC`, "cmrk") into
#: watchdog scratch slot 6 before slot 7 is trusted as a run counter.
REPEAT_MAGIC = 0x636D726B

#: Watchdog base, per family.  Both families put scratch slot 0 at +0x0C.
WATCHDOG_BASE = {"rp2040": 0x40058000, "rp2350": 0x400D8000}

SCRATCH_OFFSET = 0x0C
MAGIC_SLOT = 6          # slot 6: CORE_REPEAT_MAGIC_IDX
COUNT_SLOT = 7          # slot 7: CORE_REPEAT_COUNT_IDX

#: Schema tag written into `results.json`.  `probe.py` 1.x wrote a bare mapping
#: and `2.x` writes this wrapper; `load_results` reads both.
RESULTS_SCHEMA = "coremark-probe/results/1"

#: The two console strings the record pairs up.  The banner is printed once per
#: boot, before the timed region; a score line once per finished run.
BANNER_TEXT = "CoreMark benchmark running"
SCORE_LINE_PREFIX = "CoreMark 1.0 :"


class UsageError(Exception):
    """A value on the command line cannot be honoured (workspace exit 2)."""


# The state line, as `portable_init` prints it.  The trailing `clk_peri`/`usb`
# fields were added after the first probe runs, so they are optional here and
# the older lines still parse -- but `usb_ok` is then None rather than False.
RE_STATE = re.compile(
    r"PICO-TURBO: (\d+) kHz asked, (\d+) kHz configured, (\d+) kHz measured, "
    r"vreg sel (\d+), flash (\d+) kHz"
    r"(?:, clk_peri (\d+) kHz, usb (ok|WRONG))?")

RE_SCORE = re.compile(re.escape(SCORE_LINE_PREFIX) + r" ([\d.]+)")
RE_COUNTER = re.compile(r"COREMARK-REPEAT: run (\d+) of \d+")
RE_ALL_FINISHED = re.compile(r"COREMARK-REPEAT: all (\d+) runs finished")
RE_ITERATIONS = re.compile(r"Iterations\s*: (\d+)")

#: CoreMark's own known-good CRCs for the 2K performance run (seeds 0,0,0x66,
#: `seedcrc` 0xe9f5, `known_id` 3).  `core_main.c` `*_known_crc[]`; the log
#: format is upstream README's.  These are the benchmark's constants, not a
#: reading from any board here.
KNOWN_CRC_PERFORMANCE_2K = {"seedcrc": 0xE9F5, "crclist": 0xE714,
                            "crcmatrix": 0x1FD7, "crcstate": 0x8E3A}

#: `[<ctx>]<part> : 0x....` validation lines from `core_main.c`.
RE_CRC_LINE = re.compile(r"\[(\d+)\](crclist|crcmatrix|crcstate|crcfinal)\s*:\s*0x([0-9a-fA-F]+)")
RE_SEEDCRC = re.compile(r"seedcrc\s*:\s*0x([0-9a-fA-F]+)")

#: openocd's `mdw` prints `0x<addr>: <word> <word>` (little-endian hex words),
#: `reg pc` prints `pc (/32): 0x...`, and the CFSR is read the same way as the
#: scratch.  Parsed here so the debugger's reading is testable without a probe.
RE_SCRATCH = re.compile(r"SCRATCH:\s*\n0x[0-9a-f]+:\s*([0-9a-f]+) ([0-9a-f]+)")
RE_PC = re.compile(r"pc \(/32\): (0x[0-9a-fA-F]+)")
RE_CFSR = re.compile(r"CFSR:\s*\n0x[0-9a-f]+:\s*([0-9a-f]+)")

#: `core_main.c`: `[<ctx>]ERROR! <part> crc 0x.... - should be 0x....`.
RE_ITEM_ERROR = re.compile(r"\[\d+\]ERROR! .*crc .* - should be .*")

#: `core_main.c`: printed whenever the timed region came out under ten seconds.
SHORT_RUN_TEXT = "ERROR! Must execute for at least 10 secs for a valid result!"
VALIDATED_TEXT = "Correct operation validated"
ERRORS_TEXT = "Errors detected"
CANNOT_VALIDATE_TEXT = "Cannot validate operation for these seed values"

#: `hardware_vreg.h` assigns the select value as a binary literal; parsing the
#: header beats a hand-typed table (a first probe version had 1.60 V as sel 20,
#: which would have written 1.50 V into a 564 MHz board file).
RE_VREG = re.compile(r"(VREG_VOLTAGE_[0-9_]+)\s*=\s*0b([01]+)")

#: Fallback if the SDK header cannot be read: the same numbering, which both
#: platforms share up to 1.30 V, with the RP2350's extra steps above it.
VREG_NAME_FALLBACK = {5: "VREG_VOLTAGE_0_80", 6: "VREG_VOLTAGE_0_85",
                      7: "VREG_VOLTAGE_0_90", 8: "VREG_VOLTAGE_0_95",
                      9: "VREG_VOLTAGE_1_00", 10: "VREG_VOLTAGE_1_05",
                      11: "VREG_VOLTAGE_1_10", 12: "VREG_VOLTAGE_1_15",
                      13: "VREG_VOLTAGE_1_20", 14: "VREG_VOLTAGE_1_25",
                      15: "VREG_VOLTAGE_1_30", 16: "VREG_VOLTAGE_1_35",
                      17: "VREG_VOLTAGE_1_40", 18: "VREG_VOLTAGE_1_50",
                      19: "VREG_VOLTAGE_1_60", 20: "VREG_VOLTAGE_1_65",
                      21: "VREG_VOLTAGE_1_70"}


# ---------------------------------------------------------------------------
# Hardware addresses the debugger reads
# ---------------------------------------------------------------------------

def scratch_magic_addr(family):
    """Watchdog scratch slot 6 -- the run counter's magic -- for a family."""
    return WATCHDOG_BASE[family] + SCRATCH_OFFSET + 4 * MAGIC_SLOT


def scratch_count_addr(family):
    """Watchdog scratch slot 7 -- the run count -- for a family."""
    return WATCHDOG_BASE[family] + SCRATCH_OFFSET + 4 * COUNT_SLOT


# ---------------------------------------------------------------------------
# Console parsing
# ---------------------------------------------------------------------------

def parse_state_line(text):
    """The `PICO-TURBO:` line, as a dict, or None if the run never printed one.

    Keys: asked, configured, measured (kHz), vreg_sel, flash_khz, clk_peri_khz
    and usb_ok (True for `usb ok`, False for `usb WRONG`, None when the older
    line without those fields is what was captured).
    """
    m = RE_STATE.search(text)
    if not m:
        return None
    st = {"asked": int(m.group(1)), "configured": int(m.group(2)),
          "measured": int(m.group(3)), "vreg_sel": int(m.group(4)),
          "flash_khz": int(m.group(5))}
    if m.group(6) is not None:
        st["clk_peri_khz"] = int(m.group(6))
        st["usb_ok"] = m.group(7) == "ok"
    else:
        st["clk_peri_khz"] = None
        st["usb_ok"] = None
    return st


def clock_landed(asked, measured):
    """Did the hardware counter's clock land where the clock was asked?

    The rule `probe.py` has always applied: it does not have to match to the
    last hertz -- one part in a thousand, or 1 kHz for a slow clock, whichever
    is larger -- but a point whose clock did not move is not a result about
    stability (the SDK silently leaves the clock alone at a PLL-unreachable
    frequency, and it then reads as instability).
    """
    if not asked or not measured:
        return False
    return abs(measured - asked) <= max(1000, asked // 1000)


def item_errors(text):
    """The per-part CRC disagreement lines (`[i]ERROR! ... crc ...`).

    These, and not the bare words `Errors detected`, are what a data error
    looks like.  `Errors detected` is also CoreMark's answer to a run shorter
    than its own ten second rule.
    """
    return RE_ITEM_ERROR.findall(text)


def parse_console(text):
    """Everything the probe records from one console log.

    Returns a dict with `scores`, `validated`, `errors`, `banners`, `counter`,
    `iterations`, `item_errors`, `short_run`, `cannot_validate`,
    `all_finished` and `state` (see `parse_state_line`).
    """
    state = parse_state_line(text)
    counter = [int(v) for v in RE_COUNTER.findall(text)]
    finished = RE_ALL_FINISHED.search(text)
    return {
        "scores": [float(v) for v in RE_SCORE.findall(text)],
        "validated": text.count(VALIDATED_TEXT),
        "errors": text.count(ERRORS_TEXT),
        "banners": text.count(BANNER_TEXT),
        "counter": counter,
        "iterations": [int(v) for v in RE_ITERATIONS.findall(text)],
        "item_errors": item_errors(text),
        "short_run": SHORT_RUN_TEXT in text,
        "cannot_validate": CANNOT_VALIDATE_TEXT in text,
        "all_finished": int(finished.group(1)) if finished else None,
        "state": state,
    }


def crc_values(text):
    """The `[<ctx>]<part> : 0x....` validation lines, and `seedcrc`.

    Returns `{"seedcrc": int|None, "crc": {(ctx, part): int}}`.  A part that
    did not execute has no line; that is not the same as a mismatch, which is
    what `item_errors` names.
    """
    crc = {}
    for ctx, part, value in RE_CRC_LINE.findall(text):
        crc[(int(ctx), part)] = int(value, 16)
    seed = RE_SEEDCRC.search(text)
    return {"seedcrc": int(seed.group(1), 16) if seed else None, "crc": crc}


def parse_chip_state(text):
    """The debugger's reading of a board that never reported: scratch, PC, CFSR.

    `text` is an openocd session's output for the commands `probe.py` runs
    (`mdw <scratch> 2`, `reg pc`, `mdw 0xe000ed28 1`).  Only what is present is
    returned, so `"pc" in state` says whether the debugger answered at all --
    which is what separates "no reading" from "a reading that says nothing".
    """
    state = {}
    m = RE_SCRATCH.search(text)
    if m:
        state["repeat_magic"] = int(m.group(1), 16)
        state["repeat_count"] = int(m.group(2), 16)
    m = RE_PC.search(text)
    if m:
        state["pc"] = m.group(1)
    m = RE_CFSR.search(text)
    if m:
        state["cfsr"] = m.group(1)
    return state


# ---------------------------------------------------------------------------
# The evidence bar, and a point's verdict
# ---------------------------------------------------------------------------

def point_checks(rec):
    """The five checks `AGENTS.md` asks of every point, as a dict.

    Keys are stable because they are written into `results.json` and printed in
    the report: flash verified / a score / validated / no CoreMark errors /
    clock landed where asked.  `rec` may be a record from a results file or a
    freshly parsed observation; `readback` is the number of differing bytes.
    """
    return {
        "flash verified": rec.get("readback") == 0,
        "a score": bool(rec.get("scores")),
        "validated": (rec.get("validated") or 0) > 0,
        "no CoreMark errors": rec.get("errors") == 0,
        "clock landed where asked": clock_landed(rec.get("asked"), rec.get("measured")),
    }


def point_result(rec, pc=None):
    """The stored verdict for a point: `ok`, `failed: ...`, `hang`, `no output`.

    `pc` is the program counter read over SWD when a point produced no score;
    a hang is a fact about the chip and is recorded as one rather than as a low
    score.  This reproduces `probe.py`'s classification exactly.
    """
    checks = point_checks(rec)
    if not rec.get("scores"):
        return "hang" if pc else "no output"
    if not all(checks.values()):
        return "failed: " + ", ".join(n for n, ok in checks.items() if not ok)
    return "ok"


# ---------------------------------------------------------------------------
# Soak counting and diagnosis
# ---------------------------------------------------------------------------

def soak_count(chip_state):
    """The run counter from a `chip_state` reading, or None.

    Slot 6 must hold `REPEAT_MAGIC` first: a run counter read out of a slot
    nobody wrote (slot 4 is the SDK's) is a clean zero, and concluding anything
    from it is worse than concluding nothing.
    """
    if not chip_state:
        return None
    if chip_state.get("repeat_magic") != REPEAT_MAGIC:
        return None
    return chip_state.get("repeat_count")


def soak_diagnosis(done, rep, banners, chip_state):
    """Why a soak reported fewer runs than it was asked for.

    `done` is the number of scores the reader caught, `banners` the number of
    `CoreMark benchmark running` lines, and `chip_state` the debugger's reading
    (repeat_magic / repeat_count / pc / symbol / cfsr).  The application counts
    *finished* runs in scratch and in its `run N of M` line, so the counter
    alone cannot separate "the next run never started" from "it started and
    stopped inside itself" -- the banner can, because it is printed before the
    timed region.  Returns the human-readable verdict the report carries.
    """
    chip_state = chip_state or {}
    n = soak_count(chip_state)
    if "pc" not in chip_state:
        return "no reading from the debugger"
    if n is None:
        verdict = ("no run counter in the scratch (the magic is gone) with %d runs "
                   "reported: the application never finished a run since its last "
                   "complete soak" % done)
    elif n >= rep:
        verdict = ("the counter reached %d of %d with %d runs reported: the runs "
                   "happened and the missing output was lost on the host side"
                   % (n, rep, done))
    elif banners > done:
        verdict = ("the counter is %d with %d runs reported and %d banners: run %d "
                   "started and stopped inside itself" % (n, done, banners, done + 1))
    else:
        verdict = ("the counter is %d with %d runs reported and no banner for run %d: "
                   "it never started, so the board did not come up on that boot"
                   % (n, done, done + 1))
    if n is not None and n != done:
        verdict += (" (the counter and the score count should agree; they do not -- "
                    "read both before trusting either)")
    if chip_state.get("pc"):
        verdict += "; program counter %s %s" % (chip_state["pc"],
                                                chip_state.get("symbol") or "")
    if chip_state.get("cfsr") and chip_state["cfsr"] != "00000000":
        verdict += "; CFSR 0x%s" % chip_state["cfsr"]
    return verdict


# ---------------------------------------------------------------------------
# The results file
# ---------------------------------------------------------------------------

def load_results(raw):
    """Normalise a parsed `results.json` into `(results, command)`.

    Two layouts are in the wild and both are supported: the older bare mapping
    of point keys to records (command None), and the wrapper written since,
    `{"schema": ..., "command": ..., "results": {...}}`.
    """
    if isinstance(raw, dict) and "results" in raw:
        return (raw.get("results") or {}), raw.get("command")
    return (raw or {}), None


def dump_results(results, command):
    """The object to write to `results.json` (the current layout)."""
    return {"schema": RESULTS_SCHEMA, "command": command, "results": results}


# ---------------------------------------------------------------------------
# Build options that are contracts
# ---------------------------------------------------------------------------

def vreg_table(sdk):
    """sel -> macro name, read out of the SDK's `hardware/vreg.h`.

    A generated board file names the voltage it wants as a macro, so a wrong
    entry here produces a file asking for the wrong voltage -- and the two
    platforms do not share a shape.  Parsing the header removes that class of
    hand-typed error; the caller falls back to `VREG_NAME_FALLBACK`.
    """
    path = os.path.join(sdk, "src/rp2_common/hardware_vreg/include/hardware/vreg.h")
    table = {}
    try:
        with open(path) as fh:
            for name, bits in RE_VREG.findall(fh.read()):
                table[int(bits, 2)] = name
    except OSError:
        return {}
    return table


def _sel_by_name(table):
    return {name: sel for sel, name in table.items()}


def vreg_sel_of(table, name):
    """The select value behind a macro name, from the table."""
    return _sel_by_name(table).get(name)


def vreg_macro_of(table, value):
    """`--vreg` as an SDK macro name, checked against the SDK's own table.

    Accepts the macro (`VREG_VOLTAGE_1_65`) or the number (`1.65`).  Raises
    `UsageError` for a voltage the SDK does not have, rather than letting a
    board file be generated for a setting that does not exist.
    """
    v = (value or "").strip()
    name = v if v.startswith("VREG_VOLTAGE_") else "VREG_VOLTAGE_%s" % v.replace(".", "_")
    if name not in table.values():
        raise UsageError("--vreg %s: the SDK has no %s (its ladder is %s)"
                         % (value, name, ", ".join(table[k] for k in sorted(table))))
    return name


def cflags_tag(cflags):
    """A filename-safe tag for a flag set, empty for the default set."""
    cf = (cflags or "").strip()
    if not cf:
        return ""
    return re.sub(r"[^A-Za-z0-9._+-]+", "_", cf).strip("_")


def cflags_release(cflags):
    """`CMAKE_C_FLAGS_RELEASE` for a `--cflags` value, or None for the default.

    The default set is CMake's own `-g -O3 -DNDEBUG`; the SDK owns only the
    `-mcpu/-mthumb/-march/-mfloat-abi/-mcmse` flags.  An `-O` in `--cflags`
    replaces the level -- a later `-O` on the command line would win otherwise
    -- and anything else is appended after it.
    """
    cf = (cflags or "").strip()
    if not cf:
        return None
    if not re.search(r"(?:^|\s)-O", cf):
        cf = "-O3 " + cf
    return "-g -DNDEBUG %s" % cf


def parse_points(spec):
    """`--points 240000,300,520000` -> kHz values (a value <= 10000 is MHz)."""
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            v = int(part)
        except ValueError:
            raise UsageError("--points %s: %r is not a number" % (spec, part))
        if v <= 0:
            raise UsageError("--points %s: a clock must be positive" % spec)
        out.append(v if v > 10000 else v * 1000)
    if not out:
        raise UsageError("--points %s: no values" % spec)
    return out


def toolchain_taken(prefix, compiler_path):
    """Was the build's compiler actually inside the prefix that was asked for?

    The SDK searches `PICO_TOOLCHAIN_PATH` first and falls back to the compiler
    on `PATH` with nothing but a warning, so a ladder that trusts the variable
    can measure one compiler six times and print a flat line.  The property
    that must hold is "the compiler is inside the prefix", not "it is exactly
    `arm-none-eabi-gcc`": an LLVM ET tarball carries that driver too and the
    SDK picks `clang` from the same prefix.
    """
    if not prefix or not compiler_path:
        return False
    root = os.path.realpath(prefix)
    return os.path.realpath(compiler_path).startswith(root + os.sep)


# ---------------------------------------------------------------------------
# Clock arithmetic
# ---------------------------------------------------------------------------

def pll_reachable(khz):
    """Can a 12 MHz XOSC PLL land on this exactly?

    The SDK silently leaves the clock alone at a frequency it cannot produce,
    which then looks like instability rather than like a point that was never
    tried.  Returns `(fbdiv, vco, p1, p2)` or None.
    """
    for fbdiv in range(16, 321):
        vco = 12000 * fbdiv
        if not 750000 <= vco <= 1600000:
            continue
        for p1 in range(1, 8):
            for p2 in range(1, 8):
                if vco % (p1 * p2) == 0 and vco // (p1 * p2) == khz:
                    return fbdiv, vco, p1, p2
    return None
