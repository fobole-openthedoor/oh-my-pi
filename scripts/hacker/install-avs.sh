#!/bin/sh
# Install the `avs` Android screen CLI so the avs-tools extension and the avs
# skill work. Prefers the prebuilt binary vendored in this kit (bin/avs-<os>-<arch>)
# and replaces an older copy at the install path. Falls back to `go build` from
# $AVS_SRC only when this OS/arch has no prebuilt. Best-effort: skips cleanly
# when nothing can produce a binary.
set -eu

KIT="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
AVS_SRC="${AVS_SRC:-$HOME/MagicPhone/avs}"
LAUNCHER_DIR="${OMP_LAUNCHER_DIR:-/usr/local/bin}"

log() { printf 'omp-install-avs: %s\n' "$*"; }

osname="$(uname -s | tr 'A-Z' 'a-z')"
arch="$(uname -m)"
case "$arch" in
  x86_64|amd64) arch=amd64 ;;
  aarch64|arm64) arch=arm64 ;;
esac
prebuilt="$KIT/bin/avs-${osname}-${arch}"

# Pick a writable install dir.
if [ -d "$LAUNCHER_DIR" ] && [ -w "$LAUNCHER_DIR" ]; then
  DEST="$LAUNCHER_DIR"
elif mkdir -p "$LAUNCHER_DIR" 2>/dev/null && [ -w "$LAUNCHER_DIR" ]; then
  DEST="$LAUNCHER_DIR"
else
  DEST="$HOME/.local/bin"
  mkdir -p "$DEST"
  log "$DEST (add to PATH if avs is not found)"
fi

if [ -f "$prebuilt" ]; then
  if [ -f "$DEST/avs" ] && cmp -s "$prebuilt" "$DEST/avs"; then
    log "prebuilt ${osname}-${arch} already at $DEST/avs"
    exit 0
  fi
  install -m 755 "$prebuilt" "$DEST/avs"
  log "installed prebuilt ${osname}-${arch} → $DEST/avs"
  exit 0
fi

if command -v avs >/dev/null 2>&1; then
  log "avs already on PATH ($(command -v avs)) — no prebuilt for ${osname}-${arch}, skip"
  exit 0
fi

log "no prebuilt for ${osname}-${arch}; trying source build"
if ! command -v go >/dev/null 2>&1; then
  log "go not found — skip (put a prebuilt avs on PATH, or install Go)"
  exit 0
fi
if [ ! -f "$AVS_SRC/go.mod" ] || [ ! -d "$AVS_SRC/cmd/avs" ]; then
  log "avs source not at \$AVS_SRC ($AVS_SRC) — skip"
  exit 0
fi
log "building avs from $AVS_SRC"
( cd "$AVS_SRC" && CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o "$DEST/avs" ./cmd/avs )
log "built → $DEST/avs"
