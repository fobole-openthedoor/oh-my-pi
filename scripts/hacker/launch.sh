#!/bin/sh
# Fork launcher. Sources a dedicated env file so ~/.bashrc OPENAI_BASE_URL
# (strix/cige/other agents) does not leak into this CLI.
ENV_FILE="${OMP_ENV:-$HOME/.config/omp/env}"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

# Placeholder is not a real key. Leave unset so /login beefsms can store one.
case "${OPENAI_API_KEY:-}" in
  ""|"PASTE_YOUR_BEEFSMS_KEY_HERE"|*"set in ~/.config/omp/env"*)
    unset OPENAI_API_KEY
    ;;
esac
case "${BEEFSMS_API_KEY:-}" in
  ""|"PASTE_YOUR_BEEFSMS_KEY_HERE")
    unset BEEFSMS_API_KEY
    ;;
esac

# Bun/node crash with uv_cwd if this shell is sitting in a deleted directory.
if ! pwd >/dev/null 2>&1; then
  echo "omp: current directory is gone; falling back to \$HOME" >&2
  cd "${HOME:-/}" || exit 1
fi

export BUN_INSTALL="${BUN_INSTALL:-$HOME/.bun}"
export PATH="$BUN_INSTALL/bin:$PATH"

FORK_ROOT="${OMP_FORK_ROOT:-$HOME/oh-my-pi}"
BIN="${OMP_BIN:-$FORK_ROOT/packages/coding-agent/scripts/omp}"
if [ ! -x "$BIN" ]; then
  echo "omp: binary not found at $BIN" >&2
  echo "omp: expected fork at $FORK_ROOT (scripts/hacker/install.sh)" >&2
  exit 1
fi
if ! command -v bun >/dev/null 2>&1; then
  echo "omp: bun not on PATH (install bun ≥ 1.3.14)" >&2
  exit 1
fi
exec "$BIN" "$@"
