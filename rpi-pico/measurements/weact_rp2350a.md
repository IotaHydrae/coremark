# WeAct Studio RP2350A V1.0 (RP2350A rev 2) -- measured

> The third RP2350A board and the one where the compiler question became concrete: the
> same source and clock under two compilers, both read here.  Single core reaches
> **520 MHz** (1465.399973 under GCC 16.2.0, 1543.051200 under the committed GCC 13.2.1
> binary) and hard-faults at 546.  The **dual-core 520 MHz soak does not complete**: four
> GCC 16.2.0 attempts reported 6, 6, 7 and 5 of 10.  Flash: **Winbond W25Q32FV/JV, 4 MB**
> (`id = 0x1640ef`), the same part as the official board's.

## TL;DR

- Raw per-board table; synthesis in [../../RANKINGS.md](../../RANKINGS.md), index in
  [../MEASUREMENTS.md](../MEASUREMENTS.md).
- One core at 520 MHz is a validated configuration; **two cores at 520 MHz is a marginal
  one** -- the highest clock the board carries is a little above the heaviest load it
  carries.  A ceiling and a usable configuration are different things.
- 546 MHz hard-faults at program counter `0x1000011c` under **both** compilers, with the
  flash verified byte for byte both times, so that failure belongs to the board.

## Single core and dual-core points

| Clock | Voltage | Cores | Iterations | Iterations/sec | Notes |
|---|---|---|---|---|---|
| 150 MHz | sel 11 | 1 | 5000 | 422.710618 | exact repeat of the stock row on the other boards |
| 150 MHz | sel 11 | 2 | 10000 | 756.14 | 1.789x, the usual dual-core ratio |
| 520 MHz | 1.60 V (sel 19) | 1 | 17333 | **1465.399973** | GCC 16.2.0; 1465.40 on three separate days |
| 520 MHz | 1.60 V (sel 19) | 1 | 17333 | **1543.051200** | the committed GCC 13.2.1 binary, flashed and read back here |
| 520 MHz | 1.60 V (sel 19) | 2 | 34666 | 2613.91 | single point; see the soak rows |
| 546 MHz | 1.60 V | 1 | -- | -- | **hard fault**, PC `0x1000011c`, under both compilers |

## Dual-core soaks at 520 MHz, 1.60 V

Ten-run soaks, each run rebooting through the bootrom:

| Attempt | Compiler | Runs reported | Where it stopped |
|---|---|---|---|
| one | GCC 13.2.1 | 10 of 10, spread 0.0041%, mean 2760.73 | -- |
| two | GCC 16.2.0 | 6 of 10 | not diagnosed at the time |
| three | GCC 16.2.0 | 6 of 10 | not diagnosed at the time |
| four | GCC 16.2.0 | 7 of 10 | PC in `core_stop_parallel`, CFSR 0 |
| five | GCC 16.2.0 | 5 of 10, six banners | PC `0xeffffffe`, CFSR `0x8200` (`PRECISERR`, `BFARVALID`) |

Over the runs that reported, the GCC 16.2.0 mean was 2611.059110 with a 0.0001% spread.

Two failures, and they are not the same shape.  `core_stop_parallel` is the port's own
join: core 0 spins in `while (!s_core1_done)` with **no timeout** waiting for core 1, so a
run that ends there is a run where core 1 stopped making progress -- no fault on core 0, no
score, and the banner of the run that never reported sitting in the log above it.  The
fifth attempt instead ended in a **precise bus fault** at an address that is not memory
(`0xeffffffe`), which is a jump into nothing rather than a wait.  Both are what a supply
that is a little too weak looks like under the heaviest load available, and the official
Pico 2 shows the same join failure at 546 MHz, one step below its own ceiling.

The GCC 13.2.1 mean cannot be compared with the others directly: that compiler makes this
workload run 5.30% faster (1.0530x), so *divided* by that factor it is 2621.7 against the
official board's 2622.08 at the same clock -- 0.014% apart.  That agreement was read at the
time as a check on the compiler section; it is really a check that two different boards and
two different soak lengths can land that close.  The compiler's dual-core factor turned out
to be 5.93% rather than 5.30% once both compilers were measured on one board
([../../TOOLCHAINS.md](../../TOOLCHAINS.md)).  The arithmetic that mattered is unaffected:
520 MHz dual core on this board is a configuration it does not hold, whichever compiler
built it.

## Where this board stops

| | Value |
|---|---|
| Highest validated clock | **520 MHz** (single core) |
| First clock that failed | 546 MHz (`isr_hardfault` at PC `0x1000011c`, flash verified byte for byte, prints nothing first) -- under both compilers |
| Flash ceiling | not measured: the divider ladder has not been run.  The fastest it was *shown* to hold is 52 MHz (DIV 10 at 520 MHz) |
| Dual-core ceiling | not located between 400 and 520 MHz; `--points 480000 --mt 2 --soak 10` places it |

pico-turbo's `boards/weact_rp2350a.cmake` carries ceiling **520 MHz**, flash 52 MHz, and
profiles safe 300 / fast 400 / turbo 500 / extreme 520 -- no default profile, because
naming a board should not silently overclock it.

## Related

- [../../RANKINGS.md](../../RANKINGS.md) -- cross-board ranking.
- [../../docs/soaks.md](../../docs/soaks.md) -- every soak record, including these failures.
- [../../TOOLCHAINS.md](../../TOOLCHAINS.md) -- the compiler ladder built on this board.
- [pico2.md](pico2.md), [luckfox.md](luckfox.md), [pico_w.md](pico_w.md).
