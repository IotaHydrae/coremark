# CoreMark rankings

Every configuration measured in this repository, ranked, with the per-clock numbers
that make one chip comparable with another.

**What this repository is for.**  It is the bench.  Its job is to find where a chip
or a board stops being reliable, and to leave behind a configuration that is known
to work.  That configuration then goes *back into
[pico-turbo](https://github.com/IotaHydrae/pico-turbo)* as a board file, because the
clock, the voltage and the flash divider belong to the library that applications
link against -- not to the benchmark they were measured with.  `tools/probe.py` is
that whole loop in one command: measure, write a report, propose `boards/<board>.cmake`.

**What a row means.**  Every number below was measured by the `rpi-pico` port in
this repository, with pico-turbo owning the clock, voltage and flash divider.  A row
exists only if the application validated its own result (`Correct operation
validated`), if the clock the chip *measured itself at* was the clock that had been
asked for, and if the flash had been written, read back and compared byte for byte
first.  The method, and the reasons for it, are in
[AGENTS.md](AGENTS.md) and [rpi-pico/MEASUREMENTS.md](rpi-pico/MEASUREMENTS.md).

---

## 0. The boards on this bench

| Board | Chip | Flash | How the flash part is known |
|---|---|---|---|
| Official Pico 2 | RP2350 rev 2 (A2) | **Winbond W25Q32FV/JV, 4 MB** | measured: openocd's probe reports `win w25q32fv/jv id = 0x1640ef size = 4096 KiB` over SWD |
| Luckfox Pico 2 | RP2350A rev 2 | **Puya PY25Q32HB, 4 MB** | the vendor's board description -- *not* measured here; its JEDEC id wants reading when the board is next connected |
| WeAct Studio RP2350A V1.0 | RP2350A rev 2 | **Winbond W25Q32FV/JV, 4 MB** | measured: `win w25q32fv/jv id = 0x1640ef size = 4096 KiB` over SWD -- the same part as the official board's |
| Official Pico W | RP2040 rev 2 (B2) | **Winbond W25Q16JV, 2 MB** | measured: `win w25q16jv id = 0x1540ef size = 2048 KiB` |
| AirMech RP2040 | RP2040 | unknown | never probed; its numbers here are pico-turbo tiers, not CoreMark rows |

The flash part matters more than it looks.  It is one of the two things a board file
is really about -- the other being the supply -- and it is why `boards/pico_w.cmake`
carries a 110 MHz flash ceiling while `boards/pico2.cmake`, shared by an official board
and a clone with different flash parts, has to carry the conservative one.

## 1. Best validated configuration, per board

Ranked by single-core score, which is the currency every board here has.  The score
depends on the compiler as well as the board -- Debian's GCC 13.2.1 scores 1.053x
what Arch's GCC 16.2.0 does on this workload (section 8) -- so these are the numbers a
16.2.0-class compiler gives, and a row measured under anything else says so.

| Rank | Board | Chip | Clock | Voltage | Flash | Cores | CoreMark 1.0 | It/s per MHz |
|---|---|---|---|---|---|---|---|---|
| 1 | Official Pico 2 | RP2350A | **564 MHz** | 1.60 V | 56.4 MHz (DIV 10, derived) | 1 | **1589.37** | 2.818 |
| 2 | Luckfox Pico 2 | RP2350A | **540 MHz** | 1.60 V | &le;57 MHz (divider not recorded; that board's ceiling) | 1 | **1521.74** | 2.818 |
| 3 | WeAct RP2350A V1.0 | RP2350A | **520 MHz** | 1.60 V | 52 MHz (DIV 10) | 1 | **1465.40** | 2.818 |
| 4 | Official Pico W | RP2040 B2 | **440 MHz** | 1.30 V | 110 MHz (DIV 4) | 1 | **832.21** | 1.891 |
| 5 | Official Pico W | RP2040 B2 | 420 MHz | 1.30 V | 105 MHz (DIV 4) | 1 | 794.39 | 1.891 |
| 6 | Official Pico W | RP2040 B2 | 240 MHz | 1.10 V (stock) | 60 MHz (DIV 4) | 1 | 453.93 | 1.891 |
| 7 | AirMech RP2040 | RP2040 | 420 MHz | 1.30 V | 105 MHz (DIV 4) | 1 | *(tiers from a pico-turbo search, not scored here)* | -- |

The WeAct row is where this document's 5.30% question gets its answer, and it is
worth reading twice: the same board, at the same clock and voltage and divider,
scored **1543.05** when it was measured under GCC 13.2.1 earlier the same evening.
The board did not change and neither did the configuration; the compiler did.

Dual-core rows, same boards:

| Board | Clock | Voltage | Cores | CoreMark 1.0 | vs one core |
|---|---|---|---|---|---|
| Official Pico 2 | 520 MHz | 1.60 V | 2 | **2622.08** | 1.789x |
| Official Pico 2 | 546 MHz | 1.60 V | 2 | *(2748.29 once, and hung joining core 1 once: PC in `core_stop_parallel` -- marginal)* | -- |
| Official Pico 2 | 564 MHz | 1.60 V | 2 | *(hard-faults before it prints anything)* | -- |
| Luckfox Pico 2 | 520 MHz | 1.60 V | 2 | 2612.70 | 1.786x |
| Official Pico W | 440 MHz | 1.30 V | 2 | **1484.79** | 1.784x |
| Official Pico W | 420 MHz | 1.30 V | 2 | 1417.30 | 1.784x |
| Luckfox Pico 2 | 300 MHz | 1.20 V | 2 | 1512.07 | 1.789x |
| WeAct RP2350A V1.0 | 520 MHz | 1.60 V | 2 | 2760.73 *(10-run soak mean, GCC 13.2.1 -- 2621.7 on this table's scale)* | 1.789x |

A second core buys **1.78-1.79x** on both platforms, at every clock measured: the
core is not what runs out, the memory they share is.  The WeAct board's 1.789x was
worked out inside one toolchain, which is the only way that ratio means anything.

## 2. Per-clock efficiency -- this is the chip, not the board

| Platform | Cores | Iterations/sec per MHz | Fitted over | Worst deviation |
|---|---|---|---|---|
| RP2350 (Cortex-M33) | 1 | **2.8180** | 150-564 MHz, 11 points, 3 boards | 0.001% |
| RP2350 (Cortex-M33) | 2 | 5.0425 | 520 MHz (official board) | -- |
| RP2040 (Cortex-M0+) | 1 | **1.8914** | 125-440 MHz, 7 points | 0.001% |
| RP2040 (Cortex-M0+) | 2 | 3.3745 | 420 and 440 MHz | 0.000% |

**A constant belongs to a chip and a compiler.**  These are what a compiler producing
the same code as Arch's GCC 16.2.0 gives; Debian's GCC 13.2.1 makes the same RP2350
do 2.9674 per MHz (section 8).  Every *ratio* here is safe -- both of its sides came
out of one toolchain, whichever it was -- but an absolute constant is not meaningful
without the toolchain next to it.

The RP2040 side has not been re-measured under the other compiler, and there is one
hint that it does not move by the same factor: the sample output in
[`rpi-pico/README.md`](rpi-pico/README.md), which names a 13.2.1 toolchain, reads
1.9544 per MHz where this table records 1.8914 -- 3.3% rather than 5.3%.  The sample
does not say which board it was taken on, so that is a question and not a correction;
re-running one RP2040 point under GCC 13.2.1 would settle it.

Two things fall out of that table.

* **The M33 does 1.490x the work per clock that the M0+ does** (single core;
  1.494x by the dual-core numbers).  It is the one number in this document that is
  *derived* from the measurements rather than measured itself.
* **The score is linear in the clock on both platforms, to within 0.001%**, from
  125 to 440 MHz on the RP2040 and 150 to 564 MHz on the RP2350, with the flash
  clock rising underneath (up to 110 MHz on the Pico W).  So the work stays in the
  chip's cache and none of the ceilings in section 4 is a memory wall -- they are
  all either the regulator, the PLL or the board.

The three RP2350 boards agree on 2.8180 to four decimal places despite different
vendors, flash parts and regulators -- and despite *different ceilings*, which is the
distinction this document keeps running into.  Doing a given amount of work per clock is
the chip's; how fast the chip can be made to do it is the board's.

## 3. What one board's clock is worth on another

Derived, using section 2 -- and the answer is the same whether it is worked out from
the single-core or the dual-core numbers, which is a check on the arithmetic:

| Configuration | Score | Equivalent on the other chip |
|---|---|---|
| **Pico W at 440 MHz, 1.30 V** (its best) | 832.21 single / 1484.79 dual | **RP2350 at ~295 MHz** (295.3 single, 294.5 dual) |
| Pico W at 420 MHz, 1.30 V | 794.39 / 1417.30 | RP2350 at ~281 MHz |
| Pico W at 240 MHz, stock volts | 453.93 | RP2350 at ~161 MHz |
| Pico 2 at 564 MHz, 1.60 V | 1589.37 | a Pico W would need **~840 MHz** -- twice what its regulator allows |
| Pico 2 at 520 MHz, both cores | 2622.08 | a Pico W would need ~777 MHz, both cores |

The closest *measured* RP2350 point to the Pico W's best is 300 MHz: 845.41 single
and 1509.70 dual, about 1.7% above it.  So a Pico W held at its absolute maximum --
440 MHz, the highest voltage its regulator is documented for -- and a Pico 2 at
295 MHz, one voltage step lower (1.20 V), do the same work.  As dynamic power goes
roughly as V^2 * f, that is of the order of half the power for the same score
(*estimated*, not measured -- it would take a current probe to make that a
measurement).

## 4. Stability: what was soaked, and how it held

A point that passes once is a data point, not a configuration.  These are the ones
that were repeated, each run rebooting through the bootrom so no run inherits a warm
chip:

| Board | Configuration | Runs | Validated | Spread | Mean |
|---|---|---|---|---|---|
| Official Pico 2 | 520 MHz, 1.60 V, 2 cores, DIV 8 | 50 | 50 | 0.0002% | 2622.081163 |
| Official Pico 2 | 520 MHz, 1.60 V, 2 cores, DIV 8 (repeat) | 10 | 10 | 0.0003% | 2622.486184 |
| Official Pico 2 | 520 MHz, 1.60 V, 2 cores, DIV 10 | 10 | 10 | 0.0271% | 2611.277278 |
| Official Pico 2 | 546 MHz, 1.60 V, 2 cores | 2 (single points) | **1** -- the other hung joining core 1 | -- |
| Official Pico 2 | 564 MHz, 1.60 V, 2 cores | 30 attempted | **0** -- it never ran: hard fault before its first line of output | -- |
| Luckfox Pico 2 | 520 MHz, 1.60 V, 2 cores | 36 | 36 | 0.39% | 2612.7 |
| Official Pico W | 440 MHz, 1.30 V, 2 cores | 30 | 30 | 0.0009% | 1484.793434 |
| Official Pico W | 440 MHz, 1.30 V, 2 cores (through the board file) | 10 | 10 | 0.0008% | 1484.788171 |
| Official Pico W | 420 MHz, 1.30 V, 2 cores | 20 | 20 | 0.0001% | 1417.303771 |
| WeAct RP2350A | 520 MHz, 1.60 V, 2 cores *(GCC 13.2.1 -- see section 8)* | 10 | 10 | 0.0041% | 2760.731614 |

The two older RP2350 boards score within 0.36% of each other and differ in spread by
three orders of magnitude.  Same chip, same firmware: the jitter is the board's supply
(the Luckfox board carries a 2 A buck-boost, the official one an LDO), and it shows up
as jitter long before it shows up as failure.  The WeAct board lands between them --
0.0041% over ten runs, twenty times the official board's spread and a hundred times
less than the clone's -- which is where a third supply should land.

Its mean is the one number in this table that cannot be compared directly with the
others: it was measured under GCC 13.2.1, and that compiler makes this workload run
5.30% faster -- 1.0530x (section 8).  *Divided* by that factor it is 2621.7, against the official
board's 2622.08 at the same clock -- 0.014% apart, which is a check on section 8 made
from a measurement that was not part of it: the compiler's factor is the same with two
cores as with one, and the same on a soak mean as on a single run.

## 5. Where each board stops

| Board | Highest validated clock | First clock that failed | Flash ceiling |
|---|---|---|---|
| Official Pico 2 | 564 MHz single core; **520 MHz with two** | 570 MHz (`isr_hardfault`, flash verified).  With two cores: 546 is marginal (one pass, one hang in `core_stop_parallel`) and 564 hard-faults | **between 109.2 and 112.8 MHz**: 104 and 109.2 MHz of flash clock validate, 112.8 MHz hard-faults and 130 MHz locks the chip up.  (The flash part is rated 133 MHz, so what that brackets is the part in this configuration -- QMI timing, board layout and all -- not the part on a datasheet.)  Odd dividers are fine here -- DIV 5 and DIV 7 both measured -- which is the RP2350's boot stage 2 behaving as its source says |
| Luckfox Pico 2 | 564 MHz | 570 MHz (does not bring up USB) | between 57 and 78.75 MHz |
| WeAct RP2350A V1.0 | **520 MHz** | 546 MHz (`isr_hardfault` at program counter `0x1000011c`, flash verified byte for byte, and it prints nothing first) -- under **both** compilers, so this one is not section 8's doing | not measured: the divider ladder has not been run on this board.  The fastest it was *shown* to hold is 52 MHz (DIV 10 at 520 MHz) |
| Official Pico W | **440 MHz** (see below) | 460 MHz untested | ≥110 MHz (DIV 4 at 440 MHz, soaked); DIV 2 = 210 MHz hangs, past the QSPI interface's 133 MHz |
| AirMech RP2040 | 420 MHz | 440 MHz (locks up) | 105 MHz (DIV 4) |

The two boards that built this table stop in the same place -- 564 passes, 570 fails,
on both -- and that was the evidence for ~565-570 MHz being the chip.  The WeAct board
stops 44 MHz below it, and the compiler is not the reason: 546 MHz hard-faults at the
*same program counter* under GCC 13.2.1 and under GCC 16.2.0, so the failure is a
property of that board rather than of the code that was running on it.  On RP2350 the
top is the board's as much as it is on RP2040 -- 564 is a ceiling a board has to
*reach*, not one the silicon hands out.

The RP2040 boards differ too: the official Pico W ran 440 MHz
where the clone locked up, so on RP2040 the top is the board's.  Voltage *tiers*, on
the other hand, agree across both RP2040 boards (260/360/390/420 -> sel
11/13/14/15): the tiers are the chip's, and the board decides how far past them it
will go.  A board file should be read with that in mind -- and measured, not
assumed, which is what `tools/probe.py` is for.

## 6. Where these numbers ended up in pico-turbo

| Board | pico-turbo board file | Carries |
|---|---|---|
| Official Pico W | `boards/pico_w.cmake` | ceiling 440 MHz, flash 110 MHz; profiles safe 240 / fast 300 / turbo 360 / **extreme 440** -- and extreme is the file's **default**, so `-DPICO_BOARD=pico_w` with nothing else applies the soaked configuration |
| Official Pico 2, Luckfox Pico 2 | `boards/pico2.cmake` | ceiling 564 MHz, flash 57 MHz; profiles safe 300 / fast 400 / **turbo 520** (both cores, soaked) / extreme 564 (one core only, and the file says so).  No default profile: the name is shared with clones whose flash and supply differ |
| WeAct RP2350A V1.0 | `boards/weact_rp2350a.cmake` | ceiling **520 MHz**, flash 52 MHz; profiles safe 300 / fast 400 / **turbo 500** / extreme **520** -- the four clock-ladder points that validated, with the voltage and the divider left to the library, so a build gets what was measured rather than the file's opinion of it.  No default profile: naming a board should not silently overclock it |
| AirMech RP2040, plain Pico | `boards/pico.cmake` | ceiling 420 MHz; profiles safe 240 / turbo 360 / extreme 400 |

Three gaps are visible in that table, and all three are on purpose:

* `boards/pico.cmake` describes a plain Pico that has not been on this bench at all;
  its numbers are inherited expectations, and `tools/probe.py --board pico` is one
  command away from replacing them with measurements.
* The second core costs headroom, and the number to quote is the *soaked* one: 520
  MHz with two cores has 50 consecutive runs here (and 36 on the clone), while 546
  with two cores has been seen to pass once and to hang once, and 564 with two cores
  hard-faults.  One core validates to 564.  A single number per board would hide
  that -- and so would a single lucky run, which is why the soak column exists.
* `boards/weact_rp2350a.cmake` carries a flash ceiling that was *shown* rather than
  measured: 52 MHz is the fastest divider this board ran at, and the ladder that would
  find the real one has not been run.  It is the conservative direction to be wrong in
  -- with no board file at all the library asks the flash for 130 MHz instead -- but
  raising it is a `--flash-ladder` run, not a datasheet.

## 7. Reading these numbers honestly

* **CoreMark is one workload.**  Integer and control-flow heavy.  The M33 also has an
  FPU, DSP instructions and double precision, and those would show a much wider gap
  than 1.49x; a pure I/O workload would show none of it.
* **Scores here are comparable across boards only at the same clock, cores, iteration
  rule and compiler** -- the port scales iterations with the clock so each run is about
  twelve seconds, which is CoreMark's own reporting rule, and the compiler is worth
  1.053x on its own (section 8).  A score quoted without its toolchain is not one
  somebody else can reproduce.
* **Anything marked derived** (the 1.490x ratio, the equivalent-frequency table) is
  arithmetic on measured numbers and inherits their error, which is small: the
  linearity deviations above are 0.001%.
* **The flash divider matters with two cores and not with one.**  At 520 MHz on the
  official Pico 2, two cores measured 2622.486184 iterations/sec over ten runs at DIV
  8 (65 MHz of flash clock) and 2611.277278 over ten at DIV 10 (52 MHz): 0.43% slower,
  with a spread of 0.0271% against 0.0003%, ninety times less steady -- and both
  measured through the same flow in the same session, so it is not a session effect.
  One core at the same clock read 1465.38, 1465.39 and 1465.40 at DIV 10, 7 and 5, so
  104 MHz of flash clock with one core buys nothing at all.  That is contention rather
  than bandwidth, and it is why a row without its divider is not a row someone can
  reproduce.
* **Every row should name its flash clock**, and the rows above mostly do.  The
  Luckfox board's 540 MHz row does not, because that measurement predates this table
  and its notes do not record the divider; re-measuring it is one point.
* **A board's name is not a specification.**  Clones share `PICO_BOARD=pico2` with
  the official board and have different flash parts; that is measured, twice, and it
  is why the per-board flash ceiling exists at all.
* **Neither is a score, without its compiler.**  Section 8.

## 8. The compiler is part of the number

A board on this bench measured 5.30% more per clock than every number already written
down -- flat from 150 to 520 MHz, the same with one core as with two, on a board that
was new here.  An offset that large, that flat and that reproducible is not a supply
and not a layout.  It is the code, and the thing that makes the code is the compiler.

The experiment is one board, one clock, one configuration and one variable.  Arch's
[`arm-none-eabi-gcc`](https://archlinux.org/packages/extra/x86_64/arm-none-eabi-gcc/)
16.2.0 was unpacked under `/tmp` with binutils 2.47 and newlib 4.6.0 -- nothing was
installed system-wide -- and `PICO_TOOLCHAIN_PATH` pointed the build at it:

| 520 MHz, 1.60 V, DIV 10, one core | Score | per MHz |
|---|---|---|
| Debian's GCC 13.2.1 (the machine's own) | 1543.05 | 2.967 |
| Arch's GCC 16.2.0 | **1465.40** | **2.818** |

and at the stock clock, the same way: 445.11 against **422.71**.  Both ratios are
1.0530, so what the toolchain does to this workload is a plain multiplier -- the same
at 150 MHz as at 520, and the same with two cores as with one: the WeAct board's
ten-run dual-core soak of 2760.73, *divided* by 1.0530, is 2621.7, against the official
board's 2622.08 at the same clock.

Two things make it the compiler rather than something else that moved with it:

* **The score is real wall-clock time.**  The chip's own `time_us_32()` was checked
  against the host's clock by timestamping the console as it arrived: the state line and
  the results block were 11.238 s apart while the chip reported 11.233 s of timed
  region -- a ratio of 1.0005.  A timebase error was the other candidate explanation.
  It is not there.
* **The GCC 16.2.0 number is the one already on record.**  422.71 is the Luckfox board's
  150 MHz row in [MEASUREMENTS.md](rpi-pico/MEASUREMENTS.md) to five significant
  figures, and 1465.40 is within 0.0014% of what both older boards read at 520 MHz.  A
  different board, measured at a different time, under a compiler producing the same
  code: identical.

**What it changes.**  Nothing about the ratios, the linearity, the 1.78x a second core
buys, or where a board stops being reachable -- all of that was measured inside one
toolchain, whichever one it was.  Everything about the absolute constants: 2.8180 and
1.8914 are what a class of compiler produces, not what the silicon does.  A row should
name its compiler the way it names its flash clock.

**What it might have changed and did not.**  Where a board stops was measured under
whichever compiler was on the bench that day, so the toolchain was a candidate there
too.  It is not the answer: 546 MHz hard-faults on the WeAct board at program counter
`0x1000011c` under GCC 13.2.1 *and* under GCC 16.2.0, with the flash verified byte for
byte both times.  One board is one board, but a failure that lands in the same
instruction under two compilers belongs to the board.

**Reproducing it.**  Unpack the packages anywhere -- Arch's are plain tarballs and need
no package manager -- and point `PICO_TOOLCHAIN_PATH` at the prefix.  Then assert that
it took, because the SDK silently falls back to the compiler on `PATH` with nothing but
a warning, and a fallback measures one compiler twice and reports no difference:

```bash
PICO_TOOLCHAIN_PATH=<prefix>/usr tools/probe.py --board <board> --points 520000
grep CMAKE_C_COMPILER probe-*/build/CMakeCache.txt
```
