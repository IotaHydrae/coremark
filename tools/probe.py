#!/usr/bin/env python3
"""Tell me everything about the Pico on my desk, with one command.

Attach a debug probe, put the board in BOOTSEL, run this, and it measures the
board the way this repository's notes were written: a clock ladder, a flash
divider ladder, a dual-core point and a soak -- each point built, written, read
back, compared byte for byte, run, and kept only if the application validated its
own result and the state line it prints shows the clock the chip measured itself
at being the clock that was asked for.

    tools/probe.py --board pico_w
    tools/probe.py --board pico2 --soak 30 --flash-ladder
    tools/probe.py --identify-only
    tools/probe.py --points 240000,300000,420000 --soak 0

It writes, into the output directory (default ./probe-<board>-<stamp>):

    report.md               what was measured, in the shape the notes use
    results.json            every point, so an interrupted run resumes where it stopped
    known-good.elf          the last image that passed, used to put the board back
    logs/                   every build, flash and console log
    boards/<board>.cmake    a pico-turbo board file built from the measurements

What it will not do is guess.  A point that produces no console output is read
with the debugger -- program counter, and the symbol it lands in -- and recorded
as a hang rather than as a low score; a point whose flash did not match the build
is thrown away rather than interpreted; the walk stops at the first such point;
and the board is put back to the last known-good image before anything else runs.

Requires: openocd, picotool, arm-none-eabi-gcc, the pico-sdk, pyusb, and a
pico-turbo checkout (which the rpi-pico CoreMark port needs anyway).

Do not suspend the host while this runs.  A suspended machine drops the console
reader's device and the run leaves no score behind, which looks exactly like a
board that hung at the frequency under test -- measured, and mistaken for one.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
COREMARK_ROOT = os.path.dirname(HERE)

PICO_VID = 0x2E8A
APP_PIDS = (0x0009, 0x000A)          # stdio CDC on RP2350 / RP2040
BOOTSEL_PIDS = (0x0003, 0x000F)      # RP2040 / RP2350 bootrom
DPIDR = {0x0BC12477: "rp2040", 0x4C013477: "rp2350"}

# The stock clock, the platform's own ceiling, and the boot stage 2 divider the
# SDK uses by default, per family.
PLATFORM = {
    "rp2040": {"stock": 125000, "ceiling": 420000, "boot2_div": 2,
               "ladder": [240000, 300000, 360000, 396000, 420000, 440000]},
    "rp2350": {"stock": 150000, "ceiling": 600000, "boot2_div": 4,
               "ladder": [300000, 400000, 500000, 520000, 546000, 564000, 570000, 600000]},
}

def vreg_table(sdk):
    """sel -> macro name, read out of the SDK instead of typed in here.

    A generated board file names the voltage it wants as a macro, so a wrong entry
    in this table produces a file that asks for the wrong voltage -- and the two
    platforms do not share a shape: the RP2350's ladder has gaps (1.45 and 1.55 do
    not exist, so 1.60 V is sel 19) and it goes higher than the RP2040's.  The
    header is right there in the SDK; parsing it removes the whole class of
    hand-typed error.  The fallback below is the same table, typed correctly.

    (Measured: a first version of this file had 1.60 V as sel 20, which would have
    written VREG_VOLTAGE_1_50 into a board file for a 564 MHz configuration.)"""
    path = os.path.join(sdk, "src/rp2_common/hardware_vreg/include/hardware/vreg.h")
    table = {}
    try:
        with open(path) as fh:
            for name, bits in re.findall(r"(VREG_VOLTAGE_[0-9_]+)\s*=\s*0b([01]+)", fh.read()):
                table[int(bits, 2)] = name
    except OSError:
        return {}
    return table


# Fallback, if the SDK header cannot be read: the same numbering, which both
# platforms share up to 1.30 V, with the RP2350's extra steps above it.
VREG_NAME_FALLBACK = {5: "VREG_VOLTAGE_0_80", 6: "VREG_VOLTAGE_0_85",
                      7: "VREG_VOLTAGE_0_90", 8: "VREG_VOLTAGE_0_95",
                      9: "VREG_VOLTAGE_1_00", 10: "VREG_VOLTAGE_1_05",
                      11: "VREG_VOLTAGE_1_10", 12: "VREG_VOLTAGE_1_15",
                      13: "VREG_VOLTAGE_1_20", 14: "VREG_VOLTAGE_1_25",
                      15: "VREG_VOLTAGE_1_30", 16: "VREG_VOLTAGE_1_35",
                      17: "VREG_VOLTAGE_1_40", 18: "VREG_VOLTAGE_1_50",
                      19: "VREG_VOLTAGE_1_60", 20: "VREG_VOLTAGE_1_65",
                      21: "VREG_VOLTAGE_1_70"}


def log(msg=""):
    print(msg, flush=True)


def have(tool):
    return shutil.which(tool) is not None


def run(cmd, timeout=600, log_path=None, env=None):
    """Run a command, keep its output, and never let it hang the probe."""
    if log_path:
        with open(log_path, "w") as fh:
            try:
                proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                                      timeout=timeout, env=env)
            except subprocess.TimeoutExpired:
                return 124, "timed out after %ss" % timeout
            except FileNotFoundError:
                return 127, "%s: not found" % cmd[0]
        return proc.returncode, open(log_path).read()
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=timeout, text=True, env=env)
    except subprocess.TimeoutExpired as exc:
        return 124, (exc.stdout or "") + "\n[timed out after %ss]" % timeout
    except FileNotFoundError:
        return 127, "%s: not found" % cmd[0]
    return proc.returncode, proc.stdout


def pll_reachable(khz):
    """Can a 12 MHz XOSC PLL land on this exactly?  The SDK silently leaves the
    clock alone at a frequency it cannot produce, which then looks like
    instability rather than like a point that was never tried."""
    for fbdiv in range(16, 321):
        vco = 12000 * fbdiv
        if not 750000 <= vco <= 1600000:
            continue
        for p1 in range(1, 8):
            for p2 in range(1, 8):
                if vco % (p1 * p2) == 0 and vco // (p1 * p2) == khz:
                    return fbdiv, vco, p1, p2
    return None


def clock_landed(rec):
    """The state line reports the clock measured with the hardware counter.  It
    does not have to be identical to the last hertz, but a point that did not move
    the clock is not a result about stability."""
    asked, measured = rec.get("asked"), rec.get("measured")
    if not asked or not measured:
        return False
    return abs(measured - asked) <= max(1000, asked // 1000)


# --------------------------------------------------------------------------
# The console reader, as its own process: the port has to be held open before the
# application starts, and a reader that shared this process would take the run's
# only evidence down with it if anything else went wrong.
# --------------------------------------------------------------------------

def reader_main(log_path, idle_s, markers):
    import usb.core
    import usb.util

    def find(timeout=30.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            for pid in APP_PIDS:
                dev = usb.core.find(idVendor=PICO_VID, idProduct=pid)
                if dev is not None:
                    return dev
            time.sleep(0.25)
        return None

    def say_hello(dev, cfg, tries=6):
        """Line coding plus DTR, retried.  The SDK treats a host it has not heard
        from as no host at all and discards everything written, so one timeout here
        is an empty log rather than a slow one -- measured, the hard way."""
        ctrl = next((i for i in cfg if i.bInterfaceClass == 0x02), None)
        if ctrl is None:
            return False
        for _ in range(tries):
            try:
                dev.ctrl_transfer(0x21, 0x20, 0, ctrl.bInterfaceNumber,
                                  b"\x00\xc2\x01\x00\x00\x00\x08", timeout=2000)
                dev.ctrl_transfer(0x21, 0x22, 0x0001, ctrl.bInterfaceNumber,
                                  None, timeout=2000)
                return True
            except usb.core.USBError:
                time.sleep(0.3)
        return False

    def attach(dev):
        cfg = dev.get_active_configuration()
        data = next((i for i in cfg if i.bInterfaceClass == 0x0A), None)
        if data is None:
            return None, None
        for intf in cfg:
            try:
                if dev.is_kernel_driver_active(intf.bInterfaceNumber):
                    dev.detach_kernel_driver(intf.bInterfaceNumber)
            except usb.core.USBError:
                pass
        for _ in range(20):
            try:
                for intf in cfg:
                    usb.util.claim_interface(dev, intf.bInterfaceNumber)
                break
            except usb.core.USBError:
                time.sleep(0.5)
        ep = usb.util.find_descriptor(
            data, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
            == usb.util.ENDPOINT_IN and usb.util.endpoint_type(e.bmAttributes)
            == usb.util.ENDPOINT_TYPE_BULK)
        return cfg, ep

    out = open(log_path, "w")

    def note(text):
        out.write(text)
        out.flush()

    dev = find()
    if dev is None:
        note("[reader] no application appeared\n")
        out.close()
        return 2
    cfg, ep = attach(dev)
    if ep is None:
        note("[reader] no bulk endpoint\n")
        out.close()
        return 2
    got_any = say_hello(dev, cfg)
    hello_at = time.time()
    last = time.time()
    while time.time() - last < idle_s:
        try:
            buf = ep.read(64, timeout=500)
        except usb.core.USBError as exc:
            if getattr(exc, "errno", None) == 110 or "timeout" in str(exc).lower():
                # Nothing yet: the handshake may have been missed while the chip
                # was still coming up, and the application only waits so long.
                if not got_any and time.time() - hello_at > 2.0:
                    got_any = say_hello(dev, cfg, tries=1)
                    hello_at = time.time()
                continue
            # The chip reset (a flash, a watchdog reboot, a hang): find it again.
            note("[reader] %s -- re-attaching\n" % exc)
            try:
                usb.util.dispose_resources(dev)
            except Exception:
                pass
            time.sleep(0.5)
            dev = find(30.0)
            if dev is None:
                note("[reader] the application did not come back\n")
                out.close()
                return 2
            cfg, ep = attach(dev)
            if ep is None:
                out.close()
                return 2
            got_any = say_hello(dev, cfg)
            hello_at = time.time()
            last = time.time()
            continue
        if not buf:
            continue
        last = time.time()
        got_any = True
        text = bytes(buf).decode("utf-8", errors="replace")
        note(text)
        if any(m in text for m in markers):
            note("\n[reader] done\n")
            out.close()
            return 0
    note("[reader] idle for %gs, stopping\n" % idle_s)
    out.close()
    return 0


# --------------------------------------------------------------------------
# The debugger: the one path that needs no reset line, no BOOTSEL button and no
# cooperation from the application.
# --------------------------------------------------------------------------

class Debugger:
    def __init__(self, args, logs_dir=None):
        self.interface = args.interface
        self.speed = args.adapter_speed
        self.target = None
        self.family = None
        # Where openocd sessions write their logs.  Passed in rather than derived
        # from the ELF's path: a recovery flashes an ELF that lives somewhere else
        # (known-good.elf at the top of the output directory) and the derivation
        # then pointed outside it entirely.
        self.logs_dir = logs_dir or os.getcwd()

    def ocd(self, cmds, target=None, timeout=180, log_path=None):
        target = target or self.target
        cmd = ["openocd", "-f", self.interface, "-f", "target/%s.cfg" % target,
               "-c", "adapter speed %d" % self.speed]
        for c in cmds:
            cmd += ["-c", c]
        return run(cmd, timeout=timeout, log_path=log_path)

    def identify(self):
        """The SWD DPIDR names the family before a single byte is built.  Both
        target configs are tried because which one matches is the thing being
        discovered."""
        last = ""
        for target in ("rp2040", "rp2350"):
            rc, out = self.ocd(["init", "shutdown"], target=target, timeout=60)
            last = out
            m = re.search(r"SWD DPIDR (0x[0-9a-fA-F]+)", out)
            if not m:
                continue
            family = DPIDR.get(int(m.group(1), 16))
            if family:
                self.target = family
                self.family = family
                # Prefer the config that matches the silicon, and prove it works.
                if target != family:
                    rc2, out2 = self.ocd(["init", "shutdown"], timeout=60)
                    if rc2 != 0:
                        return None, out2
                return family, out
        return None, last

    # Where each family's watchdog lives, and what puts the chip back after a
    # session that read the flash through the debugger.
    #
    # Two things were learned here the hard way, and both cost a board that looked
    # dead.  First: reading the flash back -- which the discipline in AGENTS.md
    # requires, so it is not optional -- leaves the SSI in a mode where XIP reads
    # come back shifted by a nibble, and a vectreset does not undo that: with no
    # reset line attached, openocd's `reset run` on an RP2040 only sets the program
    # counter back and runs.  The application then boots from garbage and lands in
    # a double fault, while the write itself verified clean.  Writing the
    # watchdog's TRIGGER bit is an actual chip reset, which *does* put the SSI
    # back.  Second: a session that halted the core has to release it, or nothing
    # runs at all -- hence `reset run` after the reset, not instead of it.
    # How a point gets onto the board:
    #
    #   1. blank the flash with the debugger, which makes the chip's own bootrom
    #      bring up its USB by itself -- no BOOTSEL button, no reset line, and it
    #      works on both families (2e8a:0003 on an RP2040, 2e8a:000f on an RP2350);
    #   2. write the image with picotool, whose verification is trustworthy;
    #   3. read the flash back over SWD and compare it with the build, while the
    #      bootrom is still up and nothing is running;
    #   4. reboot through the bootrom, which is a real chip reset.
    #
    # Step 4 is the reason for all of it.  This probe has no nRESET line, so
    # openocd's `reset run` is a vectreset: it moves the program counter and runs,
    # and nothing else is reset.  On the RP2040 that leaves the SSI in a mode where
    # XIP returns nibble-shifted data; on the RP2350 it intermittently drops the
    # chip into INVSTATE at platform_entry, the very first hand-off out of boot2,
    # with the flash verified byte for byte and `reset run` reported as fine.  Both
    # were measured, and both are cured by the bootrom's own reset.  `resume` at
    # the end of step 3 is equally deliberate: a halted core takes the bootrom's USB
    # down with it, and picotool would then find nothing to reboot.
    BOOTSEL_PID = {"rp2040": 0x0003, "rp2350": 0x000F}

    def _bootsel_present(self):
        import usb.core
        return usb.core.find(idVendor=PICO_VID,
                             idProduct=self.BOOTSEL_PID[self.family]) is not None

    def flash_and_run(self, elf, timeout=300, tag="flash"):
        """Put the image on the board and start it, verifying it on the way."""
        import usb.core
        rb = os.path.join(os.path.dirname(elf), "readback.bin")
        uf2 = os.path.splitext(elf)[0] + ".uf2"
        log_path = os.path.join(self.logs_dir, tag + ".log")
        out = []

        # 1. blank the flash, so the bootrom comes up instead of the old image.
        #    Checked and retried, because openocd's flash driver borrows a 64 KB
        #    work area in SRAM (0x20010000 on an RP2350) and has been seen to fail
        #    to allocate it -- "Could not allocate stack for flash programming code"
        #    -- when the application that was running had just been halted.  When
        #    that happens the flash is *not* erased, picotool then writes into a
        #    region that still holds the old image, and the read-back in step 3
        #    catches it: the point is thrown away rather than interpreted, which is
        #    right, but it costs a run that a retry would have saved.
        erased = False
        for attempt in range(3):
            rc, o = self.ocd(["init", "halt", "flash erase_sector 0 0 last",
                              "reset run", "shutdown"], timeout=timeout)
            out.append(o)
            if "erased sectors" in o and "Could not allocate stack" not in o:
                erased = True
                break
            out.append("erase attempt %d did not take; retrying" % (attempt + 1))
            time.sleep(1)
        if not erased:
            out.append("the flash could not be blanked, so the bootrom never came up")
            open(log_path, "w").write("\n".join(out))
            return False, "\n".join(out), rb
        deadline = time.time() + 20
        while time.time() < deadline and not self._bootsel_present():
            time.sleep(0.5)
        if not self._bootsel_present():
            out.append("the bootrom's USB did not appear after blanking the flash")
            open(log_path, "w").write("\n".join(out))
            return False, "\n".join(out), rb

        # 2. write it with picotool, and stay in the bootrom afterwards
        rc, o = run(["picotool", "load", "-v", uf2,
                     "--vid", "0x2e8a",
                     "--pid", "0x%04x" % self.BOOTSEL_PID[self.family]], timeout=timeout)
        out.append(o)
        if rc != 0:
            open(log_path, "w").write("\n".join(out))
            return False, "\n".join(out), rb

        # 3. read it back and compare, with the bootrom still running
        rc, o = self.ocd(["init", "halt",
                          "dump_image %s 0x10000000 0x10000" % rb,
                          "resume", "shutdown"], timeout=timeout)
        out.append(o)

        # 4. a real reset, through the bootrom
        rc, o = run(["picotool", "reboot", "--vid", "0x2e8a",
                     "--pid", "0x%04x" % self.BOOTSEL_PID[self.family]], timeout=60)
        out.append(o)
        open(log_path, "w").write("\n".join(out))
        return rc == 0, "\n".join(out), rb

    def readback_diff(self, elf, rb):
        ref = os.path.splitext(elf)[0] + ".bin"
        if not os.path.exists(ref) or not os.path.exists(rb):
            return None
        a, b = open(ref, "rb").read(), open(rb, "rb").read()
        n = min(len(a), len(b))
        return sum(1 for i in range(n) if a[i] != b[i]), n

    def pc(self, elf=None):
        """Where is it?  A hang is a fact about the chip, not a missing score."""
        rc, out = self.ocd(["init", "halt", "reg pc", "resume", "shutdown"], timeout=60)
        m = re.search(r"pc \(/32\): (0x[0-9a-fA-F]+)", out)
        if not m:
            return None, None
        addr = int(m.group(1), 16)
        sym = None
        if elf and have("arm-none-eabi-addr2line"):
            rc, s = run(["arm-none-eabi-addr2line", "-f", "-C", "-e", elf, hex(addr)])
            if s.strip():
                sym = s.strip().splitlines()[0]
        return addr, sym

    def blank(self):
        """A blank chip brings up the bootrom's own USB by itself, which is the
        way back to a board stuck in an application when the probe has no reset
        line.  It is also the last resort before asking a human for the button."""
        return self.ocd(["init", "halt", "flash erase_sector 0 0 last",
                         "reset run", "shutdown"], timeout=120)


# --------------------------------------------------------------------------
# One board, measured one verified point at a time.
# --------------------------------------------------------------------------

class Probe:
    def __init__(self, args, family):
        self.args = args
        self.out = args.out
        self.build = os.path.join(self.out, "build")
        self.logs = os.path.join(self.out, "logs")
        os.makedirs(self.logs, exist_ok=True)
        self.results = {}
        self.dbg = Debugger(args, self.logs)
        self.family = family
        self.dbg.target = family
        self.dbg.family = family
        self.known_good = os.path.join(self.out, "known-good.elf")
        self.command = None
        self.stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.env = dict(os.environ)
        self.env["PICO_SDK_PATH"] = args.sdk
        # Voltage names straight out of the SDK; see vreg_table() for why this is
        # not a table typed into this file.
        self.vreg = vreg_table(args.sdk) or VREG_NAME_FALLBACK

    # ---- bookkeeping (a probe that can be interrupted is a probe you can use) --
    def key(self, khz, div, mt, rep):
        if self.args.profile:
            return "profile:%s/%d/%d" % (self.args.profile, mt, rep)
        return "%d/%s/%d/%d" % (khz, div or "auto", mt, rep)

    def load(self):
        path = os.path.join(self.out, "results.json")
        if os.path.exists(path):
            try:
                loaded = json.load(open(path))
            except ValueError:
                loaded = {}
            # Older files were a bare mapping; newer ones carry the command line
            # that produced them, because a run whose flags are unknown cannot be
            # reproduced -- which is exactly what a report is for.
            if isinstance(loaded, dict) and "results" in loaded:
                self.command = loaded.get("command")
                self.results = loaded["results"] or {}
            else:
                self.results = loaded or {}
        return self.results

    def save(self):
        json.dump({"command": " ".join(sys.argv), "results": self.results},
                  open(os.path.join(self.out, "results.json"), "w"),
                  indent=1, sort_keys=True)

    # ---- build -----------------------------------------------------------
    def cmake_build(self, extra, tag):
        src = os.path.join(COREMARK_ROOT, "rpi-pico")
        cmd = ["cmake", "-S", src, "-B", self.build,
               "-DPICO_BOARD=%s" % self.args.board,
               "-DPICO_TURBO_DIR=%s" % self.args.pico_turbo] + extra
        rc, out = run(cmd, timeout=300, log_path=os.path.join(self.logs, "cmake-%s.log" % tag),
                      env=self.env)
        if rc != 0:
            return None, out
        # One build directory, reconfigured per point: the SDK's own objects do not
        # change between points, only the clock in the application does.
        rc, out2 = run(["cmake", "--build", self.build, "-j", str(os.cpu_count() or 4)],
                       timeout=600, log_path=os.path.join(self.logs, "build-%s.log" % tag),
                       env=self.env)
        full = out + out2
        return (True, full) if rc == 0 else (None, full)

    # ---- one point -------------------------------------------------------
    def point(self, khz, div=None, mt=1, rep=1):
        k = self.key(khz, div, mt, rep)
        if k in self.results and not self.args.fresh:
            rec = self.results[k]
            log("  %d kHz: already measured (%s), skipping" % (khz, rec["result"]))
            return rec

        if self.args.profile:
            log("  profile %s, %d core(s), %d run(s)" % (self.args.profile, mt, rep))
        else:
            log("  %d kHz, DIV %s, %d core(s), %d run(s)" % (khz, div or "auto", mt, rep))
        extra = ["-DCOREMARK_MULTITHREAD=%d" % mt, "-DCOREMARK_REPEAT=%d" % rep]
        if self.args.profile:
            # The board file owns the clock, the voltage and the divider here; the
            # expected clock comes from what the library says it resolved to, read
            # out of the configure output below.
            if self.args.profile != "default":
                extra.append("-DPICO_TURBO_PROFILE=%s" % self.args.profile)
        else:
            extra.append("-DPICO_TURBO_SYS_CLK_KHZ=%d" % khz)
            if div:
                extra.append("-DPICO_TURBO_FLASH_CLK_DIV=%d" % div)
            if self.args.allow_above_ceiling:
                extra.append("-D_PLATFORM_MAX_KHZ=%d" % khz)

        rec = {"khz": khz, "div": div, "mt": mt, "rep": rep,
               "stamp": time.strftime("%Y-%m-%d %H:%M:%S")}
        ok, out = self.cmake_build(extra, k.replace("/", "-"))
        if not ok:
            rec["result"] = "build failed"
            rec["detail"] = [l for l in out.strip().splitlines() if "Error" in l][-2:]
            log("    build failed: " + " | ".join(rec["detail"]))
            self.store(k, rec)
            return rec
        m = re.search(r"^-- pico-turbo: (.*)$", out, re.M)
        if m:
            log("    %s" % m.group(1))
            if self.args.profile:
                r = re.search(r"pico-turbo: (\d+) MHz", out)
                if r:
                    rec["khz"] = khz = int(r.group(1)) * 1000
                    log("    the board file resolved to %d kHz" % khz)
        elf = os.path.join(self.build, "rpi-pico-coremark.elf")

        markers = ["all %d runs finished" % rep] if rep > 1 else ["CoreMark 1.0 :"]
        rlog = os.path.join(self.logs, "console-%s.log" % k.replace("/", "-"))
        idle = 45 + 60 * rep
        reader = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--reader", rlog,
             str(idle), json.dumps(markers)])
        time.sleep(2)                        # the reader before the chip

        flashed, _, rb = self.dbg.flash_and_run(elf, tag=k.replace("/", "-"))
        diff = self.dbg.readback_diff(elf, rb)
        rec["readback"] = diff[0] if diff else None
        log("    flashed and read back: %s" %
            ("%d differing bytes of %d" % diff if diff else "no read-back"))
        # The read-back is the verification; openocd's exit status is not, because
        # the reset that follows it can report an error on a session that wrote and
        # verified perfectly well.
        if diff is None or diff[0]:
            rec["result"] = "flash not verified"
            rec["detail"] = "the image in the flash is not the image that was built"
            reader.terminate()
            self.store(k, rec)
            return rec

        try:
            reader.wait(timeout=idle + 120)
        except subprocess.TimeoutExpired:
            reader.terminate()
        text = open(rlog).read() if os.path.exists(rlog) else ""

        st = re.search(r"PICO-TURBO: (\d+) kHz asked, (\d+) kHz configured, "
                       r"(\d+) kHz measured, vreg sel (\d+), flash (\d+) kHz", text)
        if st:
            rec["asked"], rec["configured"], rec["measured"] = (int(st.group(i)) for i in (1, 2, 3))
            rec["vreg_sel"], rec["flash_khz"] = int(st.group(4)), int(st.group(5))
            log("    state: %d kHz measured, vreg sel %d, flash %d kHz"
                % (rec["measured"], rec["vreg_sel"], rec["flash_khz"]))
        rec["scores"] = [float(v) for v in re.findall(r"CoreMark 1\.0 : ([\d.]+)", text)]
        rec["validated"] = text.count("Correct operation validated")
        rec["errors"] = text.count("Errors detected")
        rec["banners"] = text.count("CoreMark benchmark running")
        rec["counter"] = [int(v) for v in re.findall(r"COREMARK-REPEAT: run (\d+) of \d+", text)]
        rec["iterations"] = [int(v) for v in re.findall(r"Iterations       : (\d+)", text)]

        # The four checks AGENTS.md asks for, plus the one that catches a run too
        # short to be reportable.
        checks = {
            "flash verified": rec["readback"] == 0,
            "a score": bool(rec["scores"]),
            "validated": rec["validated"] > 0,
            "no CoreMark errors": rec["errors"] == 0,
            "clock landed where asked": clock_landed(rec),
        }
        rec["checks"] = checks
        if not rec["scores"]:
            addr, sym = self.dbg.pc(elf)
            rec["pc"] = hex(addr) if addr else None
            rec["symbol"] = sym
            rec["result"] = "hang" if addr else "no output"
            log("    NO SCORE -- program counter %s %s" % (rec["pc"], sym or ""))
        elif not all(checks.values()):
            rec["result"] = "failed: " + ", ".join(n for n, v in checks.items() if not v)
            log("    %s" % rec["result"])
        else:
            rec["result"] = "ok"
            mean = sum(rec["scores"]) / len(rec["scores"])
            log("    ok: %.2f iterations/sec%s%s"
                % (mean, ", %d validated of %d" % (rec["validated"], rep) if rep > 1 else "",
                   ", %.3f per MHz" % (mean / (khz / 1000.0)) if rep == 1 else ""))
        self.store(k, rec)
        if rec["result"] == "ok":
            shutil.copyfile(elf, self.known_good)
        else:
            self.put_back()
        return rec

    def store(self, key, rec):
        self.results[key] = rec
        self.save()

    def good(self, rec):
        return bool(rec) and rec.get("result") == "ok"

    def put_back(self):
        """A failed point can leave a board that hangs at every reset -- a flash
        divider lives in boot stage 2, so it re-happens on each one.  Rewrite the
        last image that passed before anything else runs."""
        if not os.path.exists(self.known_good):
            return
        log("    putting the last known-good image back")
        try:
            _, _, rb = self.dbg.flash_and_run(self.known_good, tag="recover")
            diff = self.dbg.readback_diff(self.known_good, rb)
            # The read-back is the verification, here as everywhere else.  Judging
            # this by openocd's exit status blanked a board whose image had been
            # written and verified perfectly well -- the reset steps at the end of
            # the session return an error on a session that did its job, and the
            # recovery then erased a good flash in response to a success.
            if diff and diff[0] == 0:
                log("    the board is back on the last image that passed its checks")
                return
            log("    the probe could not rewrite it (%s); blanking the flash so the "
                "bootrom's own USB comes up"
                % ("no read-back" if not diff else "%d bytes differ" % diff[0]))
            self.dbg.blank()
            log("    if the board is still unreachable, press BOOTSEL and re-run")
        except Exception as exc:            # a failed recovery must not take the
            log("    recovery itself failed: %s" % exc)   # rest of the run with it


# --------------------------------------------------------------------------
# phases
# --------------------------------------------------------------------------

def identify(p, args):
    ident = {"board": args.board, "family": p.family, "stamp": p.stamp}
    rc, out = run(["picotool", "info", "-a"], timeout=60)
    ident["picotool"] = out.strip().splitlines()[:40]
    for line in out.splitlines():
        for field in ("flash size", "flash id", "pico_board", "name"):
            if line.strip().startswith(field + ":"):
                ident[field.replace(" ", "_")] = line.split(":", 1)[1].strip()
    log("  chip %s, flash %s, board %s"
        % (p.family, ident.get("flash_size", "unknown"), args.board))
    if not ident.get("flash_size"):
        log("  (the board is not in BOOTSEL, so the flash part is not readable from "
            "here; the debugger flashes it either way.  picotool in BOOTSEL would "
            "name it.)")
    return ident


def cpu_ladder(p, args, base):
    fam = PLATFORM[p.family]
    points = args.points or list(fam["ladder"])
    points = [k for k in points if k > base["khz"]]
    if args.max_khz:
        points = [k for k in points if k <= args.max_khz]
    # A clock above the ceiling a board file sets is refused at configure time, so
    # trying it says nothing about the chip -- it is a build failure wearing a
    # result's clothes.  Skip those unless the caller asks for them explicitly.
    ceiling = fam["ceiling"]
    untried = [k for k in points if k > ceiling and not args.allow_above_ceiling]
    points = [k for k in points if k <= ceiling or args.allow_above_ceiling]
    if untried:
        log("  (not trying %s: above the %d kHz ceiling a board file sets -- pass "
            "--allow-above-ceiling to ask anyway)"
            % (", ".join("%d kHz" % k for k in untried), ceiling))
    log("\n== Clock ladder: %d point(s) above the stock clock" % len(points))
    passed, first_bad, skipped = [], None, []
    for khz in points:
        if not pll_reachable(khz):
            skipped.append(khz)
            log("  %d kHz: the PLL cannot land on it exactly, skipping" % khz)
            continue
        rec = p.point(khz, args.divider, 1, 1)
        if p.good(rec):
            passed.append(rec)
        else:
            first_bad = rec
            if rec["result"] == "build failed":
                log("  stopping the ladder: the build was refused, which is a fact "
                    "about the configuration and not about the chip")
            else:
                log("  stopping the ladder: an unexplained failure is worth more "
                    "than the points above it")
            break
    return passed, first_bad, skipped, untried


def flash_ladder(p, args, top):
    if not top:
        return []
    # The divider the library derived is visible in the state line: clock over
    # flash clock.  Walking it down finds where this board's flash part gives up.
    div0 = top.get("div")
    if not div0 and top.get("flash_khz"):
        div0 = max(2, int(round(top["khz"] / float(top["flash_khz"]))))
    div0 = div0 or PLATFORM[p.family]["boot2_div"]
    if div0 % 2:
        div0 += 1
    # The step is 1 where the family's boot stage 2 takes odd dividers.  Checked
    # against the SDK sources: the RP2040's w25q080 and at25sf128a carry #error
    # PICO_FLASH_SPI_CLKDIV must be even, the RP2350's w25q080 does not (only a
    # maximum), and three Waveshare RP2350 boards ship 3.  A board file may still be
    # stricter than the silicon -- if it is, the point comes back as a build failure,
    # which the ladder treats as "not a fact about the chip".
    step = 1 if p.family == "rp2350" else 2
    cands = [div0, div0 - step, div0 - 2 * step, div0 + step]
    cands = [d for d in dict.fromkeys(cands) if d >= 2]
    if step == 2:
        cands = [d for d in cands if d % 2 == 0]
    else:
        log("   (RP2350: the boot stage 2 takes odd dividers, so the ladder steps by 1)")
    # Beyond the QSPI interface's own 133 MHz there is nothing to learn about this
    # board -- the failure is guaranteed by the interface, not by the flash part --
    # and walking into it costs a lockup and a recovery.  Measured, the hard way:
    # DIV 2 at 420 MHz is 210 MHz of flash clock, and it hangs with the core at
    # 0xfffffffe.
    over = [d for d in cands if top["khz"] / float(d) > 133000]
    cands = [d for d in cands if top["khz"] / float(d) <= 133000]
    if over:
        log("   (not trying DIV %s: that is above the QSPI interface's 133 MHz, "
            "where the failure would say nothing about this board)"
            % ", ".join(str(d) for d in over))
    log("\n== Flash divider ladder at %d kHz: %s (the library derived %d)"
        % (top["khz"], ", ".join(str(d) for d in cands), div0))
    log("   (the divider lives in boot stage 2, so a step that bricks the boot "
        "re-happens on every reset: each one is written back to the known-good "
        "image before the next)")
    out = []
    for div in cands:
        rec = p.point(top["khz"], div, 1, 1)
        out.append(rec)
        if not p.good(rec):
            log("  the flash clock stops improving here")
            break
    return out


def dual_core(p, args, top):
    if not top or args.mt < 2:
        return None
    log("\n== Dual core at %d kHz (more current than one core: the voltage has "
        "less room)" % top["khz"])
    return p.point(top["khz"], top.get("div"), args.mt, 1)


def soak(p, args, top, mt):
    if not top or args.soak < 2:
        return None
    log("\n== Soak: %d runs at %d kHz, %d core(s), a bootrom reboot between runs"
        % (args.soak, top["khz"], mt))
    log("   (the run counter lives in watchdog scratch, which outlives a reset, so "
        "a resumed soak numbers its runs from where it stopped)")
    return p.point(top["khz"], top.get("div"), mt, args.soak)


# --------------------------------------------------------------------------
# report and the proposed board file
# --------------------------------------------------------------------------

def report(p, args, ident, ladder, bad, flashes, dual, soak_rec, pll_skipped, untried):
    profile_note = ("Measured through the board file rather than by pinning a clock: the build "
                    "was given %s and nothing else, so what it ran is whatever "
                    "boards/%s.cmake resolved to."
                    % ("no profile or clock (the board file's own default)"
                       if args.profile == "default" else "profile '%s'" % args.profile,
                       args.board)) if args.profile else None
    top = ladder[-1] if ladder else None
    L = []
    A = L.append
    A("# Probe: %s (%s, flash %s)" % (args.board, p.family, ident.get("flash_size", "?")))
    A("")
    A("%s.  One command, and the measurements this repository's notes are made of." % p.stamp)
    A("")
    A("```")
    A("$ %s" % (p.command or "tools/probe.py (command line not recorded)"))
    A("```")
    A("")
    A("Every point below was built, written to flash, read back and compared byte for")
    A("byte, then run -- and kept only if the application validated its own result and")
    A("the state line it prints showed the clock the chip *measured itself at* being")
    A("the clock that was asked for.  A point that fails is not interpreted; the walk")
    A("stops there and the board is put back to the last image that passed.")
    A("")
    if profile_note:
        A(profile_note)
        A("")
    A("## Identity")
    A("")
    A("| Field | Value |")
    A("|---|---|")
    for label, key in (("board", "board"), ("chip family", "family"),
                       ("flash size", "flash_size"), ("flash id", "flash_id"),
                       ("firmware board", "pico_board"), ("firmware name", "name")):
        if ident.get(key):
            A("| %s | `%s` |" % (label, ident[key]))
    A("")

    if not ladder:
        A("## Nothing passed")
        A("")
        A("The stock clock did not get through its checks, so no ladder was run.  A")
        A("board that fails at the stock clock has a problem that is not about")
        A("overclocking: start with the flash read-back and the console.")
        A("")
    else:
        A("## Clock ladder (single core)")
        A("")
        A("| Clock | Voltage applied | Flash | Iterations/sec | per MHz | Result |")
        A("|---|---|---|---|---|---|")
        for rec in ladder:
            s = rec["scores"][0] if rec.get("scores") else 0.0
            v = p.vreg.get(rec.get("vreg_sel"), "sel %s" % rec.get("vreg_sel"))
            A("| %d kHz | %s | %s kHz | %.2f | %.3f | ok |"
              % (rec["khz"], v, rec.get("flash_khz", "?"), s, s / (rec["khz"] / 1000.0)))
        if bad:
            A("| %d kHz | | | | | **%s**%s |"
              % (bad["khz"], bad["result"],
                 " -- PC `%s` %s" % (bad.get("pc"), bad.get("symbol") or "") if bad.get("pc") else ""))
        A("")
        per = [r["scores"][0] / (r["khz"] / 1000.0) for r in ladder if r.get("scores")]
        if len(per) > 2:
            lo, hi = min(per), max(per)
            if hi - lo < 0.02 * hi:
                A("The score is flat at %.3f iterations/sec per MHz from %d to %d MHz, so"
                  % (sum(per) / len(per), ladder[0]["khz"] // 1000, top["khz"] // 1000))
                A("this workload never leaves the chip's cache: what the ladder measured is")
                A("the core's clock, not the memory's.")
            else:
                A("The score per MHz is not flat (%.3f at the bottom, %.3f at the top), which"
                  % (per[0], per[-1]))
                A("is what a memory or flash limit looks like on this board.")
            A("")
        if pll_skipped:
            A("Not tried, because the PLL cannot produce them exactly (the SDK would")
            A("silently leave the clock alone and the point would look like instability):")
            A(", ".join("%d kHz" % k for k in pll_skipped) + ".")
            A("")
        if untried:
            A("Not tried, because they are above the ceiling this board's profile in")
            A("pico-turbo sets (a build asking for more is refused at configure time, so")
            A("it would say nothing about the chip): %s.  `--allow-above-ceiling` asks"
              % ", ".join("%d kHz" % k for k in untried))
            A("anyway, with `-D_PLATFORM_MAX_KHZ`.")
            A("")

    if flashes:
        A("## Flash divider ladder")
        A("")
        A("| Divider | Flash clock | Result |")
        A("|---|---|---|")
        for rec in flashes:
            fk = rec.get("flash_khz")
            if not fk and rec.get("div"):
                fk = int(rec["khz"] / float(rec["div"]))
            note = " (beyond the QSPI interface's 133 MHz)" if fk and fk > 133000 else ""
            A("| %s | %s kHz | %s%s |"
              % (rec.get("div"), fk or "?", rec["result"], note))
        A("")
        good = [r for r in flashes if r.get("result") == "ok"]
        if good:
            best = max(good, key=lambda r: r.get("flash_khz") or 0)
            A("The fastest divider this board ran at is **%s** (%s kHz of flash clock)%s"
              % (best["div"], best.get("flash_khz"), "."))
            badf = [r for r in flashes if r.get("result") != "ok"]
            if badf:
                r = badf[0]
                fk = r.get("flash_khz") or (int(r["khz"] / float(r["div"])) if r.get("div") else None)
                A("")
                A("DIV %s%s is where it stopped: %s." % (r.get("div"),
                  " (%s kHz of flash clock)" % fk if fk else "", r["result"]))
            A("")

    if dual:
        s = dual["scores"][0] if dual.get("scores") else 0.0
        one = top["scores"][0] if top and top.get("scores") else 0.0
        A("## Dual core")
        A("")
        A("%d kHz with one context per core: **%.2f** iterations/sec%s"
          % (dual["khz"], s, ", %.3fx the single-core score." % (s / one) if one else "."))
        A("")

    if soak_rec:
        scores = soak_rec.get("scores") or []
        A("## Soak")
        A("")
        A("%d runs at %d kHz, %d core(s), each rebooting through the bootrom so no run"
          % (soak_rec.get("rep", 0), soak_rec["khz"], soak_rec.get("mt", 1)))
        A("inherits a warm chip.")
        A("")
        A("| Quantity | Result |")
        A("|---|---|")
        A("| runs that produced a score | %d of %d |" % (len(scores), soak_rec.get("rep", 0)))
        A("| runs that validated | %s |" % soak_rec.get("validated"))
        A("| `Errors detected` | %s |" % soak_rec.get("errors"))
        A("| run counter reached | %s |"
          % (soak_rec.get("counter", [None])[-1] if soak_rec.get("counter") else "n/a"))
        if scores:
            mean = sum(scores) / len(scores)
            A("| spread | %.4f%% |" % ((max(scores) - min(scores)) / mean * 100))
            A("| iterations/sec | mean %.6f, min %.6f, max %.6f |"
              % (mean, min(scores), max(scores)))
        A("")
        if len(scores) != soak_rec.get("rep"):
            A("**%d of %d runs are accounted for** -- the rest produced no output, which"
              % (len(scores), soak_rec.get("rep", 0)))
            A("is a result about the board, not about the reader: the counter would say")
            A("so either way.")
            A("")

    A("## What this says")
    A("")
    if top:
        A("- Highest clock validated: **%d kHz**%s"
          % (top["khz"], "; %d kHz %s." % (bad["khz"], bad["result"]) if bad else "."))
        A("- The voltage at every point came from pico-turbo's own table, not from")
        A("  these flags: the ladder is a check on that table as much as on the board.")
        if flashes:
            good = [r for r in flashes if r.get("result") == "ok"]
            if good:
                A("- Fastest flash divider validated: **%s** (%s kHz).  The ceiling a board"
                  % (max(good, key=lambda r: r.get("flash_khz") or 0)["div"],
                     max(good, key=lambda r: r.get("flash_khz") or 0).get("flash_khz")))
                A("  file carries is what keeps a *build* from deriving something faster.")
        A("")
        A("`boards/%s.cmake` next to this report is a proposal built from the numbers"
          % args.board)
        A("above.  It describes this board, flash part and all -- read it before you")
        A("trust it, and be aware that the same board name can cover a different flash")
        A("chip (that is measured, not a caution).")
    A("")
    text = "\n".join(L) + "\n"
    open(os.path.join(p.out, "report.md"), "w").write(text)
    return text


def propose_board_file(p, args, ladder, flashes, top):
    if not ladder or not top:
        return None
    fam = PLATFORM[p.family]
    picks = []
    for frac in (0.0, 0.34, 0.67, 1.0):
        picks.append(ladder[min(len(ladder) - 1, int(round(frac * (len(ladder) - 1))))])
    picks = list({r["khz"]: r for r in picks}.values())
    names = ["safe", "fast", "turbo", "extreme"][:len(picks)]
    stock_sel = 11 if p.family == "rp2040" else 0
    good_flash = [r for r in flashes if r.get("result") == "ok"]
    flash_max = max((r.get("flash_khz") or 0 for r in good_flash), default=None) \
        or top.get("flash_khz")
    volts = lambda rec: p.vreg.get(rec.get("vreg_sel"), "?")

    def div_of(rec):
        """The divider this point actually ran at: pinned if it was pinned, else
        what the library derived -- which the state line shows as the flash clock
        it measured, so it can be recovered exactly rather than guessed."""
        if rec.get("div"):
            return rec["div"]
        if rec.get("flash_khz"):
            return max(2, int(round(rec["khz"] / float(rec["flash_khz"]))))
        return None
    out = []
    A = out.append
    A("# Board config: %s" % args.board)
    A("#")
    A("# Written by tools/probe.py in the coremark repository from measurements, not from")
    A("# a datasheet: every number below was built, written, read back and compared, run,")
    A("# and accepted only where the chip measured itself at the clock it was asked for.")
    A("#")
    A("# Probe date: %s" % p.stamp)
    A("#")
    A("# Profiles:")
    for name, rec in zip(names, picks):
        s = rec["scores"][0] if rec.get("scores") else 0.0
        volt = volts(rec)
        if volt != p.vreg.get(stock_sel):
            volt = volt.replace("VREG_VOLTAGE_", "").replace("_", ".") + " V"
        else:
            volt = "stock voltage"
        A("#   %-8s- %d MHz, %s, flash DIV %s  (%.2f iterations/sec, measured)"
          % (name, rec["khz"] // 1000, volt, div_of(rec) or "auto", s))
    A("")
    A("# The highest clock this board validated.  %s"
      % ("The library's platform ceiling is %d." % fam["ceiling"] if top["khz"] >= fam["ceiling"]
         else "Points above it were not tried."))
    A("set(_PLATFORM_MAX_KHZ %d)" % top["khz"])
    if flash_max:
        A("")
        A("# The fastest flash clock this board ran at (%s kHz).  The QSPI interface itself"
          % flash_max)
        A("# allows 133 MHz; this is what the board was *shown* to hold.")
        A("set(_FLASH_MAX_KHZ %d)" % flash_max)
    # What the SDK's own boot stage 2 would use before pico-turbo overrides it:
    # a platform constant, not something this probe measured.
    A("set(_BOOT2_DEFAULT_DIV %d)" % fam["boot2_div"])
    A("set(_FLASH_REQUIRES_EVEN ON)")
    A("")
    A('if(PICO_TURBO_PROFILE STREQUAL "%s")' % names[0])
    for i, (name, rec) in enumerate(zip(names, picks)):
        if i:
            A('elseif(PICO_TURBO_PROFILE STREQUAL "%s")' % name)
        A("    set(PICO_TURBO_SYS_CLK_KHZ %d)" % rec["khz"])
        v = p.vreg.get(rec.get("vreg_sel"))
        if v and rec.get("vreg_sel") != stock_sel:
            A("    set(PICO_TURBO_VREG_VOLTAGE %s)" % v)
        else:
            A("    # stock voltage")
        if div_of(rec):
            A("    set(PICO_TURBO_FLASH_CLK_DIV %d)" % div_of(rec))
    A('elseif(NOT PICO_TURBO_PROFILE STREQUAL "")')
    A('    message(FATAL_ERROR "pico-turbo: unknown profile '
      "'${PICO_TURBO_PROFILE}' for board %s\")" % args.board)
    A("endif()")
    A("")
    path = os.path.join(p.out, "boards", "%s.cmake" % args.board)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write("\n".join(out))
    return path


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="measure a Pico board with pico-turbo and CoreMark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("    tools/probe.py")[0])
    ap.add_argument("--board", default=None, help="PICO_BOARD (pico, pico_w, pico2, ...)")
    ap.add_argument("--sdk", default=os.environ.get("PICO_SDK_PATH") or os.path.expanduser("~/.pico-sdk"))
    ap.add_argument("--pico-turbo", default=os.environ.get("PICO_TURBO_DIR")
                    or os.path.join(os.path.dirname(COREMARK_ROOT), "pico-turbo"))
    ap.add_argument("--interface", default="interface/cmsis-dap.cfg")
    ap.add_argument("--adapter-speed", type=int, default=1000)
    ap.add_argument("--out", default=None)
    ap.add_argument("--points", default=None, help="comma separated kHz (or MHz), instead of the platform list")
    ap.add_argument("--divider", type=int, default=None,
                    help="pin the flash divider (default: let pico-turbo derive it)")
    ap.add_argument("--profile", nargs="?", const="default", default=None,
                    help="measure one board-file profile instead of a clock ladder: "
                         "--profile turbo, or --profile (bare) for whatever the board "
                         "file defaults to; nothing else is passed to the build")
    ap.add_argument("--mt", type=int, default=2, help="contexts for the dual-core phase; 1 skips it")
    ap.add_argument("--soak", type=int, default=10, help="runs in the soak phase; 0 or 1 skips it")
    ap.add_argument("--flash-ladder", action="store_true", help="also walk the flash divider")
    ap.add_argument("--max-khz", type=int, default=None)
    ap.add_argument("--allow-above-ceiling", action="store_true",
                    help="let a clock above the board's ceiling through (needs -D_PLATFORM_MAX_KHZ support in the board file)")
    ap.add_argument("--identify-only", action="store_true")
    ap.add_argument("--fresh", action="store_true", help="ignore an existing results.json")
    ap.add_argument("--reader", nargs=3, metavar=("LOG", "IDLE", "MARKERS"), help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.reader:
        return reader_main(args.reader[0], float(args.reader[1]), json.loads(args.reader[2]))

    for tool in ("openocd", "cmake", "arm-none-eabi-gcc"):
        if not have(tool):
            log("missing %s" % tool)
            return 2
    if not os.path.isdir(args.sdk):
        log("no pico-sdk at %s: pass --sdk or set PICO_SDK_PATH" % args.sdk)
        return 2
    if not os.path.exists(os.path.join(args.pico_turbo, "CMakeLists.txt")):
        log("no pico-turbo at %s: pass --pico-turbo" % args.pico_turbo)
        return 2
    try:
        import usb.core  # noqa: F401
    except ImportError:
        log("pyusb is needed for the console reader (pip install pyusb)")
        return 2

    if args.points:
        vals = [int(v) for v in args.points.split(",")]
        args.points = [v if v > 10000 else v * 1000 for v in vals]

    dbg = Debugger(args)
    family, out = dbg.identify()
    if family is None:
        log("the debug probe did not identify a chip -- is it attached, and powered "
            "from the same board?")
        log("\n".join(out.strip().splitlines()[-4:]))
        return 2
    if not args.board:
        args.board = "pico2" if family == "rp2350" else "pico"
        log("no --board given: using %s (name a Pico W explicitly)" % args.board)

    args.out = args.out or os.path.join(os.getcwd(), "probe-%s-%s"
                                        % (args.board, time.strftime("%Y%m%d-%H%M%S")))
    os.makedirs(args.out, exist_ok=True)
    p = Probe(args, family)
    p.load()

    points = args.points or PLATFORM[family]["ladder"]
    todo = [k for k in points if k > PLATFORM[family]["stock"]] + [1]
    log("probe: %s (%s) into %s" % (args.board, family, args.out))
    log("  plan: stock clock, then %d ladder point(s), %s, %s"
        % (len([k for k in todo if k != 1]),
           "a dual-core point" if args.mt > 1 else "no dual-core point",
           "a %d-run soak" % args.soak if args.soak > 1 else "no soak"))
    log("  roughly %d minutes, and it stops early if a point fails"
        % int(1.6 * (2 + len(todo) + (args.soak if args.soak > 1 else 0) / 3.0)))

    ident = identify(p, args)
    if args.identify_only:
        return 0

    if args.profile:
        log("\n== One configuration, straight from the board file: %s"
            % (args.profile if args.profile != "default" else "its default profile"))
    else:
        log("\n== First point, the stock clock: the whole path has to work once before "
            "any of this is worth the time")
    base = p.point(PLATFORM[family]["stock"], args.divider, 1, 1)
    if not p.good(base):
        log("  the stock clock did not pass, so nothing above it is worth trying")
        report(p, args, ident, [], base, [], None, None, [], [])
        return 1

    if args.profile:
        # One configuration, owned by the board file: the ladder would only measure
        # clocks the board file does not describe.
        ladder, bad, pll_skipped, untried = [base], None, [], []
    else:
        got, bad, pll_skipped, untried = cpu_ladder(p, args, base)
        ladder = [base] + got
    top = ladder[-1]
    flashes = flash_ladder(p, args, top) if args.flash_ladder else []
    div_top = top
    if flashes:
        good = [r for r in flashes if r.get("result") == "ok"]
        if good:
            div_top = max(good, key=lambda r: r.get("flash_khz") or 0)
    else:
        div_top = dict(top)
    dual = dual_core(p, args, div_top)
    soak_rec = soak(p, args, div_top, args.mt if dual else 1)

    report(p, args, ident, ladder, bad, flashes, dual, soak_rec, pll_skipped, untried)
    board_file = propose_board_file(p, args, ladder, flashes, div_top)
    log("\n== %s" % os.path.join(args.out, "report.md"))
    print(open(os.path.join(args.out, "report.md")).read())
    if board_file:
        log("proposed board file: %s" % board_file)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("\ninterrupted: results so far are in results.json, re-run to continue")
        sys.exit(130)
    except Exception:
        import traceback
        traceback.print_exc()
        log("\nunexpected failure: results so far are in results.json, and re-running "
            "with the same --out continues from them")
        sys.exit(1)
