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

if [ -f "$AGENT_DIR/extensions/beefsms-kimi-thinking.ts" ]; then
  ok "beefsms-kimi-thinking.ts present"
else
  bad "beefsms-kimi-thinking.ts missing"
fi

if [ -f "$AGENT_DIR/extensions/beefsms-provider.ts" ]; then
  ok "beefsms-provider.ts present"
  if grep -q 'id: "deepseek-flash"' "$AGENT_DIR/extensions/beefsms-provider.ts"; then
    ok "beefsms model deepseek-flash"
  else
    bad "beefsms-provider.ts missing deepseek-flash"
  fi
  if grep -q 'happy/glm-5.3-plus' "$AGENT_DIR/extensions/beefsms-provider.ts"; then
    ok "beefsms model happy/glm-5.3-plus"
  else
    bad "beefsms-provider.ts missing happy/glm-5.3-plus"
  fi
else
  bad "beefsms-provider.ts missing"
fi

if [ -f "$AGENT_DIR/config.yml" ] && grep -Eq "vision:[[:space:]]*['\"]?beefsms/deepseek-flash:low" "$AGENT_DIR/config.yml"; then
  ok "modelRoles.vision → beefsms/deepseek-flash:low"
else
  bad "config.yml vision role is not beefsms/deepseek-flash:low"
fi

if [ -f "$AGENT_DIR/config.yml" ] && grep -Eq "default:[[:space:]]*['\"]?beefsms/happy/glm-5.3-plus" "$AGENT_DIR/config.yml"; then
  ok "modelRoles.default → beefsms/happy/glm-5.3-plus"
else
  bad "config.yml default role is not beefsms/happy/glm-5.3-plus"
fi

if [ -f "$AGENT_DIR/config.yml" ] && grep -Eq "smol:[[:space:]]*['\"]?beefsms/deepseek-flash(['\"]|$)" "$AGENT_DIR/config.yml"; then
  ok "modelRoles.smol → beefsms/deepseek-flash"
else
  bad "config.yml smol role is not beefsms/deepseek-flash"
fi

if [ -f "$AGENT_DIR/config.yml" ] && grep -Eq "compact:[[:space:]]*['\"]?beefsms/deepseek-flash(['\"]|$)" "$AGENT_DIR/config.yml"; then
  ok "modelRoles.compact → beefsms/deepseek-flash"
else
  bad "config.yml compact role is not beefsms/deepseek-flash"
fi

if [ -f "$AGENT_DIR/models.yml" ] && grep -q 'compactionModel: beefsms/deepseek-flash' "$AGENT_DIR/models.yml"; then
  ok "models.yml compactionModel → beefsms/deepseek-flash"
else
  bad "models.yml missing compactionModel beefsms/deepseek-flash"
fi

if [ -f "$AGENT_DIR/extensions/beefsms-provider.ts" ] && grep -q 'beefsms/deepseek-flash' "$AGENT_DIR/extensions/beefsms-provider.ts" && grep -q 'compactionModel' "$AGENT_DIR/extensions/beefsms-provider.ts"; then
  ok "beefsms-provider.ts compactionModel → beefsms/deepseek-flash"
else
  bad "beefsms-provider.ts missing compactionModel"
fi

if [ -f "$AGENT_DIR/config.yml" ] && grep -Eq '^[[:space:]]*slow:' "$AGENT_DIR/config.yml"; then
  bad "config.yml still presets modelRoles.slow"
else
  ok "modelRoles.slow not preset"
fi

if [ -f "$AGENT_DIR/config.yml" ] && grep -Eq '(^|[[:space:]])beefsms[[:space:]]*$' "$AGENT_DIR/config.yml" && grep -q 'modelProviderOrder' "$AGENT_DIR/config.yml"; then
  ok "modelProviderOrder prefers beefsms"
else
  bad "config.yml modelProviderOrder missing beefsms"
fi

if [ -f "$AGENT_DIR/extensions/domain-route.ts" ]; then
  ok "domain-route.ts present"
else
  bad "domain-route.ts missing"
fi

if [ -f "$AGENT_DIR/extensions/ghidra-open.ts" ]; then
  ok "ghidra-open.ts present"
else
  bad "ghidra-open.ts missing"
fi

if [ -f "$AGENT_DIR/extensions/drop-degenerate-thinking.ts" ]; then
  ok "drop-degenerate-thinking.ts present"
else
  bad "drop-degenerate-thinking.ts missing"
fi

if [ -f "$KIT/skills/domain-route.py" ]; then
  if python3 "$KIT/skills/domain-route.py" --self-test >/dev/null; then
    ok "domain-route.py self-test"
  else
    bad "domain-route.py self-test"
  fi
  domain="$(python3 "$KIT/skills/domain-route.py" --hint '脱壳去校验' | awk '/^DOMAIN/{print $2}')"
  if [ "$domain" = "crack" ]; then
    ok "domain-route 脱壳 → crack"
  else
    bad "domain-route 脱壳 expected crack, got $domain"
  fi
  skip="$(python3 "$KIT/skills/domain-route.py" --json --hint hello | python3 -c 'import json,sys; print(json.load(sys.stdin).get("skip"))')"
  if [ "$skip" = "True" ]; then
    ok "domain-route hello → skip"
  else
    bad "domain-route hello expected skip, got $skip"
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
  out="$(python3 "$KIT/skills/claude-red/route.py" --root "$CLAUDE_RED_DIR" --hint xss || true)"
  case "$out" in
    *offensive-xss*) ok "route xss → offensive-xss" ;;
    *) bad "route xss missed offensive-xss: $out" ;;
  esac
  web="$(python3 "$KIT/skills/domain-route.py" --json --hint '网站渗透 https://example.com' | python3 -c 'import json,sys; print(json.load(sys.stdin).get("next"))')"
  if [ "$web" = "offensive-fast-checking" ]; then
    ok "网站渗透 → offensive-fast-checking"
  else
    bad "网站渗透 expected offensive-fast-checking, got $web"
  fi
else
  bad "router script missing or pack empty"
fi

if [ -f "$KIT/skills/claude-red/index.py" ]; then
  if python3 "$KIT/skills/claude-red/index.py" --self-test >/dev/null; then
    ok "index.py self-test"
  else
    bad "index.py self-test"
  fi
fi

if [ -d "$CLAUDE_RED_DIR/Skills" ] && [ -f "$KIT/skills/claude-red/index.py" ]; then
  if python3 "$KIT/skills/claude-red/index.py" --root "$CLAUDE_RED_DIR" --audit >/dev/null; then
    ok "skill descriptions survive YAML"
  else
    bad "skill descriptions are empty or YAML comments (omp will drop those skills)"
  fi
fi

if [ "$FAIL" -ne 0 ]; then
  echo "omp-claude-red: verify failed"
  exit 1
fi
echo "omp-claude-red: verify passed"
