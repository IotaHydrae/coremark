# Where each board stops, and where those numbers went

> Two RP2350 boards from different vendors stop in the same place -- 564 MHz passes, 570
> fails -- but the WeAct board stops 44 MHz lower and the Pico W reaches 440 MHz where an
> RP2040 clone locks up.  **How fast a chip can be made to run is the board's; doing work
> per clock is the chip's.**

## TL;DR

- A board file carries two ceilings that are easy to confuse: the highest clock the board
  validated, and the highest clock it validated *under the heaviest load* (two cores).  They
  are not the same number.
- The flash ceiling belongs to the board, not the chip: the official Pico 2 holds 109.2 MHz,
  the Luckfox board failed at 78.75 MHz, and the two RP2350 boards share one board file with
  the conservative ceiling.
- Voltage *tiers* agree across both RP2040 boards (260/360/390/420 -> sel 11/13/14/15): the
  tiers are the chip's, and the board decides how far past them it will go.

## Frequency and flash ceilings

| Board | Highest validated clock | First clock that failed | Flash ceiling |
|---|---|---|---|
| Official Pico 2 | 564 MHz single core; **520 MHz with two** | 570 MHz (`isr_hardfault`, flash verified).  With two cores: 546 is marginal (one pass, one hang in `core_stop_parallel`) and 564 hard-faults | **between 109.2 and 112.8 MHz**: 104 and 109.2 MHz of flash clock validate, 112.8 MHz hard-faults and 130 MHz locks the chip up.  (The flash part is rated 133 MHz, so what that brackets is the part in this configuration -- QMI timing, board layout and all -- not the part on a datasheet.)  Odd dividers are fine here -- DIV 5 and DIV 7 both measured -- which is the RP2350's boot stage 2 behaving as its source says |
| Luckfox Pico 2 | 564 MHz | 570 MHz (does not bring up USB) | between 57 and 78.75 MHz |
| WeAct RP2350A V1.0 | **520 MHz** | 546 MHz (`isr_hardfault` at program counter `0x1000011c`, flash verified byte for byte, and it prints nothing first) -- under **both** compilers, so this one is not a compiler effect | not measured: the divider ladder has not been run on this board.  The fastest it was *shown* to hold is 52 MHz (DIV 10 at 520 MHz) |
| Official Pico W | **440 MHz** (see below) | 460 MHz untested | >=110 MHz (DIV 4 at 440 MHz, soaked); DIV 2 = 210 MHz hangs, past the QSPI interface's 133 MHz |
| AirMech RP2040 | 420 MHz | 440 MHz (locks up) | 105 MHz (DIV 4) |

The two boards that built this table stop in the same place -- 564 passes, 570 fails, on both
-- and that was the evidence for ~565-570 MHz being the chip.  The WeAct board stops 44 MHz
below it, and the compiler is not the reason: 546 MHz hard-faults at the *same program
counter* under GCC 13.2.1 and under GCC 16.2.0, so the failure is a property of that board
rather than of the code that was running on it.  On RP2350 the top is the board's as much as
it is on RP2040 -- 564 is a ceiling a board has to *reach*, not one the silicon hands out.

The RP2040 boards differ too: the official Pico W ran 440 MHz where the clone locked up, so
on RP2040 the top is the board's.  A board file should be read with that in mind -- and
measured, not assumed, which is what `tools/probe.py` is for.

## Where these numbers ended up in pico-turbo

| Board | pico-turbo board file | Carries |
|---|---|---|
| Official Pico W | `boards/pico_w.cmake` | ceiling 440 MHz, flash 110 MHz; profiles safe 240 / fast 300 / turbo 360 / **extreme 440** -- and extreme is the file's **default**, so `-DPICO_BOARD=pico_w` with nothing else applies the soaked configuration |
| Official Pico 2, Luckfox Pico 2 | `boards/pico2.cmake` | ceiling 564 MHz, flash 57 MHz; profiles safe 300 / fast 400 / **turbo 520** (both cores, soaked) / extreme 564 (one core only, and the file says so).  No default profile: the name is shared with clones whose flash and supply differ |
| WeAct RP2350A V1.0 | `boards/weact_rp2350a.cmake` | ceiling **520 MHz**, flash 52 MHz; profiles safe 300 / fast 400 / **turbo 500** / extreme **520** -- the clock-ladder points that validated, with the voltage and divider left to the library.  No default profile: naming a board should not silently overclock it |
| AirMech RP2040, plain Pico | `boards/pico.cmake` | ceiling 420 MHz; profiles safe 240 / turbo 360 / extreme 400 |

Three gaps are visible in that table, and all three are on purpose:

* `boards/pico.cmake` describes a plain Pico that has not been on this bench at all; its
  numbers are inherited expectations, and `tools/probe.py --board pico` is one command away
  from replacing them with measurements.
* The second core costs headroom, and the number to quote is the *soaked* one: 520 MHz with
  two cores has 50 consecutive runs here (and 36 on the clone), while 546 with two cores has
  been seen to pass once and to hang once, and 564 with two cores hard-faults.  One core
  validates to 564.  A single number per board would hide that -- and so would a single lucky
  run, which is why the soak column exists.
* `boards/weact_rp2350a.cmake` carries a flash ceiling that was *shown* rather than measured:
  52 MHz is the fastest divider this board ran at, and the ladder that would find the real one
  has not been run.  It is the conservative direction to be wrong in -- with no board file at
  all the library asks the flash for 130 MHz instead -- but raising it is a `--flash-ladder`
  run, not a datasheet.

The flash part matters more than it looks.  It is one of the two things a board file is really
about -- the other being the supply -- and it is why `boards/pico_w.cmake` carries a 110 MHz
flash ceiling while `boards/pico2.cmake`, shared by an official board and a clone with
different flash parts, has to carry the conservative one.

## Related

- [../RANKINGS.md](../RANKINGS.md) -- best validated configuration per board.
- [soaks.md](soaks.md) -- the repeated runs that make a ceiling a configuration.
- [../rpi-pico/MEASUREMENTS.md](../rpi-pico/MEASUREMENTS.md) -- the raw per-board tables.
