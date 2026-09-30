---
name: reverse-skill
description: 逆向 domain: reverse-engineer APK/SO/ELF/PE/JS with Ghidra/IDA/radare2/Frida to understand how a sample works. Use when the user asks to 逆向, 反编译, 分析样本, hook, or decompile. 破解/脱壳/去校验/补丁 → skill://crack. Live pentest/打站/SQLi → offensive-* skills.
---

# reverse-skill (omp adapter)

Do not dump the whole pack into context. Route, then open one PRIMARY skill.

**Repo root:** `$REVERSE_SKILL_ROOT` (default `$HOME/tools/reverse-skill`)

## ACTION REQUIRED

1. `NOW`: Read `$REVERSE_SKILL_ROOT/RULES.md` (behavior + auth).
2. `NOW`: `bash $REVERSE_SKILL_ROOT/skills/scripts/master-route.sh --hint "<user task>"` → PRIMARY.
3. `NOW`: `bash $REVERSE_SKILL_ROOT/skills/scripts/case-init.sh --hint "<user task>"` → `work/<case>/scope.md`. **auth not granted → do not ACT on a live target.** Local sample → `offline-sample` preset.
4. `ACT`: Run `python3 "${OMP_FORK_ROOT:-$HOME/oh-my-pi}/scripts/hacker/skills/skill-section.py" --file "$REVERSE_SKILL_ROOT/skills/<PRIMARY>/SKILL.md" --query "<user task>"`. Short skills are returned whole; long skills return ACTION REQUIRED plus matching sections. Read omitted sections only when needed.
   When PRIMARY is `apk-reverse` and the sample is an APK, AAB, or dex, step 5 in that file (marker `omp-apk-reverse-sidecar-skill`) runs before jadx. Sidecar: `$APK_REVERSE_ROOT` (default `$HOME/tools/apk-reverse`), file `skills/apk-reverse/SKILL.md`. Read its symptom index and gates, then only the reference that index names. Keep `observed` / `inferred` / `unverified`. Open `ad-removal.md`, `membership-and-limits.md`, `updates-and-forced-upgrade.md`, or the kernel syscall-mask notes only when the user asked for that result. A server-side gate ends as a report.
5. Tool paths **only** from `$REVERSE_SKILL_ROOT/skills/tool-index.md`. Missing tool → `bash $REVERSE_SKILL_ROOT/skills/scripts/bootstrap-reverse.sh <capability>`.

Ghidra is at `$GHIDRA_INSTALL_DIR` (default `$HOME/tools/ghidra`). For a local sample, run `/ghidra-open <binary>` or the `ghidra_open` tool (analyzeHeadless into `<dir>/ghidra_projects/<basename>`), then MCP `open_database` with that file_path (`run_auto_analysis` false if analysis already ran). `decompile_function` defaults to 200-line pages; read `evidence_path` for other pages instead of repeating decompilation, or use `detail=complete` for full inline output.

Evidence chain: `$REVERSE_SKILL_ROOT/skills/ops/evidence-finding-path.md`.
