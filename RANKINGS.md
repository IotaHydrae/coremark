# CoreMark rankings

> Every configuration measured in this repository, ranked, with the per-clock numbers that
> make one chip comparable with another.  This is the cross-board view; the raw per-board
> tables are in [rpi-pico/MEASUREMENTS.md](rpi-pico/MEASUREMENTS.md).

## TL;DR

- **The score depends on the compiler as much as on the board.**  Debian's GCC 13.2.1 scores
  1.053x what Arch's GCC 16.2.0 does on this workload, flat from 150 to 520 MHz, so a row
  that does not name its toolchain is not reproducible (section 8,
  [TOOLCHAINS.md](TOOLCHAINS.md)).
- **A ceiling and a usable configuration are different things.**  One core validates to
  564 MHz on the official Pico 2; the configuration with a soak behind it is 520 MHz with two
  cores.  See [docs/soaks.md](docs/soaks.md) and [docs/ceilings.md](docs/ceilings.md).
- Per-clock efficiency, the cross-chip conversion, soak records and each board's wall all
  live in their own documents now; sections 2-6 below point at them.

**What this repository is for.**  It is the bench.  Its job is to find where a chip or a board
stops being reliable, and to leave behind a configuration that is known to work.  That
configuration then goes *back into
[pico-turbo](https://github.com/IotaHydrae/pico-turbo)* as a board file, because the clock,
the voltage and the flash divider belong to the library that applications link against -- not
to the benchmark they were measured with.  `tools/probe.py` is that whole loop in one command:
measure, write a report, propose `boards/<board>.cmake`.

**What a row means.**  Every number below was measured by the `rpi-pico` port in this
repository, with pico-turbo owning the clock, voltage and flash divider.  A row exists only if
the application validated its own result (`Correct operation validated`), if the clock the chip
*measured itself at* was the clock that had been asked for, and if the flash had been written,
read back and compared byte for byte first.  The method, and the reasons for it, are in
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

The flash part matters more than it looks.  It is one of the two things a board file is really
about -- the other being the supply -- and it is why `boards/pico_w.cmake` carries a 110 MHz
flash ceiling while `boards/pico2.cmake`, shared by an official board and a clone with
different flash parts, has to carry the conservative one.

## 1. Best validated configuration, per board

Ranked by single-core score, which is the currency every board here has.  These are the
numbers a 16.2.0-class compiler gives; a row measured under anything else says so.

| Rank | Board | Chip | Clock | Voltage | Flash | Cores | CoreMark 1.0 | It/s per MHz |
|---|---|---|---|---|---|---|---|---|
| 1 | Official Pico 2 | RP2350A | **564 MHz** | 1.60 V | 56.4 MHz (DIV 10, derived) | 1 | **1589.37** | 2.818 |
| 2 | Luckfox Pico 2 | RP2350A | **540 MHz** | 1.60 V | &le;57 MHz (divider not recorded; that board's ceiling) | 1 | **1521.74** | 2.818 |
| 3 | WeAct RP2350A V1.0 | RP2350A | **520 MHz** | 1.60 V | 52 MHz (DIV 10) | 1 | **1465.40** | 2.818 |
| 4 | Official Pico W | RP2040 B2 | **440 MHz** | 1.30 V | 110 MHz (DIV 4) | 1 | **832.21** | 1.891 |
| 5 | Official Pico W | RP2040 B2 | 420 MHz | 1.30 V | 105 MHz (DIV 4) | 1 | 794.38 | 1.891 |
| 6 | Official Pico W | RP2040 B2 | 240 MHz | 1.10 V (stock) | 60 MHz (DIV 4) | 1 | 453.93 | 1.891 |
| 7 | AirMech RP2040 | RP2040 | 420 MHz | 1.30 V | 105 MHz (DIV 4) | 1 | *(tiers from a pico-turbo search, not scored here)* | -- |

The WeAct row is where this document's 5.30% question gets its answer, and it is worth reading
twice: the same board, at the same clock and voltage and divider, scored **1543.05** when it
was measured under GCC 13.2.1 earlier the same evening.  The board did not change and neither
did the configuration; the compiler did.

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

A second core buys **1.78-1.79x** on both platforms, at every clock measured: the core is not
what runs out, the memory they share is.  The WeAct board's 1.789x was worked out inside one
toolchain, which is the only way that ratio means anything.

## 2. Per-clock efficiency -- this is the chip, not the board

2.8180 iterations/sec per MHz on the RP2350 and 1.8914 on the RP2040, linear to 0.001%, with a
compiler attached to every constant.  Full table and reasoning:
**[docs/per-clock-efficiency.md](docs/per-clock-efficiency.md)**.

## 3. What one board's clock is worth on another

Derived from section 2; the full conversion table (Pico W 440 MHz = RP2350 ~295 MHz, Pico 2
564 MHz = a Pico W's ~840 MHz) is in the same document, section *What one board's clock is
worth on another*: **[docs/per-clock-efficiency.md](docs/per-clock-efficiency.md)**.

## 4. Stability: what was soaked, and how it held

Every repeated run, the two shapes of WeAct failure, and why the spreads differ by three
orders of magnitude: **[docs/soaks.md](docs/soaks.md)**.

## 5. Where each board stops

Frequency and flash ceilings per board, and the voltage tiers: 
**[docs/ceilings.md](docs/ceilings.md)**.

## 6. Where these numbers ended up in pico-turbo

The `boards/<board>.cmake` mapping, the three deliberate gaps and the conservative flash
ceiling: **[docs/ceilings.md](docs/ceilings.md)**.

## 7. Reading these numbers honestly

* **CoreMark is one workload.**  Integer and control-flow heavy.  The M33 also has an FPU, DSP
  instructions and double precision, and those would show a much wider gap than 1.49x; a pure
  I/O workload would show none of it ([docs/compiler-vs-workload.md](docs/compiler-vs-workload.md)).
* **Scores here are comparable across boards only at the same clock, cores, iteration rule and
  compiler** -- the port scales iterations with the clock so each run is about twelve seconds,
  which is CoreMark's own reporting rule, and the compiler is worth 1.053x on its own.  A score
  quoted without its toolchain is not one somebody else can reproduce.
* **Anything marked derived** (the 1.490x ratio, the equivalent-frequency table) is arithmetic
  on measured numbers and inherits their error, which is small: the linearity deviations above
  are 0.001%.
* **The flash divider matters with two cores and not with one.**  At 520 MHz on the official
  Pico 2, two cores measured 2622.486184 iterations/sec over ten runs at DIV 8 (65 MHz of flash
  clock) and 2611.277278 over ten at DIV 10 (52 MHz): 0.43% slower, with a spread of 0.0271%
  against 0.0003%, ninety times less steady -- and both measured through the same flow in the
  same session, so it is not a session effect.  One core at the same clock read 1465.38,
  1465.39 and 1465.40 at DIV 10, 7 and 5, so 104 MHz of flash clock with one core buys nothing
  at all.  That is contention rather than bandwidth, and it is why a row without its divider is
  not a row someone can reproduce.
* **Every row should name its flash clock**, and the rows above mostly do.  The Luckfox board's
  540 MHz row does not, because that measurement predates this table and its notes do not
  record the divider; re-measuring it is one point.
* **A board's name is not a specification.**  Clones share `PICO_BOARD=pico2` with the official
  board and have different flash parts; that is measured, twice, and it is why the per-board
  flash ceiling exists at all.
* **Neither is a score, without its compiler.**  Section 8.

## 8. The compiler is part of the number

The ladder behind this section -- GCC 12.2.0 through 16.2.0 from the Arch archive, plus ARM's
own toolchain releases and a recipe for clang, same board, same configuration, one compiler at
a time -- is [TOOLCHAINS.md](TOOLCHAINS.md), and it is where the numbers below come from rather
than being a footnote to them.  The short version: 13.2.0 is the fastest release measured,
16.1.0 and 16.2.0 are the same compiler for this purpose, and four independent builds of the
13.x generation (Debian's, Arch's, ARM's own and xPack's) agree to six significant figures, so
the *version* is the variable and the packager is not.  clang was measured too, for
completeness, and is slower than every GCC on the ladder -- which says more about CoreMark than
about clang.

A board on this bench measured 5.30% more per clock than every number already written down --
flat from 150 to 520 MHz, on a board that was new here.  An offset that large, that flat and
that reproducible is not a supply and not a layout.  It is the code, and the thing that makes
the code is the compiler.

| 520 MHz, 1.60 V, DIV 10, one core | Score | per MHz |
|---|---|---|
| Debian's GCC 13.2.1 (the machine's own) | 1543.05 | 2.967 |
| Arch's GCC 16.2.0 | **1465.40** | **2.818** |

At the stock clock the same way: 445.11 against **422.71**.  Both ratios are 1.0530, so what
the toolchain does to this workload is a plain multiplier -- the same at 150 MHz as at 520.
The ratio is exact to six significant figures: **1.052990**.

**With two cores it is a *different* multiplier, and the honest correction is that this section
first got that wrong.**  The original claim rested on comparing a 13.2.1 dual-core soak mean
against a 16.2.0 single dual-core point *on two different boards*; with both compilers now
measured on the same board ([TOOLCHAINS.md](TOOLCHAINS.md)), the newest compilers are further
behind in dual core than in single core -- 5.93% against 5.30% for 13.2.0, 5.46% against 2.69%
for 14.2.0, 3.76% against 3.52% for 12.2.0.  The "one core is worth 1.78x two" factor is
therefore itself a compiler's number, **1.7745 to 1.8321** across the releases measured (Arch
14.2.0 gives 1.8319; ARM GNU 14.2.rel1 gives 1.8321), and a dual-core comparison is only safe
inside one compiler -- which is how every dual-core row here was measured.

Two things make it the compiler rather than something else that moved with it:

* **The score is real wall-clock time.**  The chip's own `time_us_32()` was checked against the
  host's clock by timestamping the console as it arrived: the state line and the results block
  were 11.238 s apart while the chip reported 11.233 s of timed region -- a ratio of 1.0005.
* **The GCC 16.2.0 number is the one already on record.**  422.71 is the Luckfox board's
  150 MHz row in [rpi-pico/MEASUREMENTS.md](rpi-pico/MEASUREMENTS.md) to five significant
  figures, and 1465.40 is within 0.0014% of what both older boards read at 520 MHz.

**What it changes.**  Nothing about the ratios, the linearity, the 1.78x a second core buys, or
where a board stops being reachable -- all of that was measured inside one toolchain, whichever
one it was.  Everything about the absolute constants: 2.8180 and 1.8914 are what a class of
compiler produces, not what the silicon does.  A row should name its compiler the way it names
its flash clock.

**What it might have changed and did not.**  Where a board stops was measured under whichever
compiler was on the bench that day, so the toolchain was a candidate there too.  It is not the
answer: 546 MHz hard-faults on the WeAct board at program counter `0x1000011c` under GCC 13.2.1
*and* under GCC 16.2.0, with the flash verified byte for byte both times.  A failure that lands
in the same instruction under two compilers belongs to the board.

The flag half of the experiment -- `-O2` and `-Os`, and why the SDK's flags are not the lever
-- is [docs/compiler-flags.md](docs/compiler-flags.md).  The 13.2.1 binary behind the 1543.05
row, and the SDK-revision difference that turned out not to matter, are in
[docs/compiler-packagers.md](docs/compiler-packagers.md).

## Related

- [rpi-pico/MEASUREMENTS.md](rpi-pico/MEASUREMENTS.md) -- raw per-board tables and method.
- [TOOLCHAINS.md](TOOLCHAINS.md) -- the compiler ladder.
- [docs/per-clock-efficiency.md](docs/per-clock-efficiency.md), [docs/soaks.md](docs/soaks.md),
  [docs/ceilings.md](docs/ceilings.md), [docs/compiler-flags.md](docs/compiler-flags.md),
  [docs/compiler-vs-workload.md](docs/compiler-vs-workload.md).
- [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) -- what is still unknown, harm-ordered.
- [toolchain-ab/README.md](toolchain-ab/README.md) -- the two binaries behind section 8.
