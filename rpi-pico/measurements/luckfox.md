# Luckfox Pico 2 (RP2350A rev 2, QFN60) -- measured

> 520 MHz one core: **1465.38** it/s.  520 MHz two cores: **2612.7** mean over 36
> consecutive runs (0.39% spread).  540 MHz one core: **1521.74**.  570 MHz does not
> bring up USB.  Board flash: **Puya PY25Q32HB, 4 MB**.

## TL;DR

- This is a raw per-board table.  The cross-board synthesis is
  [../../RANKINGS.md](../../RANKINGS.md); the index is
  [../MEASUREMENTS.md](../MEASUREMENTS.md).
- Clock, voltage and flash divider are pico-turbo's, not this port's.  Every row below
  reports `Correct operation validated`, and the clock the chip *measured itself at*
  was the clock that was asked for.
- The flash ceiling is somewhere between **57 and 78.75 MHz** -- only those two points
  are known; the divider ladder that would locate it has not been run.
- The supply is a 2 A buck-boost.  Same chip and firmware as the official Pico 2, but
  this board's soak spread is 0.39% against that board's 0.0002%: jitter is the board's
  supply, and it shows up long before failure.
- The flash part is the vendor's description, **not measured here**; its JEDEC id wants
  reading when the board is next connected.

## Single core

| Clock | Voltage | Iterations | Iterations/sec | Notes |
|---|---|---|---|---|
| 150 MHz | 1.10 V | 5000 | 422.71 | flash 37.5 MHz |
| 300 MHz | 1.20 V | 10000 | 845.41 | 2.00x the 150 MHz run, same work per unit |
| 400 MHz | 1.30 V | 13333 | 1127.21 | 2.67x |
| 520 MHz | 1.60 V | 17333 | 1465.38 | three runs: 1465.383744 / 1465.382629 / 1465.382505, 11.83 s each |
| 540 MHz | 1.60 V | 18000 | 1521.74 | 3.60x; the divider was not recorded |
| 564 MHz | 1.60 V | -- | -- | passes and validates, but this table never recorded its score |
| 570 MHz | 1.60 V | -- | -- | the same firmware does not bring up its USB |

## Dual core

| Clock | Voltage | Iterations | Iterations/sec | Notes |
|---|---|---|---|---|
| 300 MHz | 1.20 V | 20000 | 1512.07 | 1.79x one core, 13.2 s |
| 520 MHz | 1.60 V | 34666 | 2612.7 (mean) | 36 consecutive runs, all validated, **0.39% spread** |

## Linearity and where the top is

- Scores are linear in the clock from 150 to 540 MHz: 1465.38/422.71 = 3.47x against a
  520/150 = 3.47x clock ratio.  The flash clock stays under 60 MHz and the working set
  fits the XIP cache, so there is no memory wall to find at these settings.
- The 570 MHz failure is not a flash artifact: a
  `-DPICO_TURBO_BINARY_TYPE=copy_to_ram` build, which fetches nothing from flash after
  startup, does not come up there either.
- A pico-turbo search with its default 200 ms soak accepted 570 MHz; with a 2 s soak it
  settles at 540 MHz, which agrees with the table above.  This is the reason to accept a
  frequency with a long, mixed workload rather than a short self-check.
- The board's flash clock ceiling is between 57 and 78.75 MHz (solid at 57, wrong at
  78.75); the divider ladder that would locate it is not run yet.

## Related

- [../../RANKINGS.md](../../RANKINGS.md) -- cross-board ranking and per-clock constants.
- [../../docs/soaks.md](../../docs/soaks.md) -- all soak records in one place.
- [../../TOOLCHAINS.md](../../TOOLCHAINS.md) -- the compiler is part of every number here.
