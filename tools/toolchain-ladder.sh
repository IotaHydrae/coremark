#!/bin/bash
# One board, one configuration, several compilers: the ladder in TOOLCHAINS.md.
#
# Each toolchain is unpacked into its own prefix and pointed at with the SDK's own
# PICO_TOOLCHAIN_PATH.  That knob is not trusted on its own -- the SDK falls back
# to the compiler on PATH with nothing but a warning, which would measure one
# compiler six times and print a flat line -- so probe.py asserts the prefix after
# every build (--toolchain) and refuses the point if the build used something else.
#
#   tools/toolchain-ladder.sh                       # every compiler below
#   tools/toolchain-ladder.sh 13.2.0 arm-14.3.rel1  # named ones only
#   PROXY=host:port tools/toolchain-ladder.sh       # fetch through a proxy
#
# Two things have to be in place first, and both are checked before anything is
# downloaded rather than forty lines later where the message reads like a probe bug:
#
#   export PICO_SDK_PATH=<pico-sdk>                 # or SDK=<pico-sdk>
#   export PATH=$PWD/.venv/bin:$PATH                # the console reader needs pyusb
#
# The results go to $OUT (default /tmp/tcl) and the unpacked prefixes to $TC_DIR
# (default $HOME/tc).  Put both somewhere that survives a reboot: an earlier ladder
# on this bench lost its prefixes to /tmp and had to fetch 300 MB again.
#
# Four builders, because "which compiler" is not one question:
#
#   arch     the Arch Linux Archive's arm-none-eabi-gcc packages, unpacked with the
#            binutils and newlib they were packaged with
#   armgnu   ARM's own GNU toolchain releases (developer.arm.com)
#   xpack    xPack's arm-none-eabi-gcc redistributions, which include the 15.x
#            releases Arch never packaged for this target
#   llvmet   ARM's LLVM embedded toolchain for Arm (clang), which the pico-sdk
#            supports natively -- PICO_COMPILER=pico_arm_cortex_m33_clang -- and
#            which brings its own newlib runtimes under lib/clang-runtimes
#
# Results land in $OUT/<name>/ (results.json, report.md, logs), one directory per
# toolchain: a shared build directory keeps the first compiler in its CMakeCache, so
# every later run would be the same measurement again.
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
TC_DIR=${TC_DIR:-$HOME/tc}
OUT=${OUT:-/tmp/tcl}
BOARD=${BOARD:-weact_rp2350a}
POINTS=${POINTS:-520000}
SDK=${SDK:-${PICO_SDK_PATH:-}}
ARCHIVE=https://archive.archlinux.org/packages/a
ARM_GNU=https://developer.arm.com/-/media/Files/downloads/gnu
XPACK=https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases/download
LLVMET=https://github.com/ARM-software/LLVM-embedded-toolchain-for-Arm/releases/download
WANT=("$@")

curl_opts=(-sSL --retry 3)
if [ -n "${PROXY:-}" ]; then
    curl_opts+=(--proxy "http://$PROXY")
    export http_proxy="http://$PROXY" https_proxy="http://$PROXY"
fi

# Two things probe.py needs that this script cannot work out for it, checked before
# anything is downloaded rather than forty lines later, where the message reads like a
# bug in the probe.  Both were hit on the first run of this script.
if [ ! -f "$SDK/pico_sdk_init.cmake" ]; then
    echo "no pico-sdk at '${SDK:-<unset>}': export PICO_SDK_PATH=<pico-sdk>, or pass SDK=<pico-sdk>" >&2
    exit 2
fi
if ! python3 -c "import usb.core" 2>/dev/null; then
    echo "the python3 on PATH cannot import pyusb, which the console reader needs;" >&2
    echo "  the checkout's .venv has it:  PATH=\$PWD/.venv/bin:\$PATH tools/toolchain-ladder.sh ..." >&2
    exit 2
fi

wanted() {
    [ ${#WANT[@]} -eq 0 ] && return 0
    local w
    for w in "${WANT[@]}"; do [ "$w" = "$1" ] && return 0; done
    return 1
}

fetch() {    # file name, url
    local file=$1 url=$2
    [ -s "$TC_DIR/dl/$file" ] && return 0
    mkdir -p "$TC_DIR/dl"
    echo "  fetching $file"
    curl "${curl_opts[@]}" -C - -o "$TC_DIR/dl/$file" "$url" ||
        { echo "  DOWNLOAD FAILED: $url" >&2; return 1; }
}

# An archive that is a valid header over a truncated stream is what an interrupted
# download leaves behind, and it fails much later as a compiler that will not run.
unpack() {   # file name, destination
    local file=$1 dest=$2
    if ! tar -tf "$TC_DIR/dl/$file" >/dev/null 2>&1 &&
       ! tar --zstd -tf "$TC_DIR/dl/$file" >/dev/null 2>&1; then
        echo "  $file is not a complete archive; fetching it again" >&2
        rm -f "$TC_DIR/dl/$file"
        return 1
    fi
    mkdir -p "$dest"
    if ! tar -xf "$TC_DIR/dl/$file" -C "$dest" 2>/dev/null; then
        tar --zstd -xf "$TC_DIR/dl/$file" -C "$dest" || return 1
    fi
    rm -f "$TC_DIR/dl/$file"
}

# Sets PREFIX (the directory holding bin/) and EXTRA (probe arguments) for one entry.
ensure_prefix() {   # name, kind, spec
    local name=$1 kind=$2 spec=$3
    PREFIX=""; EXTRA=()
    case $kind in
    arch)
        # spec: "gcc-version binutils-version newlib-version", as packaged together
        # shellcheck disable=SC2086
        set -- $spec
        local gcc=$1 binutils=$2 newlib=$3
        PREFIX=$TC_DIR/$name/usr
        [ -x "$PREFIX/bin/arm-none-eabi-gcc" ] && return 0
        local spec2 file
        for spec2 in \
            "arm-none-eabi-gcc:arm-none-eabi-gcc-$gcc-x86_64" \
            "arm-none-eabi-binutils:arm-none-eabi-binutils-$binutils-x86_64" \
            "arm-none-eabi-newlib:arm-none-eabi-newlib-$newlib-any"
        do
            file=${spec2#*:}.pkg.tar.zst
            fetch "$file" "$ARCHIVE/${spec2%%:*}/$file" || return 1
            if ! unpack "$file" "$TC_DIR/$name"; then
                fetch "$file" "$ARCHIVE/${spec2%%:*}/$file" || return 1
                unpack "$file" "$TC_DIR/$name" || return 1
            fi
        done
        ;;
    armgnu)
        PREFIX=$TC_DIR/$name/arm-gnu-toolchain-$spec-x86_64-arm-none-eabi
        [ -x "$PREFIX/bin/arm-none-eabi-gcc" ] && return 0
        local file=arm-gnu-toolchain-$spec-x86_64-arm-none-eabi.tar.xz
        fetch "$file" "$ARM_GNU/$spec/binrel/$file" || return 1
        unpack "$file" "$TC_DIR/$name" || return 1
        ;;
    xpack)
        PREFIX=$TC_DIR/$name/xpack-arm-none-eabi-gcc-$spec
        [ -x "$PREFIX/bin/arm-none-eabi-gcc" ] && return 0
        local file=xpack-arm-none-eabi-gcc-$spec-linux-x64.tar.gz
        fetch "$file" "$XPACK/v$spec/$file" || return 1
        unpack "$file" "$TC_DIR/$name" || return 1
        ;;
    llvmet)
        # The asset name's spelling changed between releases, so find the prefix by
        # looking for bin/clang instead of writing the directory name out.
        PREFIX=$(find "$TC_DIR/$name" -maxdepth 2 -type d -name bin -printf '%h\n' 2>/dev/null | head -1)
        if [ -n "$PREFIX" ] && [ -x "$PREFIX/bin/clang" ]; then
            EXTRA=(--cmake-arg PICO_COMPILER=pico_arm_cortex_m33_clang)
            return 0
        fi
        local file
        if [ "$spec" = "19.1.5" ]; then
            file=LLVM-ET-Arm-$spec-Linux-x86_64.tar.xz
        else
            file=LLVMEmbeddedToolchainForArm-$spec-Linux-x86_64.tar.xz
        fi
        fetch "$file" "$LLVMET/release-$spec/$file" || return 1
        unpack "$file" "$TC_DIR/$name" || return 1
        PREFIX=$(find "$TC_DIR/$name" -maxdepth 2 -type d -name bin -printf '%h\n' | head -1)
        EXTRA=(--cmake-arg PICO_COMPILER=pico_arm_cortex_m33_clang)
        ;;
    *) echo "unknown builder kind $kind" >&2; return 1 ;;
    esac
    [ -x "$PREFIX/bin/arm-none-eabi-gcc" ] || [ -x "$PREFIX/bin/clang" ]
}

BUILDERS=(
    "12.2.0|arch|12.2.0-1 2.39-1 4.1.0-2"
    "13.2.0|arch|13.2.0-2 2.41-1 4.3.0.20230120-1"
    "14.1.0|arch|14.1.0-1 2.42-1 4.4.0.20231231-1"
    "14.2.0|arch|14.2.0-2 2.43-2 4.5.0.20241231-2"
    "16.1.0|arch|16.1.0-1 2.46.1-1 4.6.0.20260123-1"
    "arm-13.2.rel1|armgnu|13.2.rel1"
    "arm-13.3.rel1|armgnu|13.3.rel1"
    "arm-14.2.rel1|armgnu|14.2.rel1"
    "arm-14.3.rel1|armgnu|14.3.rel1"
    "xpack-13.3.1|xpack|13.3.1-1.1"
    "xpack-14.2.1|xpack|14.2.1-1.1"
    "xpack-15.2.1|xpack|15.2.1-1.1"
    "llvm-19.1.5|llvmet|19.1.5"
    "llvm-17.0.1|llvmet|17.0.1"
)

for row in "${BUILDERS[@]}"; do
    name=${row%%|*}; rest=${row#*|}; kind=${rest%%|*}; spec=${rest#*|}
    wanted "$name" || continue
    echo "== $name ($kind)"
    if ! ensure_prefix "$name" "$kind" "$spec"; then
        echo "  could not prepare $name" >&2
        continue
    fi
    if [ -x "$PREFIX/bin/clang" ]; then
        echo "  $PREFIX/bin/clang: $("$PREFIX/bin/clang" --version | head -1)"
    else
        echo "  $PREFIX/bin/arm-none-eabi-gcc: $("$PREFIX/bin/arm-none-eabi-gcc" --version | head -1)"
    fi
done

for row in "${BUILDERS[@]}"; do
    name=${row%%|*}; rest=${row#*|}; kind=${rest%%|*}; spec=${rest#*|}
    wanted "$name" || continue
    ensure_prefix "$name" "$kind" "$spec" || continue
    out=$OUT/$name
    rm -rf "$out"
    echo
    echo "########## $name, one core and two, at $POINTS kHz"
    "$HERE/probe.py" --board "$BOARD" --points "$POINTS" --soak 0 \
        --sdk "$SDK" --toolchain "$PREFIX" "${EXTRA[@]+"${EXTRA[@]}"}" --out "$out" ||
        echo "  probe exited $?"
done

echo
echo "########## the ladder"
python3 - "$OUT" <<'PY'
import json, os, sys
rows = []
for name in sorted(os.listdir(sys.argv[1])) if os.path.isdir(sys.argv[1]) else []:
    path = os.path.join(sys.argv[1], name, "results.json")
    if not os.path.exists(path):
        continue
    row = {"toolchain": name}
    for rec in json.load(open(path)).get("results", {}).values():
        if not rec.get("scores"):
            continue
        where = "150" if rec.get("khz", 0) < 300000 else ("%d/%d" % (rec["khz"] // 1000, rec.get("mt", 1)))
        row[where] = sum(rec["scores"]) / len(rec["scores"])
        row["compiler"] = rec.get("compiler", row.get("compiler"))
    rows.append(row)
cols = sorted({c for r in rows for c in r if c not in ("toolchain", "compiler")})
print("%-16s %-50s %s" % ("toolchain", "compiler", "  ".join("%-14s" % c for c in cols)))
for r in sorted(rows, key=lambda r: r["toolchain"]):
    print("%-16s %-50s %s" % (r["toolchain"], (r.get("compiler") or "?")[:50],
                              "  ".join("%-14s" % (("%.3f" % r[c]) if c in r else "-")
                                        for c in cols)))
PY
