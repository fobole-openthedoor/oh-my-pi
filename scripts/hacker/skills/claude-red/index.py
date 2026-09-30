#!/usr/bin/env python3
"""Write INDEX.md from Claude-Red SKILL.md frontmatter.

--ensure-descriptions fills missing descriptions so omp's native skill loader
(requireDescription: true) will pick the skill up. Descriptions are YAML
double-quoted. An unquoted value that starts with '#' is a YAML comment, so
the loader sees an empty description and drops the skill.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from route import iter_skills, parse_frontmatter

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
DESCRIPTION_SECTION = re.compile(r"^## Description\s*$", re.M)


def first_sentence(text: str, limit: int = 140) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def body_without_frontmatter(text: str) -> str:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return text
    return text[match.end() :]


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        inner = value[1:-1]
        if value[0] == '"':
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return inner
        return inner
    return value


def description_usable(text: str) -> bool:
    """True when the description line survives YAML and is real prose.

    `description: # SKILL: …` parses as an empty value because '#' starts a
    comment. omp then drops the skill.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        return False
    for line in match.group(1).splitlines():
        if not line.startswith("description:"):
            continue
        value = line.split(":", 1)[1].strip()
        if not value:
            return False
        if value[0] in (">", "|"):
            return True
        if value[0] in ('"', "'"):
            inner = _unquote(value).strip()
            return bool(inner) and not inner.startswith("#")
        if value.startswith("#"):
            return False
        return True
    return False


def summary_from_body(body: str, name: str) -> str:
    chunk = ""
    match = DESCRIPTION_SECTION.search(body)
    if match:
        lines: list[str] = []
        for line in body[match.end() :].splitlines():
            if line.startswith("#"):
                break
            lines.append(line)
        chunk = " ".join(line.strip() for line in lines if line.strip())
    if not chunk:
        lines = []
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped:
                if lines:
                    break
                continue
            if stripped.startswith(("#", "-", "`", "|")):
                if lines:
                    break
                continue
            lines.append(stripped)
        chunk = " ".join(lines)
    summary = first_sentence(chunk, 360)
    if not summary or summary.startswith("#"):
        return f"Offensive security skill {name}."
    return summary


def yaml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def ensure_description(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    if description_usable(text):
        return False
    meta = parse_frontmatter(text)
    name = (meta.get("name") or path.parent.name).strip() or path.parent.name
    body = body_without_frontmatter(text).lstrip("\n")
    summary = summary_from_body(body, name)
    extra: list[str] = []
    match = FRONTMATTER_RE.match(text)
    if match:
        for line in match.group(1).splitlines():
            if ":" not in line or line[:1].isspace():
                continue
            key = line.split(":", 1)[0].strip().lower()
            if key in ("name", "description"):
                continue
            extra.append(line)
    lines = ["---", f"name: {name}", f"description: {yaml_quote(summary)}", *extra, "---", "", body]
    rendered = "\n".join(lines)
    if not rendered.endswith("\n"):
        rendered += "\n"
    path.write_text(rendered, encoding="utf-8")
    return True


def write_index(root: Path) -> Path:
    skills = iter_skills(root)
    lines = [
        "# claude-red index (omp)",
        "",
        "Generated at install time. Route with `route.py --hint \"<task>\"`.",
        "",
        f"Skills: {len(skills)}",
        "",
        "| Skill | Path | Summary |",
        "| --- | --- | --- |",
    ]
    for path in skills:
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        meta = parse_frontmatter(text)
        name = meta.get("name") or path.parent.name
        summary = first_sentence(meta.get("description") or "").replace("|", "/")
        lines.append(f"| `{name}` | `{rel}` | {summary} |")
    lines.append("")
    dest = root / "INDEX.md"
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest


def audit(root: Path) -> int:
    bad: list[str] = []
    skills = iter_skills(root)
    for path in skills:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            bad.append(str(path))
            continue
        if not description_usable(text):
            bad.append(str(path.relative_to(root)))
    if bad:
        print(f"unusable descriptions: {len(bad)}", file=sys.stderr)
        for item in bad:
            print(item, file=sys.stderr)
        return 1
    print(f"descriptions usable: {len(skills)}")
    return 0


def self_test() -> int:
    sample = """# SKILL: Cross-Site Scripting (XSS)

## Metadata
- **Skill Name**: xss

## Description
Cross-Site Scripting testing checklist: stored and reflected XSS. Use for web app XSS testing.

## Trigger Phrases
`XSS`
"""
    bad = (
        "---\n"
        "name: offensive-xss\n"
        "description: # SKILL: Cross-Site Scripting (XSS) ## Metadata\n"
        "---\n" + sample
    )
    good = (
        "---\n"
        'name: offensive-sqli\n'
        'description: "SQL injection testing skill for web assessments."\n'
        "---\n\n"
        "# SQL Injection\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        web = root / "Skills" / "web"
        xss = web / "offensive-xss" / "SKILL.md"
        sqli = web / "offensive-sqli" / "SKILL.md"
        xss.parent.mkdir(parents=True)
        sqli.parent.mkdir(parents=True)
        xss.write_text(bad, encoding="utf-8")
        sqli.write_text(good, encoding="utf-8")
        if not ensure_description(xss):
            print("FAIL expected rewrite of commented description", file=sys.stderr)
            return 1
        if ensure_description(sqli):
            print("FAIL quoted description was rewritten", file=sys.stderr)
            return 1
        rewritten = xss.read_text(encoding="utf-8")
        desc_line = next(line for line in rewritten.splitlines() if line.startswith("description:"))
        if not desc_line.startswith('description: "'):
            print(f"FAIL description not quoted: {desc_line}", file=sys.stderr)
            return 1
        if "# SKILL" in desc_line or "stored and reflected XSS" not in desc_line:
            print(f"FAIL description is not the Description section: {desc_line}", file=sys.stderr)
            return 1
        if not description_usable(rewritten):
            print("FAIL rewritten description still unusable", file=sys.stderr)
            return 1
        body = body_without_frontmatter(rewritten).lstrip()
        if not body.startswith("# SKILL: Cross-Site Scripting"):
            print("FAIL methodology body was dropped", file=sys.stderr)
            return 1
        if ensure_description(xss):
            print("FAIL second pass rewrote a usable description", file=sys.stderr)
            return 1
        if sqli.read_text(encoding="utf-8") != good:
            print("FAIL sqli bytes changed", file=sys.stderr)
            return 1
    print("index: self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=os.environ.get("CLAUDE_RED_ROOT", str(Path.home() / "tools" / "claude-red")),
    )
    parser.add_argument(
        "--ensure-descriptions",
        action="store_true",
        help="Fill empty or YAML-commented SKILL.md descriptions so omp will load them",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Exit 1 if any skill description would be dropped by a YAML loader",
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    root = Path(args.root).expanduser()
    if args.ensure_descriptions:
        n = 0
        for path in iter_skills(root):
            if ensure_description(path):
                n += 1
        print(f"ensured description on {n} skills")
    if args.audit:
        return audit(root)
    dest = write_index(root)
    print(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
