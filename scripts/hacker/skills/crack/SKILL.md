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
5. `ACT`: Run `python3 "${OMP_FORK_ROOT:-$HOME/oh-my-pi}/scripts/hacker/skills/skill-section.py" --file "$REVERSE_SKILL_ROOT/skills/<PRIMARY>/SKILL.md" --query "<user task> 破解 脱壳 去校验"`. Short skills are returned whole; long skills return ACTION REQUIRED plus matching sections. Read omitted sections only when needed.
   When the sample is an APK, AAB, or dex, read `$APK_REVERSE_ROOT/skills/apk-reverse/SKILL.md` (default `$HOME/tools/apk-reverse`) through the symptom index and gates before editing. Equal-length dex edits and repack rules live there. Open `ad-removal.md`, `membership-and-limits.md`, `updates-and-forced-upgrade.md`, or the kernel syscall-mask notes only when the user asked for that result. A server-side gate ends as a report. Keep `observed` / `inferred` / `unverified`.
6. Tools only from `$REVERSE_SKILL_ROOT/skills/tool-index.md`.

Ghidra: `$GHIDRA_INSTALL_DIR` (`analyzeHeadless`). Local sample: `/ghidra-open <binary>` or tool `ghidra_open`, then MCP `open_database` with that file_path. `decompile_function` defaults to 200-line pages; read `evidence_path` for other pages instead of repeating decompilation, or use `detail=complete` for full inline output.

Live web/AD/cloud exploitation → matching `offensive-*` skill. Understanding-only reverse → `/skill:reverse-skill`.
