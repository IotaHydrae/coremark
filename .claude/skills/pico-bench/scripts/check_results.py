#!/usr/bin/env python3
"""Do the points in a results.json actually satisfy the evidence bar?

tools/probe.py applies the bar as it records each point, and writes its verdict
into the record.  This re-derives the verdict from the record -- and, where the
console log is still there, from the raw text as well -- without trusting the
verdict that was written next to it.  A report is the summary; the log is the
evidence, and the two agreeing is the point.

The questions it answers that report.md does not:

  * is every point recorded as "ok" actually backed by all five checks?
  * did a soak's own counter -- COREMARK-REPEAT: run N of M -- reach M?  The
    reader's line count is not the measure.  It once read 2 where the counter read
    3, and nearly had a run called short for the reader's sake.
  * does the record still match the log it came from, or was one of them edited,
    truncated, or written by an older version of the tool?

    check_results.py probe-pico2-20260928-142342/
    check_results.py probe-*/results.json

Exit status is 0 only if every point that claims to have passed is backed by
evidence, and every record agrees with its log.
"""

import argparse
import glob
import json
import os
import re
import sys

# Recovered from the console text, by the same patterns tools/probe.py uses --
# spelled out again rather than imported, so that a change in the tool shows up
# here as a disagreement instead of quietly moving both sides together.
RE_SCORE = re.compile(r"CoreMark 1\.0 : ([\d.]+)")
RE_STATE = re.compile(r"PICO-TURBO: (\d+) kHz asked, (\d+) kHz configured, "
                      r"(\d+) kHz measured, vreg sel (\d+), flash (\d+) kHz")
RE_COUNTER = re.compile(r"COREMARK-REPEAT: run (\d+) of \d+")


def clock_landed(rec):
    """The rule from tools/probe.py: the state line reports the clock measured with
    the hardware counter, and it does not have to match to the last hertz -- but a
    point that did not move the clock is not a result about stability."""
    asked, measured = rec.get("asked"), rec.get("measured")
    if not asked or not measured:
        return False
    return abs(measured - asked) <= max(1000, asked // 1000)


def evidence(rec):
    """The bar, computed from the record alone: the five checks probe.py applies to
    every point, plus the three that only a repeated run has."""
    checks = {
        "flash verified": rec.get("readback") == 0,
        "a score": bool(rec.get("scores")),
        "validated": (rec.get("validated") or 0) > 0,
        "no errors": rec.get("errors") == 0,
        "clock landed": clock_landed(rec),
    }
    runs = rec.get("rep") or 1
    if runs > 1:
        counter = rec.get("counter") or []
        checks["every run scored"] = len(rec.get("scores") or []) == runs
        checks["counter reached M"] = bool(counter) and counter[-1] == runs
        checks["every run validated"] = (rec.get("validated") or 0) >= runs
    return checks


def from_log(text):
    """What the console actually said, if it is still on disk."""
    state = RE_STATE.search(text)
    return {
        "scores": [float(v) for v in RE_SCORE.findall(text)],
        "validated": text.count("Correct operation validated"),
        "errors": text.count("Errors detected"),
        "counter": [int(v) for v in RE_COUNTER.findall(text)],
        "asked": int(state.group(1)) if state else None,
        "measured": int(state.group(3)) if state else None,
    }


def log_disagreements(rec, said):
    """Where the record and the log part company."""
    out = []
    for key in ("validated", "errors"):
        if rec.get(key) != said[key]:
            out.append("%s: record %s, log %s" % (key, rec.get(key), said[key]))
    if [round(s, 6) for s in (rec.get("scores") or [])] != \
       [round(s, 6) for s in said["scores"]]:
        out.append("scores: record %s, log %s"
                   % (rec.get("scores") or "none", said["scores"] or "none"))
    if (rec.get("counter") or []) != said["counter"]:
        out.append("counter: record %s, log %s"
                   % (rec.get("counter") or "none", said["counter"] or "none"))
    if said["measured"] and rec.get("measured") != said["measured"]:
        out.append("measured clock: record %s, log %s"
                   % (rec.get("measured"), said["measured"]))
    return out


def load(path):
    """A probe directory, or a results.json.  Both file layouts are supported: the
    older one is a bare mapping of points, the newer one carries the command line
    that produced them."""
    if os.path.isdir(path):
        path = os.path.join(path, "results.json")
    if not os.path.exists(path):
        return None, None, None
    raw = json.load(open(path))
    if isinstance(raw, dict) and "results" in raw:
        return path, (raw.get("results") or {}), raw.get("command")
    return path, (raw or {}), None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("target", help="a probe output directory, or a results.json")
    args = ap.parse_args()

    targets = sorted(glob.glob(args.target)) or [args.target]
    worst = 0
    for target in targets:
        path, results, command = load(target)
        if results is None:
            print("%s: no results.json there" % target)
            worst = max(worst, 2)
            continue

        print("== %s" % path)
        if command:
            print("   $ %s" % command)
        print("   every point is re-judged below from its own record; the verdict\n"
              "   the tool stored is on the right, to be compared rather than used\n")

        header = ("point", "read-back", "score", "valid", "err", "clock",
                  "counter", "evidence", "stored")
        rows = []
        bad = 0
        for key in sorted(results):
            rec = results[key]
            checks = evidence(rec)
            passed = all(checks.values())
            stored = rec.get("result")
            failed = [n for n, ok in checks.items() if not ok]

            agree = (stored == "ok") == passed
            if not agree or (stored == "ok" and not passed):
                bad += 1

            rb = rec.get("readback")
            rows.append((
                key,
                "no read-back" if rb is None else "%d B differ" % rb,
                "%d" % len(rec.get("scores") or []),
                "%s" % (rec.get("validated") if rec.get("validated") is not None else "-"),
                "%s" % (rec.get("errors") if rec.get("errors") is not None else "-"),
                "%d kHz" % rec["measured"] if rec.get("measured") else "-",
                "%s" % (rec.get("counter") or ["-"])[-1],
                "ok" if passed else "NO (" + ", ".join(failed) + ")",
                ("%s" % stored) + ("" if agree else "  <-- disagrees"),
            ))

        if rows:
            widths = [max(len(str(r[i])) for r in rows + [header]) for i in range(len(header))]
            line = lambda r: "  ".join(str(c).ljust(widths[i]) for i, c in enumerate(r))
            print(line(header))
            print("  ".join("-" * w for w in widths))
            for r in rows:
                print(line(r))
        else:
            print("   (no points recorded)")

        # The log is the primary source; the record is a summary of it.
        logs_dir = os.path.join(os.path.dirname(path), "logs")
        missing, disagreed = 0, 0
        for key in sorted(results):
            log = os.path.join(logs_dir, "console-%s.log" % key.replace("/", "-"))
            if not os.path.exists(log):
                missing += 1
                continue
            said = from_log(open(log, errors="replace").read())
            diffs = log_disagreements(results[key], said)
            if diffs:
                disagreed += 1
                print("\n   %s does not match its log %s:" % (key, log))
                for d in diffs:
                    print("     - %s" % d)

        print()
        if bad:
            print("   %d point(s) whose evidence and verdict do not agree -- treat "
                  "those as observations, not results." % bad)
        if disagreed:
            print("   %d record(s) disagree with their console log." % disagreed)
        if missing:
            print("   %d point(s) have no console log left to check against."
                  % missing)
        if not bad and not disagreed:
            print("   every recorded verdict is backed by its evidence.")
        worst = max(worst, 1 if (bad or disagreed) else 0)

    return worst


if __name__ == "__main__":
    sys.exit(main())
