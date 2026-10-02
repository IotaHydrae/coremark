# CoreMark port for Raspberry Pi Pico

> This port only runs CoreMark and reports what the chip was actually doing; the
> clock, the core voltage and the flash divider belong to
> [pico-turbo](https://github.com/IotaHydrae/pico-turbo).  Measured results for
> every board are in [MEASUREMENTS.md](MEASUREMENTS.md).

## TL;DR

- **Build**: `cmake -S . -B build -DPICO_BOARD=<board> -DPICO_TURBO_DIR=<pico-turbo>
  -DPICO_TURBO_SYS_CLK_KHZ=<kHz>`, then `cmake --build build -j`.
- **Run**: `COREMARK_MULTITHREAD=1` or `2` (one context per core; two draw more
  current and are where a marginal voltage shows up).  `COREMARK_REPEAT=N` makes
  the soak a build option; `COREMARK_ITERATIONS=0` scales each run to ~12 s.
- **Judge by the state line**, not the score alone: it carries the clock the
  hardware counter *measured*, the vreg select and whether USB came up.
- The `flash` / `flash-erase` targets use openocd's `verify`, which is **not
  evidence** a write matched the build.  The verified path is `tools/probe.py`
  (erase → bootrom → picotool → read back and compare).  See
  [../AGENTS.md](../AGENTS.md) hardware discipline 2 and 8b.

## Build and flash

```bash
# one core at 520 MHz and 1.60 V
cmake -S . -B build -DPICO_BOARD=pico2 \
      -DPICO_TURBO_DIR=<pico-turbo> \
      -DPICO_TURBO_SYS_CLK_KHZ=520000 -DPICO_TURBO_VREG_VOLTAGE=VREG_VOLTAGE_1_60
cmake --build build -j
cmake --build build --target flash-erase    # convenience; verify is not evidence
```

For a plain Pico or Pico 2 pass `-DPICO_BOARD=pico` / `-DPICO_BOARD=pico2`; the
RP2350's RISC-V core builds with `-DPICO_PLATFORM=rp2350-riscv`.  Flashing from a
host with picotool instead:

```bash
picotool load -fvux ./rpi-pico-coremark.uf2
```

Every run prints one line that says what the chip was doing, so a log is readable
on its own -- including the clock measured by the hardware frequency counter, not
just the one that was configured:

```text
PICO-TURBO: 520000 kHz asked, 520000 kHz configured, 520000 kHz measured,
            vreg sel 19, flash 52000 kHz, clk_peri 520000 kHz, usb ok
```

## Options

| Option | Meaning |
|---|---|
| `COREMARK_ITERATIONS` | 0 (default) scales with the clock, and doubles with two contexts, so a run takes about twelve seconds -- CoreMark's own rule for a reportable result.  Set a number to compare two runs on identical work. |
| `COREMARK_REPEAT` | Runs the benchmark this many times, rebooting through the watchdog between runs, so a soak is a build option.  ~50 single-core runs is about ten minutes; a 520 MHz dual-core soak measured 26.4 s per run, so ~50 is closer to 28 minutes. |
| `COREMARK_MULTITHREAD` | Contexts: 2 puts one on each core. |
| `PICO_TURBO_AUTOTUNE` | Search for the frequency and voltage instead of being given them (pico-turbo's option). |

Both USB and UART debug output are enabled.  `PICO_STDIO_USB_CONNECT_WAIT_TIMEOUT_MS`
is set to **20000 ms** by `CMakeLists.txt`, so each boot waits for a reader before
it starts: the SDK discards output written while no host has the port open, and a
soak reboots between runs.

Onboard LED: on = test in progress, blinking = test complete.

## Measured, on a Luckfox Pico 2 (RP2350A rev 2, heatsink)

Single core unless stated, `Correct operation validated` in every case:

| Clock | Voltage | Iterations/sec | Notes |
|---|---|---|---|
| 150 MHz | 1.10 V | 422.71 | stock |
| 300 MHz | 1.20 V | 845.41 | 2.00x |
| 300 MHz | 1.20 V | 1512.07 | two cores, 1.79x that |
| 400 MHz | 1.30 V | 1127.21 | 2.67x |
| 520 MHz | 1.60 V | 1465.38 | 3.47x, three runs within 0.0001% |
| 540 MHz | 1.60 V | 1521.74 | 3.60x |
| 570 MHz | 1.60 V | -- | the same firmware does not bring up its USB |

The scores scale with the clock and nothing else: the flash clock stays under
60 MHz and the working set fits the XIP cache, so there is no memory wall to
find.  The last row is the interesting one -- a pico-turbo search accepted
570 MHz at 1.60 V and this benchmark cannot start there, which is the reason to
accept a frequency with a long, mixed workload rather than a short self-check.

Every board's raw tables, soak records and method notes are in
[MEASUREMENTS.md](MEASUREMENTS.md); the cross-board ranking is
[../RANKINGS.md](../RANKINGS.md).

### A recorded run (historical, GCC 13.2.1, 400 MHz)

This block predates both pico-turbo and the `PICO-TURBO:` state line.  It is kept
because [RANKINGS.md](../RANKINGS.md) section 2 quotes its 1.9544 per MHz as an
open question; it does not name the board it was taken on, so it is an
observation and not a correction to the tables.

```text
Raspberry Pi Pico CoreMark benchmark running ...
CPU speed: 400(MHz), Flash speed: 100(MHz)

2K performance run parameters for coremark.
CoreMark Size    : 666
Total ticks      : 12279725
Total time (secs): 12.279725
Iterations/Sec   : 781.776465
Iterations       : 9600
Compiler version : GCC13.2.1 20231009
Compiler flags   : -mcpu=cortex-m0plus -mthumb -g -O3 -DNDEBUG
Memory location  : STACK
seedcrc          : 0xe9f5
[0]crclist       : 0xe714
[0]crcmatrix     : 0x1fd7
[0]crcstate      : 0x8e3a
[0]crcfinal      : 0xcc42
Correct operation validated. See README.md for run and reporting rules.
CoreMark 1.0 : 781.776465 / GCC13.2.1 20231009 -mcpu=cortex-m0plus -mthumb -g -O3 -DNDEBUG / STACK
```

## Overclocking moved to pico-turbo

`OVERCLOCK_ENABLED` and `OVERCLOCK_PROFILE` used to be options of this port, with
their own SYS_CLK / FLASH_CLK / voltage table for `pico`.  They no longer exist
here: the clock, the voltage and the divider are pico-turbo's, and this project
does not carry a second profile table that can disagree with it.  The pico-turbo
board files are the profiles now (`boards/<board>.cmake`, selected with
`-DPICO_BOARD` and `-DPICO_TURBO_PROFILE`).

The flash divider is likewise pico-turbo's: it sets `PICO_FLASH_SPI_CLKDIV`
itself from the board's ceiling.  The image below is the flash CLK pin measured
on an earlier build running at 400 MHz with `PICO_FLASH_SPI_CLKDIV=4`; it is kept
as a measurement, not as the way to set the divider.

![img](./assets/DS1Z_QuickPrint23.png)

## Links

- <https://github.com/eembc/coremark>
