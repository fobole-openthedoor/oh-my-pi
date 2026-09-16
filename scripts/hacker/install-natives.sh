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
sentinel="$(python3 -c "print('__piNativesV' + ''.join(c if c.isalnum() else '_' for c in '$ver'))")"
osname="$(uname -s | tr 'A-Z' 'a-z')"
arch="$(uname -m)"
case "$arch" in
  x86_64|amd64) arch=x64 ;;
  aarch64|arm64) arch=arm64 ;;
esac
plat="${osname}-${arch}"

have_match=0
for f in "$DEST/pi_natives.${plat}-modern.node" \
         "$DEST/pi_natives.${plat}-baseline.node" \
         "$DEST/pi_natives.${plat}.node"; do
  [ -f "$f" ] || continue
  if grep -a -F -q "$sentinel" "$f"; then
    have_match=1
    break
  fi
done
if [ "$have_match" -eq 1 ]; then
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
