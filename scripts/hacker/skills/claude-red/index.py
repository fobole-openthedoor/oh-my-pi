#!/usr/bin/env python3
"""Write INDEX.md from Claude-Red SKILL.md frontmatter.

--ensure-descriptions patches empty frontmatter descriptions so omp's
native skill loader (requireDescription: true) will pick them up.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from route import iter_skills, parse_frontmatter

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


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


def ensure_description(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    meta = parse_frontmatter(text)
    if (meta.get("description") or "").strip():
        return False
    name = meta.get("name") or path.parent.name
    summary = first_sentence(body_without_frontmatter(text)) or f"Offensive skill {name}"
    rest = body_without_frontmatter(text)
    extra = {k: v for k, v in meta.items() if k not in ("name", "description")}
    lines = ["---", f"name: {name}", f"description: {summary}"]
    for key, value in extra.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    path.write_text("\n".join(lines) + rest.lstrip("\n"), encoding="utf-8")
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
        summary = first_sentence(meta.get("description") or "")
        lines.append(f"| `{name}` | `{rel}` | {summary} |")
    lines.append("")
    dest = root / "INDEX.md"
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=os.environ.get("CLAUDE_RED_ROOT", str(Path.home() / "tools" / "claude-red")),
    )
    parser.add_argument(
        "--ensure-descriptions",
        action="store_true",
        help="Fill empty SKILL.md descriptions so omp will load them",
    )
    args = parser.parse_args()
    root = Path(args.root).expanduser()
    if args.ensure_descriptions:
        n = 0
        for path in iter_skills(root):
            if ensure_description(path):
                n += 1
        print(f"ensured description on {n} skills")
    dest = write_index(root)
    print(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
