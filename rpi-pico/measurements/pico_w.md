# Official Pico W (RP2040 B2) -- measured

> One core is linear at **1.891 it/s per MHz** from 125 to 420 MHz, and **440 MHz at
> 1.30 V works** (832.21 it/s; 30-run dual-core soak, mean 1484.793434, spread 0.0009%),
> even though 420 is the platform's own ceiling.  Flash: **Winbond W25Q16JV, 2 MB**
> (measured: `win w25q16jv id = 0x1540ef size = 2048 KiB`).  The AirMech RP2040 clone
> locks up at 440, so on RP2040 the top is the board's.

## TL;DR

- Raw per-board table; synthesis in [../../RANKINGS.md](../../RANKINGS.md), index in
  [../MEASUREMENTS.md](../MEASUREMENTS.md).
- The one board here that is not a clone.  Single core, iterations scaled at 24 per MHz
  so every run is about twelve seconds, flash divider 4 -- what pico-turbo derives for an
  RP2040 board it has no profile for, and what its voltage table picks at 420 MHz.
- Every row reports `Correct operation validated`, and every row's flash was written,
  read back and compared byte for byte before it ran.

## Single core

| Clock | Voltage applied | Iterations | Iterations/sec | per MHz | Flash clock |
|---|---|---|---|---|---|
| 125 MHz | 1.10 V (sel 11, stock) | 3000 | 236.42 | 1.891 | 62.5 MHz (DIV 2, stock) |
| 240 MHz | 1.10 V (sel 11) | 5760 | 453.93 | 1.891 | 60 MHz |
| 264 MHz | 1.10 V (sel 11) | 6336 | 499.32 | 1.891 | 66 MHz |
| 300 MHz | 1.20 V (sel 13) | 7200 | 567.41 | 1.891 | 75 MHz |
| 360 MHz | 1.20 V (sel 13) | 8640 | 680.90 | 1.891 | 90 MHz |
| 396 MHz | 1.25 V (sel 14) | 9504 | 748.99 | 1.892 | 99 MHz |
| 420 MHz | 1.30 V (sel 15) | 10080 | 794.38 | 1.891 | 105 MHz |
| 440 MHz | 1.30 V (sel 15) | -- | 832.21 | 1.891 | DIV 6 = 73.3 MHz derived; DIV 4 = 110 MHz measured identical |

The score is linear at 1.891 it/s per MHz from 125 to 420 MHz, so this load never leaves
the chip: the working set stays in the XIP cache even as the flash clock climbs from 60 to
105 MHz, and there is no memory wall in this range to fall off.  The 125 MHz row -- stock
clock, stock voltage, stock divider -- landing on the same number is what makes that a
measurement rather than a curve fitted to itself.

The voltage column is the library's own table rather than something typed into the build:
1.10 V up to 266 MHz, 1.20 V above that, 1.25 V above 360, 1.30 V above 396.  Every step of
it landed on a clock this board ran, and the 264 MHz row sitting just under the 266 MHz
boundary at stock voltage is the interesting one.  420 MHz is also where the platform's box
ends -- 1.30 V is the highest the RP2040's regulator is documented for, and 420 MHz is the
platform's own ceiling -- so its top row is the corner of the box, not a limit this board
found.

## 440 MHz at the regulator's maximum

Raising the ceiling out of the way (`-D_PLATFORM_MAX_KHZ=440000`, which the board files
allow from the command line) one more point was tried: **440 MHz at 1.30 V, 832.21 it/s,
1.891 per MHz, validated**.  The AirMech RP2040 board locked up at that clock, so the top of
the RP2040 range is a property of the board and not of the chip -- unlike the two RP2350
boards here, which both stop at 564 passing and 570 failing.

Pinning the divider to DIV 4 -- 110 MHz of flash clock, above the 105 MHz the board file
carried -- changed the score not at all (832.21 both ways: the working set really does live
in the XIP cache), and 30 consecutive dual-core runs at that configuration all validated:

| Quantity | Result |
|---|---|
| Configuration | 440 MHz, 1.30 V (sel 15), DIV 4 = 110 MHz flash, 2 cores |
| Runs that produced a score | 30 of 30 |
| Runs that validated | 30 of 30 |
| `Errors detected` | 0 |
| Iterations/sec | mean 1484.793434, min 1484.786266, max 1484.798949 |
| Spread | 0.0009% |
| Dual-core ratio | 1484.79 / 832.21 = 1.784x, the same as every other tier here |

That configuration is what `boards/pico_w.cmake` in pico-turbo defaults to, and the default
was checked the way the numbers above were: a build given only `-DPICO_BOARD=pico_w`
resolved to 440 MHz, 1.30 V and a 110 MHz flash clock, and the application came up at
440000 kHz measured with vreg sel 15 and validated 832.21 it/s.  The board file now carries
110 MHz rather than 105 because 105 was what the ladder had shown at 420 MHz and this is
what the soak showed two rows above it.

## Dual-core soaks

Two contexts, one context per core, each run rebooting through the bootrom so no run
inherits a warm chip:

| Configuration | Runs | Mean | Spread | Source |
|---|---|---|---|---|
| 420 MHz, 1.30 V, 20160 iterations each (40320 reported) | 27 consecutive complete | 1417.301508 (min 1417.221057, max 1417.305348) | 0.0059% (19 distinct scores) | [../MEASUREMENTS.md](../MEASUREMENTS.md) |
| 420 MHz, 1.30 V, 2 cores | 20 | 1417.303771 | 0.0001% | [../../RANKINGS.md](../../RANKINGS.md) section 4 |
| 440 MHz, 1.30 V, DIV 4, 2 cores | 30 | 1484.793434 | 0.0009% | this board's 440 point |
| 440 MHz, 1.30 V, 2 cores, through the board file | 10 | 1484.788171 | 0.0008% | [../../RANKINGS.md](../../RANKINGS.md) section 4 |

The two 420 MHz dual-core soaks are recorded with different means and spreads; they are
kept as two records rather than merged (see
[../../OPEN-QUESTIONS.md](../../OPEN-QUESTIONS.md) -- one may be a retyping).  The 27-run
soak above ran 28.449 s per run, every run within 1.7 ms of that.

The 420 MHz soak's application counter numbers runs from a watchdog scratch register, and
those outlive a reset, so this soak's counter reads 4 through 30 rather than 1 through 30:
three runs belonged to an earlier attempt that a debugger halt killed mid-run.  What is
claimed here is 27 consecutive complete runs, not 30.  Two consequences are worth keeping:
an interrupted soak resumes where it stopped, which is deliberate, and a clean N-run soak
needs the scratch cleared or the chip power-cycled.

Dual core at 420 MHz, 20160 iterations: 1417.30 it/s, which is 1.784x the single-core
score -- the same 1.78x the RP2350 boards show, because a second core is limited by the
memory the two share rather than by the core itself.

## Where this board stops

| | Value |
|---|---|
| Highest validated clock | **440 MHz** (1.30 V, the highest the RP2040's regulator is documented for) |
| First clock that failed | none measured; 460 MHz untested |
| Flash clock ceiling | **>=110 MHz** (DIV 4 at 440 MHz, soaked); DIV 2 = 210 MHz hangs, past the QSPI interface's 133 MHz |

## Related

- [../../RANKINGS.md](../../RANKINGS.md) -- cross-board ranking and the RP2040 conversion.
- [../../docs/ceilings.md](../../docs/ceilings.md) -- where every board stops.
- [pico2.md](pico2.md), [luckfox.md](luckfox.md), [weact_rp2350a.md](weact_rp2350a.md).
