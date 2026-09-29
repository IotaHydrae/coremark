#!/bin/bash
# One board, one configuration, several compilers: the ladder in TOOLCHAINS.md.
#
# Each toolchain is unpacked into its own prefix and pointed at with the SDK's own
# PICO_TOOLCHAIN_PATH.  That knob is not trusted on its own -- the SDK falls back
# to the compiler on PATH with nothing but a warning, which would measure one
# compiler six times and print a flat line -- so probe.py asserts the prefix after
# every build (--toolchain) and refuses the point if the build used something else.
#
#   tools/toolchain-ladder.sh                  # every toolchain below
#   tools/toolchain-ladder.sh 13.2.0 16.2.0    # named ones only
#   PROXY=host:port tools/toolchain-ladder.sh  # fetch through a proxy
#
# Results land in $OUT/<version>/ (results.json, report.md, logs), one directory
# per toolchain: a shared build directory keeps the first compiler in its
# CMakeCache, so every later run would be the same measurement again.
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
TC_DIR=${TC_DIR:-$HOME/tc}
OUT=${OUT:-/tmp/tcl}
BOARD=${BOARD:-weact_rp2350a}
POINTS=${POINTS:-520000}
ARCHIVE=https://archive.archlinux.org/packages/a
WANT=("$@")

# "gcc-version binutils-version newlib-version", as the three sat in the Arch
# archive on the same day.  The compiler is the variable here; its companions are
# held to what was current when it was packaged, which is what any distribution
# build would have used.
TOOLCHAINS=(
    "12.2.0-1  2.39-1    4.1.0-2"
    "13.2.0-2  2.41-1    4.3.0.20230120-1"
    "14.1.0-1  2.42-1    4.4.0.20231231-1"
    "14.2.0-2  2.43-2    4.5.0.20241231-2"
    "16.1.0-1  2.46.1-1  4.6.0.20260123-1"
    "16.2.0-1  2.47-1    4.6.0.20260123-1"
)

curl_opts=(-sSL --retry 3)
if [ -n "${PROXY:-}" ]; then
    curl_opts+=(--proxy "http://$PROXY")
    export http_proxy="http://$PROXY" https_proxy="http://$PROXY"
fi

wanted() {   # version without its release suffix: everything, or the named ones
    [ ${#WANT[@]} -eq 0 ] && return 0
    local w
    for w in "${WANT[@]}"; do [ "$w" = "$1" ] && return 0; done
    return 1
}

fetch() {    # package name, file name
    local dir=$1 file=$2
    [ -s "$TC_DIR/dl/$file" ] && return 0
    mkdir -p "$TC_DIR/dl"
    echo "  fetching $file"
    curl "${curl_opts[@]}" -C - -o "$TC_DIR/dl/$file" "$ARCHIVE/$dir/$file" ||
        { echo "  DOWNLOAD FAILED: $ARCHIVE/$dir/$file" >&2; return 1; }
}

for row in "${TOOLCHAINS[@]}"; do
    # shellcheck disable=SC2086
    set -- $row
    gcc=$1; binutils=$2; newlib=$3
    version=${gcc%-*}
    wanted "$version" || continue

    prefix=$TC_DIR/$version
    if [ ! -x "$prefix/usr/bin/arm-none-eabi-gcc" ]; then
        echo "== unpacking $version (binutils $binutils, newlib $newlib, as packaged with it)"
        mkdir -p "$prefix"
        for spec in \
            "arm-none-eabi-gcc:arm-none-eabi-gcc-$gcc-x86_64" \
            "arm-none-eabi-binutils:arm-none-eabi-binutils-$binutils-x86_64" \
            "arm-none-eabi-newlib:arm-none-eabi-newlib-$newlib-any"
        do
            file=${spec#*:}.pkg.tar.zst
            fetch "${spec%%:*}" "$file" || exit 1
            # An archived package that is a valid zstd header but a truncated
            # stream is what a resumed download can leave behind, and it fails
            # later as a compiler that will not run.  Test the archive first.
            if ! tar --zstd -tf "$TC_DIR/dl/$file" >/dev/null 2>&1; then
                echo "  $file is not a complete archive; fetching it again" >&2
                rm -f "$TC_DIR/dl/$file"
                fetch "${spec%%:*}" "$file" || exit 1
                tar --zstd -tf "$TC_DIR/dl/$file" >/dev/null || { echo "  still broken" >&2; exit 1; }
            fi
            tar --zstd -xf "$TC_DIR/dl/${spec#*:}.pkg.tar.zst" -C "$prefix" || exit 1
            rm -f "$TC_DIR/dl/${spec#*:}.pkg.tar.zst"
        done
    fi
    echo "  $version: $("$prefix/usr/bin/arm-none-eabi-gcc" --version | head -1)"
done

for row in "${TOOLCHAINS[@]}"; do
    # shellcheck disable=SC2086
    set -- $row
    version=${1%-*}
    wanted "$version" || continue
    out=$OUT/$version
    rm -rf "$out"
    echo
    echo "########## $version, one core and two, at $POINTS kHz"
    "$HERE/probe.py" --board "$BOARD" --points "$POINTS" --soak 0 \
        --toolchain "$TC_DIR/$version/usr" --out "$out" || echo "  probe exited $?"
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
print("%-12s %-50s %s" % ("toolchain", "compiler", "  ".join("%-14s" % c for c in cols)))
for r in sorted(rows, key=lambda r: [int(x) for x in r["toolchain"].split(".")]):
    print("%-12s %-50s %s" % (r["toolchain"], (r.get("compiler") or "?")[:50],
                              "  ".join("%-14s" % (("%.3f" % r[c]) if c in r else "-")
                                        for c in cols)))
PY
