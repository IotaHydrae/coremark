# Per-clock efficiency, and what one board's clock is worth on another

> On a given chip and compiler CoreMark is a constant number of iterations per MHz:
> **2.8180** on the RP2350 (Cortex-M33) and **1.8914** on the RP2040 (Cortex-M0+), linear to
> 0.001% over the whole measured range.  The M33 does **1.490x** the work per clock that the
> M0+ does.

## TL;DR

- Doing a given amount of work *per clock* is the chip's; how fast the chip can be made to
  run is the board's.  Three RP2350 boards from different vendors agree on 2.8180 to four
  decimal places despite different flash parts, regulators and ceilings.
- **A constant belongs to a chip and a compiler.**  These are what a compiler producing the
  same code as Arch's GCC 16.2.0 gives; Debian's GCC 13.2.1 makes the same RP2350 do
  **2.9674** per MHz ([../TOOLCHAINS.md](../TOOLCHAINS.md)).  Ratios are safe; an absolute
  constant is not meaningful without its toolchain.
- The score is linear in the clock on both platforms to within 0.001%, from 125 to 440 MHz
  on the RP2040 and 150 to 564 MHz on the RP2350, with the flash clock rising underneath (up
  to 110 MHz on the Pico W).  None of the ceilings in [ceilings.md](ceilings.md) is a memory
  wall -- they are the regulator, the PLL or the board.

## The constants

| Platform | Cores | Iterations/sec per MHz | Fitted over | Worst deviation |
|---|---|---|---|---|
| RP2350 (Cortex-M33) | 1 | **2.8180** | 150-564 MHz, 11 points, 3 boards | 0.001% |
| RP2350 (Cortex-M33) | 2 | 5.0425 | 520 MHz (official board) | -- |
| RP2040 (Cortex-M0+) | 1 | **1.8914** | 125-440 MHz, 7 points | 0.001% |
| RP2040 (Cortex-M0+) | 2 | 3.3745 | 420 and 440 MHz | 0.000% |

Two things fall out of the table:

* **The M33 does 1.490x the work per clock that the M0+ does** (single core; 1.494x by the
  dual-core numbers).  It is the one number in this document that is *derived* from the
  measurements rather than measured itself.
* **The score is linear in the clock on both platforms**, so the work stays in the chip's
  cache.

The RP2040 side has not been re-measured under the other compiler, and there is one hint
that it does not move by the same factor: the sample output in
[../rpi-pico/README.md](../rpi-pico/README.md), which names a 13.2.1 toolchain, reads
1.9544 per MHz where this table records 1.8914 -- 3.3% rather than 5.3%.  The sample does
not say which board it was taken on, so that is a question and not a correction;
re-running one RP2040 point under GCC 13.2.1 would settle it
([../OPEN-QUESTIONS.md](../OPEN-QUESTIONS.md)).

## What one board's clock is worth on another

Derived, using the constants above -- and the answer is the same whether it is worked out
from the single-core or the dual-core numbers, which is a check on the arithmetic:

| Configuration | Score | Equivalent on the other chip |
|---|---|---|
| **Pico W at 440 MHz, 1.30 V** (its best) | 832.21 single / 1484.79 dual | **RP2350 at ~295 MHz** (295.3 single, 294.5 dual) |
| Pico W at 420 MHz, 1.30 V | 794.38 / 1417.30 | RP2350 at ~281 MHz |
| Pico W at 240 MHz, stock volts | 453.93 | RP2350 at ~161 MHz |
| Pico 2 at 564 MHz, 1.60 V | 1589.37 | a Pico W would need **~840 MHz** -- twice what its regulator allows |
| Pico 2 at 520 MHz, both cores | 2622.08 | a Pico W would need ~777 MHz, both cores |

The closest *measured* RP2350 point to the Pico W's best is 300 MHz: 845.41 single and
1509.70 dual, about 1.7% above it.  So a Pico W held at its absolute maximum -- 440 MHz, the
highest voltage its regulator is documented for -- and a Pico 2 at 295 MHz, one voltage step
lower (1.20 V), do the same work.  As dynamic power goes roughly as V^2 * f, that is of the
order of half the power for the same score (*estimated*, not measured -- it would take a
current probe to make that a measurement).

## Related

- [../RANKINGS.md](../RANKINGS.md) -- per-board ladder and the reading rules.
- [soaks.md](soaks.md) -- the repeated runs behind these constants.
- [ceilings.md](ceilings.md) -- where each board stops and where the numbers landed in pico-turbo.
