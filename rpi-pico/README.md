# CoreMark port for Raspberry Pi Pico

Currently, only single-core operation is supported.

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