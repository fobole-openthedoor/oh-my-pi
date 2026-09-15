#!/usr/bin/env python3
"""Upsert Work mode + Claude-Red sections in ~/.omp/agent/AGENTS.md."""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


def work_mode(fork_root: str, reverse_root: str, ghidra: str) -> str:
    route = f"{fork_root}/scripts/hacker/skills/domain-route.py"
    return f"""## Work mode: 逆向 / 破解 / 渗透

On **every** user task, pick one domain first, then `read skill://<name>` immediately. Do not start acting until a skill is loaded.

If the domain is unclear, run `python3 {route} --hint "<user task>"` and follow `NEXT`.

| Domain | User is talking about | Invoke |
| --- | --- | --- |
| 逆向 reverse | 反编译, Ghidra, IDA, Frida, APK/SO/ELF/PE, 样本怎么工作 | `skill://reverse-skill` |
| 破解 crack | 脱壳, 去校验, 补丁, 激活/授权, 加壳, OLLVM, crackme, keygen | `skill://crack` |
| 渗透 pentest | 打站, SQLi, XSS, 内网, AD, 云, 口令, 打点, 绕过 WAF | matching `skill://offensive-*` |

Do not mix packs on the first turn. Reverse a binary then pentest the service → 逆向/破解 first, 渗透 second. 「破解网站」 is pentest; 「破解软件/授权/壳」 is crack.

Reverse pack: `{reverse_root}` (`REVERSE_SKILL_ROOT`). Ghidra: `{ghidra}` (`analyzeHeadless`). Prefer the `ghidra` MCP server when connected.
"""


def claude_red_section(root: str) -> str:
    return f"""## Claude-Red skills

The Claude-Red pack is installed as normal omp skills (`offensive-sqli`, `offensive-jwt`, `offensive-k8s-attacks`, …). Pack root: `{root}` (`CLAUDE_RED_ROOT`).

When the domain is **渗透**, `read skill://<matching-offensive-skill>` immediately. `/skill:claude-red` is only a catalog. 逆向 → `/skill:reverse-skill`. 破解 → `/skill:crack`.
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
        work_mode(args.fork_root, args.reverse_root, args.ghidra),
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
