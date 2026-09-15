#!/bin/sh
# Check that Claude-Red is cloned and the omp adapter can route.
set -eu

KIT="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
TOOLS="${CLAUDE_RED_TOOLS_DIR:-$HOME/tools}"
CLAUDE_RED_DIR="${CLAUDE_RED_DIR:-${CLAUDE_RED_ROOT:-$TOOLS/claude-red}}"
AGENT_DIR="${OMP_AGENT_DIR:-$HOME/.omp/agent}"
ENV_FILE="${OMP_ENV:-$HOME/.config/omp/env}"
FAIL=0

ok() { printf 'ok   %s\n' "$*"; }
bad() { printf 'FAIL %s\n' "$*"; FAIL=1; }

if [ -d "$CLAUDE_RED_DIR/Skills" ]; then
  count="$(find "$CLAUDE_RED_DIR/Skills" -name SKILL.md | wc -l | tr -d ' ')"
  ok "claude-red → $CLAUDE_RED_DIR ($count SKILL.md)"
else
  bad "missing $CLAUDE_RED_DIR/Skills (run $KIT/install-claude-red.sh)"
  count=0
fi

if [ -f "$CLAUDE_RED_DIR/INDEX.md" ] || [ -f "$CLAUDE_RED_DIR/INDEX.openclaude.md" ]; then
  ok "skill index present"
else
  bad "INDEX.md missing"
fi

if [ -f "$AGENT_DIR/skills/claude-red/SKILL.md" ]; then
  ok "adapter → $AGENT_DIR/skills/claude-red/SKILL.md"
else
  bad "adapter SKILL.md missing"
fi

if [ -f "$AGENT_DIR/skills/crack/SKILL.md" ]; then
  ok "adapter → $AGENT_DIR/skills/crack/SKILL.md"
else
  bad "crack SKILL.md missing"
fi

if [ -f "$AGENT_DIR/skills/offensive-sqli/SKILL.md" ]; then
  ok "skill offensive-sqli → $AGENT_DIR/skills/offensive-sqli"
else
  bad "offensive-sqli not linked into $AGENT_DIR/skills"
fi

linked="$(find -L "$AGENT_DIR/skills" -name SKILL.md 2>/dev/null | wc -l | tr -d ' ')"
if [ "$linked" -ge 78 ]; then
  ok "agent skills dir has $linked SKILL.md"
else
  bad "expected ≥78 SKILL.md under $AGENT_DIR/skills, got $linked"
fi

if [ -f "$ENV_FILE" ] && grep -q '^export CLAUDE_RED_ROOT=' "$ENV_FILE"; then
  ok "CLAUDE_RED_ROOT in $ENV_FILE"
else
  bad "CLAUDE_RED_ROOT not in $ENV_FILE"
fi

if [ -f "$AGENT_DIR/AGENTS.md" ] && grep -q 'Work mode: 逆向 / 破解 / 渗透' "$AGENT_DIR/AGENTS.md"; then
  ok "AGENTS.md has 逆向/破解/渗透 work mode"
else
  bad "AGENTS.md missing Work mode triage"
fi

if [ -f "$AGENT_DIR/extensions/glm-auto-continue.ts" ]; then
  ok "glm-auto-continue.ts present"
else
  bad "glm-auto-continue.ts missing"
fi

if [ -f "$AGENT_DIR/extensions/beefsms-kimi-thinking.ts" ]; then
  ok "beefsms-kimi-thinking.ts present"
else
  bad "beefsms-kimi-thinking.ts missing"
fi

if [ -f "$AGENT_DIR/extensions/beefsms-provider.ts" ]; then
  ok "beefsms-provider.ts present"
else
  bad "beefsms-provider.ts missing"
fi

if [ -f "$KIT/skills/domain-route.py" ]; then
  domain="$(python3 "$KIT/skills/domain-route.py" --hint '脱壳去校验' | awk '/^DOMAIN/{print $2}')"
  if [ "$domain" = "crack" ]; then
    ok "domain-route 脱壳 → crack"
  else
    bad "domain-route 脱壳 expected crack, got $domain"
  fi
else
  bad "domain-route.py missing"
fi

if [ -f "$KIT/skills/claude-red/route.py" ] && [ "$count" -gt 0 ]; then
  out="$(python3 "$KIT/skills/claude-red/route.py" --root "$CLAUDE_RED_DIR" --hint sqli || true)"
  case "$out" in
    *offensive-sqli*) ok "route sqli → offensive-sqli" ;;
    *) bad "route sqli missed offensive-sqli: $out" ;;
  esac
else
  bad "router script missing or pack empty"
fi

if [ "$FAIL" -ne 0 ]; then
  echo "omp-claude-red: verify failed"
  exit 1
fi
echo "omp-claude-red: verify passed"
