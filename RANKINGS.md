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

## 1. Best validated configuration, per board

Ranked by single-core score, which is the currency every board here has.

| Rank | Board | Chip | Clock | Voltage | Flash | Cores | CoreMark 1.0 | It/s per MHz |
|---|---|---|---|---|---|---|---|---|
| 1 | Official Pico 2 | RP2350A | **564 MHz** | 1.60 V | 56.4 MHz (DIV 10, derived) | 1 | **1589.37** | 2.818 |
| 2 | Luckfox Pico 2 | RP2350A | **540 MHz** | 1.60 V | &le;57 MHz (divider not recorded; that board's ceiling) | 1 | **1521.74** | 2.818 |
| 3 | Official Pico W | RP2040 B2 | **440 MHz** | 1.30 V | 110 MHz (DIV 4) | 1 | **832.21** | 1.891 |
| 4 | Official Pico W | RP2040 B2 | 420 MHz | 1.30 V | 105 MHz (DIV 4) | 1 | 794.39 | 1.891 |
| 5 | Official Pico W | RP2040 B2 | 240 MHz | 1.10 V (stock) | 60 MHz (DIV 4) | 1 | 453.93 | 1.891 |
| 6 | AirMech RP2040 | RP2040 | 420 MHz | 1.30 V | 105 MHz (DIV 4) | 1 | *(tiers from a pico-turbo search, not scored here)* | -- |

Dual-core rows, same boards:

| Board | Clock | Voltage | Cores | CoreMark 1.0 | vs one core |
|---|---|---|---|---|---|
| Official Pico 2 | 520 MHz | 1.60 V | 2 | **2622.08** | 1.789x |
| Luckfox Pico 2 | 520 MHz | 1.60 V | 2 | 2612.70 | 1.786x |
| Official Pico W | 440 MHz | 1.30 V | 2 | **1484.79** | 1.784x |
| Official Pico W | 420 MHz | 1.30 V | 2 | 1417.30 | 1.784x |
| Luckfox Pico 2 | 300 MHz | 1.20 V | 2 | 1512.07 | 1.789x |

A second core buys **1.78-1.79x** on both platforms, at every clock measured: the
core is not what runs out, the memory they share is.

## 2. Per-clock efficiency -- this is the chip, not the board

| Platform | Cores | Iterations/sec per MHz | Fitted over | Worst deviation |
|---|---|---|---|---|
| RP2350 (Cortex-M33) | 1 | **2.8180** | 150-564 MHz, 9 points, 2 boards | 0.001% |
| RP2350 (Cortex-M33) | 2 | 5.0425 | 520 MHz (official board) | -- |
| RP2040 (Cortex-M0+) | 1 | **1.8914** | 125-440 MHz, 7 points | 0.001% |
| RP2040 (Cortex-M0+) | 2 | 3.3745 | 420 and 440 MHz | 0.000% |

Two things fall out of that table.

* **The M33 does 1.490x the work per clock that the M0+ does** (single core;
  1.494x by the dual-core numbers).  It is the one number in this document that is
  *derived* from the measurements rather than measured itself.
* **The score is linear in the clock on both platforms, to within 0.001%**, from
  125 to 440 MHz on the RP2040 and 150 to 564 MHz on the RP2350, with the flash
  clock rising underneath (up to 110 MHz on the Pico W).  So the work stays in the
  chip's cache and none of the ceilings in section 4 is a memory wall -- they are
  all either the regulator, the PLL or the board.

The two RP2350 boards agree on 2.8180 to four decimal places despite different
vendors, flash parts and regulators.  That is what makes it a property of the chip.

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
| Official Pico 2 | 520 MHz, 1.60 V, 2 cores | 50 | 50 | 0.0002% | 2622.081163 |
| Luckfox Pico 2 | 520 MHz, 1.60 V, 2 cores | 36 | 36 | 0.39% | 2612.7 |
| Official Pico W | 440 MHz, 1.30 V, 2 cores | 30 | 30 | 0.0009% | 1484.793434 |
| Official Pico W | 440 MHz, 1.30 V, 2 cores (through the board file) | 10 | 10 | 0.0008% | 1484.788171 |
| Official Pico W | 420 MHz, 1.30 V, 2 cores | 20 | 20 | 0.0001% | 1417.303771 |

The two RP2350 boards score within 0.36% of each other and differ in spread by three
orders of magnitude.  Same chip, same firmware: the jitter is the board's supply
(the Luckfox board carries a 2 A buck-boost, the official one an LDO), and it shows up
as jitter long before it shows up as failure.

## 5. Where each board stops

| Board | Highest validated clock | First clock that failed | Flash ceiling |
|---|---|---|---|
| Official Pico 2 | 564 MHz | 570 MHz (`isr_hardfault`, flash verified) | between 86.7 and 130 MHz (DIV 6 good, DIV 4 locks up) |
| Luckfox Pico 2 | 564 MHz | 570 MHz (does not bring up USB) | between 57 and 78.75 MHz |
| Official Pico W | **440 MHz** (see below) | 460 MHz untested | ≥110 MHz (DIV 4 at 440 MHz, soaked); DIV 2 = 210 MHz hangs, past the QSPI interface's 133 MHz |
| AirMech RP2040 | 420 MHz | 440 MHz (locks up) | 105 MHz (DIV 4) |

The RP2350 boards stop in the same place -- 564 passes, 570 fails, on both -- so
~565-570 MHz is the chip.  The RP2040 boards do not: the official Pico W ran 440 MHz
where the clone locked up, so on RP2040 the top is the board's.  Voltage *tiers*, on
the other hand, agree across both RP2040 boards (260/360/390/420 -> sel
11/13/14/15): the tiers are the chip's, and the board decides how far past them it
will go.  A board file should be read with that in mind -- and measured, not
assumed, which is what `tools/probe.py` is for.

## 6. Where these numbers ended up in pico-turbo

| Board | pico-turbo board file | Carries |
|---|---|---|
| Official Pico W | `boards/pico_w.cmake` | ceiling 440 MHz, flash 110 MHz; profiles safe 240 / fast 300 / turbo 360 / **extreme 440** -- and extreme is the file's **default**, so `-DPICO_BOARD=pico_w` with nothing else applies the soaked configuration |
| Official Pico 2, Luckfox Pico 2 | `boards/pico2.cmake` | ceiling 600 MHz, flash 60 MHz; profiles safe 225 / fast 300 / turbo 366 / extreme 512 |
| AirMech RP2040, plain Pico | `boards/pico.cmake` | ceiling 420 MHz; profiles safe 240 / turbo 360 / extreme 400 |

Two gaps are visible in that table, and both are on purpose:

* `boards/pico2.cmake`'s extreme profile is 512 MHz while the measurements here say
  564 MHz validates.  Refreshing it wants a soak at 564 first (section 4 has none),
  because a configuration that is going to be handed to applications should have
  been repeated, not just passed once.
* `boards/pico.cmake` describes a plain Pico that has not been on this bench at all;
  its numbers are inherited expectations, and `tools/probe.py --board pico` is one
  command away from replacing them with measurements.

## 7. Reading these numbers honestly

* **CoreMark is one workload.**  Integer and control-flow heavy.  The M33 also has an
  FPU, DSP instructions and double precision, and those would show a much wider gap
  than 1.49x; a pure I/O workload would show none of it.
* **Scores here are comparable across boards only at the same clock, cores and
  iteration rule** -- the port scales iterations with the clock so each run is about
  twelve seconds, which is CoreMark's own reporting rule.
* **Anything marked derived** (the 1.490x ratio, the equivalent-frequency table) is
  arithmetic on measured numbers and inherits their error, which is small: the
  linearity deviations above are 0.001%.
* **Every row should name its flash clock**, and the rows above mostly do.  The
  Luckfox board's 540 MHz row does not, because that measurement predates this table
  and its notes do not record the divider; re-measuring it is one point.
* **A board's name is not a specification.**  Clones share `PICO_BOARD=pico2` with
  the official board and have different flash parts; that is measured, twice, and it
  is why the per-board flash ceiling exists at all.
