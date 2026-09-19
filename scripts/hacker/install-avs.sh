#!/bin/sh
# Build and install the `avs` Android screen CLI so the avs-tools extension and
# the avs skill work. Best-effort: skips cleanly if avs is already on PATH or
# the toolchain/source is missing. avs is developed in its own repo; point
# AVS_SRC at that checkout (default: $HOME/MagicPhone/avs).
set -eu

AVS_SRC="${AVS_SRC:-$HOME/MagicPhone/avs}"
LAUNCHER_DIR="${OMP_LAUNCHER_DIR:-/usr/local/bin}"

log() { printf 'omp-install-avs: %s\n' "$*"; }

if command -v avs >/dev/null 2>&1; then
  log "avs already on PATH ($(command -v avs)) — skip"
  exit 0
fi

if ! command -v go >/dev/null 2>&1; then
  log "go not found — skip (install Go and re-run, or put a prebuilt avs on PATH)"
  exit 0
fi

if [ ! -f "$AVS_SRC/go.mod" ] || [ ! -d "$AVS_SRC/cmd/avs" ]; then
  log "avs source not at \$AVS_SRC ($AVS_SRC) — skip (set AVS_SRC to the avs checkout)"
  exit 0
fi

if [ -d "$LAUNCHER_DIR" ] && [ -w "$LAUNCHER_DIR" ]; then
  DEST="$LAUNCHER_DIR"
elif mkdir -p "$LAUNCHER_DIR" 2>/dev/null && [ -w "$LAUNCHER_DIR" ]; then
  DEST="$LAUNCHER_DIR"
else
  DEST="$HOME/.local/bin"
  mkdir -p "$DEST"
  log "$DEST (add to PATH if avs is not found)"
fi

log "building avs from $AVS_SRC"
( cd "$AVS_SRC" && go build -o "$DEST/avs" ./cmd/avs )
log "installed → $DEST/avs"
