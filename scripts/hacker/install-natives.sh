#!/bin/sh
# Fetch the matching prebuilt @oh-my-pi/pi-natives-<os>-<arch> addon into the
# workspace tree so `omp` can start without a Rust/Bazel build.
set -eu

PREFIX="${OMP_FORK_ROOT:-$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)}"
NATIVE_PKG="$PREFIX/packages/natives/package.json"
DEST="$PREFIX/packages/natives/native"

log() { printf 'omp-natives: %s\n' "$*"; }

if [ ! -f "$NATIVE_PKG" ]; then
  echo "omp-natives: missing $NATIVE_PKG" >&2
  exit 1
fi

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "omp-natives: missing $1" >&2
    exit 1
  fi
}

need curl
need python3
need tar
need uname

ver="$(python3 -c "import json; print(json.load(open('$NATIVE_PKG'))['version'])")"
osname="$(uname -s | tr 'A-Z' 'a-z')"
arch="$(uname -m)"
case "$arch" in
  x86_64|amd64) arch=x64 ;;
  aarch64|arm64) arch=arm64 ;;
esac
plat="${osname}-${arch}"

# 18.3.4+ stamps PI_NATIVES_VERSION_STAMP:<ver>\0 after link.
# Older releases export __piNativesV<ver> instead. Either identity matches.
if python3 - "$ver" \
  "$DEST/pi_natives.${plat}-modern.node" \
  "$DEST/pi_natives.${plat}-baseline.node" \
  "$DEST/pi_natives.${plat}.node" <<'PY'
import pathlib, sys
ver = sys.argv[1]
stamp = b"PI_NATIVES_VERSION_STAMP:" + ver.encode() + b"\0"
legacy = ("__piNativesV" + "".join(c if c.isalnum() else "_" for c in ver)).encode()
def legacy_hit(data: bytes) -> bool:
    start = 0
    while True:
        at = data.find(legacy, start)
        if at < 0:
            return False
        nxt = data[at + len(legacy):at + len(legacy) + 1]
        if nxt == b"" or not (nxt.isalnum() or nxt == b"_"):
            return True
        start = at + 1
for raw in sys.argv[2:]:
    path = pathlib.Path(raw)
    if not path.is_file():
        continue
    data = path.read_bytes()
    if stamp in data or legacy_hit(data):
        sys.exit(0)
sys.exit(1)
PY
then
  log "already present in $DEST ($ver)"
  exit 0
fi
log "refresh $plat natives to $ver"

tgz="${TMPDIR:-/tmp}/pi-natives-${plat}-${ver}.tgz"
url="https://registry.npmjs.org/@oh-my-pi/pi-natives-${plat}/-/pi-natives-${plat}-${ver}.tgz"
log "download $url"
curl -fL --retry 3 --retry-delay 2 -o "$tgz" "$url"

unpack="${TMPDIR:-/tmp}/pi-natives-${plat}-${ver}-unpack"
rm -rf "$unpack"
mkdir -p "$unpack" "$DEST"
tar -xzf "$tgz" -C "$unpack"
found=0
for f in "$unpack"/package/pi_natives."${plat}"*.node; do
  [ -f "$f" ] || continue
  cp "$f" "$DEST/"
  log "installed $(basename "$f")"
  found=1
done
rm -rf "$unpack" "$tgz"
if [ "$found" -eq 0 ]; then
  echo "omp-natives: tarball had no .node for $plat" >&2
  exit 1
fi
log "done ($plat v$ver)"
