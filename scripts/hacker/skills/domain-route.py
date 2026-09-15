#!/usr/bin/env python3
"""Classify a task into reverse | crack | pentest and print the next skill."""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# Import Claude-Red router when the pack is present.
_HERE = Path(__file__).resolve().parent
if str(_HERE / "claude-red") not in sys.path:
    sys.path.insert(0, str(_HERE / "claude-red"))

REVERSE_HITS = [
    r"逆向", r"反编译", r"反汇编", r"decompile", r"disassembl",
    r"ghidra", r"\bida\b", r"radare", r"\bfrida\b", r"jadx", r"apktool",
    r"分析样本", r"怎么工作", r"控制流", r"伪代码", r"decompiler",
    r"\belf\b", r"\bpe\b", r"\bdll\b", r"\bso\b", r"mach-?o",
]
CRACK_HITS = [
    r"破解", r"脱壳", r"加壳", r"去校验", r"去验证", r"去授权", r"去掉校验",
    r"激活码", r"授权码", r"注册机", r"补丁", r"crackme", r"keygen",
    r"unpack", r"packer", r"upx", r"vmprotect", r"themida", r"ollvm",
    r"license", r"activation", r"serial.?check", r"nop\b", r"patch.{0,12}(jmp|je|jnz|check)",
    r"加壳", r"壳", r"混淆还原", r"去混淆", r"deobfuscat",
]
PENTEST_HITS = [
    r"渗透", r"打站", r"打点", r"内网", r"漏洞", r"注入", r"sqli", r"xss",
    r"ssrf", r"rce", r"越权", r"未授权", r"burp", r"nmap", r"nuclei", r"sqlmap",
    r"口令", r"爆破", r"bounty", r"众测", r"红队", r"打域", r"域控",
    r"http://", r"https://", r"靶场", r"src\b",
]

REVERSE_NEXT = "reverse-skill"
CRACK_NEXT = "crack"
PENTEST_FALLBACK = "offensive-fast-checking"


def tokens(text: str) -> str:
    return text.lower()


def score(blob: str, patterns: list[str]) -> int:
    n = 0
    for pat in patterns:
        if re.search(pat, blob, re.I):
            n += 1
    return n


def classify(hint: str) -> tuple[str, int, int, int]:
    blob = tokens(hint)
    r, c, p = score(blob, REVERSE_HITS), score(blob, CRACK_HITS), score(blob, PENTEST_HITS)

    # Colloquial 「破解这个网站」 is pentest, not binary crack.
    if re.search(r"破解", blob) and re.search(r"网站|站点|url|http|\.com|\.net|\.org", blob):
        p += 3
        c = max(0, c - 1)
    # 「绕过 WAF」 on a live app is pentest; 「WAF 程序/授权/二进制」 is crack.
    if re.search(r"waf", blob):
        if re.search(r"绕过|bypass|payload|注入", blob):
            p += 2
        if re.search(r"二进制|授权|license|破解|逆向", blob):
            c += 2

    if p >= c and p >= r and p > 0:
        domain = "pentest"
    elif c >= r and c > 0:
        domain = "crack"
    elif r > 0:
        domain = "reverse"
    else:
        domain = "reverse" if re.search(r"\.(apk|so|elf|exe|dll|bin|ipa)(\b|$)", blob) else "pentest"
        if domain == "pentest" and p == 0 and c == 0 and r == 0:
            # Bare file-ish → reverse; otherwise pentest triage.
            domain = "reverse" if re.search(r"样本|二进制|程序|软件|apk|so|elf|exe", blob) else "pentest"
    return domain, r, c, p


def pentest_next(hint: str, claude_red_root: str) -> str:
    route = _HERE / "claude-red" / "route.py"
    root = Path(claude_red_root)
    if not route.is_file() or not (root / "Skills").is_dir():
        return PENTEST_FALLBACK
    import subprocess

    try:
        out = subprocess.check_output(
            [sys.executable, str(route), "--root", str(root), "--hint", hint],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return PENTEST_FALLBACK
    for line in out.splitlines():
        if line.startswith("PRIMARY ") and "SKILL.md" in line:
            rel = line.split(" ", 1)[1].strip()
            name = Path(rel).parent.name
            return name or PENTEST_FALLBACK
    return PENTEST_FALLBACK


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hint", default="")
    parser.add_argument(
        "--claude-red-root",
        default=os.environ.get("CLAUDE_RED_ROOT", str(Path.home() / "tools" / "claude-red")),
    )
    args = parser.parse_args()
    hint = args.hint.strip() or "<user task>"
    domain, r, c, p = classify(hint)
    if domain == "pentest":
        nxt = pentest_next(hint, args.claude_red_root)
    elif domain == "crack":
        nxt = CRACK_NEXT
    else:
        nxt = REVERSE_NEXT
    print(f"DOMAIN {domain}")
    print(f"NEXT {nxt}")
    print(f"SCORE reverse={r} crack={c} pentest={p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
