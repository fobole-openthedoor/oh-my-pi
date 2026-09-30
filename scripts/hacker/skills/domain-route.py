#!/usr/bin/env python3
"""Classify a task into reverse | crack | pentest | cve | skip and print the next skill."""
from __future__ import annotations

import argparse
import json
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
    r"分析样本", r"控制流", r"伪代码", r"decompiler",
    r"\belf\b", r"\bdll\b", r"mach-?o",
]
CRACK_HITS = [
    r"破解", r"脱壳", r"加壳", r"去校验", r"去验证", r"去授权", r"去掉校验",
    r"激活码", r"授权码", r"注册机", r"crackme", r"keygen",
    r"upx", r"vmprotect", r"themida", r"ollvm",
    r"serial.?check", r"nop\b", r"patch.{0,12}(jmp|je|jnz|check)",
    r"混淆还原", r"去混淆", r"deobfuscat",
]
PENTEST_HITS = [
    r"渗透", r"打站", r"打点", r"内网", r"漏洞", r"注入", r"sqli", r"xss",
    r"ssrf", r"rce", r"越权", r"未授权", r"burp", r"nmap", r"nuclei", r"sqlmap",
    r"口令", r"爆破", r"bounty", r"众测", r"红队", r"打域", r"域控", r"靶场",
]

REVERSE_NEXT = "reverse-skill"
CRACK_NEXT = "crack"
CVE_NEXT = "cve-intel"
PENTEST_FALLBACK = "offensive-fast-checking"
CVE_ID_RE = re.compile(r"\bcve-\d{4}-\d{4,}\b", re.I)
CVE_HITS = [
    r"\bepss\b", r"\bkev\b", r"\bosv(?:\.dev)?\b", r"\bn-?day\b", r"\b1-?day\b",
    r"(?:cve|漏洞).{0,16}(?:情报|优先级|影响版本|修复版本|复现|triage|enrich)",
]


def tokens(text: str) -> str:
    return text.lower()


def score(blob: str, patterns: list[str]) -> int:
    n = 0
    for pat in patterns:
        if re.search(pat, blob, re.I):
            n += 1
    return n


def is_cve_task(blob: str) -> bool:
    if CVE_ID_RE.search(blob):
        return True
    if re.search(r"skills?", blob) and re.search(r"路由|优化|修改|开发|编写|实现", blob):
        return False
    return score(blob, CVE_HITS) > 0


def classify(hint: str) -> tuple[str, int, int, int]:
    blob = tokens(hint)
    if is_cve_task(blob):
        return "cve", 0, 0, 0
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

    ranked = [("reverse", r), ("crack", c), ("pentest", p)]
    best = max(score_value for _, score_value in ranked)
    winners = [name for name, score_value in ranked if score_value == best and score_value > 0]
    domain = winners[0] if len(winners) == 1 else "skip"
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


def next_skill(domain: str, hint: str, claude_red_root: str) -> str:
    if domain == "pentest":
        return pentest_next(hint, claude_red_root)
    if domain == "crack":
        return CRACK_NEXT
    if domain == "reverse":
        return REVERSE_NEXT
    if domain == "cve":
        return CVE_NEXT
    return ""


def result(hint: str, claude_red_root: str) -> dict:
    domain, r, c, p = classify(hint)
    nxt = next_skill(domain, hint, claude_red_root)
    return {
        "domain": domain,
        "next": nxt,
        "skip": domain == "skip",
        "score": {"reverse": r, "crack": c, "pentest": p, "cve": int(domain == "cve")},
    }


def self_test() -> int:
    cases = [
        ("脱壳去校验", "crack", "crack"),
        ("反编译这个 so", "reverse", "reverse-skill"),
        ("sql注入", "pentest", None),
        ("hello", "skip", ""),
        ("你好", "skip", ""),
        ("/login", "skip", ""),
        ("foo.exe", "skip", ""),
        ("https://example.com 整理文档", "skip", ""),
        ("this is so cool", "skip", ""),
        ("给程序补一个补丁", "skip", ""),
        ("fix the license wording", "skip", ""),
        ("优化 skills 路由和模型配置", "skip", ""),
        ("优化 CVE skills 路由", "skip", ""),
        ("分析 CVE-2021-44228 的影响版本", "cve", "cve-intel"),
        ("漏洞优先级 EPSS KEV", "cve", "cve-intel"),
        ("CVE-2024-1234 N-day 复现和补丁差分", "cve", "cve-intel"),
        ("破解这个网站 https://example.com", "pentest", None),
        ("分析样本", "reverse", "reverse-skill"),
        ("先逆向再渗透", "skip", ""),
    ]
    failed = 0
    for hint, want_domain, want_next in cases:
        domain, r, c, p = classify(hint)
        if domain != want_domain:
            print(f"FAIL domain {hint!r}: got {domain} want {want_domain} scores r={r} c={c} p={p}", file=sys.stderr)
            failed += 1
            continue
        if want_next is None:
            if domain != "pentest":
                print(f"FAIL {hint!r}: expected pentest", file=sys.stderr)
                failed += 1
            continue
        nxt = next_skill(domain, hint, os.environ.get("CLAUDE_RED_ROOT", str(Path.home() / "tools" / "claude-red")))
        if nxt != want_next:
            print(f"FAIL next {hint!r}: got {nxt} want {want_next}", file=sys.stderr)
            failed += 1
    if failed:
        print(f"domain-route: {failed} self-test failure(s)", file=sys.stderr)
        return 1
    print("domain-route: self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hint", default="")
    parser.add_argument(
        "--claude-red-root",
        default=os.environ.get("CLAUDE_RED_ROOT", str(Path.home() / "tools" / "claude-red")),
    )
    parser.add_argument("--json", action="store_true", help="print one JSON object")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    hint = args.hint.strip() or "<user task>"
    payload = result(hint, args.claude_red_root)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    print(f"DOMAIN {payload['domain']}")
    print(f"NEXT {payload['next'] or '-'}")
    s = payload["score"]
    print(f"SCORE reverse={s['reverse']} crack={s['crack']} pentest={s['pentest']} cve={s['cve']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
