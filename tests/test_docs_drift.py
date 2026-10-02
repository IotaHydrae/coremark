#!/usr/bin/env python3
"""Guards against the docs and the code drifting apart.

A knowledge base is only worth reading if its claims still match the thing they
describe.  These tests read the sources this repository's documents make claims
about -- the port's console format, the repeat counter's slots, the CMake
defaults, the pico-turbo board files -- and fail when a claim and the code stop
agreeing.  They are host-only and touch no hardware.

Run:

    python3 -m unittest discover -s tests -v
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLS = os.path.join(ROOT, "tools")
sys.path.insert(0, TOOLS)

import probe_parse as pp  # noqa: E402


def read_text(path):
    with open(path, errors="replace") as fh:
        return fh.read()


class TestPortFormatMatchesParser(unittest.TestCase):
    """The console contract: what core_portme.c prints, probe_parse reads."""

    def setUp(self):
        self.portme = read_text(os.path.join(ROOT, "rpi-pico", "core_portme.c"))
        self.main = read_text(os.path.join(ROOT, "core_main.c"))

    def test_state_line_format(self):
        # ORACLE: SPEC (the producer's own printf format)
        # SOURCE: rpi-pico/core_portme.c portable_init()
        # EXPECTED: every field probe_parse.parse_state_line consumes is in the
        #           format string, and a line with those fields parses
        for fragment in ("PICO-TURBO: %lu kHz asked, %lu kHz configured, ",
                         "%lu kHz measured, vreg sel %u, flash %lu kHz, ",
                         "clk_peri %lu kHz, usb %s\\n"):
            self.assertIn(fragment, self.portme)
        st = pp.parse_state_line(
            "PICO-TURBO: 520000 kHz asked, 520000 kHz configured, 520000 kHz "
            "measured, vreg sel 19, flash 52000 kHz, clk_peri 520000 kHz, usb ok")
        self.assertEqual(st["vreg_sel"], 19)
        self.assertIs(st["usb_ok"], True)

    def test_repeat_magic_and_slots(self):
        # ORACLE: SPEC (the producer's own constants)
        # SOURCE: rpi-pico/core_portme.c CORE_REPEAT_MAGIC / _MAGIC_IDX / _COUNT_IDX
        # EXPECTED: probe_parse's magic and slots equal the port's
        self.assertIn("CORE_REPEAT_MAGIC 0x636d726bu", self.portme)
        self.assertIn("CORE_REPEAT_MAGIC_IDX 6u", self.portme)
        self.assertIn("CORE_REPEAT_COUNT_IDX 7u", self.portme)
        self.assertEqual(pp.REPEAT_MAGIC, 0x636D726B)
        self.assertEqual((pp.MAGIC_SLOT, pp.COUNT_SLOT), (6, 7))

    def test_repeat_counter_lines(self):
        # ORACLE: SPEC (the producer's own printf formats)
        # SOURCE: rpi-pico/core_portme.c portable_fini()
        # EXPECTED: the strings probe_parse's counter/all-finished regexes match
        self.assertIn('"COREMARK-REPEAT: run %lu of %d\\n"', self.portme)
        self.assertIn('"COREMARK-REPEAT: all %d runs finished\\n"', self.portme)
        self.assertEqual(pp.RE_COUNTER.findall("COREMARK-REPEAT: run 7 of 10"),
                         ["7"])
        self.assertEqual(pp.RE_ALL_FINISHED.findall("COREMARK-REPEAT: all 10 runs finished"),
                         ["10"])

    def test_banner_and_score_lines(self):
        # ORACLE: SPEC (the producers' own printf formats)
        # SOURCE: rpi-pico/core_portme.c (banner), core_main.c (score)
        # EXPECTED: the strings probe_parse counts and matches
        self.assertIn("CoreMark benchmark running", self.portme)
        self.assertIn('ee_printf("CoreMark 1.0 : %f / %s %s"', self.main)
        self.assertEqual(pp.RE_SCORE.findall("CoreMark 1.0 : 1465.399973 / GCC -O3"),
                         ["1465.399973"])

    def test_item_error_lines(self):
        # ORACLE: SPEC (the producer's own printf formats)
        # SOURCE: core_main.c `[%u]ERROR! <part> crc 0x%04x - should be 0x%04x`
        # EXPECTED: a real-format line is what probe_parse.item_errors returns
        self.assertIn('"[%u]ERROR! list crc 0x%04x - should be 0x%04x\\n"', self.main)
        self.assertIn('"[%u]ERROR! matrix crc 0x%04x - should be 0x%04x\\n"', self.main)
        self.assertIn('"[%u]ERROR! state crc 0x%04x - should be 0x%04x\\n"', self.main)
        line = "[0]ERROR! state crc 0x0000 - should be 0x8e3a"
        self.assertEqual(pp.item_errors(line), [line])

    def test_ten_second_rule_text(self):
        # ORACLE: SPEC (the producer's own printf format)
        # SOURCE: core_main.c: the under-ten-seconds error, and upstream README
        #         run rule 1 ("at least 10 secs")
        # EXPECTED: the string probe_parse keys on is in the source
        self.assertIn('"ERROR! Must execute for at least 10 secs for a valid result!\\n"',
                      self.main)
        self.assertTrue(pp.parse_console(
            "ERROR! Must execute for at least 10 secs for a valid result!\n"
            "Errors detected\n")["short_run"])


class TestBuildDefaults(unittest.TestCase):
    """The CMake options the documents quote, against rpi-pico/CMakeLists.txt."""

    def setUp(self):
        self.cmake = read_text(os.path.join(ROOT, "rpi-pico", "CMakeLists.txt"))
        self.readme = read_text(os.path.join(ROOT, "rpi-pico", "README.md"))

    def test_soak_and_multithread_defaults(self):
        # ORACLE: REQUIREMENT
        # SOURCE: AGENTS.md option table: COREMARK_REPEAT default 1,
        #         COREMARK_MULTITHREAD default 1
        # EXPECTED: exactly one is the default and two contexts is opt-in
        self.assertIn("set(COREMARK_REPEAT 1)", self.cmake)
        self.assertIn("set(COREMARK_MULTITHREAD 1)", self.cmake)

    def test_usb_connect_wait_timeout_matches_the_readme(self):
        # ORACLE: REQUIREMENT
        # SOURCE: CMakeLists sets PICO_STDIO_USB_CONNECT_WAIT_TIMEOUT_MS so a boot
        #         waits for the reader; the README states the value
        # EXPECTED: both say 20000 ms, and the stale 3000 ms is gone
        self.assertIn("set(PICO_STDIO_USB_CONNECT_WAIT_TIMEOUT_MS 20000)", self.cmake)
        self.assertIn("20000 ms", self.readme)
        self.assertNotIn("3000 ms", self.readme)

    def test_measured_table_names_the_luckfox_board(self):
        # ORACLE: REQUIREMENT
        # SOURCE: rpi-pico/MEASUREMENTS.md: 422.71 / 845.41 / 1512.07 / 1465.38
        #         are the Luckfox Pico 2's rows, not a generic "Pico 2"
        # EXPECTED: the port README does not attribute them to a plain Pico 2
        self.assertIn("Luckfox Pico 2", self.readme)

    def test_flash_comment_marks_openocd_verify_as_not_evidence(self):
        # ORACLE: REQUIREMENT
        # SOURCE: AGENTS.md hardware discipline 2: `openocd program ... verify`
        #         can report "Verified OK" for a partial write; only the read-back
        #         counts
        # EXPECTED: the CMake comment says so, so the two flash targets are not
        #           mistaken for a verified path
        self.assertIn("not evidence", self.cmake)


class TestPicoTurboBoardFiles(unittest.TestCase):
    """The board files RANKINGS.md section 6 says carry these numbers."""

    BOARDS = {"pico_w.cmake": (440000, 110000),
              "pico2.cmake": (564000, 57000),
              "weact_rp2350a.cmake": (520000, 52000),
              "pico.cmake": (420000, None)}

    def setUp(self):
        self.boards = os.path.join(os.path.dirname(ROOT), "pico-turbo", "boards")
        if not os.path.isdir(self.boards):
            self.skipTest("pico-turbo is not checked out next to this repository")

    def test_ceilings_match_rankings(self):
        # ORACLE: SPEC
        # SOURCE: RANKINGS.md section 6 (and pico-turbo's boards/*.cmake)
        # EXPECTED: each board file's _PLATFORM_MAX_KHZ and _FLASH_MAX_KHZ are the
        #           ones the rankings table says it carries
        for name, (ceiling, flash) in self.BOARDS.items():
            text = read_text(os.path.join(self.boards, name))
            self.assertIn("set(_PLATFORM_MAX_KHZ %d)" % ceiling, text, name)
            if flash is not None:
                self.assertIn("set(_FLASH_MAX_KHZ %d)" % flash, text, name)


if __name__ == "__main__":
    unittest.main()
