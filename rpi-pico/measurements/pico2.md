# Official Pico 2 (RP2350A rev 2 / A2) -- measured

> Single core validates to **564 MHz** (1589.37 it/s) and hard-faults at 570.  Two cores
> validate to **520 MHz** (50-run soak, mean 2622.081163, spread 0.0002%) and stop being
> reliable by 546.  Flash ceiling is between **109.2 and 112.8 MHz**.  Flash:
> **Winbond W25Q32FV/JV, 4 MB** (measured: `win w25q32fv/jv id = 0x1640ef size = 4096 KiB`).

## TL;DR

- Raw per-board table; synthesis in [../../RANKINGS.md](../../RANKINGS.md), index in
  [../MEASUREMENTS.md](../MEASUREMENTS.md).
- Same port, same iteration rule, 1.60 V, all `Correct operation validated`, each point
  written to flash, read back and compared byte for byte before it ran.
- One core validates to 564; the dual-core configuration *with a soak behind it* is 520.
  A single passing point is not a usable configuration.

## Single core, 1.60 V

| Clock | Iterations/sec | Notes |
|---|---|---|
| 520 MHz | 1465.38 | within 0.0002% of the Luckfox board's 1465.38 |
| 546 MHz | 1538.64 | |
| 552 MHz | 1555.56 | |
| 558 MHz | 1572.47 | |
| 564 MHz | 1589.37 | the highest that runs |
| 570 MHz | does not run | verified: the flash matched the build exactly and the core was in `isr_hardfault` |

Scores are linear in the clock across the range (564/520 = 1.085x, 1589.37/1465.38 =
1.085x).  Two boards from different vendors stop at the same place, so this edge is the
chip's rather than either board's.

Dual core changes that edge.  At 546 MHz two contexts have been seen to pass once --
2748.29 it/s -- and to hang once with the program counter in `core_stop_parallel`, i.e.
core 0 waiting for a core 1 that never came back.  At 564 MHz with two contexts the board
hard-faults before it prints its first line.

## Flash divider ladder (520 MHz core, 1.60 V)

Every point written and read back before it was run:

| Divider | Flash clock | Result |
|---|---|---|
| 4 | 130 MHz | locks the chip up; the BOOTSEL button is what brings it back |
| 5 | 104 MHz | 1465.40 it/s, validated -- an odd divider, which the RP2350's boot stage 2 takes (the RP2040's does not) |
| 5 | 109.2 MHz | 1538.66 at 546 MHz, validated |
| 6 | 86.7 MHz | 1465.39 it/s, validated |
| 7 | 74.3 MHz | 1465.39, validated (odd as well) |
| 8 | 65 MHz | 1465.39, validated |
| 10 | 52 MHz | 1465.38, validated |

The ceiling is therefore between 109.2 and 112.8 MHz: 546 MHz at DIV 5 validates and
564 MHz at DIV 5 hard-faults, while 130 MHz locks the chip up.  The Luckfox board -- same
chip, different vendor -- failed at 78.75 MHz, so the flash ceiling belongs to the board,
not to the RP2350.  One core reads 1465.38, 1465.39 and 1465.40 at DIV 10, 7 and 5, so
104 MHz of flash clock buys nothing at all with one core.

## Dual-core soak, 520 MHz at 1.60 V

Two contexts, 34666 iterations each (69332 total), DIV 8 for a 65 MHz flash clock,
**fifty consecutive runs**, each rebooting through the bootrom so no run inherits a warm
chip:

| Quantity | Result |
|---|---|
| Runs that produced a score | 50 of 50 |
| Runs that validated (`Correct operation validated`) | 50 of 50 |
| `Errors detected` | 0 |
| Iterations/sec | mean 2622.081163, min 2622.078177, max 2622.083036 |
| Spread | **0.0002%** (two parts per million; 30 distinct scores in 50 runs) |
| Total time per run | 26.4416 s, every run within 49 microseconds of that |
| Clock state lines at 520000 kHz asked / configured / measured | 50 of 50 |
| Wall clock | 1677 s for the whole soak (~28 minutes) |

The application's own `COREMARK-REPEAT: run 50 of 50` counter and its `all 50 runs
finished` line agree with the fifty scores the console reader caught, which is what makes
"50 of 50" a statement about the chip rather than about the reader.

Two shorter runs at the same clock show what the divider costs two cores:

| Soak | Divider / flash clock | Runs | Mean | Spread |
|---|---|---|---|---|
| 520 MHz, 2 cores | DIV 8 / 65 MHz | 50 | 2622.081163 | 0.0002% |
| 520 MHz, 2 cores (repeat) | DIV 8 / 65 MHz | 10 | 2622.486184 | 0.0003% |
| 520 MHz, 2 cores | DIV 10 / 52 MHz | 10 | 2611.277278 | 0.0271% |

DIV 10 is 0.43% slower and ninety times less steady, measured through the same flow in the
same session, so it is not a session effect.  That is contention rather than bandwidth --
and it is why a row without its divider is not a row someone can reproduce.

Against the Luckfox board's 2612.7 (mean of 36 runs, 0.39% spread) this board is 0.36%
faster and three orders of magnitude steadier.  Same chip, same clock, same firmware: the
difference is the board's supply (the Luckfox board carries a 2 A buck-boost, this one an
LDO), and it shows up as jitter long before it shows up as failure.

## Related

- [../../RANKINGS.md](../../RANKINGS.md) -- cross-board ranking.
- [../../docs/soaks.md](../../docs/soaks.md) -- all soak records, including the 546/564 failures.
- [pico_w.md](pico_w.md), [luckfox.md](luckfox.md), [weact_rp2350a.md](weact_rp2350a.md).
