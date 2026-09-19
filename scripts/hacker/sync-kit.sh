#!/bin/sh
# Re-seed this fork's kit into ~/.omp/agent.
# Overwrites extensions and skill adapters. Merges config.yml (kit-owned keys)
# and beefsms compactionModel. Does not overwrite API keys or ~/.config/omp/env.
set -eu

KIT="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
PREFIX="${OMP_FORK_ROOT:-$(CDPATH= cd -- "$KIT/../.." && pwd)}"
AGENT_DIR="${OMP_AGENT_DIR:-$HOME/.omp/agent}"
ENV_FILE="${OMP_ENV:-$HOME/.config/omp/env}"
LAUNCHER_DIR="${OMP_LAUNCHER_DIR:-/usr/local/bin}"
GHIDRA_HOME="${GHIDRA_INSTALL_DIR:-${GHIDRA_HOME:-$HOME/tools/ghidra}}"
REVERSE_SKILL_ROOT="${REVERSE_SKILL_ROOT:-$HOME/tools/reverse-skill}"
CLAUDE_RED_ROOT="${CLAUDE_RED_ROOT:-$HOME/tools/claude-red}"
JAVA_HOME_VAL="${JAVA_HOME:-/usr/lib/jvm/java-21-openjdk-amd64}"

log() { printf 'omp-sync-kit: %s\n' "$*"; }

ensure_env() {
  key="$1"
  value="$2"
  [ -f "$ENV_FILE" ] || return 0
  if grep -q "^export ${key}=" "$ENV_FILE" 2>/dev/null; then
    return 0
  fi
  printf '\nexport %s="%s"\n' "$key" "$value" >>"$ENV_FILE"
}

seed_if_missing() {
  src="$1"
  dst="$2"
  if [ -f "$dst" ]; then
    return 0
  fi
  python3 - "$src" "$dst" "$PREFIX" "$GHIDRA_HOME" "$REVERSE_SKILL_ROOT" "$CLAUDE_RED_ROOT" <<'PY'
import os, sys
src, dst, fork, ghidra, reverse, claude_red = sys.argv[1:7]
text = open(src, encoding="utf-8").read()
text = (
    text.replace("__OMP_FORK_ROOT__", fork)
    .replace("__GHIDRA_HOME__", ghidra)
    .replace("__REVERSE_SKILL_ROOT__", reverse)
    .replace("__CLAUDE_RED_ROOT__", claude_red)
)
os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
with open(dst, "w", encoding="utf-8") as f:
    f.write(text)
os.chmod(dst, 0o600)
print(f"omp-sync-kit: wrote {dst}")
PY
}

pick_launcher_dir() {
  if [ -d "$LAUNCHER_DIR" ] && [ -w "$LAUNCHER_DIR" ]; then
    return 0
  fi
  if mkdir -p "$LAUNCHER_DIR" 2>/dev/null && [ -w "$LAUNCHER_DIR" ]; then
    return 0
  fi
  LAUNCHER_DIR="${HOME}/.local/bin"
  mkdir -p "$LAUNCHER_DIR"
  log "$LAUNCHER_DIR (add this to PATH if omp is not found)"
}

mkdir -p "$AGENT_DIR/skills" "$AGENT_DIR/extensions" "$(dirname "$ENV_FILE")"
ensure_env DOMAIN_ROUTE "${DOMAIN_ROUTE:-1}"
ensure_env DOMAIN_ROUTE_GATE "${DOMAIN_ROUTE_GATE:-1}"
ensure_env DROP_DEGENERATE_THINKING "${DROP_DEGENERATE_THINKING:-1}"

seed_if_missing "$KIT/models.yml.example" "$AGENT_DIR/models.yml"
seed_if_missing "$KIT/mcp.json.example" "$AGENT_DIR/mcp.json"
seed_if_missing "$KIT/AGENTS.md.example" "$AGENT_DIR/AGENTS.md"
seed_if_missing "$KIT/config.yml.example" "$AGENT_DIR/config.yml"

python3 "$KIT/merge-config.py" --config "$AGENT_DIR/config.yml" --example "$KIT/config.yml.example"

for ext in "$KIT/extensions"/*.ts; do
  [ -f "$ext" ] || continue
  base="$(basename "$ext")"
  install -m 644 "$ext" "$AGENT_DIR/extensions/$base"
  log "extension → $AGENT_DIR/extensions/$base"
done

mkdir -p "$AGENT_DIR/rules"
for rule in "$KIT/rules"/*.md; do
  [ -f "$rule" ] || continue
  base="$(basename "$rule")"
  install -m 644 "$rule" "$AGENT_DIR/rules/$base"
  log "rule → $AGENT_DIR/rules/$base"
done

for adapter in reverse-skill crack claude-red avs; do
  if [ -f "$KIT/skills/$adapter/SKILL.md" ]; then
    mkdir -p "$AGENT_DIR/skills/$adapter"
    install -m 644 "$KIT/skills/$adapter/SKILL.md" "$AGENT_DIR/skills/$adapter/SKILL.md"
    log "adapter → $AGENT_DIR/skills/$adapter/SKILL.md"
  fi
done

python3 "$KIT/sync-user-memory.py" \
  --agents-md "$AGENT_DIR/AGENTS.md" \
  --fork-root "$PREFIX" \
  --claude-red-root "$CLAUDE_RED_ROOT" \
  --reverse-root "$REVERSE_SKILL_ROOT" \
  --ghidra "$GHIDRA_HOME"

MCP_CMD="$(command -v re-mcp-ghidra 2>/dev/null || true)"
if [ -z "$MCP_CMD" ] && [ -x "$HOME/.local/bin/re-mcp-ghidra" ]; then
  MCP_CMD="$HOME/.local/bin/re-mcp-ghidra"
fi
if [ -n "$MCP_CMD" ]; then
  python3 "$KIT/wire-ghidra-mcp.py" \
    "$AGENT_DIR/mcp.json" "$MCP_CMD" "$GHIDRA_HOME" "$JAVA_HOME_VAL"
else
  log "re-mcp-ghidra not on PATH — skip MCP wire"
fi

if [ -f "$KIT/launch.sh" ]; then
  chmod +x "$KIT/launch.sh"
  pick_launcher_dir
  install -m 755 "$KIT/launch.sh" "$LAUNCHER_DIR/omp"
  log "launcher → $LAUNCHER_DIR/omp"
fi

chmod +x "$KIT/ghidra-open.sh" "$KIT/merge-config.py" "$KIT/skills/domain-route.py" 2>/dev/null || true
log "done"
