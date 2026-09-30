#!/usr/bin/env python3
"""Print a short skill whole, or ACTION REQUIRED plus matching sections of a long skill."""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

FULL_FILE_MAX_BYTES = 16_384
MAX_SOURCE_BYTES = 4 * 1024 * 1024
MAX_MATCHES = 3

STOP_WORDS = {
    "about",
    "and",
    "from",
    "need",
    "please",
    "read",
    "skill",
    "task",
    "that",
    "the",
    "this",
    "use",
    "user",
    "using",
    "want",
    "with",
}
STOP_BIGRAMS = {
    "一个",
    "一下",
    "不是",
    "可以",
    "我们",
    "用户",
    "然后",
    "现在",
    "这个",
    "任务",
    "看看",
    "需要",
    "进行",
    "问题",
}
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def terms(text: str) -> set[str]:
    result = {
        word.lower()
        for word in re.findall(r"[A-Za-z][A-Za-z0-9_.-]+", text)
        if word.lower() not in STOP_WORDS
    }
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        for index in range(len(run) - 1):
            bigram = run[index : index + 2]
            if bigram not in STOP_BIGRAMS:
                result.add(bigram)
    return result


def parse_sections(lines: list[str]) -> list[dict]:
    headings = []
    for index, line in enumerate(lines):
        match = HEADING.match(line)
        if match:
            headings.append((index, len(match.group(1)), match.group(2).strip()))
    result = []
    for pos, (start, level, title) in enumerate(headings):
        end = len(lines)
        for next_start, next_level, _ in headings[pos + 1 :]:
            if next_level <= level:
                end = next_start
                break
        result.append({"start": start, "end": end, "level": level, "title": title})
    return result


def select_sections(sections: list[dict], query: str) -> list[int]:
    selected = {
        index
        for index, section in enumerate(sections)
        if section["title"].lower() == "action required"
    }
    query_terms = terms(query)
    if query_terms:
        ranked = []
        for index, section in enumerate(sections):
            if section["level"] == 1 or index in selected:
                continue
            body_terms = terms(section["text"])
            title_terms = terms(section["title"])
            score = sum(3 for term in query_terms if term in title_terms)
            score += sum(1 for term in query_terms if term in body_terms)
            if score:
                ranked.append((score, -section["start"], index))
        for _, _, index in sorted(ranked, reverse=True)[:MAX_MATCHES]:
            selected.add(index)
    return sorted(
        index
        for index in selected
        if not any(
            other != index
            and sections[other]["start"] <= sections[index]["start"]
            and sections[other]["end"] >= sections[index]["end"]
            for other in selected
        )
    )


def render(path: Path, query: str) -> str:
    raw = path.read_bytes()
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError(f"Skill exceeds {MAX_SOURCE_BYTES} bytes: {path}")
    text = raw.decode("utf-8")
    if len(raw) <= FULL_FILE_MAX_BYTES:
        return text
    lines = text.splitlines(keepends=True)
    sections = parse_sections(lines)
    for section in sections:
        section["text"] = "".join(lines[section["start"] : section["end"]])
    selected = select_sections(sections, query)
    if not selected:
        selected = [index for index, section in enumerate(sections) if section["level"] == 2][:1]
    selected_set = set(selected)
    selected_lines = sum(sections[index]["end"] - sections[index]["start"] for index in selected)
    output = [
        f"source: {path}\n",
        f"mode: sections\ntotal_lines: {len(lines)}\nselected_lines: {selected_lines}\n\n",
    ]
    for index in selected:
        section = sections[index]
        output.append(f"<!-- lines {section['start'] + 1}-{section['end']} -->\n")
        output.append(section["text"].rstrip() + "\n\n")
    omitted = [
        section
        for index, section in enumerate(sections)
        if index not in selected_set and section["level"] <= 3
    ]
    if omitted:
        output.append("## Omitted sections — read only if needed\n\n")
        for section in omitted[:20]:
            output.append(f"- lines {section['start'] + 1}-{section['end']}: {section['title']}\n")
        if len(omitted) > 20:
            output.append(f"- … {len(omitted) - 20} more\n")
    return "".join(output).rstrip() + "\n"


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        short = root / "short.md"
        short.write_text("# Short\n\nRead everything.\n", encoding="utf-8")
        if render(short, "anything") != short.read_text(encoding="utf-8"):
            print("FAIL short skill was not preserved", file=sys.stderr)
            return 1
        long = root / "long.md"
        long.write_text(
            "# Long\n\n"
            + "preface\n" * 2500
            + "## ACTION REQUIRED\n\nFollow the scope gate.\n\n"
            + "## Ghidra decompiler\n\nUse summary and pages.\n\n"
            + "## Network capture\n\nRecord packets.\n",
            encoding="utf-8",
        )
        output = render(long, "用 Ghidra 反编译")
        if "ACTION REQUIRED" not in output or "Ghidra decompiler" not in output:
            print("FAIL required or matching section missing", file=sys.stderr)
            return 1
        if "Record packets." in output or "Network capture" not in output:
            print("FAIL unrelated section selection", file=sys.stderr)
            return 1
        if "preface\n" * 10 in output:
            print("FAIL long preface leaked into section view", file=sys.stderr)
            return 1
    print("skill-section: self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path)
    parser.add_argument("--query", default="")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.file is None:
        parser.error("--file is required")
    try:
        sys.stdout.write(render(args.file, args.query))
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"skill-section: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
