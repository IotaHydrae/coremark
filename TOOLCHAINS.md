# The toolchain ladder: one board, one configuration, several compilers

CoreMark is a compiler benchmark as much as a hardware one.  [RANKINGS.md](RANKINGS.md)
section 8 established that the *same source* built by two compilers differs by 5.30% at
one clock and one voltage; this file is the part that follows from it -- the same
measurement run across the release versions anyone might have installed, so that "which
compiler" can be answered with a number instead of a shrug.

Everything below is one board (WeAct RP2350A, RP2350A rev 2, W25Q32FV/JV), one clock
(520 MHz), one voltage (1.60 V, the top of pico-turbo's table), one divider (DIV 10, 52
MHz of flash clock), one source, one flag set (`-O3`, CMake's `Release` default, the only
one the SDK allows by default), and one compiler as the only variable.  Each toolchain
also ran the 150 MHz stock point, which is the control: if a number moved because of the
*board* or the *supply* that day, both columns would move together.

## The ladder

The first table is one packager's builds -- the Arch Linux Archive's `arm-none-eabi-gcc`
packages, each unpacked with the binutils and newlib it was packaged with -- plus the one
row from somewhere else, xPack's 15.2.1, because Arch never packaged that release for
this target and the row is worth more than the tidiness:

| GCC | 150 MHz | 520 MHz, 1 core | 520 MHz, 2 cores | per MHz (1 core) | against 16.2.0 |
|---|---|---|---|---|---|
| 12.2.0 | 437.575 | 1516.929 | 2712.285 | 2.9172 | **+3.52%** |
| 13.2.0 | 445.111 | **1543.052** | **2768.943** | **2.9674** | **+5.30%** |
| 14.1.0 | 430.509 | 1492.433 | 2711.127 | 2.8701 | +1.84% |
| 14.2.0 | 434.087 | 1504.837 | 2756.757 | 2.8939 | +2.69% |
| 15.2.1 (xPack) | 426.364 | 1478.050 | 2636.628 | 2.8424 | +0.86% |
| 16.1.0 | 422.729 | 1465.466 | 2600.491 | 2.8182 | +0.004% |
| 16.2.0 | 422.711 | 1465.401 | 2613.904 | 2.8181 | -- |

The dual-core column is one run each, and dual-core runs on this board scatter by a few
tenths of a percent ([RANKINGS.md](RANKINGS.md) section 4) -- so read the 14.x and 13.x
dual rows as percentages rather than as four decimal places, and read 16.1.0 against
16.2.0 as "the same compiler" rather than as a 0.5% difference.

## What the ladder says

**It is a decline, not a cliff.**  15.2.1 is the row that would have said *where* the drop
from 2.9674 to 2.8181 happens, and what it says is that there is no single drop to
locate: at 2.8424 it sits between the 14.x releases and the 16.x pair, so from 13.2.0
onward each release is a little worse than the one before -- 2.9674, 2.8939, 2.8701,
2.8424, 2.8182 -- with the two 16.x releases identical to four figures, so a version bump
inside a generation buys nothing and costs nothing.

What is *not* a slope is the near end: **12.2.0 sits above both 14.x releases**, and
13.2.0 is far above everything.  This workload had a good release and then a decade of
gradual regression, which is worth knowing before choosing a compiler for it -- the
answer is neither the newest nor the oldest, and the ladder is one measurement of one
workload rather than a property of GCC.

**The effect is a multiplier on the clock, not a percentage that grows with it.**  Every
toolchain's 150 MHz deficit against 16.2.0 matches its 520 MHz deficit to three significant
figures: 13.2.0 is +5.299% at 150 MHz and +5.30% at 520, 12.2.0 is +3.516% and +3.52%,
14.2.0 is +2.691% and +2.69%.  That is a compiler making every unit of work cost a fixed
number of extra instructions, whatever the clock is doing -- the same conclusion the flag
experiment in section 8 reaches from the other side, and the same one the strict linearity
of score with clock reaches from a third.

**The second core does not inherit the first core's ratio.**  The dual-core column moves by
a different amount than the single-core column for the same compiler: +3.76% against
+3.52% for 12.2.0, +5.93% against +5.30% for 13.2.0, and +5.47% against +2.69% for 14.2.0.
Equivalently, the "one core is worth 1.78x two" factor everyone quotes is itself a
compiler's number, and here it runs from 1.7745 (16.1.0) to 1.8321 (14.2.rel1).  So the
dual-core score is affected by the toolchain in a way the single-core score cannot predict,
and a dual-core comparison is only safe inside one compiler -- which is how every dual-core
row in this repository was measured.

**What this does not change.**  Every ratio, ceiling and stability result in
[RANKINGS.md](RANKINGS.md) and in pico-turbo's measurements was measured *inside* one
compiler, so all of them stand: where a board stops, what voltage a clock needs, the
linearity, the flash divider behaviour.  What it changes is the reading of absolute
constants: 2.8181 per MHz on an RP2350 is GCC 16.2.0's number, 2.9674 is GCC 13.2.0's,
and a row without its compiler is not reproducible.  That is why
`tools/probe.py` records the compiler with every point and why `--toolchain` asserts it.

## Why the newer compiler is slower

The 5.30% between 13.2.0 and 16.2.0 is not one decision, and both halves of the search
are worth recording, because each of them closed off a plausible answer.

**It is two layers, not one.**  The same board, the same configuration, one core, with
both compilers dropped to `-O2` -- the gap is still there, but it is smaller:

| 520 MHz, one core | GCC 13.2.1 | GCC 16.2.0 | gap |
|---|---|---|---|
| `-O3` | 2.9674 per MHz | 2.8181 | **+5.30%** |
| `-O2` | 2.8651 | 2.8066 | **+2.08%** |

So about 2.1% is present at `-O2` -- base passes, instruction selection, register
allocation -- and about 3.2% arrives with the `-O3` set alone.  Neither half is a single
pass, and a first reading of `-fopt-info` was misleading for exactly that reason: the
one optimization only the newer compiler reported (an unrolled pseudo-vectorization of a
four-byte copy loop in `core_init_state`) is far too small to carry 5%.

**Where the code differs.**  Counted per function in the two `-O3` binaries committed in
[toolchain-ab/](toolchain-ab/README.md):

| | GCC 13.2.1 | GCC 16.2.0 | |
|---|---|---|---|
| the matrix kernel, inlined into `matrix_test` | 340 instructions | 338 | unchanged |
| `core_state_transition` | 185 | 207 | **+12%** |
| `core_bench_list` | 317 | 334 | +5% |
| `crcu16` / `crc16` / `crcu32` | 84 / 85 / 166 | 113 / 112 / 211 | +34% / +32% / +27% |

The matrix algorithms are inlined into `matrix_test` in both builds and that function
differs by two instructions -- which says the difference is in the state machine and the
list, and not which of them.

**Where the time goes, measured.**  All three algorithms are dispatched from inside
`calc_func` -- the comparison function the list traversal calls -- so a build can be
gated to skip one of them, and the difference between two such builds *is* that
algorithm's time.  Six builds, three variants against two compilers, same board, 150 MHz
(the longer run is the better measurement; the skipped kernels make the run short enough
that CoreMark refuses to call it a score, so the timings come from `Total time (secs)`
in the console rather than from the score line):

| 150 MHz, seconds | list only | list + matrix | list + state |
|---|---|---|---|
| GCC 13.2.1 | 4.718 | 7.746 | 8.254 |
| GCC 16.2.0 | 4.689 | 7.787 | 8.726 |

which separates into:

| algorithm | share of the run (GCC 13) | GCC 16.2.0 against 13.2.1 |
|---|---|---|
| list | 42% | **-0.6%** (the newer compiler is faster here) |
| matrix | 27% | +2.3% |
| state | 31% | **+14.2%** |

**It is the state machine.**  `core_bench_state` and the `core_state_transition` it
drives carry about **4.4 of the 5.30 points** on their own; the matrix accounts for 0.6
and the list gives a little back.  The three parts sum to +4.80% where a single run of
the whole workload measures +5.30%, and the difference is the interaction the
decomposition cannot see -- but the shape of it is not in doubt, and it is the opposite
of what the static counts suggested: `core_bench_list` grew by 5% of instructions and
did not get slower.

**Two named decisions, measured rather than argued.**  Each was turned back on and the
point re-run on the board:

| what GCC 16 does differently | recovered |
|---|---|
| `calc_func` is no longer inlined, so `core_bench_list` calls it **twice per comparison** where GCC 13 called `cmp_complex` once with `calc_func` already inside it | **+1.01%** -- forced `always_inline`: 2.8181 -> 2.8465 |
| `core_list_mergesort` becomes a `.constprop` clone called from `core_bench_list`, instead of being inlined into it | **+0.53%** -- `-fno-ipa-cp-clone`: -> 2.8330 |

That is 1.5% of the 5.30%, and it is everything that could be pointed at and then turned
off.  Neither of them is the list's own loop either: that algorithm measures *faster* in
the newer compiler.  Both decisions are on the path that *dispatches* into the state
machine -- `calc_func` is what decides whether `core_bench_state` runs at all -- so what
they buy is on the state side of that call, which is where the remaining 3.8 points are.

Those 3.8 points have no name, and that is the finding.  No pass could be turned off to
recover them: **the thresholds did not move** -- both compilers report the same
`inline-min-speedup=15`, `inline-unit-growth=40`, `max-inline-insns-auto=30` and
`max-inline-insns-single=200` under `-O3` -- so what changed is the *estimates* those
thresholds are applied to.  The state machine's translated code came out 12% bigger and
runs 14% slower, and no single decision in the compiler did that; its cost model simply
thinks a different program is the right one to emit.

**The flag axis is closed, from the other side.**  `-O2` costs GCC 16 0.41% and `-Os`
costs it 17.9%, and both losses are the same proportion at 150 MHz as at 520 -- which is
what says a score here tracks the number of instructions *executed* and not anything
about code size or fetch.  A compiler that is 5% slower by executing 5% more
instructions is not going to be fixed by a flag; it is a different compiler's opinion
about what the code should be.

## The same compiler, packaged by somebody else

A score that moved between packagers would be a score nobody could reproduce from a
version number, so the same measurement was run on toolchains from other builders:

| Toolchain | `--version` | 150 MHz | 520 MHz, 1 core | 520 MHz, 2 cores | per MHz |
|---|---|---|---|---|---|
| Arch 13.2.0 | Arch Repository 13.2.0 | 445.111 | 1543.052 | 2768.943 | 2.9674 |
| ARM GNU 13.3.rel1 | Arm GNU Toolchain 13.3.Rel1 (Build arm-13.24) 13.3.1 | 445.111 | 1543.052 | 2768.909 | 2.9674 |
| xPack 13.3.1 | xPack GNU Arm Embedded GCC 13.3.1 20240614 | 445.113 | 1543.051 | 2774.859 | 2.9674 |
| Debian 13.2.1 | 15:13.2.rel1-2 (the committed binary, single core only) | -- | 1543.051 | -- | 2.9674 |
| Arch 14.2.0 | Arch Repository 14.2.0 | 434.087 | 1504.837 | 2756.757 | 2.8939 |
| ARM GNU 14.2.rel1 | Arm GNU Toolchain 14.2.Rel1 (Build arm-14.52) 14.2.1 | 434.087 | 1504.838 | 2756.976 | 2.8939 |
| xPack 14.2.1 | xPack GNU Arm Embedded GCC 14.2.1 20241119 | 434.090 | 1504.838 | 2748.157 | 2.8939 |
| ARM GNU 14.3.rel1 | Arm GNU Toolchain 14.3.Rel1 (Build arm-14.174) 14.3.1 | 434.087 | 1504.838 | 2740.230 | 2.8939 |

Four independent builds of the 13.x generation -- Debian's, Arch's, ARM's own and xPack's --
read 1543.051, 1543.052, 1543.052 and 1543.051 at 520 MHz single core: four packagers, four
package versions, one number to six significant figures.  Three builds of the 14.2
generation agree the same way, 1504.837 and 1504.838 twice, to 0.00007% on the single-core
column.  So the ladder is a
ladder of **GCC releases**: the packager, the binutils version, the newlib version and the
configure flags that go with them are invisible in this number, and a row can be compared
against somebody else's by version alone.

Two more things fall out of that table.  ARM's 14.3.rel1 reads exactly what 14.2.rel1
reads on one core (both 1504.838, the same to six significant figures), so a patch release
inside a generation is not a variable either.  And its dual-core row, 2740.23, is 0.6%
below the 14.2 pair -- larger than the few tenths of a percent dual-core runs scatter by,
and not something a single run can settle; if it matters, it is a soak away.

## clang

ARM's LLVM embedded toolchain for Arm (the "LLVM ET" tarballs) is what the pico-sdk
supports natively, and on this board it is the slowest thing measured -- slower than every
GCC on the ladder, including the one at the bottom of it:

| Toolchain | 150 MHz | 520 MHz, 1 core | 520 MHz, 2 cores | per MHz |
|---|---|---|---|---|
| clang 19.1.5 (LLVM ET) | 418.956 | 1452.371 | 2598.331 | **2.7930** |
| clang 17.0.1 (LLVM ET) | 416.679 | 1444.478 | 2573.543 | **2.7778** |

Both are below every GCC on the ladder -- 19.1.5 by 0.9% against 16.2.0, the worst of them,
and 17.0.1 by another 0.5% -- so this is clang on this workload rather than one release of
it, which is the same question the GCC half of the ladder answers with four packagers
agreeing and seven versions not.  One workload, one board: it says nothing about clang in
general and everything about how much of a CoreMark number is the compiler.

The recipe is `tools/toolchain-ladder.sh llvm-19.1.5`: it unpacks the tarball, finds
`bin/clang`, and configures the build with `--cmake-arg PICO_COMPILER=pico_arm_cortex_m33_clang`,
which is the SDK's own switch.  The SDK then finds the newlib/picolibc runtimes the
tarball carries under `lib/clang-runtimes/`, so no sysroot has to be assembled by hand --
a system `clang` would need one, because the SDK only looks in that layout, which is why
the tarball is the one to use.

**The toolchain assertion had to be widened for it, and that is worth knowing about.**
`probe.py --toolchain` required the build to have used exactly
`<prefix>/bin/arm-none-eabi-gcc`.  An LLVM ET tarball carries that driver *and* `clang`,
and the SDK picks the latter, so the first clang run was refused -- correctly, in the
sense that it would not record a point it could not attribute, but by a rule that was
one file too narrow.  The assertion now requires the compiler to be *inside* the prefix,
which is the property that matters: a prefix the SDK silently declined to take is one
whose compiler is somewhere else entirely.

## Method, because a ladder of compilers is easy to get wrong

* The toolchains come from the Arch Linux Archive, ARM's own releases, xPack's
  redistributions and ARM's LLVM releases, each unpacked into one prefix of its own.
  Nothing is installed system-wide, and the 16.2.0 row is this machine's own package
  rather than a copy of one.
* Each build is pointed at its prefix with the SDK's own `PICO_TOOLCHAIN_PATH`.
* **The prefix is then asserted, not assumed.**  The SDK searches it first but falls back
  to the compiler on `PATH` with nothing but a warning, so a ladder that trusts the
  environment variable can measure one compiler six times and print a flat line.
  `probe.py --toolchain` reads the build's own `CMAKE_C_COMPILER` out of the CMakeCache
  and refuses the point when it is not the one asked for; every row here passed that check,
  and the compiler string it recorded is in each `results.json`.
* Each point is built, written to flash, **read back and compared byte for byte**, run, and
  kept only if the application validated its own result and the state line showed the clock
  the chip measured *itself* at being the clock it was asked for.  Every 520 MHz row reports
  `520000 kHz measured, vreg sel 19, flash 52000 kHz`, and every read-back reported zero
  differing bytes.
* One output directory per toolchain: a shared build directory keeps the first compiler in
  its CMakeCache, and every later run would then be the same measurement again.
* Archives are integrity-tested before they are unpacked.  A download that was interrupted
  and resumed can leave a valid archive header over a truncated stream, and that fails much
  later, as a compiler which will not compile the simplest program -- measured, the hard
  way, on the first batch.

## Where each toolchain came from

Every row is reproducible from a public URL, and the script knows all of them:

| Builder | Versions | Where |
|---|---|---|
| Arch Linux Archive, `arm-none-eabi-{gcc,binutils,newlib}` | **12.2.0**, **13.2.0**, **14.1.0**, **14.2.0**, **16.1.0**, **16.2.0** | `https://archive.archlinux.org/packages/a/<pkg>/<pkg>-<version>-<arch>.pkg.tar.zst` |
| ARM GNU Toolchain releases | 12.3.rel1, 13.2.rel1, **13.3.rel1**, **14.2.rel1**, **14.3.rel1** | `https://developer.arm.com/-/media/Files/downloads/gnu/<ver>/binrel/arm-gnu-toolchain-<ver>-x86_64-arm-none-eabi.tar.xz` |
| xPack `arm-none-eabi-gcc` (carries the 15.x releases Arch never packaged) | 12.3.1, 13.2.1, **13.3.1**, **14.2.1**, **15.2.1** | `https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases/download/v<ver>/xpack-arm-none-eabi-gcc-<ver>-linux-x64.tar.gz` |
| ARM LLVM embedded toolchain for Arm (clang) | 16.0.0, **17.0.1**, 18.1.3, 19.1.1, **19.1.5** | `https://github.com/ARM-software/LLVM-embedded-toolchain-for-Arm/releases/download/release-<ver>/` -- the asset spelling changed at 19.1.5: `LLVMEmbeddedToolchainForArm-<ver>-Linux-x86_64.tar.xz` before, `LLVM-ET-Arm-<ver>-Linux-x86_64.tar.xz` from 19.1.5 on |
| Debian's `gcc-arm-none-eabi` | 15:13.2.rel1-2 on Ubuntu noble | `apt install gcc-arm-none-eabi`; the 13.2.1 row here is the committed binary in [toolchain-ab/](toolchain-ab/README.md), not a local install |

Bold entries are the ones measured here; the rest are wired into the script and waiting.

## Reproducing it

```bash
PROXY=host:port tools/toolchain-ladder.sh                        # every compiler in this file
PROXY=host:port tools/toolchain-ladder.sh 13.2.0 arm-14.3.rel1   # or named ones
```

The script downloads, verifies and unpacks each toolchain under `$TC_DIR` (default
`$HOME/tc`), runs the ladder, and prints the table.  The proxy variable is only needed
where the sources are not reachable directly, and re-running an already-unpacked toolchain
needs no network at all -- the prefixes stay and the archives are deleted as soon as they
are unpacked.

## Not measured yet

* **ARM GNU 13.2.rel1**, the one row that is wired in and still unreachable: the tarball's
  URL on `developer.arm.com` times out (`curl` gets no response at all, while the site root
  and the 13.3/14.2/14.3 tarballs answer), and it has failed twice on this bench.  It is
  the least valuable of the missing rows -- 13.3.rel1 covers that generation from ARM's
  side and xPack's 13.3.1 from a fourth packager -- so it is left failing rather than
  chased.
* **Older than 12.2.0**, and any builder other than the five above (Zephyr's SDK is the
  obvious next one).
* **Whether the ladder looks the same on an RP2040.**  The 5.30% has only ever been
  measured on an RP2350; one Pico W point under GCC 13.2.0 would say whether the M0+ moves
  by the same factor, and that is the same open question as [RANKINGS.md](RANKINGS.md)
  section 8's.
* **What the state machine's 14.2% actually is.**  The accounting above says where the
  5.30% lives -- `core_bench_state` and the `core_state_transition` it drives -- and it
  says what it is not: not the list, not the matrix, not any pass that can be turned off,
  and not the inlining thresholds.  What is left is the translated code itself: 22 more
  instructions than GCC 13 emitted for the same state machine.  Which of them is the
  expensive one is a question for a cycle-accurate model or a much finer instrument than
  this bench has.

## The state of this file, and why

The downloads above went through an HTTP proxy on the local network, given to the script
the way it takes one (`PROXY=<host>:<port>`), which is the only route to the internet from
this bench; it was switched off before the batch finished.  So the ladder is "everything that had already
arrived, plus everything that does not need the network": the Arch rows, the three ARM GNU
rows and the Debian binary are measured, and the rest are prepared, linked above and listed
as not measured.

Resuming needs the proxy and nothing else -- the partial archives are still on disk and the
script's `curl -C -` picks them up where they stopped, and the prefixes that are already
unpacked are skipped entirely.
