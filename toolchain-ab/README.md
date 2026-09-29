# The same firmware, built twice, by two compilers

Two binaries of one board at one clock, differing in nothing but the toolchain -- and
the one built by the *newer* compiler is **5.30% slower** (both sides now read from the
same board, below).  This directory exists so that the difference can be taken apart
instruction by instruction without reproducing anything.

It is the other half of [RANKINGS.md](../RANKINGS.md) section 8.  A board on this bench
measured 5.30% above every number already written down; the toolchain turned out to be
the whole of it, and these are the two artifacts of that measurement.

## The measurement

| | Debian's GCC 13.2.1 | Arch's GCC 16.2.0 |
|---|---|---|
| `arm-none-eabi-gcc --version` | `(15:13.2.rel1-2) 13.2.1 20231009` | `(Arch Repository) 16.2.0` |
| Compiler flags as the firmware reports them | `-mcpu=cortex-m33 -mthumb -march=armv8-m.main+fp+dsp -mcmse -mfloat-abi=softfp -ftls-model=local-exec -g -O3 -DNDEBUG` | *identical* |
| CoreMark 1.0 at 520 MHz, 1.60 V, DIV 10, 1 core | 1543.05 | **1465.40** |
| it/s per MHz | 2.967 | 2.818 |
| `.text` | 32396 bytes | 33220 bytes (+2.5%) |
| instructions in `.text` | 13490 | 13771 (+2.1%) |
| `.bin` | 39808 bytes | 41040 bytes (+3.1%) |

**The extra code does not account for the lost time.**  2.5% more bytes and 5.03% less
throughput leaves roughly half the difference to be explained by the code itself --
scheduling, addressing modes, inlining decisions, or the library routines that got
linked in.  That is the question this directory is here to have answered.

Note also what the firmware *cannot* tell you.  CoreMark prints a `Compiler version`
line, and it comes from `__VERSION__`, which is identical for every rebuild of a given
upstream release: Debian's and Arch's 13.2.rel1 would both print `13.2.1 20231009`.
The distinguishing string is in the ELF's `.comment` section, which is why it is quoted
above and why the packages are named by their packager:

    strings gcc16.2.0-arch-520mhz.elf | grep '^GCC: '
    GCC: (Arch Repository) 16.1.0
    GCC: (Arch Repository) 16.2.0

Two versions appear because the toolchain ships prebuilt libraries -- `libgcc`, the
newlib objects -- built when 16.1.0 was current.  Only the compiler that built *this
program* is 16.2.0.

## How the two were built

Identical in every argument; the toolchain was selected by `PICO_TOOLCHAIN_PATH`, which
is the Pico SDK's own knob for it (it searches that prefix before `PATH`, and falls
back to `PATH` with only a warning if the prefix is wrong -- so an A/B like this one
must assert that it took, with `grep CMAKE_C_COMPILER <build>/CMakeCache.txt`):

```bash
export PICO_SDK_PATH=<pico-sdk>
PICO_TOOLCHAIN_PATH=<prefix> \
PICO_SDK_PATH=$PICO_SDK_PATH \
cmake -S rpi-pico -B build \
      -DPICO_BOARD=weact_rp2350a \
      -DPICO_TURBO_DIR=<pico-turbo> \
      -DCOREMARK_MULTITHREAD=1 -DCOREMARK_REPEAT=1 \
      -DPICO_TURBO_SYS_CLK_KHZ=520000
cmake --build build -j
```

`ITERATIONS` resolves to 17333 (the port scales it with the clock so a run takes about
twelve seconds, which is CoreMark's own reporting rule), and the board file
`boards/weact_rp2350a.cmake` in pico-turbo supplies the 1.60 V and the DIV 10.

## What each file is

| File | Where it came from |
|---|---|
| `gcc16.2.0-arch-520mhz.elf` | Built, flashed, read back byte for byte, run and scored: **1465.40**, `Correct operation validated`. This is the binary that produced that number. Re-measured later on the WeAct board through the same verified path: **1465.404062**, 0.0003% from the first reading. |
| `gcc13.2.1-debian-520mhz.elf` | Built and flashed with the same arguments, and read back byte for byte (`0 differing bytes of 39808`); its score was for a long time not read, because the run was stopped after the flash and before the measurement finished. **It has since been read on the same board, the same way: 1543.051200** -- with the state line reporting 520000 kHz measured and vreg sel 19, `ITERATIONS` 17333, 11.23 s of timed region, and `0 differing bytes of 39808` on the read-back. That is 1543.05, the figure the same configuration gave earlier using `-DPICO_BOARD=pico2`, so the board-header change moves nothing. |

Both `.bin` files are the exact bytes that were written to the flash and compared
against it.  Both `.map` files are the linker's, for symbol sizes and layout.

One difference between these two and a build made elsewhere has been checked and is
worth knowing about: they were built against a different revision of the SDK, which
shows up in the flags string above (`-ftls-model=local-exec`, and `-mcmse` before
`-mfloat-abi` rather than after).  A build from the current SDK, without that flag,
scores 1465.399973 at the same point -- 0.0003% from this binary.  The SDK revision is
not part of the number; the compiler version is, and it is worth 1.052990.

## Taking it apart

```bash
# how many instructions, and where they are
arm-none-eabi-size -A gcc16.2.0-arch-520mhz.elf
arm-none-eabi-objdump -d gcc16.2.0-arch-520mhz.elf | grep -cE "^[0-9a-f]+:"

# the biggest symbols, biggest last
arm-none-eabi-nm --size-sort --print-size gcc16.2.0-arch-520mhz.elf | tail -20

# one symbol's size on both sides (the field layout of `nm --print-size` shifts
# for a symbol with no size, so grep for the name rather than counting columns)
for f in gcc1*-520mhz.elf; do echo "== $f"; arm-none-eabi-nm --print-size "$f" | grep -wE 'core_bench_list|memcpy|memset'; done

# the whole disassembly, to diff however you like
arm-none-eabi-objdump -d gcc13.2.1-debian-520mhz.elf > /tmp/gcc13.dis
arm-none-eabi-objdump -d gcc16.2.0-arch-520mhz.elf > /tmp/gcc16.dis
```

Worth checking, in the order they are likely to matter:

1. **The linked-in library.**  The two toolchains ship different newlib builds (4.6.0
   on Arch, whatever Debian pairs with 13.2.rel1), and CoreMark calls `memcpy`/`memset`
   through the timed region.  `arm-none-eabi-nm` on both and compare the `memcpy`,
   `memset`, `__aeabi_*` and `_etoa`/`_vsnprintf` symbols -- sizes and addresses.
2. **The three CoreMark kernels.**  `core_list_join.c`, `core_matrix.c` and
   `core_state.c` are the timed code; per-symbol size deltas and instruction counts
   there are the direct answer to "where did 5% go".
3. **`main` and `iterate`**, which the port measures around, and whether either got
   inlined differently.
4. **Alignment and layout.**  `.text` moved by 824 bytes, so every function after the
   first change sits at a different address; on a part with a cache this alone can be
   worth a fraction of a percent.  Distinguishing that from a code-quality difference
   is the hard part, and worth being explicit about in whatever comes out of this.

## Reproducing either side

Both toolchains are public packages; neither was installed system-wide here.

* **Arch's GCC 16.2.0** -- `extra/os/x86_64` on any Arch mirror, three plain tarballs
  extracted into one prefix: `arm-none-eabi-gcc-16.2.0-1-x86_64.pkg.tar.zst`
  (267 MB), `arm-none-eabi-binutils-2.47-1-x86_64.pkg.tar.zst`,
  `arm-none-eabi-newlib-4.6.0.20260123-1-any.pkg.tar.zst`.  The build is relocatable --
  its sysroot resolves relative to the binary -- so `tar --zstd -xf` into a directory
  and point `PICO_TOOLCHAIN_PATH` at `<prefix>/usr` is all it takes.
* **Debian's GCC 13.2.1** -- `apt install gcc-arm-none-eabi` (`15:13.2.rel1-2` on
  Ubuntu noble and its derivatives), and nothing else; it is what the machine's
  `arm-none-eabi-gcc` is.

Then `tools/probe.py --board weact_rp2350a --points 520000 --mt 1 --soak 0`, which
builds, flashes, reads the flash back and compares it, runs, and keeps a point only if
the application validated its own result and the clock the chip measured itself at was
the clock it was asked for.
