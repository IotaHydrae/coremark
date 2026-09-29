# The toolchain ladder: one board, one configuration, six compilers

CoreMark is a compiler benchmark as much as a hardware one.  [RANKINGS.md](RANKINGS.md)
section 8 established that the *same source* built by two compilers differs by 5.30% at
one clock and one voltage; this file is the part that follows from it -- the same
measurement run across the release versions anyone might have installed, so that "which
compiler" can be answered with a number instead of a shrug.

Everything below is one board (WeAct RP2350A, RP2350A rev 2, W25Q32FV/JV), one clock
(520 MHz), one voltage (1.60 V, the top of pico-turbo's table), one divider (DIV 10, 52
MHz of flash clock), one source, one flag set (`-O3`, CMake's `Release` default, the only
one the SDK allows by default), and one compiler version as the only variable.  Each
toolchain also ran the 150 MHz stock point, which is the control: if a number moved
because of the *board* or the *supply* that day, both columns would move together.

| GCC | `arm-none-eabi-gcc --version` | 150 MHz | 520 MHz, 1 core | 520 MHz, 2 cores | per MHz (1 core) | against 16.2.0 |
|---|---|---|---|---|---|---|
| 12.2.0 | Arch 12.2.0, binutils 2.39, newlib 4.1.0 | 437.575 | 1516.929 | 2712.285 | 2.9172 | **+3.52%** |
| 13.2.0 | Arch 13.2.0, binutils 2.41, newlib 4.3.0 | 445.111 | **1543.052** | **2768.943** | **2.9674** | **+5.30%** |
| 13.2.1 | Debian 15:13.2.rel1-2 (the committed binary, single core only) | -- | 1543.051 | -- | 2.9674 | +5.30% |
| 14.1.0 | Arch 14.1.0, binutils 2.42, newlib 4.4.0 | 430.509 | 1492.433 | 2711.127 | 2.8701 | +1.84% |
| 14.2.0 | Arch 14.2.0, binutils 2.43, newlib 4.5.0 | 434.087 | 1504.837 | 2756.757 | 2.8939 | +2.69% |
| 16.1.0 | Arch 16.1.0, binutils 2.46.1, newlib 4.6.0 | 422.729 | 1465.466 | 2600.491 | 2.8182 | +0.004% |
| 16.2.0 | Arch 16.2.0, binutils 2.47, newlib 4.6.0 (this machine's own) | 422.711 | 1465.401 | 2613.904 | 2.8181 | -- |

The dual-core column is one run each, and dual-core runs on this board scatter by a few
tenths of a percent ([RANKINGS.md](RANKINGS.md) section 4) -- so read the 14.x and 13.x
dual rows as percentages, not as four decimal places, and read 16.1.0 against 16.2.0 as
"the same compiler" rather than as a 0.5% difference.

## What the ladder says

**It is not a slope, it is a step.**  The newest two releases produce identical code
quality for this workload (2.8182 against 2.8181 per MHz, and their 150 MHz rows agree to
0.004%), and everything older is faster -- but not in version order: 13.2.0 is the fastest
of the six, 12.2.0 is faster than both 14.x releases, and 14.1.0 is the slowest of the
pre-16 group.  Choosing a compiler for this workload is not a matter of taking the newest
or the oldest; the two useful bands happen to be a release apart.

**The effect is a multiplier on the clock, not a percentage that grows with it.**  Every
toolchain's 150 MHz deficit against 16.2.0 matches its 520 MHz deficit to three significant
figures: 13.2.0 is +5.299% at 150 MHz and +5.30% at 520, 12.2.0 is +3.516% and +3.52%,
14.2.0 is +2.691% and +2.69%.  That is a compiler making every unit of work cost a fixed
number of extra instructions, whatever the clock is doing -- the same conclusion the flag
experiment in section 8 reaches from the other side, and the same one the strict linearity
of score with clock reaches from a third.

**The second core does not inherit the first core's ratio.**  The dual-core column moves by
a different amount than the single-core column for the same compiler: +3.76% against
+3.52% for 12.2.0, +5.93% against +5.30% for 13.2.0, and +5.46% against +2.69% for 14.2.0.
Equivalently, the "one core is worth 1.78x two" factor everyone quotes is itself a
compiler's number, and here it runs from 1.7745 (16.1.0) to 1.8319 (14.2.0).  So the
dual-core score is affected by the toolchain in a way the single-core score cannot predict,
and a dual-core comparison is only safe inside one compiler -- which is how every dual-core
row in this repository was measured.

**The packager is not the variable.**  Debian's 13.2.1 and Arch's 13.2.0 are different
builds of the same upstream release, with different binutils, different newlib and
different configure flags, and their 520 MHz single-core scores are 1543.051 and 1543.052 --
identical to six significant figures.  What moves the score is the compiler release, not
who packaged it.

**What this does not change.**  Every ratio, ceiling and stability result in
[RANKINGS.md](RANKINGS.md) and in pico-turbo's measurements was measured *inside* one
compiler, so all of them stand: where a board stops, what voltage a clock needs, the
linearity, the flash divider behaviour.  What it changes is the reading of absolute
constants: 2.8181 per MHz on an RP2350 is GCC 16.2.0's number, 2.9674 is GCC 13.2.0's,
and a row without its compiler is not reproducible.  That is why
`tools/probe.py` records the compiler with every point and why `--toolchain` asserts it.

## Method, because a ladder of compilers is easy to get wrong

* The toolchains are the Arch Linux Archive's packages, unpacked into one prefix each
  (compiler, binutils and newlib from the same day, which is what a distribution build
  would have paired).  Nothing was installed system-wide, and 16.2.0 is this machine's
  own package, not a copy of one.
* Each build is pointed at its prefix with the SDK's own `PICO_TOOLCHAIN_PATH`.
* **The prefix is then asserted, not assumed.**  The SDK searches it first but falls back
  to the compiler on `PATH` with nothing but a warning, so a ladder that trusts the
  environment variable can measure one compiler six times and print a flat line.
  `probe.py --toolchain` reads the build's own `CMake_C_COMPILER` out of the CMakeCache
  and refuses the point when it is not the one asked for; every row above passed that
  check, and the compiler string it recorded is in each `results.json`.
* Each point is built, written to flash, **read back and compared byte for byte**, run,
  and kept only if the application validated its own result and the state line showed the
  clock the chip measured *itself* at being the clock it was asked for.  The 520 MHz rows
  all report `520000 kHz measured, vreg sel 19, flash 52000 kHz`.
* One output directory per toolchain: a shared build directory keeps the first compiler in
  its CMakeCache, and every later run would then be the same measurement again.

## Reproducing it

```bash
PROXY=host:port tools/toolchain-ladder.sh              # every release in the table
PROXY=host:port tools/toolchain-ladder.sh 13.2.0 16.2.0  # or named ones
```

The script downloads the packages, unpacks them under `$TC_DIR` (default `$HOME/tc`),
verifies each archive before using it (a resumed download can leave a truncated stream
that fails later as a compiler which will not run), runs the ladder, and prints the table.
The proxy variable is only needed if the archive is not reachable directly.

## Not measured yet

* **Anything other than GCC.**  ARM's own release toolchains and `arm-none-eabi-clang`
  are the obvious next rows, and they are the ones a user is most likely to have.
* **Older than 12.2.0** and the 15.x releases, which Arch skipped for this target.
* **Whether the ladder looks the same on an RP2040.**  The 5.30% has only ever been
  measured on an RP2350; one Pico W point under GCC 13.2.0 would say whether the M0+
  moves by the same factor, and that is the same open question as
  [RANKINGS.md](RANKINGS.md) section 8's.
* **Why 13.2.0 wins.**  The instruction-mix difference is visible in the disassembly
  (2.5% more `.text`, 2.1% more instructions, and a CRC kernel that grew from 166 to 211
  instructions in the newer compiler), but which pass is responsible has not been
  established, and the flag axis that might have explained it is closed: see section 8.
