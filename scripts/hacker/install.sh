#!/bin/sh
# Install this oh-my-pi fork from git, then wire the omp launcher and seed a
# key-less replica of the beefsms environment.
# Does not install the upstream omp.sh binary. Does not write API keys.
set -eu

GIT_URL="${OMP_GIT_URL:-https://github.com/fobole-openthedoor/oh-my-pi.git}"
BRANCH="${OMP_GIT_BRANCH:-main}"
PREFIX="${OMP_FORK_ROOT:-$HOME/oh-my-pi}"
LAUNCHER_DIR="${OMP_LAUNCHER_DIR:-/usr/local/bin}"
ENV_FILE="${OMP_ENV:-$HOME/.config/omp/env}"
AGENT_DIR="${OMP_AGENT_DIR:-$HOME/.omp/agent}"
HERE="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "omp-install: missing $1" >&2
    exit 1
  fi
}

bun_new_enough() {
  python3 - "$1" <<'PY'
import sys
ver = sys.argv[1].split("+", 1)[0]
parts = []
for bit in ver.split("."):
    try:
        parts.append(int(bit))
    except ValueError:
        parts.append(0)
while len(parts) < 3:
    parts.append(0)
sys.exit(0 if tuple(parts[:3]) >= (1, 3, 14) else 1)
PY
}

ensure_bun() {
  export BUN_INSTALL="${BUN_INSTALL:-$HOME/.bun}"
  export PATH="$BUN_INSTALL/bin:$PATH"
  if command -v bun >/dev/null 2>&1 && bun_new_enough "$(bun --version)"; then
    return 0
  fi
  echo "omp-install: installing bun (>= 1.3.14)"
  curl -fsSL https://bun.sh/install | bash
  export PATH="$BUN_INSTALL/bin:$PATH"
  need bun
  if ! bun_new_enough "$(bun --version)"; then
    echo "omp-install: bun $(bun --version) is too old (need >= 1.3.14)" >&2
    exit 1
  fi
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
  echo "omp-install: $LAUNCHER_DIR (add this to PATH if omp is not found)"
}

need git
need python3
need curl
ensure_bun

clone_or_update() {
  if [ -d "$PREFIX/.git" ]; then
    echo "omp-install: existing checkout $PREFIX"
    git -C "$PREFIX" fetch --prune origin || true
    git -C "$PREFIX" checkout "$BRANCH" 2>/dev/null || \
      git -C "$PREFIX" checkout -B "$BRANCH"
    return 0
  fi
  mkdir -p "$(dirname "$PREFIX")"
  echo "omp-install: clone $GIT_URL → $PREFIX"
  git clone --branch "$BRANCH" "$GIT_URL" "$PREFIX"
}

clone_or_update
cd "$PREFIX"

KIT="$PREFIX/scripts/hacker"
if [ ! -d "$KIT" ] && [ -d "$HERE" ]; then
  KIT="$HERE"
fi

echo "omp-install: bun install"
bun install
if [ -f "$KIT/install-natives.sh" ]; then
  echo "omp-install: prebuilt natives"
  sh "$KIT/install-natives.sh"
fi
if [ -x "$PREFIX/scripts/link-omp.sh" ]; then
  echo "omp-install: link-omp.sh"
  sh "$PREFIX/scripts/link-omp.sh" || \
    echo "omp-install: link-omp.sh failed (non-fatal; launch.sh still works)" >&2
fi

LAUNCHER="$KIT/launch.sh"
if [ ! -f "$LAUNCHER" ]; then
  echo "omp-install: missing $LAUNCHER" >&2
  exit 1
fi
chmod +x "$LAUNCHER"
pick_launcher_dir
install -m 755 "$LAUNCHER" "$LAUNCHER_DIR/omp"
echo "omp-install: launcher → $LAUNCHER_DIR/omp"

mkdir -p "$(dirname "$ENV_FILE")" "$AGENT_DIR/skills" "$AGENT_DIR/extensions"
if [ ! -f "$ENV_FILE" ]; then
  cp "$KIT/env.example" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "omp-install: wrote $ENV_FILE from env.example — set OPENAI_API_KEY"
else
  echo "omp-install: keeping existing $ENV_FILE"
fi

ensure_env() {
  key="$1"
  value="$2"
  if grep -q "^export ${key}=" "$ENV_FILE" 2>/dev/null; then
    return 0
  fi
  printf '\nexport %s="%s"\n' "$key" "$value" >>"$ENV_FILE"
}

ensure_env OMP_FORK_ROOT "$PREFIX"
ensure_env OMP_BIN "$PREFIX/packages/coding-agent/scripts/omp"
ensure_env OMP_AGENT_DIR "$AGENT_DIR"

seed_file() {
  src="$1"
  dst="$2"
  if [ -f "$dst" ]; then
    echo "omp-install: keeping existing $dst"
    return 0
  fi
  python3 - "$src" "$dst" "$PREFIX" \
    "${GHIDRA_INSTALL_DIR:-${GHIDRA_HOME:-$HOME/tools/ghidra}}" \
    "${REVERSE_SKILL_ROOT:-$HOME/tools/reverse-skill}" \
    "${CLAUDE_RED_ROOT:-$HOME/tools/claude-red}" <<'PY'
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
print(f"omp-install: wrote {dst}")
PY
}

GHIDRA_HOME="${GHIDRA_INSTALL_DIR:-${GHIDRA_HOME:-$HOME/tools/ghidra}}"
REVERSE_SKILL_ROOT="${REVERSE_SKILL_ROOT:-$HOME/tools/reverse-skill}"
CLAUDE_RED_ROOT="${CLAUDE_RED_ROOT:-$HOME/tools/claude-red}"
JAVA_HOME_VAL="${JAVA_HOME:-/usr/lib/jvm/java-21-openjdk-amd64}"

seed_file "$KIT/models.yml.example" "$AGENT_DIR/models.yml"
seed_file "$KIT/config.yml.example" "$AGENT_DIR/config.yml"
seed_file "$KIT/mcp.json.example" "$AGENT_DIR/mcp.json"
seed_file "$KIT/AGENTS.md.example" "$AGENT_DIR/AGENTS.md"
seed_file "$KIT/skills/reverse-skill/SKILL.md" \
  "$AGENT_DIR/skills/reverse-skill/SKILL.md"
seed_file "$KIT/skills/crack/SKILL.md" \
  "$AGENT_DIR/skills/crack/SKILL.md"
seed_file "$KIT/skills/claude-red/SKILL.md" \
  "$AGENT_DIR/skills/claude-red/SKILL.md"

for ext in glm-auto-continue.ts beefsms-kimi-thinking.ts beefsms-provider.ts; do
  if [ -f "$KIT/extensions/$ext" ]; then
    install -m 644 "$KIT/extensions/$ext" "$AGENT_DIR/extensions/$ext"
    echo "omp-install: extension → $AGENT_DIR/extensions/$ext"
  fi
done

if [ -f "$KIT/sync-user-memory.py" ]; then
  python3 "$KIT/sync-user-memory.py" \
    --agents-md "$AGENT_DIR/AGENTS.md" \
    --fork-root "$PREFIX" \
    --claude-red-root "$CLAUDE_RED_ROOT"
fi

if [ "${OMP_SKIP_CLAUDE_RED:-0}" != "1" ]; then
  if [ -f "$KIT/install-claude-red.sh" ]; then
    echo "omp-install: claude-red pack"
    if ! sh "$KIT/install-claude-red.sh"; then
      echo "omp-install: claude-red clone failed (non-fatal; retry $KIT/install-claude-red.sh)" >&2
    fi
  fi
fi

if command -v re-mcp-ghidra >/dev/null 2>&1 || [ -x "$HOME/.local/bin/re-mcp-ghidra" ]; then
  MCP_CMD="$(command -v re-mcp-ghidra 2>/dev/null || true)"
  if [ -z "$MCP_CMD" ]; then
    MCP_CMD="$HOME/.local/bin/re-mcp-ghidra"
  fi
  python3 "$KIT/wire-ghidra-mcp.py" \
    "$AGENT_DIR/mcp.json" "$MCP_CMD" "$GHIDRA_HOME" "$JAVA_HOME_VAL"
else
  echo "omp-install: re-mcp-ghidra not on PATH — skip MCP (optional)"
fi

echo "omp-install: done"
echo "omp-install: $PREFIX @ $(git -C "$PREFIX" log -1 --oneline)"
echo "omp-install: set OPENAI_API_KEY in $ENV_FILE (beefsms), then: omp"
echo "omp-install: later: $KIT/update.sh"
echo "omp-install: reverse env: $KIT/install-reverse.sh"
echo "omp-install: claude-red: $KIT/install-claude-red.sh"
echo "omp-install: or paste $PREFIX/PROMPT.md to another AI"
