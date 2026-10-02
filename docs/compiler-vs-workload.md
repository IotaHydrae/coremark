# The compiler effect belongs to the program, not to the chip

> The same compiler pair on the same board and clock gives CoreMark **5.3% slower** under
> GCC 16.2.0, Embench `statemate` **1.9% slower**, Embench `matmult-int` **27.5% faster** and
> Dhrystone **1.2% faster**.  So a compiler ladder reads as "**CoreMark says**" and never as
> "on this chip".

## TL;DR

- "GCC 13 is the best compiler for this chip" is not something that is true.  On one of
  Embench's nineteen programs GCC 16 wins by 27.5%; the effect belongs to the *program*, and
  its sign is not stable from one program to the next.
- Dhrystone is the surprise: the workload with the worst reputation for being easy to improve
  gives one of the two *smallest* differences of the four.  The reputation describes what a
  vendor does when it sets out to game a benchmark -- special flags, hand-written library
  routines, a compiler tuned for one program -- not what two ordinary `-O3` builds do.
- CoreMark's own result does not generalise either.  4.4 of its 5.30 points sit in
  `core_state_transition`, but the penalty on a benchmark called `statemate` is 1.9%, not
  large: what CoreMark found is a property of that function, not of state machines.

## The measurement

[Embench](https://github.com/embench/embench-iot) is nineteen programs, from a CRC to a JPEG
decoder, and it runs on this same board with pico-turbo owning the clock
([`examples/pico/rp2350-pico2/`](https://github.com/IotaHydrae/embench-iot/tree/master/examples/pico/rp2350-pico2),
which imports this repository's flash path and console reader rather than copying them).
[Dhrystone 2.1](https://github.com/IotaHydrae/dhrystone-pico) runs on it too, in a port that
compiles Weicker's three source files byte for byte as netlib distributes them and supplies
the three things a 1988 Unix program expects from beside the code rather than inside it.
Four workloads, one board, one clock, one pair of compilers:

| 520 MHz, one core | GCC 13.2.1 | GCC 16.2.0 | GCC 16 against 13 |
|---|---|---|---|
| CoreMark | 2.9674 per MHz | 2.8181 per MHz | **5.3% slower** |
| Embench `statemate` | 700000 us | 713423 us | 1.9% slower |
| Embench `matmult-int` | 817093 us | 592063 us | **27.5% faster** |
| Dhrystone 2.1 | 1.581 DMIPS/MHz | 1.600 DMIPS/MHz | 1.2% faster |

Every row verified its own result -- CoreMark and Embench through their own checkers,
Dhrystone through the block of final values it prints, which its harness has to compare
because the benchmark leaves that to the reader -- and every row was written to the flash,
read back and compared byte for byte.

## What it changes

Nothing about the ladder in [../TOOLCHAINS.md](../TOOLCHAINS.md): the ratios between
compilers *on one workload* are as measured, and they are still the reason a row has to name
its compiler.  What changes is the question a reader should be asking -- "is the compiler I am
using worse than the one I could be using, on *my* code" is a question that takes a benchmark
of their own, and the ladder is a measurement of CoreMark.

## Caveats

- Only two of Embench's nineteen programs have been run here (`statemate`, `matmult-int`).
  Two points that point in opposite directions cannot give a GM/GSD, so "this compiler on this
  chip" is not yet a statement this bench can make
  ([../OPEN-QUESTIONS.md](../OPEN-QUESTIONS.md)).
- The Dhrystone port's tick is 1/60 s (`HZ=60`, kept to preserve Weicker's two-second validity
  check), so a run has to be long: `--runs` below about 10 million cannot resolve a 1%
  difference.

## Related

- [../TOOLCHAINS.md](../TOOLCHAINS.md) -- the CoreMark compiler ladder.
- [compiler-flags.md](compiler-flags.md) -- why flags cannot close the gap.
- [per-clock-efficiency.md](per-clock-efficiency.md) -- the constants a compiler shifts.
