#!/bin/sh
# Install SnailSploit/Claude-Red as the omp /skill:claude-red pack.
# Idempotent. Markdown only — no Ghidra-sized downloads.
set -eu

KIT="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
TOOLS="${CLAUDE_RED_TOOLS_DIR:-$HOME/tools}"
CLAUDE_RED_DIR="${CLAUDE_RED_DIR:-$TOOLS/claude-red}"
CLAUDE_RED_REPO="${CLAUDE_RED_REPO:-https://github.com/SnailSploit/Claude-Red.git}"
AGENT_DIR="${OMP_AGENT_DIR:-$HOME/.omp/agent}"
ENV_FILE="${OMP_ENV:-$HOME/.config/omp/env}"
FORK_ROOT="${OMP_FORK_ROOT:-$HOME/oh-my-pi}"

log() { printf 'omp-claude-red: %s\n' "$*"; }

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "omp-claude-red: missing $1" >&2
    exit 1
  fi
}

ensure_env() {
  key="$1"
  value="$2"
  mkdir -p "$(dirname "$ENV_FILE")"
  if [ ! -f "$ENV_FILE" ]; then
    return 0
  fi
  if grep -q "^export ${key}=" "$ENV_FILE" 2>/dev/null; then
    return 0
  fi
  printf '\nexport %s="%s"\n' "$key" "$value" >>"$ENV_FILE"
}

need git
need python3

mkdir -p "$TOOLS"

if [ -d "$CLAUDE_RED_DIR/.git" ]; then
  log "already at $CLAUDE_RED_DIR"
  # Descriptions are rewritten onto upstream SKILL.md files. Restore those
  # paths first so a dirty tree does not block a fast-forward, then rewrite.
  git -C "$CLAUDE_RED_DIR" checkout -- Skills \
    || log "could not restore Skills before update"
  git -C "$CLAUDE_RED_DIR" fetch --prune --quiet || true
  git -C "$CLAUDE_RED_DIR" merge --ff-only --quiet FETCH_HEAD 2>/dev/null || \
    log "left existing checkout as-is (not fast-forward)"
else
  log "clone $CLAUDE_RED_REPO → $CLAUDE_RED_DIR"
  git clone --depth 1 "$CLAUDE_RED_REPO" "$CLAUDE_RED_DIR"
fi

count="$(find "$CLAUDE_RED_DIR/Skills" -name SKILL.md 2>/dev/null | wc -l | tr -d ' ')"
if [ "$count" -eq 0 ]; then
  echo "omp-claude-red: no SKILL.md under $CLAUDE_RED_DIR/Skills" >&2
  exit 1
fi

log "generating INDEX.md ($count skills)"
python3 "$KIT/skills/claude-red/index.py" --root "$CLAUDE_RED_DIR"

mkdir -p "$AGENT_DIR/skills/claude-red" \
  "$AGENT_DIR/skills/reverse-skill" \
  "$AGENT_DIR/skills/crack"
for adapter in claude-red reverse-skill crack; do
  if [ -f "$KIT/skills/$adapter/SKILL.md" ]; then
    mkdir -p "$AGENT_DIR/skills/$adapter"
    cp "$KIT/skills/$adapter/SKILL.md" \
      "$AGENT_DIR/skills/$adapter/SKILL.md"
    log "adapter → $AGENT_DIR/skills/$adapter/SKILL.md"
  fi
done

ensure_env CLAUDE_RED_ROOT "$CLAUDE_RED_DIR"
ensure_env OMP_FORK_ROOT "$FORK_ROOT"

mkdir -p "$AGENT_DIR/skills"
linked=0
for cat in "$CLAUDE_RED_DIR/Skills"/*; do
  [ -d "$cat" ] || continue
  for skill_dir in "$cat"/*; do
    [ -f "$skill_dir/SKILL.md" ] || continue
    name="$(basename "$skill_dir")"
    case "$name" in
      reverse-skill|claude-red|crack)
        log "skip reserved name $name"
        continue
        ;;
    esac
    dest="$AGENT_DIR/skills/$name"
    if [ -e "$dest" ] && [ ! -L "$dest" ]; then
      log "keep existing non-symlink $dest"
      continue
    fi
    ln -sfn "$skill_dir" "$dest"
    linked=$((linked + 1))
  done
done
log "linked $linked skills → $AGENT_DIR/skills/<name>"

python3 "$KIT/skills/claude-red/index.py" --root "$CLAUDE_RED_DIR" --ensure-descriptions
python3 "$KIT/sync-user-memory.py" \
  --agents-md "$AGENT_DIR/AGENTS.md" \
  --fork-root "$FORK_ROOT" \
  --claude-red-root "$CLAUDE_RED_DIR"

log "done"
log "claude-red $CLAUDE_RED_DIR ($count skills, $linked linked)"
log "verify: $KIT/verify-claude-red.sh"
log "in omp: 逆向 → /skill:reverse-skill ; 破解 → /skill:crack ; 渗透 → offensive-*"
