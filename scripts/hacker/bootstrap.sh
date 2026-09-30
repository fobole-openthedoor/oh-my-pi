#!/bin/sh
# One-command replica of this oh-my-pi fork.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/fobole-openthedoor/oh-my-pi/main/scripts/hacker/bootstrap.sh | sh
# Then edit ~/.config/omp/env and set OPENAI_API_KEY (same beefsms vendor).
set -eu

BRANCH="${OMP_GIT_BRANCH:-main}"
PREFIX="${OMP_FORK_ROOT:-$HOME/oh-my-pi}"
GIT_URL="${OMP_GIT_URL:-https://github.com/fobole-openthedoor/oh-my-pi.git}"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "omp-bootstrap: missing $1" >&2
    exit 1
  fi
}

need git
need python3

if ! command -v bun >/dev/null 2>&1; then
  echo "omp-bootstrap: installing bun"
  curl -fsSL https://bun.sh/install | bash
  export BUN_INSTALL="${BUN_INSTALL:-$HOME/.bun}"
  export PATH="$BUN_INSTALL/bin:$PATH"
fi
need bun

if [ -d "$PREFIX/.git" ]; then
  echo "omp-bootstrap: existing checkout $PREFIX"
else
  mkdir -p "$(dirname "$PREFIX")"
  echo "omp-bootstrap: clone $GIT_URL ($BRANCH) → $PREFIX"
  git clone --branch "$BRANCH" "$GIT_URL" "$PREFIX"
fi

sh "$PREFIX/scripts/hacker/install.sh"
if [ "${OMP_WITH_REVERSE:-0}" = "1" ]; then
  echo "omp-bootstrap: installing reverse stack"
  sh "$PREFIX/scripts/hacker/install-reverse.sh"
fi
