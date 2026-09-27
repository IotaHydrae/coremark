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

The flash divider ladder on this board, fixed 520 MHz core at 1.60 V, every point
written and read back before it was run:

| Divider | Flash clock | Result |
|---|---|---|
| 4 | 130 MHz | locks the chip up; the BOOTSEL button is what brings it back |
| 6 | 86.7 MHz | 1465.39 iterations/sec, validated |
| 8 | 65 MHz | 1465.39, validated |
| 10 | 52 MHz | 1465.38, validated |

This board's flash ceiling is therefore between 86.7 and 130 MHz, and the Luckfox
board -- same chip, different vendor -- failed at 78.75 MHz.  The flash ceiling
belongs to the board, not the RP2350.

### Dual core soak, 520 MHz at 1.60 V

Two contexts, 34666 iterations each (69332 total), DIV 8 for a 65 MHz flash clock,
**fifty consecutive runs**, each one rebooting through the bootrom between runs so
no run inherits a warm chip:

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

The application's own `COREMARK-REPEAT: run 50 of 50` counter and its
`all 50 runs finished` line agree with the fifty scores the console reader caught,
which is what makes "50 of 50" a statement about the chip rather than about the
reader.

Against the Luckfox board's 2612.7 iterations/sec (mean of 36 runs, 0.39% spread)
this board is 0.36% faster and three orders of magnitude steadier.  Same chip, same
clock, same firmware: the difference is the board's power supply (the Luckfox board
carries a 2 A buck-boost, the official one an LDO), and it shows up as jitter long
before it shows up as failure.

## Pico W (RP2040 B2, 2 MB flash)

The RP2040 side of the same questions, on the one board here that is not a clone.
Single core, iterations scaled at 24 per MHz so every run is about twelve seconds,
flash divider 4 -- which is what pico-turbo derives for an RP2040 board it has no
profile for, and what its voltage table picks at 420 MHz.  Every row reports
`Correct operation validated`, and every row's flash was written, read back and
compared byte for byte before it ran.

| Clock | Voltage applied | Iterations | Iterations/sec | per MHz | Flash clock |
|---|---|---|---|---|---|
| 125 MHz | 1.10 V (sel 11, stock) | 3000 | 236.42 | 1.891 | 62.5 MHz (DIV 2, stock) |
| 240 MHz | 1.10 V (sel 11) | 5760 | 453.93 | 1.891 | 60 MHz |
| 264 MHz | 1.10 V (sel 11) | 6336 | 499.32 | 1.891 | 66 MHz |
| 300 MHz | 1.20 V (sel 13) | 7200 | 567.41 | 1.891 | 75 MHz |
| 360 MHz | 1.20 V (sel 13) | 8640 | 680.90 | 1.891 | 90 MHz |
| 396 MHz | 1.25 V (sel 14) | 9504 | 748.99 | 1.892 | 99 MHz |
| 420 MHz | 1.30 V (sel 15) | 10080 | 794.38 | 1.891 | 105 MHz |

Two things fall out of that last column being the same all the way down.  The
score is linear at 1.891 iterations/sec per MHz from 125 to 420 MHz, so this load
never leaves the chip: the working set stays in the XIP cache even as the flash
clock climbs from 60 to 105 MHz, and there is no memory wall in this range to fall
off.  The 125 MHz row -- stock clock, stock voltage, stock divider -- landing on
the same number is what makes that a measurement rather than a curve fitted to
itself.

The voltage column is the library's own table rather than something typed into the
build: 1.10 V up to 266 MHz, 1.20 V above that, 1.25 V above 360, 1.30 V above
396.  Every step of it landed on a clock this board ran, and the 264 MHz row
sitting just under the 266 MHz boundary at stock voltage is the interesting one.
420 MHz is also where the box ends -- 1.30 V is the highest the RP2040's regulator
is documented for, and 420 MHz is the platform's own ceiling -- so its top row is
the corner of the box, not a limit this board found.

### Dual core soak, 420 MHz at 1.30 V

Two contexts, 20160 iterations each (40320 reported), divider 4 for a 105 MHz
flash clock, every run rebooting through the bootrom so no run inherits a warm
chip:

| Quantity | Result |
|---|---|
| Consecutive complete runs | 27, every one validated |
| `Errors detected` | 0 |
| Iterations/sec | mean 1417.301508, min 1417.221057, max 1417.305348 |
| Spread | 0.0059% (19 distinct scores in 27 runs) |
| Total time per run | 28.449 s, every run within 1.7 ms of that |
| Clock state lines at 420000 kHz asked / configured / measured | 27 of 27 |

The application numbers its runs from a watchdog scratch register, and those
outlive a reset, so this soak's counter reads 4 through 30 rather than 1 through
30: three runs belonged to an earlier attempt that a debugger halt killed
mid-run.  What is claimed here is 27 consecutive complete runs, not 30.  Two
consequences are worth keeping: an interrupted soak resumes where it stopped,
which is deliberate, and a clean N-run soak needs the scratch cleared or the chip
power-cycled.

The platform ceiling for RP2040 is 420 MHz, which is also where the library's
voltage table ends (1.30 V).  Raising the ceiling out of the way
(`-D_PLATFORM_MAX_KHZ=440000`, which the board files allow from the command line)
one more point was tried: **440 MHz at 1.30 V, 832.21 iterations/sec, 1.891 per
MHz, validated**.  The AirMech RP2040 board locked up at that clock, so the top of
the RP2040 range is a property of the board and not of the chip -- unlike the two
RP2350 boards here, which both stop at 564 passing and 570 failing.

Dual core at 420 MHz, one context per core, 20160 iterations: 1417.30
iterations/sec, which is 1.784x the single-core score.  That is the same 1.78x the
RP2350 boards show, because a second core is limited by the memory the two share
rather than by the core itself.

## Not measured yet

- The Pico W above 420 MHz: 440 MHz locked the AirMech RP2040 up, and whether
  this board does the same is the RP2040 counterpart of the 570 MHz question.
- The Pico W's flash divider above 105 MHz of flash clock (DIV 4 at 420 MHz); the
  QSPI interface's own 133 MHz limit is what makes faster dividers meaningless.
- The Luckfox board's full flash divider ladder (only "solid at 57 MHz, wrong at
  78.75 MHz" is known).
- The RP2350 boards' dual-core soak above 520 MHz, where the single core still
  validates.

## Method notes

- **Check one point end to end before running a sweep**: build, read the flash back,
  and read the state line.  Two batches here waited minutes to learn what the first
  point would have said in one -- one died in the flashing step, one locked the
  board up -- and `-DPICO_TURBO_FLASH_CLK_DIV` is a good example of why the flash
  step deserves a look before it is trusted.
- **A flash divider the chip cannot survive is not recoverable in software**: the
  divider is in boot stage 2, so every reset fails the same way (DIV 4 at 520 MHz
  left an official Pico 2 in lockup until the BOOTSEL button was pressed).
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
- **Output written while no host is attached is dropped, not buffered.**  The SDK's
  USB stdio discards characters when nobody has the port open, and a soak reboots
  between runs, so a reader that re-attaches a second late loses a whole run's log.
  It looks like a counter that read 3 with only two logs to go with it; the fix is
  `PICO_STDIO_USB_CONNECT_WAIT_TIMEOUT_MS`, which makes each boot wait for the port
  before it starts (the wait is before the timing, so it costs nothing).  Judge a
  soak by the counter the application prints, not by the lines the reader happened
  to catch.
- **Reading state over SWD disturbs the run** (it halts the core, and the SDK's
  watchdog pauses on debug), so the console is the channel to measure with, and
  the port prints everything it wants judged there.
