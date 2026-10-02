#!/usr/bin/env python3
"""Offline tests for tools/probe_parse.py -- the rules the bench judges by.

No board, no probe, no SDK, no network: every test feeds the module recorded
console text, a results record, or a value, and asserts the interpretation.
Fixtures are real logs captured by `tools/probe.py` on this bench, copied out of
the (gitignored) `probe-*/` directories so they survive; `tests/README.md`
records where each came from.  One fixture is constructed from a source string
and is labelled as such.

Run:

    python3 -m unittest discover -s tests -v
"""

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import probe_parse as pp  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures")


def fixture(name):
    with open(os.path.join(FIXTURES, name), errors="replace") as fh:
        return fh.read()


def record(name):
    with open(os.path.join(FIXTURES, name)) as fh:
        results, _ = pp.load_results(json.load(fh))
    return results


class TestStateLine(unittest.TestCase):

    def test_real_single_core_state_line(self):
        # ORACLE: SPEC
        # SOURCE: rpi-pico/core_portme.c portable_init() state-line format string
        # EXPECTED: 520000 asked/configured/measured, vreg sel 19, flash 52000,
        #           clk_peri 520000, usb ok -- the line the fixture contains
        st = pp.parse_state_line(fixture("console-single-520.log"))
        self.assertEqual(st["asked"], 520000)
        self.assertEqual(st["configured"], 520000)
        self.assertEqual(st["measured"], 520000)
        self.assertEqual(st["vreg_sel"], 19)
        self.assertEqual(st["flash_khz"], 52000)
        self.assertEqual(st["clk_peri_khz"], 520000)
        self.assertIs(st["usb_ok"], True)

    def test_real_soak_state_line(self):
        # ORACLE: SPEC
        # SOURCE: rpi-pico/core_portme.c portable_init() state-line format string
        # EXPECTED: 400000 / 400000 / 400000, vreg sel 17, flash 50000, usb ok
        st = pp.parse_state_line(fixture("console-soak-10of10.log"))
        self.assertEqual((st["asked"], st["measured"], st["vreg_sel"], st["flash_khz"]),
                         (400000, 400000, 17, 50000))

    def test_usb_wrong_is_not_ok(self):
        # ORACLE: SPEC
        # SOURCE: rpi-pico/core_portme.c: `usb %s`, "ok" if st.usb_ok else "WRONG"
        # EXPECTED: `usb WRONG` parses to usb_ok False (not None, not True)
        line = ("PICO-TURBO: 150000 kHz asked, 150000 kHz configured, 150000 kHz "
                "measured, vreg sel 11, flash 37500 kHz, clk_peri 150000 kHz, usb WRONG")
        self.assertIs(pp.parse_state_line(line)["usb_ok"], False)

    def test_older_line_without_peri_fields_still_parses(self):
        # ORACLE: REQUIREMENT
        # SOURCE: tools/probe.py reads logs from before clk_peri/usb were added
        # EXPECTED: fields parse; usb_ok is None (unknown), not False
        line = ("PICO-TURBO: 520000 kHz asked, 520000 kHz configured, 520000 kHz "
                "measured, vreg sel 19, flash 52000 kHz")
        st = pp.parse_state_line(line)
        self.assertEqual(st["measured"], 520000)
        self.assertIsNone(st["usb_ok"])
        self.assertIsNone(st["clk_peri_khz"])

    def test_no_state_line_returns_none(self):
        # ORACLE: REQUIREMENT
        # SOURCE: rpi-pico/README.md's sample output block predates the state line
        # EXPECTED: a log the port did not write a state line into parses to None
        self.assertIsNone(pp.parse_state_line("CPU speed: 400(MHz), Flash speed: 100(MHz)\n"))


class TestClockLanded(unittest.TestCase):

    def test_exact_and_within_tolerance(self):
        # ORACLE: REQUIREMENT
        # SOURCE: tools/probe_parse.clock_landed docstring (the rule probe.py used)
        # EXPECTED: |measured-asked| <= max(1000, asked//1000)
        self.assertTrue(pp.clock_landed(520000, 520000))
        self.assertTrue(pp.clock_landed(520000, 521000))     # tolerance is 1000
        self.assertTrue(pp.clock_landed(125000, 124001))
        self.assertFalse(pp.clock_landed(520000, 521001))
        self.assertFalse(pp.clock_landed(125000, 123999))

    def test_missing_values_are_not_landed(self):
        # ORACLE: REQUIREMENT
        # SOURCE: the SDK leaves the clock alone at a PLL-unreachable frequency;
        #         a point with no reading is not a stability result
        # EXPECTED: False when asked or measured is absent/zero
        self.assertFalse(pp.clock_landed(None, 520000))
        self.assertFalse(pp.clock_landed(520000, None))
        self.assertFalse(pp.clock_landed(0, 0))


class TestConsole(unittest.TestCase):

    def test_full_soak_10_of_10(self):
        # ORACLE: SPEC + RELATIONSHIP
        # SOURCE: rpi-pico/core_portme.c portable_fini() prints
        #         `COREMARK-REPEAT: run N of M` per finished run, then
        #         `all M runs finished`; core_main.c prints one score per run and
        #         the banner once per boot
        # EXPECTED: 10 scores, 10 validated, 0 errors, 10 banners, counter 1..10,
        #           all_finished 10, no item errors
        obs = pp.parse_console(fixture("console-soak-10of10.log"))
        self.assertEqual(len(obs["scores"]), 10)
        self.assertEqual(obs["validated"], 10)
        self.assertEqual(obs["errors"], 0)
        self.assertEqual(obs["banners"], 10)
        self.assertEqual(obs["counter"], list(range(1, 11)))
        self.assertEqual(obs["all_finished"], 10)
        self.assertEqual(obs["item_errors"], [])

    def test_soak_counts_agree_by_construction(self):
        # ORACLE: RELATIONSHIP
        # SOURCE: the counter, the score lines and the banner all count finished
        #         runs in portable_fini(); a complete soak has all three equal to M
        # EXPECTED: scores == counter[-1] == all_finished == banners == M
        obs = pp.parse_console(fixture("console-soak-10of10.log"))
        self.assertEqual(len(obs["scores"]), obs["counter"][-1])
        self.assertEqual(len(obs["scores"]), obs["all_finished"])
        self.assertEqual(len(obs["scores"]), obs["banners"])

    def test_errors_detected_can_be_only_the_ten_second_rule(self):
        # ORACLE: SPEC
        # SOURCE: core_main.c: `Errors detected` is printed whenever total_errors
        #         > 0, and the <10 s rule increments total_errors.  The per-part
        #         `[i]ERROR! ... crc` lines are the data-error signal.
        # EXPECTED: errors == 1 with item_errors == [] and short_run True
        obs = pp.parse_console(fixture("console-short-run-only.log"))
        self.assertEqual(obs["errors"], 1)
        self.assertEqual(obs["item_errors"], [])
        self.assertTrue(obs["short_run"])
        self.assertEqual(obs["scores"], [])
        self.assertEqual(obs["validated"], 0)

    def test_item_errors_mark_a_crc_disagreement(self):
        # ORACLE: SPEC
        # SOURCE: core_main.c prints `[<ctx>]ERROR! <part> crc 0x.... - should be
        #         0x....` once per disagreeing part
        # EXPECTED: the real skip-kernels log has three (list, matrix, state)
        obs = pp.parse_console(fixture("console-skip-kernels-short.log"))
        self.assertEqual(len(obs["item_errors"]), 3)
        self.assertTrue(obs["short_run"])
        self.assertEqual(obs["errors"], 1)

    def test_crc_values_match_coremark_constants(self):
        # ORACLE: SPEC
        # SOURCE: core_main.c *_known_crc[] for the 2K performance run,
        #         seedcrc 0xe9f5 (known_id 3); upstream README log format
        # EXPECTED: seedcrc 0xe9f5, list 0xe714, matrix 0x1fd7, state 0x8e3a,
        #           identical for both contexts
        crc = pp.crc_values(fixture("console-soak-10of10.log"))
        self.assertEqual(crc["seedcrc"], pp.KNOWN_CRC_PERFORMANCE_2K["seedcrc"])
        for ctx in (0, 1):
            self.assertEqual(crc["crc"][(ctx, "crclist")],
                             pp.KNOWN_CRC_PERFORMANCE_2K["crclist"])
            self.assertEqual(crc["crc"][(ctx, "crcmatrix")],
                             pp.KNOWN_CRC_PERFORMANCE_2K["crcmatrix"])
            self.assertEqual(crc["crc"][(ctx, "crcstate")],
                             pp.KNOWN_CRC_PERFORMANCE_2K["crcstate"])

    def test_crc_mismatch_is_visible_as_a_value_not_only_a_line(self):
        # ORACLE: SPEC
        # SOURCE: core_main.c compares against *_known_crc[]; a skipped kernel
        #         leaves its CRC zero
        # EXPECTED: the skip-kernels log reads crcmatrix 0x0000 and crcstate
        #           0x0000 while crclist is a real value
        crc = pp.crc_values(fixture("console-skip-kernels-short.log"))
        self.assertEqual(crc["crc"][(0, "crcmatrix")], 0x0000)
        self.assertEqual(crc["crc"][(0, "crcstate")], 0x0000)
        self.assertNotEqual(crc["crc"][(0, "crclist")], 0x0000)


class TestPointChecks(unittest.TestCase):

    def base_record(self):
        results = record("results-wrapper.json")
        return dict(next(iter(results.values())))

    def test_real_passing_record_passes_all_five(self):
        # ORACLE: REQUIREMENT
        # SOURCE: AGENTS.md evidence bar (five checks)
        # EXPECTED: every check True on a record the bench stored as ok
        rec = self.base_record()
        self.assertEqual(rec["result"], "ok")
        self.assertTrue(all(pp.point_checks(rec).values()), pp.point_checks(rec))

    def test_each_missing_evidence_fails_its_check(self):
        # ORACLE: REQUIREMENT
        # SOURCE: AGENTS.md evidence bar
        # EXPECTED: exactly the check for the removed evidence flips to False
        rec = self.base_record()
        cases = {"readback": 1, "scores": [], "validated": 0, "errors": 1,
                 "measured": 0}
        for field, value in cases.items():
            broken = dict(rec, **{field: value})
            checks = pp.point_checks(broken)
            self.assertFalse(all(checks.values()), field)
            self.assertEqual(sum(1 for v in checks.values() if not v), 1, field)

    def test_point_result_classification(self):
        # ORACLE: REQUIREMENT
        # SOURCE: AGENTS.md: a hang is a fact about the chip, not a low score
        # EXPECTED: ok / failed: ... / hang (pc known) / no output (pc unknown)
        rec = self.base_record()
        self.assertEqual(pp.point_result(rec), "ok")
        self.assertEqual(pp.point_result(dict(rec, readback=1)),
                         "failed: flash verified")
        self.assertEqual(pp.point_result(dict(rec, scores=[]), pc=0x1000), "hang")
        self.assertNotEqual(pp.point_result(dict(rec, scores=[], pc=None)), "hang")
        self.assertEqual(pp.point_result(dict(rec, scores=[])), "no output")


class TestSoak(unittest.TestCase):

    def test_scratch_addresses(self):
        # ORACLE: SPEC
        # SOURCE: rpi-pico/core_portme.c CORE_REPEAT_MAGIC_IDX 6 /
        #         CORE_REPEAT_COUNT_IDX 7; scratch slot 0 at watchdog+0x0C on both
        #         families (RP2040 0x40058000, RP2350 0x400D8000)
        # EXPECTED: slot 6 = +0x24, slot 7 = +0x28
        self.assertEqual(pp.scratch_magic_addr("rp2040"), 0x40058024)
        self.assertEqual(pp.scratch_count_addr("rp2040"), 0x40058028)
        self.assertEqual(pp.scratch_magic_addr("rp2350"), 0x400D8024)
        self.assertEqual(pp.scratch_count_addr("rp2350"), 0x400D8028)

    def test_magic_is_required_before_the_count_is_trusted(self):
        # ORACLE: SPEC
        # SOURCE: rpi-pico/core_portme.c only reads slot 7 when slot 6 holds the
        #         magic; slot 4 belongs to the SDK and reads as a clean zero
        # EXPECTED: a slot that is not the port's yields None, not 0
        sdk_slot = {"repeat_magic": 0x00000000, "repeat_count": 0x00000000, "pc": "0x1000"}
        self.assertIsNone(pp.soak_count(sdk_slot))
        port_slot = {"repeat_magic": pp.REPEAT_MAGIC, "repeat_count": 7, "pc": "0x1000"}
        self.assertEqual(pp.soak_count(port_slot), 7)

    def test_missing_debugger_reading(self):
        # ORACLE: REQUIREMENT
        # SOURCE: probe.py asks the chip before put_back(); no answer is no verdict
        # EXPECTED: a chip_state without "pc" says so instead of guessing
        self.assertEqual(pp.soak_diagnosis(6, 10, 6, {}),
                         "no reading from the debugger")

    def test_counter_reached_m_means_host_lost_output(self):
        # ORACLE: SPEC
        # SOURCE: AGENTS.md rule 5/5b: the counter is the application's; the
        #         missing part is the host's reader
        # EXPECTED: n >= rep names host-side output loss
        verdict = pp.soak_diagnosis(8, 10, 8,
                                    {"repeat_magic": pp.REPEAT_MAGIC, "repeat_count": 10,
                                     "pc": "0x1000"})
        self.assertIn("lost on the host side", verdict)

    def test_started_and_stopped_inside_itself(self):
        # ORACLE: SPEC
        # SOURCE: rpi-pico/MEASUREMENTS.md WeAct soak attempt five: counter 5,
        #         five scores, six banners (run six started and never came back)
        # EXPECTED: banners > done names the run that started and stopped
        verdict = pp.soak_diagnosis(5, 10, 6,
                                    {"repeat_magic": pp.REPEAT_MAGIC, "repeat_count": 5,
                                     "pc": "0xeffffffe", "symbol": "??",
                                     "cfsr": "00008200"})
        self.assertIn("run 6 started and stopped inside itself", verdict)
        self.assertIn("CFSR 0x00008200", verdict)
        self.assertIn("program counter 0xeffffffe", verdict)

    def test_never_started_has_no_banner(self):
        # ORACLE: SPEC
        # SOURCE: rpi-pico/MEASUREMENTS.md WeAct soak attempts two/three: 6 of 10
        #         reported with no further banner
        # EXPECTED: banners == done names the boot that did not come up
        verdict = pp.soak_diagnosis(6, 10, 6,
                                    {"repeat_magic": pp.REPEAT_MAGIC, "repeat_count": 6,
                                     "pc": "0x1000"})
        self.assertIn("no banner for run 7", verdict)
        self.assertIn("did not come up on that boot", verdict)

    def test_magic_gone(self):
        # ORACLE: SPEC
        # SOURCE: core_portme.c writes the magic before slot 7; its absence means
        #         the application never finished a run
        # EXPECTED: names the missing magic rather than a count
        verdict = pp.soak_diagnosis(3, 10, 3,
                                    {"repeat_magic": 0, "repeat_count": 0, "pc": "0x1000"})
        self.assertIn("the magic is gone", verdict)


class TestChipStateParser(unittest.TestCase):

    OPENOCD_SAMPLE = (
        "SCRATCH:\n"
        "0x400d8024: 636d726b 00000007 \n"
        "PC:\n"
        "pc (/32): 0x1000011c\n"
        "CFSR:\n"
        "0xe000ed28: 00008200 \n")

    def test_parses_scratch_pc_and_cfsr(self):
        # ORACLE: SPEC
        # SOURCE: the openocd commands probe.py issues (`echo {SCRATCH:}; mdw
        #         <addr> 2`, `reg pc`, `mdw 0xe000ed28 1`); Jim Tcl strips the
        #         braces from `echo {X}`, so the output line is `X:` and openocd's
        #         mdw output is `0x<addr>: <word> <word>`
        # EXPECTED: magic 0x636d726b, count 7, pc 0x1000011c, cfsr 00008200
        st = pp.parse_chip_state(self.OPENOCD_SAMPLE)
        self.assertEqual(st["repeat_magic"], pp.REPEAT_MAGIC)
        self.assertEqual(st["repeat_count"], 7)
        self.assertEqual(st["pc"], "0x1000011c")
        self.assertEqual(st["cfsr"], "00008200")

    def test_the_slot4_reading_has_no_magic(self):
        # ORACLE: SPEC
        # SOURCE: AGENTS.md rule 5a: reading slot 4 (the SDK's) returns a clean
        #         zero; the probe must not build a verdict on it
        # EXPECTED: a mdw of the SDK slot parses but fails the magic check
        text = "SCRATCH:\n0x400d801c: 00000000 00000000 \nPC:\npc (/32): 0x1000\n"
        st = pp.parse_chip_state(text)
        self.assertIsNone(pp.soak_count(st))

    def test_empty_output_is_empty(self):
        # ORACLE: REQUIREMENT
        # SOURCE: a session that did not answer must not invent a reading
        # EXPECTED: {}
        self.assertEqual(pp.parse_chip_state(""), {})


class TestResultsFile(unittest.TestCase):

    def test_old_bare_mapping_is_read(self):
        # ORACLE: SPEC
        # SOURCE: probe.py 1.x wrote a bare mapping; the layout is documented in
        #         probe_parse.load_results
        # EXPECTED: records are returned and command is None
        with open(os.path.join(FIXTURES, "results-bare.json")) as fh:
            results, command = pp.load_results(json.load(fh))
        self.assertTrue(results)
        self.assertIsNone(command)

    def test_wrapper_is_read(self):
        # ORACLE: SPEC
        # SOURCE: probe.py 2.x writes {"schema", "command", "results"}
        # EXPECTED: records are returned and the command line is recovered
        with open(os.path.join(FIXTURES, "results-wrapper.json")) as fh:
            results, command = pp.load_results(json.load(fh))
        self.assertTrue(results)
        self.assertIn("tools/probe.py", command)

    def test_dump_round_trips(self):
        # ORACLE: SPEC
        # SOURCE: the results.json schema documented in probe.py's docstring
        # EXPECTED: schema tag and command are written, results survive a round trip
        results = {"300000/auto/1/1": {"khz": 300000, "result": "ok"}}
        dumped = pp.dump_results(results, "tools/probe.py --board pico2")
        self.assertEqual(dumped["schema"], pp.RESULTS_SCHEMA)
        self.assertEqual(dumped["command"], "tools/probe.py --board pico2")
        self.assertEqual(pp.load_results(dumped), (results, "tools/probe.py --board pico2"))

    def test_real_records_have_the_documented_fields(self):
        # ORACLE: REQUIREMENT
        # SOURCE: probe.py result record (fields the report and check_results.py
        #         consume); toolchain-ladder.sh reads scores/khz/mt/compiler
        # EXPECTED: the fields are present on a real stored record
        for rec in record("results-wrapper.json").values():
            for field in ("khz", "mt", "rep", "result", "scores", "validated",
                          "errors", "readback", "checks", "compiler"):
                self.assertIn(field, rec)
            for field in ("flash verified", "a score", "validated",
                          "no CoreMark errors", "clock landed where asked"):
                self.assertIn(field, rec["checks"])


class TestVreg(unittest.TestCase):

    def test_fallback_has_160v_at_sel_19(self):
        # ORACLE: SPEC
        # SOURCE: pico-sdk hardware/vreg.h numbering (AGENTS.md: 1.60 V = sel 19;
        #         the RP2350 ladder has gaps and 1.45/1.55 do not exist)
        # EXPECTED: sel 19 -> VREG_VOLTAGE_1_60, sel 11 -> VREG_VOLTAGE_1_10
        self.assertEqual(pp.VREG_NAME_FALLBACK[19], "VREG_VOLTAGE_1_60")
        self.assertEqual(pp.VREG_NAME_FALLBACK[11], "VREG_VOLTAGE_1_10")
        self.assertNotIn(20, [k for k, v in pp.VREG_NAME_FALLBACK.items()
                              if v == "VREG_VOLTAGE_1_60"])

    def test_parses_an_sdk_style_header(self):
        # ORACLE: SPEC
        # SOURCE: the SDK header's `NAME = 0bBBBBB` assignment form
        # EXPECTED: the select value is the decoded binary literal
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "src/rp2_common/hardware_vreg/include/hardware")
            os.makedirs(path)
            with open(os.path.join(path, "vreg.h"), "w") as fh:
                fh.write("enum {\n VREG_VOLTAGE_1_10 = 0b01011,\n"
                         " VREG_VOLTAGE_1_60 = 0b10011,\n};\n")
            table = pp.vreg_table(tmp)
        self.assertEqual(table[11], "VREG_VOLTAGE_1_10")
        self.assertEqual(table[19], "VREG_VOLTAGE_1_60")

    def test_macro_of_accepts_name_and_number(self):
        # ORACLE: REQUIREMENT
        # SOURCE: --vreg help text: an SDK macro name or a number
        # EXPECTED: both spellings resolve to the same macro
        table = pp.VREG_NAME_FALLBACK
        self.assertEqual(pp.vreg_macro_of(table, "VREG_VOLTAGE_1_65"),
                         "VREG_VOLTAGE_1_65")
        self.assertEqual(pp.vreg_macro_of(table, "1.65"), "VREG_VOLTAGE_1_65")

    def test_macro_of_refuses_a_voltage_the_sdk_lacks(self):
        # ORACLE: SPEC
        # SOURCE: pico-sdk vreg ladder: 1.45 and 1.55 are not values
        # EXPECTED: UsageError, not a generated board file for a setting that
        #           does not exist
        with self.assertRaises(pp.UsageError):
            pp.vreg_macro_of(pp.VREG_NAME_FALLBACK, "1.55")

    def test_sel_of_round_trips(self):
        # ORACLE: SPEC
        # SOURCE: the SDK table is a bijection between sel and macro
        # EXPECTED: sel of VREG_VOLTAGE_1_60 is 19
        self.assertEqual(pp.vreg_sel_of(pp.VREG_NAME_FALLBACK, "VREG_VOLTAGE_1_60"), 19)


class TestBuildOptions(unittest.TestCase):

    def test_cflags_release(self):
        # ORACLE: REQUIREMENT
        # SOURCE: probe_parse.cflags_release docstring: CMake's default is
        #         `-g -O3 -DNDEBUG`; an -O in --cflags replaces the level
        # EXPECTED: None for the default; the level is not doubled
        self.assertIsNone(pp.cflags_release(None))
        self.assertIsNone(pp.cflags_release(""))
        self.assertEqual(pp.cflags_release("-O2"), "-g -DNDEBUG -O2")
        self.assertEqual(pp.cflags_release("-DCOREMARK_SKIP_MATRIX"),
                         "-g -DNDEBUG -O3 -DCOREMARK_SKIP_MATRIX")
        self.assertEqual(pp.cflags_release("-Os"), "-g -DNDEBUG -Os")

    def test_cflags_tag(self):
        # ORACLE: REQUIREMENT
        # SOURCE: the tag is used in results.json keys and log filenames (existing
        #         records use the leading `-` spelling, so it is preserved)
        # EXPECTED: filename-safe, empty for the default set
        self.assertEqual(pp.cflags_tag(None), "")
        self.assertEqual(pp.cflags_tag("-O2"), "-O2")
        self.assertEqual(pp.cflags_tag("-DCOREMARK_SKIP_STATE -DCOREMARK_SKIP_MATRIX"),
                         "-DCOREMARK_SKIP_STATE_-DCOREMARK_SKIP_MATRIX")

    def test_parse_points_khz_and_mhz(self):
        # ORACLE: REQUIREMENT
        # SOURCE: --points help text: "comma separated kHz (or MHz)"
        # EXPECTED: a value <= 10000 is MHz, anything larger is already kHz
        self.assertEqual(pp.parse_points("240000,300,520000"),
                         [240000, 300000, 520000])
        self.assertEqual(pp.parse_points(" 520000 "), [520000])

    def test_parse_points_refuses_garbage(self):
        # ORACLE: REQUIREMENT
        # SOURCE: workspace exit-code convention: INVALID_USAGE is 2
        # EXPECTED: UsageError for a non-number, zero and an empty list
        for bad in ("abc", "0", "-5", ","):
            with self.assertRaises(pp.UsageError, msg=bad):
                pp.parse_points(bad)

    def test_toolchain_taken_checks_the_prefix(self):
        # ORACLE: REQUIREMENT
        # SOURCE: AGENTS.md rule 7 / TOOLCHAIN ladder method: the SDK falls back
        #         to PATH silently, so the build's compiler must be inside the
        #         prefix that was asked for
        # EXPECTED: inside True, outside False, missing False
        with tempfile.TemporaryDirectory() as tmp:
            prefix = os.path.join(tmp, "tc")
            other = os.path.join(tmp, "other")
            os.makedirs(os.path.join(prefix, "bin"))
            os.makedirs(os.path.join(other, "bin"))
            inside = os.path.join(prefix, "bin", "arm-none-eabi-gcc")
            outside = os.path.join(other, "bin", "arm-none-eabi-gcc")
            for path in (inside, outside):
                open(path, "w").close()
            self.assertTrue(pp.toolchain_taken(prefix, inside))
            self.assertFalse(pp.toolchain_taken(prefix, outside))
            self.assertFalse(pp.toolchain_taken(prefix, None))
            self.assertFalse(pp.toolchain_taken(None, inside))

    def test_toolchain_taken_accepts_clang_in_the_same_prefix(self):
        # ORACLE: REQUIREMENT
        # SOURCE: TOOLCHAINS.md: an LLVM ET tarball carries clang and the gcc
        #         driver; the SDK may pick either one from the same prefix
        # EXPECTED: clang inside the prefix is still "taken"
        with tempfile.TemporaryDirectory() as tmp:
            prefix = os.path.join(tmp, "llvm")
            os.makedirs(os.path.join(prefix, "bin"))
            clang = os.path.join(prefix, "bin", "clang")
            open(clang, "w").close()
            self.assertTrue(pp.toolchain_taken(prefix, clang))


class TestPll(unittest.TestCase):

    def test_known_reachable_and_unreachable_clocks(self):
        # ORACLE: SPEC
        # SOURCE: RP2350/RP2040 PLL arithmetic (12 MHz XOSC, fbdiv 16..320,
        #         VCO 750-1600 MHz, /p1/p2); MEASUREMENTS.md: 550 and 560 MHz
        #         "looked like failures until the state line showed the CPU was
        #         still at 150 MHz" -- the PLL cannot land on them
        # EXPECTED: 520/564/150 reachable, 550/560 not
        for khz in (150000, 520000, 564000):
            self.assertIsNotNone(pp.pll_reachable(khz), khz)
        for khz in (550000, 560000):
            self.assertIsNone(pp.pll_reachable(khz), khz)


if __name__ == "__main__":
    unittest.main()
