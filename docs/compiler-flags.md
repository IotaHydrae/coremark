# Compile flags are a measured variable, not a tuning knob

> `-O2` costs this workload **0.41%** and `-Os` costs **17.9%**, and each loses exactly the
> same percentage at 150 MHz as at 520 MHz -- so the score tracks the number of instructions
> *executed* and nothing about code size or fetch.  Every table in this repository is `-O3`,
> which is CMake's own `Release` default; the SDK sets no optimization level.

## TL;DR

- One board, one core, one divider, two clocks, so a cost caused by *where the code lives*
  would have to show up as a difference between the two clock columns instead of as one
  number.
- The core clock moves 3.5x between the columns while the flash clock barely moves (50 MHz
  against 52 MHz), and `-Os`'s image is 48% smaller.  It still loses exactly as much at both
  clocks, so instruction fetch, flash latency and code footprint are all excluded.
- The flag axis is closed from the other side too: a compiler that is 5% slower by executing
  5% more instructions is not going to be fixed by a flag
  ([../TOOLCHAINS.md](../TOOLCHAINS.md)).

## The measurement

| C flags (`tools/probe.py --cflags=...`) | 150 MHz | 520 MHz | per MHz at 520 | against `-O3`, at 150 / at 520 |
|---|---|---|---|---|
| `-O3` (CMake's `Release` default) | 422.710618 | **1465.399973** | 2.8181 | -- |
| `-O2` | 420.978965 | 1459.397012 | 2.8065 | **-0.4097% / -0.4096%** |
| `-Os` | 346.894936 | 1202.569765 | 2.3126 | **-17.9356% / -17.9357%** |

Board: WeAct RP2350A, DIV 10, one core, GCC 16.2.0 throughout.  `-O2` costs 2.08% of the gap
between GCC 13.2.1 and 16.2.0 when both are dropped to `-O2` as well -- i.e. the compiler gap
is two layers, not one ([../TOOLCHAINS.md](../TOOLCHAINS.md)).

## What does not change anything

* `-fno-unroll-loops` and `-fno-ipa-cp-clone` were built offline and disassembled: each
  variant came out identical to `-O3` except for 16 bytes of `.rodata` -- the `FLAGS_STR`
  string that names the flag.  The unrolled CRC kernels in the disassembly are complete
  unrolling of constant-trip loops, which neither switch controls.  **However**, the compiler
  section separately reports `-fno-ipa-cp-clone` recovering **+0.53%** on the board
  (2.8181 -> 2.8330), which the byte-identical offline builds cannot explain.  The two
  documents disagree; the measurement is recorded in
  [../TOOLCHAINS.md](../TOOLCHAINS.md) and the contradiction is
  [../OPEN-QUESTIONS.md](../OPEN-QUESTIONS.md).
* `-flto` does not link here: `dangerous relocation: unsupported relocation` at
  `core_main.c:301` (`.text.startup`), binutils against this SDK's linker script.  Left
  untested rather than worked around.
* Nothing was ever tuned: the SDK's
  `cmake/preload/toolchains/pico_arm_cortex_m33_gcc.cmake` sets `-mcpu=cortex-m33 -mthumb
  -march=armv8-m.main+fp+dsp -mfloat-abi=softfp -mcmse` and nothing else, there is no
  compiler-version test anywhere in the SDK's cmake (the only one is in pioasm, a host tool),
  and `-O3` is CMake's own `Release` default.  GCC 13.2.1 and GCC 16.2.0 were therefore handed
  the same flags, and the 5.30% is what the newer compiler made of them: 2.5% more `.text`,
  2.1% more instructions, and a CRC kernel that grew from 166 instructions to 211 with eight
  loads and stores where there had been one.

## Reproducing it

The flag half needs no second toolchain -- one flag set per run, in a fresh output directory
so the point is measured again rather than read back out of `results.json` (use `--cflags=-O2`,
with `=`, for anything that begins with a dash):

```bash
tools/probe.py --board weact_rp2350a --points 520000 --mt 1 --soak 0 \
               --cflags=-O2 --out probe-o2
```

## Related

- [../TOOLCHAINS.md](../TOOLCHAINS.md) -- the compiler ladder and the 5.30% decomposition.
- [compiler-vs-workload.md](compiler-vs-workload.md) -- why "which compiler is better" has no
  answer outside a benchmark.
- [../rpi-pico/MEASUREMENTS.md](../rpi-pico/MEASUREMENTS.md) -- every raw table is `-O3`.
