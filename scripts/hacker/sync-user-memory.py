#!/usr/bin/env python3
"""Upsert Work mode + Claude-Red sections in ~/.omp/agent/AGENTS.md."""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


def work_mode(_fork_root: str, reverse_root: str, ghidra: str, apk_reverse: str) -> str:
    return f"""## Work mode: 逆向 / 破解 / 渗透

Load a domain skill only when the user explicitly requests a matching activity or names its tools. General coding, configuration, model/provider changes, questions, and greetings do not need a domain pack.

Do not infer a domain from a filename, URL, or generic words such as “program”, “patch”, or “so”. If the intent is uncertain or spans multiple domains, skip the skill; the user can invoke one explicitly.

The `domain-route` extension gives advisory hints only by default and does not block tools (`DOMAIN_ROUTE=0` disables hints; `DOMAIN_ROUTE_GATE=1` opts into blocking).

Subagent delegation (`task.eager = always`, `task.maxConcurrency = 4`): across multi-slice coding, reverse/audit, or authorized assessment work, once 1–3 brief scoping steps confirm ≥2 genuinely independent slices, proactively launch a **2-subagent baseline** in a single `task` batch (`{{ context, tasks[] }}`) instead of working sequentially inline. Self-evaluate scaling to **3–4 subagents** only when evidence shows 3–4 disjoint, substantial slices within budget; stay single-threaded for single-slice tasks, small edits, or direct questions.

For explicit authorized web pentests, `parallel-pentest` defaults to `auto` (proactive 2-lane baseline, model-evaluated 3–4 lanes) without blocking on a popup; it never grants target authorization. `/parallel-pentest` or `PARALLEL_PENTEST=select` opens the manual selector; `PARALLEL_PENTEST=2|3|4` caps lanes; `PARALLEL_PENTEST=0` disables it.

| Domain | Explicit task | Skill |
| --- | --- | --- |
| 逆向 reverse | 反编译, 样本分析, Ghidra, IDA, Frida | `skill://reverse-skill` |
| 破解 crack | 脱壳, 去校验, 二进制补丁, 激活/授权, 加壳, OLLVM | `skill://crack` |
| 渗透 pentest | 打站, SQLi, XSS, 内网, AD, 口令, 打点, 绕过 WAF | matching `skill://offensive-*` |
| CVE intelligence | CVE 编号, N-day, EPSS, KEV, OSV, 漏洞优先级 | `skill://cve-intel` |

Reverse pack: `{reverse_root}` (`REVERSE_SKILL_ROOT`). Ghidra: `{ghidra}` (`analyzeHeadless`). Local sample: `/ghidra-open <binary>` (or tool `ghidra_open`), then MCP `open_database` with that file_path. `decompile_function` returns at most 200 lines by default; read its `evidence_path` for other pages instead of decompiling again, or use `detail=complete` for full inline output.

Android APK depth — packer, repack, code that is not plain dex, Dart AOT, split APK — is the sidecar `{apk_reverse}` (`APK_REVERSE_ROOT`). The reverse-skill and crack adapters open it. Same domain, separate clone.
"""


def claude_red_section(root: str) -> str:
    return f"""## Claude-Red skills

The Claude-Red pack is installed as normal omp skills (`offensive-sqli`, `offensive-jwt`, `offensive-k8s-attacks`, …). Pack root: `{root}` (`CLAUDE_RED_ROOT`).

For an explicit pentest task, read only the matching offensive skill. `/skill:claude-red` is just a catalog; do not load it when no specific skill matches.
"""


def upsert_section(text: str, heading: str, body: str) -> str:
    pattern = rf"## {re.escape(heading)}\b.*?(?=\n## |\Z)"
    section = body.rstrip() + "\n\n"
    new, n = re.subn(pattern, section, text, count=1, flags=re.S)
    if n:
        return new
    if not text.strip():
        return section
    return text.rstrip() + "\n\n" + section


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agents-md",
        default=os.path.join(
            os.environ.get("OMP_AGENT_DIR", str(Path.home() / ".omp" / "agent")),
            "AGENTS.md",
        ),
    )
    parser.add_argument(
        "--fork-root",
        default=os.environ.get("OMP_FORK_ROOT", str(Path.home() / "oh-my-pi")),
    )
    parser.add_argument(
        "--claude-red-root",
        default=os.environ.get("CLAUDE_RED_ROOT", str(Path.home() / "tools" / "claude-red")),
    )
    parser.add_argument(
        "--reverse-root",
        default=os.environ.get("REVERSE_SKILL_ROOT", str(Path.home() / "tools" / "reverse-skill")),
    )
    parser.add_argument(
        "--ghidra",
        default=os.environ.get("GHIDRA_INSTALL_DIR")
        or os.environ.get("GHIDRA_HOME")
        or str(Path.home() / "tools" / "ghidra"),
    )
    parser.add_argument(
        "--apk-reverse-root",
        default=os.environ.get("APK_REVERSE_ROOT", str(Path.home() / "tools" / "apk-reverse")),
    )
    args = parser.parse_args()
    path = Path(args.agents_md)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8") if path.is_file() else "# omp user memory\n"
    text = re.sub(
        r"\nReverse-engineering pack lives at.*?(?=\n## |\Z)",
        "\n",
        text,
        count=1,
        flags=re.S,
    )
    text = upsert_section(
        text,
        "Work mode: 逆向 / 破解 / 渗透",
        work_mode(args.fork_root, args.reverse_root, args.ghidra, args.apk_reverse_root),
    )
    text = upsert_section(text, "Claude-Red skills", claude_red_section(args.claude_red_root))
    text = re.sub(r"## claude-red\b.*?(?=\n## |\Z)", "", text, count=1, flags=re.S)
    wm = re.search(r"## Work mode: 逆向 / 破解 / 渗透\b.*?(?=\n## |\Z)", text, re.S)
    if wm:
        body = wm.group(0).strip() + "\n\n"
        rest = (text[: wm.start()] + text[wm.end() :]).strip() + "\n"
        if rest.startswith("# "):
            first, _, rem = rest.partition("\n")
            text = first + "\n\n" + body + rem.lstrip()
        else:
            text = "# omp user memory\n\n" + body + rest
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o600)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
