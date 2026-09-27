# CoreMark port for Raspberry Pi Pico

CoreMark runs on one core or on both (`-DCOREMARK_MULTITHREAD=2`).  Two cores
are worth having: it is the same measurement with more current asked of the
regulator, which is where a marginal voltage shows up, and it is where the
overclock stops looking free.

The clock, the core voltage and the flash divider belong to
[pico-turbo](https://github.com/IotaHydrae/pico-turbo): this project used to
carry its own overclocking profiles and its own divider arithmetic, and on an
RP2350 that arithmetic asked for an odd divider the boot stage 2 refuses.

```bash
# one core at 520 MHz and 1.60 V
cmake -S . -B build -DPICO_BOARD=pico2 \
      -DPICO_TURBO_DIR=/path/to/pico-turbo \
      -DPICO_TURBO_SYS_CLK_KHZ=520000 -DPICO_TURBO_VREG_VOLTAGE=VREG_VOLTAGE_1_60
cmake --build build -j
cmake --build build --target flash-erase    # erase, program, verify, run
```

Every run prints one line that says what the chip was doing, so a log is
readable on its own -- including the clock measured by the hardware frequency
counter, not just the one that was configured:

```text
PICO-TURBO: 520000 kHz asked, 520000 kHz configured, 520000 kHz measured,
            vreg sel 19, flash 52000 kHz, clk_peri 520000 kHz, usb ok
```

| Option | Meaning |
|---|---|
| `COREMARK_ITERATIONS` | 0 (default) scales with the clock, and doubles with two contexts, so a run takes about twelve seconds -- CoreMark's own rule for a reportable result.  Set a number to compare two runs on identical work. |
| `COREMARK_REPEAT` | Runs the benchmark this many times, rebooting through the watchdog between runs, so a soak is a build option.  ~50 runs is ten minutes. |
| `COREMARK_MULTITHREAD` | Contexts: 2 puts one on each core. |
| `PICO_TURBO_AUTOTUNE` | Search for the frequency and voltage instead of being given them. |

Measured on a Pico 2 (RP2350A rev 2, heatsink), single core unless stated,
`Correct operation validated` in every case:

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

Measured results on the boards this was run on, and the method notes that go with
them: [MEASUREMENTS.md](MEASUREMENTS.md).

Onboard LED behavior:
- On: Test in progress
- Blinking: Test complete

Both USB and UART debug port are enabled. The default USB connection wait timeout is 3000 ms.

```bash
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

## Build & Flash

For pico and pico2 board

```
cmake -DPICO_BOARD=pico  .. -G Ninja
cmake -DPICO_BOARD=pico2 .. -G Ninja
```

And riscv core on rp2350

```bash
cmake -DPICO_PLATFORM=rp2350-riscv -DOVERCLOCK_ENABLED=1 -DOVERCLOCK_PROFILE=1 .. -G Ninja
```

Flash firmware via picotool

```bash
sudo picotool load -fvux ./rpi-pico-coremark.uf2
```

## Configs

There are several configuration options available in CMake.

### OVERCLOCK_ENABLED

- 0 : Disabled
- 1 : Enabled

### OVERCLOCK_PROFILE

For example on pico

```
#      SYS_CLK  | FLASH_CLK | Voltage
#  1  | 240MHz  |  120MHZ   |  1.10(V)
#  2  | 266MHz  |  133MHz   |  1.10(V)
#  3  | 360MHz  |  90MHz    |  1.20(V)
#  4  | 400MHz  |  100MHz   |  1.30(V)
#  5  | 416MHz  |  104MHz   |  1.30(V)
```

Here is an example.

```bash
cmake -DPICO_BOARD=pico -DOVERCLOCK_ENABLED=1 -DOVERCLOCK_PROFILE=1 .. -G Ninja
```

which means build for pico, enable overclock, select overclock profile 1.

## More 

On the Raspberry Pi Pico, you can determine the flash operating frequency by setting PICO_FLASH_SPI_CLKDIV. The image below shows the waveform on the Flash CLK pin when the Pico is running at 400 MHz and PICO_FLASH_SPI_CLKDIV is set to 4.

![img](./assets/DS1Z_QuickPrint23.png)

## Links

- https://github.com/eembc/coremark