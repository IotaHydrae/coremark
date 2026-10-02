#!/usr/bin/env python3
"""Offline tests for the probe.py command-line surface and its constants.

Nothing here attaches a probe, builds, or flashes: `--help`/`--version` and the
argument-validation paths exit before any of that, and the remaining tests
import the module and inspect its documented constants.

Run:

    python3 -m unittest discover -s tests -v
"""

import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLS = os.path.join(ROOT, "tools")
sys.path.insert(0, TOOLS)

import probe  # noqa: E402


def run_probe(*argv, env=None):
    cmd = [sys.executable, os.path.join(TOOLS, "probe.py")] + list(argv)
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, timeout=120, env=env)


def read_text(path):
    with open(path, errors="replace") as fh:
        return fh.read()


class TestExitCodes(unittest.TestCase):
    """The workspace convention, as constants probe.py returns."""

    def test_constants(self):
        # ORACLE: REQUIREMENT
        # SOURCE: pud_ws/AGENTS.md -- 0 ok / 1 FAIL / 2 INVALID_USAGE /
        #         3 ENVIRONMENT_ERROR / 4 TIMEOUT / 5 INCONCLUSIVE
        # EXPECTED: probe.py exposes exactly those numbers
        self.assertEqual((probe.EXIT_OK, probe.EXIT_FAIL, probe.EXIT_USAGE,
                          probe.EXIT_ENV, probe.EXIT_TIMEOUT, probe.EXIT_INCONCLUSIVE),
                         (0, 1, 2, 3, 4, 5))


class TestCli(unittest.TestCase):

    def test_version_exits_zero_and_names_the_schema(self):
        # ORACLE: REQUIREMENT
        # SOURCE: workspace CLI convention (--version)
        # EXPECTED: exit 0, "probe.py <version>" and the results schema
        r = run_probe("--version")
        self.assertEqual(r.returncode, 0)
        self.assertIn("probe.py %s" % probe.__version__, r.stdout)
        self.assertIn(probe.probe_parse.RESULTS_SCHEMA, r.stdout)

    def test_help_exits_zero_and_lists_workspace_options(self):
        # ORACLE: REQUIREMENT
        # SOURCE: workspace CLI convention (--help/--version/--timeout/--quiet/--verbose)
        # EXPECTED: all five options are advertised and the hidden reader is not
        r = run_probe("--help")
        self.assertEqual(r.returncode, 0)
        for option in ("--help", "--version", "--timeout", "--quiet", "--verbose"):
            self.assertIn(option, r.stdout)
        self.assertNotIn("--reader", r.stdout)

    def test_unknown_option_is_invalid_usage(self):
        # ORACLE: REQUIREMENT
        # SOURCE: workspace exit-code convention: INVALID_USAGE = 2
        # EXPECTED: argparse rejects it with 2
        self.assertEqual(run_probe("--definitely-not-an-option").returncode, 2)

    def test_quiet_and_verbose_are_mutually_exclusive(self):
        # ORACLE: REQUIREMENT
        # SOURCE: the two flags mean opposite things
        # EXPECTED: INVALID_USAGE (2)
        self.assertEqual(run_probe("--quiet", "--verbose").returncode, 2)

    def test_bad_points_is_invalid_usage(self):
        # ORACLE: REQUIREMENT
        # SOURCE: probe_parse.parse_points
        # EXPECTED: a bad value is 2 even with no board and no SDK, because the
        #           command line is checked before the environment
        r = run_probe("--points", "abc")
        self.assertEqual(r.returncode, 2)
        self.assertIn("usage:", r.stdout)

    def test_missing_environment_is_environment_error(self):
        # ORACLE: REQUIREMENT
        # SOURCE: workspace rule: a missing SDK/tool/probe is ENVIRONMENT_ERROR
        #         (3), not FAIL and not INVALID_USAGE
        # EXPECTED: 3 with the reason on stdout
        env = dict(os.environ)
        with tempfile.TemporaryDirectory() as tmp:
            env["PICO_SDK_PATH"] = os.path.join(tmp, "no-such-sdk")
            env["PICO_TURBO_DIR"] = os.path.join(tmp, "no-such-turbo")
            r = run_probe("--identify-only", env=env)
        self.assertEqual(r.returncode, 3)
        self.assertIn("no pico-sdk", r.stdout)


class TestConstants(unittest.TestCase):

    def test_platform_ladder_and_ceiling(self):
        # ORACLE: SPEC
        # SOURCE: rpi-pico/MEASUREMENTS.md + RANKINGS.md section 5: RP2040 stock
        #         125 MHz / ceiling 420 MHz; RP2350 stock 150 MHz
        # EXPECTED: the constants the ladder walks from
        self.assertEqual(probe.PLATFORM["rp2040"]["stock"], 125000)
        self.assertEqual(probe.PLATFORM["rp2040"]["ceiling"], 420000)
        self.assertEqual(probe.PLATFORM["rp2350"]["stock"], 150000)

    def test_usb_ids_are_the_documented_ones(self):
        # ORACLE: SPEC
        # SOURCE: AGENTS.md hardware discipline 8b: RP2040 bootrom 2e8a:0003,
        #         RP2350 bootrom 2e8a:000f; applications' CDC 0009/000A
        # EXPECTED: the constants match
        self.assertEqual(probe.BOOTSEL_PIDS, (0x0003, 0x000F))
        self.assertEqual(probe.APP_PIDS, (0x0009, 0x000A))
        self.assertEqual(probe.PICO_VID, 0x2E8A)

    def test_soak_default_is_ten(self):
        # ORACLE: REQUIREMENT
        # SOURCE: AGENTS.md: `tools/probe.py --board pico_w` defaults to a 10-run soak
        # EXPECTED: the argparse default is 10
        source = read_text(os.path.join(TOOLS, "probe.py"))
        self.assertIn('"--soak", type=int, default=10', source)


if __name__ == "__main__":
    unittest.main()
