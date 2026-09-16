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

if [ -f "$AGENT_DIR/rules/no-telegraph.md" ]; then
  ok "rule no-telegraph present"
else
  bad "rule no-telegraph missing"
fi

if python3 "$KIT/skills/domain-route.py" --self-test >/dev/null; then
  ok "domain-route.py self-test"
else
  bad "domain-route.py self-test"
fi

if python3 "$KIT/merge-config.py" --self-test >/dev/null; then
  ok "merge-config.py self-test"
else
  bad "merge-config.py self-test"
fi

if [ -x "$KIT/ghidra-open.sh" ] || [ -f "$KIT/ghidra-open.sh" ]; then
  if sh "$KIT/ghidra-open.sh" --dry-run /bin/true >/dev/null; then
    ok "ghidra-open.sh --dry-run /bin/true"
  else
    bad "ghidra-open.sh --dry-run failed"
  fi
else
  bad "ghidra-open.sh missing"
fi

if [ -f "$AGENT_DIR/config.yml" ]; then
  python3 - "$AGENT_DIR/config.yml" <<'PY' || FAIL=1
import sys, yaml
data = yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}
comp = data.get("compaction") or {}
if comp.get("enabled") is True and comp.get("methodOrder") == ["shake", "soft"]:
    print("ok   compaction shake then soft")
else:
    print("FAIL compaction methodOrder is not [shake, soft]:", comp)
    raise SystemExit(1)
ttsr = data.get("ttsr") or {}
if ttsr.get("repeatMode") == "after-gap" and ttsr.get("repeatGap") == 2:
    print("ok   ttsr after-gap/2")
else:
    print("FAIL ttsr:", ttsr)
    raise SystemExit(1)
PY
fi

if command -v bun >/dev/null 2>&1; then
  if bun -e '
    import { isDegenerateThinking, dropDegenerateFromPayload } from "'"$KIT"'/extensions/drop-degenerate-thinking.ts";
    const caps = Array(10).fill("YES").join("\n") + "\nWAIT\nDONE\n";
    if (!isDegenerateThinking(caps)) throw new Error("caps salad should be degenerate");
    const prose = "The license check is in sub_401000. I will open Ghidra next and dump the function.";
    if (isDegenerateThinking(prose)) throw new Error("normal prose should pass");
    const payload = dropDegenerateFromPayload({
      messages: [
        { role: "assistant", reasoning_content: caps, content: "next I will read the skill" },
        { role: "user", content: "go" },
      ],
    });
    if (payload.messages?.[0]?.reasoning_content) throw new Error("degenerate reasoning should be dropped");
    if (payload.messages?.[0]?.content !== "next I will read the skill") throw new Error("visible content must stay");
    const patterns = [
      "(?m)(?:^[A-Z]{2,24}[.!?]{0,3}\\r?\\n){8,}",
      "(?m)(?:^[A-Z]{2,16}\\s*[🔥💥✅❌🎯🚀⚠️❗💯✨🎉]?\\s*\\r?\\n){6,}",
    ];
    for (const p of patterns) {
      const flags = p.startsWith("(?m)") ? "m" : "";
      const body = p.startsWith("(?m)") ? p.slice(4) : p;
      if (!new RegExp(body, flags).test(caps + "\n")) throw new Error("ttsr pattern missed caps: " + p);
    }
    console.log("ok");
  ' >/dev/null; then
    ok "drop-degenerate-thinking classifier"
  else
    bad "drop-degenerate-thinking classifier"
  fi
fi

if [ "$FAIL" -ne 0 ]; then
  echo "omp-reverse: verify failed"
  exit 1
fi
echo "omp-reverse: verify passed"
