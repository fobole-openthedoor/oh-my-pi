---
name: crack
description: 破解 domain: unpack/脱壳, deobfuscate, patch license/activation checks, packer/OLLVM, crackme/keygen, local binary patches. Use when the user asks to 破解, 脱壳, 去校验, 补丁, 激活, 加壳, unpack, or patch a program. Not live-site pentest (use offensive-* skills). Not “just explain this binary” (use reverse-skill).
---

# crack (破解)

This is the **破解** domain. Goal: locate protection → unpack/deobfuscate → document the check → propose a **local** patch. Not a live pentest.

**Reverse pack:** `$REVERSE_SKILL_ROOT` (default `$HOME/tools/reverse-skill`)

Authorized local-sample / lab work only. No live-target ACT without written scope.

## ACTION REQUIRED

1. `NOW`: Read `$REVERSE_SKILL_ROOT/RULES.md`.
2. `NOW`: `bash $REVERSE_SKILL_ROOT/skills/scripts/master-route.sh --hint "<user task> 破解 脱壳 去校验"` → PRIMARY.
3. If PRIMARY is `pentest-tools/` or `attack-chain/`, use `$REVERSE_SKILL_ROOT/skills/reverse-engineering/SKILL.md` instead.
4. `NOW`: `bash $REVERSE_SKILL_ROOT/skills/scripts/case-init.sh --hint "<user task>"` → `work/<case>/scope.md`. Local sample → `offline-sample` preset.
5. `ACT`: Open `$REVERSE_SKILL_ROOT/skills/<PRIMARY>/SKILL.md` and follow ACTION REQUIRED.
6. Tools only from `$REVERSE_SKILL_ROOT/skills/tool-index.md`.

Ghidra: `$GHIDRA_INSTALL_DIR` (`analyzeHeadless`). Prefer the `ghidra` MCP server when connected.

Live web/AD/cloud exploitation → matching `offensive-*` skill. Understanding-only reverse → `/skill:reverse-skill`.
