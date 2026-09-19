#!/bin/sh
# Update the local oh-my-pi fork: fetch, fast-forward, bun install.
set -eu

ROOT="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [ ! -d .git ]; then
  echo "omp-update: $ROOT is not a git checkout" >&2
  exit 1
fi

if ! command -v bun >/dev/null 2>&1; then
  echo "omp-update: bun is required (https://bun.sh)" >&2
  exit 1
fi

pick_remote() {
  if [ -n "${OMP_GIT_REMOTE:-}" ]; then
    if git remote get-url "$OMP_GIT_REMOTE" >/dev/null 2>&1; then
      printf '%s\n' "$OMP_GIT_REMOTE"
      return 0
    fi
    echo "omp-update: unknown remote $OMP_GIT_REMOTE" >&2
    exit 1
  fi
  for r in origin github; do
    if git remote get-url "$r" >/dev/null 2>&1; then
      printf '%s\n' "$r"
      return 0
    fi
  done
  git remote | head -1
}

REMOTE="$(pick_remote)"
if [ -z "$REMOTE" ]; then
  echo "omp-update: no git remotes" >&2
  exit 1
fi

BRANCH="${OMP_GIT_BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"
if [ "$BRANCH" = "HEAD" ]; then
  echo "omp-update: detached HEAD; set OMP_GIT_BRANCH" >&2
  exit 1
fi

echo "omp-update: $ROOT"
echo "omp-update: was $(git log -1 --oneline)"
echo "omp-update: fetch $REMOTE $BRANCH"

git fetch --prune "$REMOTE" "$BRANCH"

if ! git merge-base --is-ancestor HEAD "$REMOTE/$BRANCH" && \
   ! git merge-base --is-ancestor "$REMOTE/$BRANCH" HEAD; then
  echo "omp-update: local and $REMOTE/$BRANCH have diverged; merge/rebase by hand" >&2
  exit 1
fi

git checkout "$BRANCH" >/dev/null 2>&1 || git checkout -B "$BRANCH" "$REMOTE/$BRANCH"
git merge --ff-only "$REMOTE/$BRANCH"

echo "omp-update: bun install"
bun install
if [ -x "$ROOT/scripts/link-omp.sh" ]; then
  sh "$ROOT/scripts/link-omp.sh" || true
fi
if [ -x "$ROOT/scripts/hacker/install-natives.sh" ]; then
  sh "$ROOT/scripts/hacker/install-natives.sh" || true
fi
if [ -f "$ROOT/scripts/hacker/install-avs.sh" ]; then
  echo "omp-update: avs android screen cli (best-effort)"
  sh "$ROOT/scripts/hacker/install-avs.sh" || echo "omp-update: avs build skipped/failed (non-fatal)"
fi

KIT="$ROOT/scripts/hacker"
export OMP_FORK_ROOT="$ROOT"
echo "omp-update: sync kit into ~/.omp/agent"
sh "$KIT/sync-kit.sh"

CLAUDE_RED_DIR="${CLAUDE_RED_ROOT:-$HOME/tools/claude-red}"
if [ -d "$CLAUDE_RED_DIR/.git" ] && [ -f "$KIT/install-claude-red.sh" ]; then
  echo "omp-update: refresh claude-red links"
  sh "$KIT/install-claude-red.sh" || \
    echo "omp-update: claude-red refresh failed (non-fatal)" >&2
fi

echo "omp-update: now $(git log -1 --oneline)"
echo "omp-update: restart omp to load the new tree"
