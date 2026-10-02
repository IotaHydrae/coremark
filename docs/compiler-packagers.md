# The same compiler, packaged by somebody else

> Four independent builds of the 13.x GCC generation -- Debian's, Arch's, ARM's own and xPack's
> -- read **1543.051 / 1543.052 / 1543.052 / 1543.051** at 520 MHz single core.  The packager,
> the binutils version, the newlib version and the configure flags are invisible in this
> number: a row can be compared against somebody else's by **version alone**.

## TL;DR

- A score that moved between packagers would be a score nobody could reproduce from a version
  number, so the same measurement was run on toolchains from other builders.
- A patch release inside a generation is not a variable either: ARM's 14.3.rel1 reads exactly
  what 14.2.rel1 reads on one core.
- This is why [../TOOLCHAINS.md](../TOOLCHAINS.md) is a ladder of **GCC releases**, and why a
  dual-core row still needs its own compiler named ([soaks.md](soaks.md)).

## The measurement

Same board, clock, voltage, divider, source and flag set as the ladder
([../TOOLCHAINS.md](../TOOLCHAINS.md)):

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

Four independent builds of the 13.x generation read 1543.051, 1543.052, 1543.052 and 1543.051 at
520 MHz single core: four packagers, four package versions, one number to six significant
figures.  Three builds of the 14.2 generation agree the same way, 1504.837 and 1504.838 twice, to
0.00007% on the single-core column.

ARM's 14.3.rel1 reads exactly what 14.2.rel1 reads on one core (both 1504.838), so a patch
release inside a generation is not a variable either.  Its dual-core row, 2740.23, is 0.6% below
the 14.2 pair -- larger than the few tenths of a percent dual-core runs scatter by, and not
something a single run can settle; if it matters, it is a soak away
([soaks.md](soaks.md)).

## The committed 13.2.1 binary, read here

[toolchain-ab/](../toolchain-ab/README.md) had a 13.2.1 binary whose score was never read -- the
run was stopped after the flash.  It was read on the WeAct board, through this repository's own
verified path (erase, bootrom, `picotool load -v`, read back, compare), and it is
**1543.051200**, with the state line reporting 520000 kHz measured and vreg sel 19, `ITERATIONS`
17333, **11.23 s per run** and **0 differing bytes of 39808**.  That is 1543.05, the number the
same configuration gave earlier on a different board, so the board-header change in between
moves nothing.

That pair of binaries also turned out to carry one flag this machine's builds do not
(`-ftls-model=local-exec`, and `-mcmse` before `-mfloat-abi` rather than after): they were built
against a different revision of the SDK.  It does not matter, and checking is the point: this
bench's own 16.2.0 build, without that flag, scores **1465.399973** against the committed
binary's **1465.404062** -- 0.0003% apart, which is one run of CoreMark.  The SDK revision and
that flag are not part of the number; the compiler version is, and it is worth exactly
**1.052990** ([../RANKINGS.md](../RANKINGS.md) section 8).

## Related

- [../TOOLCHAINS.md](../TOOLCHAINS.md) -- the ladder these rows belong to.
- [compiler-vs-workload.md](compiler-vs-workload.md) -- why the version order is workload-specific.
- [../RANKINGS.md](../RANKINGS.md) -- the board rankings.
