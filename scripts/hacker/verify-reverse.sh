#!/bin/sh
# Check that this machine matches the oh-my-pi + reverse replica.
set -eu

KIT="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$KIT/reverse-versions.env"

TOOLS="${REVERSE_SKILL_TOOLS_DIR:-$HOME/tools}"
REVERSE_SKILL_DIR="${REVERSE_SKILL_DIR:-$TOOLS/reverse-skill}"
GHIDRA_HOME="${GHIDRA_INSTALL_DIR:-${GHIDRA_HOME:-$TOOLS/ghidra}}"
JADX_DIR="${JADX_DIR:-$TOOLS/jadx}"
AGENT_DIR="${OMP_AGENT_DIR:-$HOME/.omp/agent}"
ENV_FILE="${OMP_ENV:-$HOME/.config/omp/env}"
FAIL=0

ok() { printf 'ok   %s\n' "$*"; }
bad() { printf 'FAIL %s\n' "$*"; FAIL=1; }

have() { command -v "$1" >/dev/null 2>&1; }

check_cmd() {
  if have "$1"; then
    ok "$1 → $(command -v "$1")"
  else
    bad "missing $1"
  fi
}

check_cmd git
check_cmd python3
check_cmd java
check_cmd pipx
check_cmd r2
check_cmd jadx
check_cmd apktool
check_cmd binwalk
check_cmd frida
check_cmd objection
check_cmd pwn
check_cmd re-mcp-ghidra

if [ -x "$GHIDRA_HOME/support/analyzeHeadless" ]; then
  ok "analyzeHeadless → $GHIDRA_HOME/support/analyzeHeadless"
else
  bad "analyzeHeadless not at $GHIDRA_HOME/support/analyzeHeadless"
fi

if [ -f "$REVERSE_SKILL_DIR/RULES.md" ]; then
  ok "reverse-skill → $REVERSE_SKILL_DIR"
else
  bad "reverse-skill RULES.md missing at $REVERSE_SKILL_DIR"
fi

if [ -f "$REVERSE_SKILL_DIR/skills/tool-index.md" ]; then
  ok "tool-index.md present"
else
  bad "tool-index.md missing (run bash $REVERSE_SKILL_DIR/skills/scripts/refresh-tool-index.sh)"
fi

if [ -f "$ENV_FILE" ]; then
  if grep -q 'openai.beefsms.com:38888' "$ENV_FILE"; then
    ok "env vendor is beefsms"
  else
    bad "$ENV_FILE is not the beefsms vendor"
  fi
  if grep -q 'PASTE_YOUR_BEEFSMS_KEY_HERE' "$ENV_FILE"; then
    bad "OPENAI_API_KEY still placeholder in $ENV_FILE"
  else
    ok "OPENAI_API_KEY looks filled"
  fi
else
  bad "missing $ENV_FILE"
fi

if [ -f "$AGENT_DIR/mcp.json" ]; then
  python3 - "$AGENT_DIR/mcp.json" <<'PY' || FAIL=1
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
g = (d.get("mcpServers") or {}).get("ghidra")
if not g:
    print("FAIL no mcpServers.ghidra in", p)
    raise SystemExit(1)
if g.get("command") in (None, ""):
    print("FAIL ghidra MCP command empty")
    raise SystemExit(1)
blob = json.dumps(g)
if "apiKey" in blob:
    print("FAIL ghidra MCP unexpectedly contains apiKey")
    raise SystemExit(1)
print("ok   ghidra MCP", g.get("command"), g.get("args"))
PY
else
  bad "missing $AGENT_DIR/mcp.json"
fi

if [ -f "$AGENT_DIR/models.yml" ]; then
  if grep -q 'PASTE_YOUR_BEEFSMS_KEY_HERE' "$AGENT_DIR/models.yml" || \
     grep -qE 'apiKey: sk-' "$AGENT_DIR/models.yml"; then
    bad "$AGENT_DIR/models.yml looks like it contains a real key"
  else
    ok "models.yml does not embed a key"
  fi
else
  bad "missing $AGENT_DIR/models.yml"
fi

if have java; then
  ver="$(java -version 2>&1 | head -1)"
  case "$ver" in
    *21*) ok "java $ver" ;;
    *) bad "java is not 21: $ver" ;;
  esac
fi

if [ "$FAIL" -ne 0 ]; then
  echo "omp-reverse: verify failed"
  exit 1
fi
echo "omp-reverse: verify passed"
