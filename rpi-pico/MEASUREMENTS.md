# Measured results

CoreMark 1.0 on an RP2350A, run by this port with pico-turbo owning the clock,
voltage and flash divider.  Iterations scale with the clock so every run is about
twelve seconds, which is CoreMark's own rule for a reportable result; every row
below reports `Correct operation validated`.

Clock and voltage work (which frequencies a search accepts, what a longer soak
changes) is in the [pico-turbo notes](https://github.com/IotaHydrae/pico-turbo/blob/main/docs/measurements.md).

## Luckfox Pico 2 (RP2350A rev 2, QFN60, Puya PY25Q32HB flash, heatsink)

| Clock | Voltage | Cores | Iterations | Iterations/sec | Notes |
|---|---|---|---|---|---|
| 150 MHz | 1.10 V | 1 | 5000 | 422.71 | flash 37.5 MHz |
| 300 MHz | 1.20 V | 1 | 10000 | 845.41 | 2.00x the 150 MHz run, same work per unit |
| 300 MHz | 1.20 V | 2 | 20000 | 1512.07 | 1.79x one core, 13.2 s |
| 400 MHz | 1.30 V | 1 | 13333 | 1127.21 | 2.67x |
| 520 MHz | 1.60 V | 1 | 17333 | 1465.38 | three runs: 1465.383744 / 1465.382629 / 1465.382505, 11.83 s each |
| 520 MHz | 1.60 V | 2 | 34666 | 2612.7 (mean) | 36 consecutive runs, all validated, 0.39% spread |
| 540 MHz | 1.60 V | 1 | 18000 | 1521.74 | 3.60x |
| 570 MHz | 1.60 V | 1 | -- | -- | the same firmware does not bring up its USB |

The scores are linear in the clock from 150 to 540 MHz -- 1465.38/422.71 = 3.47x
against a 520/150 = 3.47x clock ratio -- because the flash clock stays under
60 MHz and the working set fits the XIP cache: there is no memory wall to find at
these settings.  The 570 MHz row is the interesting one and it is not a flash
artifact either: a `-DPICO_TURBO_BINARY_TYPE=copy_to_ram` build, which fetches
nothing from flash after startup, does not come up there either.  A pico-turbo
search with its default 200 ms soak accepted that setting; with a 2 s soak it
settles at 540 MHz, which agrees with the table above.

The board's flash part is a Puya PY25Q32HB.  This board's flash clock ceiling is
somewhere between 57 and 78.75 MHz (see the pico-turbo notes); the divider ladder
that would locate it is not run yet.

## Official Pico 2 (RP2350A, its own flash part)

Same port, same iteration rule, 1.60 V, single core, all `Correct operation
validated`:

| Clock | Iterations/sec | Notes |
|---|---|---|
| 520 MHz | 1465.38 | within 0.0002% of the Luckfox board's 1465.38 |
| 546 MHz | 1538.64 | |
| 552 MHz | 1555.56 | |
| 558 MHz | 1572.47 | |
| 564 MHz | 1589.37 | the highest that runs |
| 570 MHz | does not run | verified: the flash matched the build exactly and the core was in `isr_hardfault` |

Two boards from different vendors stop at the same place, so the edge is the
chip's rather than either board's.  Scores are linear in the clock across the
range (564/520 = 1.085x, 1589.37/1465.38 = 1.085x).

A flash divider ladder on this board has one point so far: DIV 4 at 520 MHz (a
130 MHz flash clock) locks it up, DIV 10 (52 MHz) is fine.  The middle points
would say where the flash ceiling sits, and the lockup ended the walk early.

## Not measured yet

- A Pico W, for the RP2040 side of the same questions.
- The flash divider ladder's middle points (DIV 6 and 8 on both boards).
- Three of the PLL points between 540 and 570 MHz: 546, 552, 558, 564.

## Method notes

- **A clock that never moved is not a result about stability.**  The PLL produces a
  discrete set of frequencies; the SDK leaves the clock alone at the rest.  550 and
  560 MHz looked like failures until the run's own state line showed the CPU was
  still at 150 MHz.
- **"Errors detected" can be the ten second rule**, not a wrong answer: CoreMark
  counts a short run as an error, and a fixed iteration count that is fine at
  150 MHz is short at 500 MHz.  Use the state line and the per-item CRC lines, not
  that word alone.
- **Flashing over openocd can silently write only part of an image** while saying
  "Verified OK"; the `flash-erase` target erases first, programs, verifies, and
  leaves the check where a human can repeat it.  Read the flash back and compare
  when in doubt.
- **Reading state over SWD disturbs the run** (it halts the core, and the SDK's
  watchdog pauses on debug), so the console is the channel to measure with, and
  the port prints everything it wants judged there.
