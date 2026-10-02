# Soak records: what was repeated, and how it held

> A point that passes once is a data point, not a configuration.  Every row here was
> repeated, each run rebooting through the bootrom so no run inherits a warm chip.  The
> useful number is the one with a soak behind it: on the official Pico 2 that is 520 MHz
> with two cores, not 564 MHz with one.

## TL;DR

- **Jitter is the board's supply, and it appears long before failure.**  The two older
  RP2350 boards score within 0.36% of each other and differ in spread by three orders of
  magnitude (0.39% vs 0.0002%); same chip, same firmware.
- **A ceiling and a usable configuration are different things.**  The WeAct board validates
  520 MHz single core but has never completed a ten-run dual-core soak there: four GCC 16.2.0
  attempts reported 6, 6, 7 and 5 of 10.
- **A soak is judged by the counter the application prints** (`COREMARK-REPEAT: run N of M`
  and `all M runs finished`), not by the lines the console reader caught.

## The soaks

| Board | Configuration | Runs | Validated | Spread | Mean |
|---|---|---|---|---|---|
| Official Pico 2 | 520 MHz, 1.60 V, 2 cores, DIV 8 | 50 | 50 | 0.0002% | 2622.081163 |
| Official Pico 2 | 520 MHz, 1.60 V, 2 cores, DIV 8 (repeat) | 10 | 10 | 0.0003% | 2622.486184 |
| Official Pico 2 | 520 MHz, 1.60 V, 2 cores, DIV 10 | 10 | 10 | 0.0271% | 2611.277278 |
| Official Pico 2 | 546 MHz, 1.60 V, 2 cores | 2 (single points) | **1** -- the other hung joining core 1 | -- | -- |
| Official Pico 2 | 564 MHz, 1.60 V, 2 cores | 30 attempted | **0** -- it never ran: hard fault before its first line of output | -- | -- |
| Luckfox Pico 2 | 520 MHz, 1.60 V, 2 cores | 36 | 36 | 0.39% | 2612.7 |
| Official Pico W | 440 MHz, 1.30 V, 2 cores | 30 | 30 | 0.0009% | 1484.793434 |
| Official Pico W | 440 MHz, 1.30 V, 2 cores (through the board file) | 10 | 10 | 0.0008% | 1484.788171 |
| Official Pico W | 420 MHz, 1.30 V, 2 cores | 20 | 20 | 0.0001% | 1417.303771 |
| WeAct RP2350A | 520 MHz, 1.60 V, 2 cores *(GCC 13.2.1)* | 10 | 10 | 0.0041% | 2760.731614 |
| WeAct RP2350A | 520 MHz, 1.60 V, 2 cores *(GCC 16.2.0)* | 10 attempted, 4 times | **6, 6, 7 and 5** -- every attempt stopped, none reported all ten | 0.0001% over the runs that reported | 2611.059110 |

A second 420 MHz dual-core soak on the Pico W is recorded separately in
[../rpi-pico/measurements/pico_w.md](../rpi-pico/measurements/pico_w.md): 27 consecutive
complete runs, mean 1417.301508, spread 0.0059%.  The two records differ and are kept as
two, not merged ([../OPEN-QUESTIONS.md](../OPEN-QUESTIONS.md)).

## What stopped the WeAct soaks

The point of these rows is one board at one configuration measured four times, with the
debugger saying what stopped each attempt instead of leaving it at "the board hung" -- and
it turned out to be two different things:

* **attempt four, 7 of 10:** the program counter was in `core_stop_parallel` -- core 0
  spinning in `while (!s_core1_done)` waiting for core 1 with **no timeout** -- with CFSR
  zero, no fault, no score, and the banner of the run that never reported sitting in the log
  above it.  Core 1 simply stopped making progress.
* **attempt five, 5 of 10:** the counter read 5 with five scores and six banners, so run six
  started and never came back, and the program counter was `0xeffffffe` with CFSR
  `0x00008200` -- `PRECISERR` with `BFARVALID` set, a precise bus fault on an address that is
  not memory.  That is a jump into nothing rather than a wait.

A hang in an inter-core join and a bus fault on a wild address are both what a rail that is
a little too weak looks like at the heaviest load.  Both are the same failure the official
Pico 2 shows at 546 MHz, one step below its own limit: the heaviest load a board can carry is
a little below its highest clock.

The failure is not buyable-back with voltage: 1.60 V is already pico-turbo's ceiling
(`PICO_TURBO_MAX_VREG_VOLTAGE`), and an out-of-envelope request is **clamped rather than
refused** -- measured at 520 MHz with 1.65 V asked for, the application came back running at
the stock 150 MHz with the divider applied, which the probe's "clock landed where asked"
check is what caught.

## Why the spreads differ

The two older RP2350 boards score within 0.36% of each other and differ in spread by three
orders of magnitude.  Same chip, same firmware: the jitter is the board's supply (the Luckfox
board carries a 2 A buck-boost, the official one an LDO).  The WeAct board lands between them
-- 0.0041% over ten runs, twenty times the official board's spread and a hundred times less
than the clone's -- which is where a third supply should land.

The WeAct GCC 13.2.1 mean is the one number in the table that cannot be compared directly
with the others: it was measured under a compiler that makes this workload run 5.30% faster
(1.0530x).  *Divided* by that factor it is 2621.7, against the official board's 2622.08 at the
same clock -- 0.014% apart.  That agreement was read at the time as a check on the compiler
section; it is really a check that two *different* boards and two different soak lengths can
land that close, and the compiler's dual-core factor turned out to be 5.93% rather than 5.30%
once both compilers were measured on one board ([../TOOLCHAINS.md](../TOOLCHAINS.md)).  The
arithmetic that mattered is unaffected -- 520 MHz dual core on a WeAct board is a
configuration this board does not hold, whichever compiler built it.

## Related

- [../rpi-pico/MEASUREMENTS.md](../rpi-pico/MEASUREMENTS.md) -- raw per-board tables and the
  method notes (including how to tell a short run from a wrong answer).
- [per-clock-efficiency.md](per-clock-efficiency.md) -- what the repeated numbers average to.
- [../OPEN-QUESTIONS.md](../OPEN-QUESTIONS.md) -- the dual-core ceiling between 400 and 520 MHz
  on the WeAct board is still unmeasured.
