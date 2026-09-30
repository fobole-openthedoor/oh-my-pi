#!/usr/bin/env python3
"""Pick one Claude-Red SKILL.md for a task hint. Prints PRIMARY path."""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ALIASES = {
    "sqli": "offensive-sqli",
    "sql": "offensive-sqli",
    "injection": "offensive-sqli",
    "xss": "offensive-xss",
    "ssrf": "offensive-ssrf",
    "ssti": "offensive-ssti",
    "xxe": "offensive-xxe",
    "idor": "offensive-idor",
    "jwt": "offensive-jwt",
    "oauth": "offensive-oauth",
    "oidc": "offensive-oauth",
    "ad": "offensive-active-directory",
    "kerberos": "offensive-active-directory",
    "kerberoast": "offensive-active-directory",
    "adcs": "offensive-active-directory",
    "wifi": "offensive-wifi",
    "wpa": "offensive-wpa2-psk",
    "wpa2": "offensive-wpa2-psk",
    "wpa3": "offensive-wpa3-sae",
    "ble": "offensive-bluetooth-ble",
    "bluetooth": "offensive-bluetooth-ble",
    "k8s": "offensive-k8s-attacks",
    "kubernetes": "offensive-k8s-attacks",
    "docker": "offensive-container-escape",
    "container": "offensive-container-escape",
    "privesc": "offensive-linux-privesc",
    "linux": "offensive-linux-privesc",
    "windows": "offensive-windows-privesc",
    "edr": "offensive-edr-evasion",
    "c2": "offensive-c2-frameworks",
    "cobalt": "offensive-c2-frameworks",
    "osint": "offensive-osint",
    "recon": "offensive-osint",
    "fuzz": "offensive-fuzzing",
    "fuzzing": "offensive-fuzzing",
    "rop": "offensive-exploit-development",
    "pwn": "offensive-basic-exploitation",
    "phishing": "offensive-phishing",
    "graphql": "offensive-graphql",
    "waf": "offensive-waf-bypass",
    "rce": "offensive-rce",
    "lfi": "offensive-file-upload",
    "upload": "offensive-file-upload",
    "deserial": "offensive-deserialization",
    "smuggle": "offensive-request-smuggling",
    "redirect": "offensive-open-redirect",
    "hpp": "offensive-parameter-pollution",
    "tls": "offensive-tls-attacks",
    "crypto": "offensive-crypto-attacks",
    "cicd": "offensive-cicd-pipeline",
    "github-actions": "offensive-cicd-pipeline",
    "secrets": "offensive-cicd-secrets",
    "exfil": "offensive-data-exfiltration",
    "lateral": "offensive-lateral-movement",
    "persist": "offensive-persistence",
    "cloud": "offensive-cloud",
    "aws": "offensive-cloud",
    "azure": "offensive-cloud",
    "gcp": "offensive-cloud",
    "mobile": "offensive-mobile",
    "android": "offensive-mobile",
    "ios": "offensive-mobile",
    "iot": "offensive-iot",
    "api": "offensive-api-security",
    "report": "offensive-reporting",
}

TOKEN_RE = re.compile(r"[a-z0-9+]{3,}")
# Host fragments in a pasted URL are not a vulnerability. Without this filter
# "网站渗透 https://example.com" scores every skill that mentions https/com
# and the alphabetical winner (offensive-api-abuse) is treated as the match.
STOPWORDS = frozenset({
    "http",
    "https",
    "www",
    "com",
    "net",
    "org",
    "html",
    "php",
    "example",
})
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


def tokenize(text: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(text.lower()) if token not in STOPWORDS]


def parse_frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip().lower()] = value.strip().strip('"').strip("'")
    return data


def iter_skills(root: Path) -> list[Path]:
    skills_dir = root / "Skills"
    if not skills_dir.is_dir():
        return []
    return sorted(skills_dir.rglob("SKILL.md"))


def score_skill(path: Path, root: Path, hint: str, tokens: list[str]) -> int:
    rel = path.relative_to(root).as_posix().lower()
    name = path.parent.name.lower()
    score = 0
    hint_l = hint.lower().strip()
    if hint_l and (hint_l == name or hint_l == name.removeprefix("offensive-")):
        score += 50
    alias = ALIASES.get(hint_l)
    if alias and alias == name:
        score += 40
    for token in tokens:
        mapped = ALIASES.get(token)
        if mapped == name or token == name or f"offensive-{token}" == name:
            score += 12
        if token in rel:
            score += 4
    try:
        body = path.read_text(encoding="utf-8", errors="replace")[:4000].lower()
    except OSError:
        body = ""
    for token in tokens:
        if token in body:
            score += 1
    return score


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=os.environ.get("CLAUDE_RED_ROOT", str(Path.home() / "tools" / "claude-red")),
    )
    parser.add_argument("--hint", default="")
    parser.add_argument("--top", type=int, default=5)
    args = parser.parse_args()

    root = Path(args.root).expanduser()
    if not root.is_dir():
        print(f"MISSING {root}", file=sys.stderr)
        print("PRIMARY:")
        return 2

    skills = iter_skills(root)
    if not skills:
        print(f"EMPTY {root}/Skills", file=sys.stderr)
        print("PRIMARY:")
        return 2

    hint = args.hint.strip()
    tokens = tokenize(hint)
    ranked = sorted(
        ((score_skill(path, root, hint, tokens), path) for path in skills),
        key=lambda item: (-item[0], str(item[1])),
    )
    best_score, best = ranked[0]
    if not hint or best_score <= 0:
        index = root / "INDEX.openclaude.md"
        print("PRIMARY:")
        print(f"INDEX {index}")
        return 0

    print(f"PRIMARY {best.relative_to(root).as_posix()}")
    print(f"SCORE {best_score}")
    print("ALSO")
    shown = 0
    for score, path in ranked[1:]:
        if score <= 0:
            continue
        print(f"- {path.relative_to(root).as_posix()} ({score})")
        shown += 1
        if shown >= args.top:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
