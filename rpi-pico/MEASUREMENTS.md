# Measured results

> CoreMark 1.0 on RP2350/RP2040 boards, run by this port with pico-turbo owning the clock,
> voltage and flash divider.  This file is the index and the method; the raw per-board
> tables are one file each below.

## TL;DR

- **Every number in this file was built by one toolchain: `arm-none-eabi-gcc` GCC 16.2.0
  (Arch)**, which is what the `Compiler version` line of all 140 runs behind these tables
  says -- except where a row names another compiler.
- The compiler is part of the number: the same source built by Debian's GCC 13.2.1 scores
  5.30% higher on this workload, flat across the clock range.  Every *ratio* here is safe
  (both sides came out of one compiler); the absolute constants (2.8180 per MHz on the
  RP2350, 1.8914 on the RP2040) are that compiler's numbers, not the silicon's.  The
  compiler ladder is [../TOOLCHAINS.md](../TOOLCHAINS.md); the 5.30% decomposition is
  [../docs/compiler-flags.md](../docs/compiler-flags.md) and
  [../TOOLCHAINS.md](../TOOLCHAINS.md).
- **The compile options are not a knob either, and every table below is `-O3`.**  `-O2`
  costs 0.41% and `-Os` costs 17.9%, each by exactly the same percentage at 150 MHz as at
  520 MHz -- so a score here is instructions executed per unit of work and nothing else.
  `-O3` is CMake's own `Release` default; the SDK sets no optimization level.
- Iterations scale with the clock so every run is about twelve seconds, CoreMark's own
  rule for a reportable result.  Every row reports `Correct operation validated`, and the
  clock in its state line is the one the hardware counter *measured*, not the one asked
  for.
- Clock and voltage work (which frequencies a search accepts, what a longer soak changes)
  is in the [pico-turbo notes](https://github.com/IotaHydrae/pico-turbo/blob/main/docs/measurements.md).

## The boards

| Board | File | Chip | Flash |
|---|---|---|---|
| Official Pico 2 | [measurements/pico2.md](measurements/pico2.md) | RP2350A rev 2 / A2 | Winbond W25Q32FV/JV 4 MB |
| Luckfox Pico 2 | [measurements/luckfox.md](measurements/luckfox.md) | RP2350A rev 2, QFN60 | Puya PY25Q32HB 4 MB (vendor's description, not measured here) |
| WeAct RP2350A V1.0 | [measurements/weact_rp2350a.md](measurements/weact_rp2350a.md) | RP2350A rev 2 | Winbond W25Q32FV/JV 4 MB |
| Official Pico W | [measurements/pico_w.md](measurements/pico_w.md) | RP2040 B2 | Winbond W25Q16JV 2 MB |

Cross-board ranking and the per-clock constants are in [../RANKINGS.md](../RANKINGS.md);
soak records by question are in [../docs/soaks.md](../docs/soaks.md); where each board
stops is [../docs/ceilings.md](../docs/ceilings.md).

## Method notes

- **Check one point end to end before running a sweep**: build, read the flash back, and
  read the state line.  Two batches here waited minutes to learn what the first point would
  have said in one -- one died in the flashing step, one locked the board up -- and
  `-DPICO_TURBO_FLASH_CLK_DIV` is a good example of why the flash step deserves a look
  before it is trusted.
- **A flash divider the chip cannot survive is not recoverable in software**: the divider
  is in boot stage 2, so every reset fails the same way (DIV 4 at 520 MHz left an official
  Pico 2 in lockup until the BOOTSEL button was pressed).
- **A clock that never moved is not a result about stability.**  The PLL produces a
  discrete set of frequencies; the SDK leaves the clock alone at the rest.  550 and 560 MHz
  looked like failures until the run's own state line showed the CPU was still at 150 MHz.
- **"Errors detected" can be the ten second rule**, not a wrong answer: CoreMark counts a
  short run as an error, and a fixed iteration count that is fine at 150 MHz is short at
  500 MHz.  Use the state line and the per-item CRC lines, not that word alone.
- **Flashing over openocd can silently write only part of an image** while saying
  "Verified OK"; `tools/probe.py` erases, writes through the bootrom with picotool, reads
  the flash back and compares.  That read-back is the only evidence a write matched the
  build.
- **Output written while no host is attached is dropped, not buffered.**  The SDK's USB
  stdio discards characters when nobody has the port open, and a soak reboots between runs,
  so a reader that re-attaches a second late loses a whole run's log.  It looks like a
  counter that read 3 with only two logs to go with it; the fix is
  `PICO_STDIO_USB_CONNECT_WAIT_TIMEOUT_MS`, which makes each boot wait for the port before
  it starts (the wait is before the timing, so it costs nothing).  Judge a soak by the
  counter the application prints, not by the lines the reader happened to catch.
- **A debugger session's ending is part of the measurement.**  This probe has no reset
  line, so openocd's `reset run` is a vectreset on both families: it moves the program
  counter and runs, and resets nothing else.  On the RP2350 that intermittently produced an
  INVSTATE fault at `platform_entry` -- the first hand-off out of boot2 -- with the flash
  verified byte for byte and `reset run` reporting success, which reads exactly like a board
  that cannot do 150 MHz.  What cured it, and what the port now does for every point, is a
  real chip reset through the bootrom: blank the flash so the bootrom brings up its own USB,
  write with picotool, read the flash back over SWD and compare, then `picotool reboot`.
- **Reading state over SWD disturbs the run** (it halts the core, and the SDK's watchdog
  pauses on debug), so the console is the channel to measure with, and the port prints
  everything it wants judged there.

## Not measured yet

- The Pico W above 440 MHz: 440 validated and soaked; **460 untested**.
- The Pico W's flash divider above 110 MHz of flash clock (DIV 4 at 440 MHz); the QSPI
  interface's own 133 MHz limit is what makes faster dividers meaningless.
- The Luckfox board's full flash divider ladder (only "solid at 57 MHz, wrong at 78.75 MHz"
  is known).
- The RP2350 boards' dual-core soak above 520 MHz, where the single core still validates.
- The WeAct board's dual-core ceiling (400-520 MHz) and its flash divider ladder; the
  official Pico 2 was taken to 109 MHz of flash clock, this board has only ever been run at
  DIV 10 (52 MHz).
- One RP2040 point under GCC 13.2.1, which is what would say whether the 1.0530 multiplier
  is the same on the M0+.

The full, ordered list of open questions is [../OPEN-QUESTIONS.md](../OPEN-QUESTIONS.md).
