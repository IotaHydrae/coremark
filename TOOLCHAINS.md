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
packages, each unpacked with the binutils and newlib it was packaged with:

| GCC | 150 MHz | 520 MHz, 1 core | 520 MHz, 2 cores | per MHz (1 core) | against 16.2.0 |
|---|---|---|---|---|---|
| 12.2.0 | 437.575 | 1516.929 | 2712.285 | 2.9172 | **+3.52%** |
| 13.2.0 | 445.111 | **1543.052** | **2768.943** | **2.9674** | **+5.30%** |
| 14.1.0 | 430.509 | 1492.433 | 2711.127 | 2.8701 | +1.84% |
| 14.2.0 | 434.087 | 1504.837 | 2756.757 | 2.8939 | +2.69% |
| 16.1.0 | 422.729 | 1465.466 | 2600.491 | 2.8182 | +0.004% |
| 16.2.0 | 422.711 | 1465.401 | 2613.904 | 2.8181 | -- |

The dual-core column is one run each, and dual-core runs on this board scatter by a few
tenths of a percent ([RANKINGS.md](RANKINGS.md) section 4) -- so read the 14.x and 13.x
dual rows as percentages rather than as four decimal places, and read 16.1.0 against
16.2.0 as "the same compiler" rather than as a 0.5% difference.

## What the ladder says

**It is not a slope, it is a step.**  The newest two releases produce identical code
quality for this workload (2.8182 against 2.8181 per MHz, and their 150 MHz rows agree to
0.004%), and everything older is faster -- but not in version order: 13.2.0 is the fastest
of the six, 12.2.0 is faster than both 14.x releases, and 14.1.0 is the slowest of the
pre-16 group.  Choosing a compiler for this workload is not a matter of taking the newest
or the oldest.

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

## The same compiler, packaged by somebody else

A score that moved between packagers would be a score nobody could reproduce from a
version number, so the same measurement was run on toolchains from other builders:

| Toolchain | `--version` | 150 MHz | 520 MHz, 1 core | 520 MHz, 2 cores | per MHz |
|---|---|---|---|---|---|
| Arch 13.2.0 | Arch Repository 13.2.0 | 445.111 | 1543.052 | 2768.943 | 2.9674 |
| ARM GNU 13.3.rel1 | Arm GNU Toolchain 13.3.Rel1 (Build arm-13.24) 13.3.1 | 445.111 | 1543.052 | 2768.909 | 2.9674 |
| Debian 13.2.1 | 15:13.2.rel1-2 (the committed binary, single core only) | -- | 1543.051 | -- | 2.9674 |
| Arch 14.2.0 | Arch Repository 14.2.0 | 434.087 | 1504.837 | 2756.757 | 2.8939 |
| ARM GNU 14.2.rel1 | Arm GNU Toolchain 14.2.Rel1 (Build arm-14.52) 14.2.1 | 434.087 | 1504.838 | 2756.976 | 2.8939 |
| ARM GNU 14.3.rel1 | Arm GNU Toolchain 14.3.Rel1 (Build arm-14.174) 14.3.1 | 434.087 | 1504.838 | 2740.230 | 2.8939 |

Three independent builds of the 13.x generation -- Debian's, Arch's and ARM's own -- read
1543.051, 1543.052 and 1543.052 at 520 MHz single core, and the 14.2 pair agrees to
0.00007% on the single-core column and 0.008% on the dual-core one.  So the ladder is a
ladder of **GCC releases**: the packager, the binutils version, the newlib version and the
configure flags that go with them are invisible in this number, and a row can be compared
against somebody else's by version alone.

Two more things fall out of that table.  ARM's 14.3.rel1 reads exactly what 14.2.rel1
reads on one core (both 1504.838, the same to six significant figures), so a patch release
inside a generation is not a variable either.  And its dual-core row, 2740.23, is 0.6%
below the 14.2 pair -- larger than the few tenths of a percent dual-core runs scatter by,
and not something a single run can settle; if it matters, it is a soak away.

## clang: the recipe is ready, the measurement is not

ARM's LLVM embedded toolchain for Arm (the "LLVM ET" tarballs) is what the pico-sdk
supports natively, and `tools/toolchain-ladder.sh` already carries it as the `llvmet`
builder: it unpacks the tarball, finds `bin/clang`, and configures the build with
`--cmake-arg PICO_COMPILER=pico_arm_cortex_m33_clang`, which is the SDK's own switch.  The
SDK then finds the newlib/picolibc runtimes the tarball carries under `lib/clang-runtimes/`,
so no sysroot has to be assembled by hand -- a system `clang` would need one, because the
SDK only looks in that layout, which is why the tarball is the one to use.

The rows are **not measured yet**: the downloads were still in flight when the proxy this
bench was using went away (see the last section).  The command, once the tarballs are
unpacked:

```bash
PROXY=host:port tools/toolchain-ladder.sh llvm-19.1.5 llvm-17.0.1
```

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
| Arch Linux Archive, `arm-none-eabi-{gcc,binutils,newlib}` | 12.2.0, 13.2.0, 14.1.0, 14.2.0, 16.1.0, 16.2.0 | `https://archive.archlinux.org/packages/a/<pkg>/<pkg>-<version>-<arch>.pkg.tar.zst` |
| ARM GNU Toolchain releases | 12.3.rel1, 13.2.rel1, **13.3.rel1**, **14.2.rel1**, **14.3.rel1** | `https://developer.arm.com/-/media/Files/downloads/gnu/<ver>/binrel/arm-gnu-toolchain-<ver>-x86_64-arm-none-eabi.tar.xz` |
| xPack `arm-none-eabi-gcc` (carries the 15.x releases Arch never packaged) | 12.3.1, 13.2.1, 13.3.1, 14.2.1, 15.2.1 | `https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases/download/v<ver>/xpack-arm-none-eabi-gcc-<ver>-linux-x64.tar.gz` |
| ARM LLVM embedded toolchain for Arm (clang) | 16.0.0, 17.0.1, 18.1.3, 19.1.1, 19.1.5 | `https://github.com/ARM-software/LLVM-embedded-toolchain-for-Arm/releases/download/release-<ver>/` -- the asset spelling changed at 19.1.5: `LLVMEmbeddedToolchainForArm-<ver>-Linux-x86_64.tar.xz` before, `LLVM-ET-Arm-<ver>-Linux-x86_64.tar.xz` from 19.1.5 on |
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

* **clang**, as above: `llvm-19.1.5` and `llvm-17.0.1` are wired into the script and not
  yet run.
* **The 15.x release**, the one version band missing from the ladder.  Arch never packaged
  it for this target; xPack's `15.2.1` was still downloading.  It matters more than the
  others: it is the row that would say whether the step down from 2.9674 to 2.8181 per MHz
  happens with GCC 15 or with GCC 16.
* **xPack 13.3.1 and 14.2.1**, which would extend "the packager is invisible" to a third
  builder at two more versions.
* **ARM GNU 13.2.rel1**, whose download was interrupted; 13.3.rel1 already covers that
  generation from ARM's side.
* **Older than 12.2.0**, and any builder other than the four above (Zephyr's SDK is the
  obvious next one).
* **Whether the ladder looks the same on an RP2040.**  The 5.30% has only ever been
  measured on an RP2350; one Pico W point under GCC 13.2.0 would say whether the M0+ moves
  by the same factor, and that is the same open question as [RANKINGS.md](RANKINGS.md)
  section 8's.
* **Why 13.2.0 wins.**  The instruction-mix difference is visible in the disassembly (2.5%
  more `.text`, 2.1% more instructions, and a CRC kernel that grew from 166 to 211
  instructions in the newer compiler), but which pass is responsible has not been
  established, and the flag axis that might have explained it is closed: see section 8.

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
