#!/usr/bin/env python3
"""Point the local reverse-skill checkout at the apk-reverse sidecar.

The sidecar stays a separate clone. This inserts a short gate into the APK
skill, a source note into the community map, and the dex-index tools into
the tool-index refresh script. install-reverse.sh re-runs it after every
clone, so a fresh reverse-skill tree picks the gate up again.

A second run replaces the marked blocks. It does not append another copy.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

SKILL_ANCHOR = '5. `ACT`: 进入"工作流"第一步并执行，不要停在确认状态\n'
COMMUNITY_ANCHOR = "## 2. 安全标准与威胁（2025–2026）\n"
TOOLS_ANCHOR = '  "apktool|apk-reverse|APK decode and rebuild|apktool|apktool --version|"\n'
HINTS_ANCHOR = (
    '    linux:apktool) echo "apt or jar: sudo apt install apktool; or official apktool.jar" ;;\n'
)

SKILL_MARK = "omp-apk-reverse-sidecar-skill"
COMMUNITY_MARK = "omp-apk-reverse-sidecar-community"
TOOLS_MARK = "omp-apk-reverse-sidecar-tools"
HINTS_MARK = "omp-apk-reverse-sidecar-hints"

SKILL_BODY = """5. `NOW`（omp kit，先于 jadx）: 样本是 APK、AAB 或 dex，且问题涉及壳、重打包或重签名、代码不在明文 dex、Dart AOT / Flutter、分包或 App Bundle、native 自终止，或构建成功但行为不对时，先读 `$APK_REVERSE_ROOT/skills/apk-reverse/SKILL.md`（默认 `$HOME/tools/apk-reverse`）的症状索引和四道闸门，只打开索引点名的那一篇。转述时保留 `observed` / `inferred` / `unverified`。`ad-removal.md`、`membership-and-limits.md`、`updates-and-forced-upgrade.md` 和内核系统调用掩码只在用户明确要那个结果时打开。门闩在服务端时，交付物是写明边界的报告。来源 MIT https://github.com/newliver666/apk-reverse ，检索 2026-09-27。对照说明见 `../references/community-security-skills.md` §1.2。"""

COMMUNITY_BODY = """### 1.2 Android APK 深度 sidecar（2026-09-27）

[newliver666/apk-reverse](https://github.com/newliver666/apk-reverse)（MIT）。本机路径 `$APK_REVERSE_ROOT`（默认 `$HOME/tools/apk-reverse`），由 oh-my-pi `install-reverse.sh` 克隆，不并入本包。

借鉴决策层：症状索引、四道闸门、壳 / 抽取壳 / Dex VMP / Java2C / JNI 下沉的判别、重打包后仍看起来健康的失败、签名证书被当成请求密钥、Dart AOT、split APK、先用 `droidasc` / `ddc` 做索引再反编译。转述结论时保留原文的 `observed`、`inferred`、`unverified`。扩展文档里多数路线是推断，工具量过不等于整条路径跑过。

`references/ad-removal.md`、`references/membership-and-limits.md`、`references/updates-and-forced-upgrade.md`，以及 `references/kernel-and-environment-hardening.md` 里的系统调用掩码，只在用户明确要那个结果时打开。服务端权威的门闩，结论写成报告。"""

TOOLS_BODY = """\
  "droidasc|apk-reverse|Whole-APK string and type cross-reference index|droidasc|droidasc -h|"
  "ddc|apk-reverse|Dex-to-Java decompiler with query subcommands|ddc|ddc -V|$HOME/tools/ddc/ddc"
  "apksigner|apk-reverse|APK Signature Scheme v1/v2/v3 signer|apksigner|apksigner version|"
  "zipalign|apk-reverse|Align uncompressed APK entries|zipalign|none|"
"""

HINTS_BODY = """\
    linux:droidasc) echo "pipx: pipx install droidasc==0.1.1.post2" ;;
    linux:ddc) echo "GitHub release: ejfkdev/ddc v0.1.15 linux-x64 into ~/tools/ddc" ;;
    linux:apksigner) echo "apt: sudo apt install apksigner" ;;
    linux:zipalign) echo "apt: sudo apt install zipalign" ;;
"""


def _block(mark: str, body: str, style: str) -> tuple[str, str, str]:
    if style == "html":
        start = f"<!-- {mark}:start -->"
        end = f"<!-- {mark}:end -->"
    else:
        start = f"# {mark}:start"
        end = f"# {mark}:end"
    return start, end, f"{start}\n{body.rstrip()}\n{end}\n"


def _upsert(text: str, mark: str, body: str, anchor: str, *, after: bool, style: str) -> str:
    start, end, block = _block(mark, body, style)
    if start in text and end in text:
        pre, _, rest = text.partition(start)
        _, _, post = rest.partition(end)
        if post.startswith("\n"):
            post = post[1:]
        return pre + block + post
    if anchor not in text:
        raise SystemExit(f"apply-apk-sidecar: anchor for {mark} not found")
    if mark == SKILL_MARK:
        # The gate has to run before the jadx workflow, so the old step 5
        # becomes step 6 and stays outside the replaced block.
        moved = anchor.replace("5. `ACT`:", "6. `ACT`:", 1)
        return text.replace(anchor, block + moved, 1)
    if after:
        return text.replace(anchor, anchor + block, 1)
    return text.replace(anchor, block + anchor, 1)


def apply(reverse_skill: Path, apk_reverse: Path) -> None:
    skill_md = apk_reverse / "skills" / "apk-reverse" / "SKILL.md"
    if not skill_md.is_file():
        raise SystemExit(f"apply-apk-sidecar: sidecar skill missing: {skill_md}")
    skill_path = reverse_skill / "skills" / "apk-reverse" / "SKILL.md"
    community_path = reverse_skill / "skills" / "references" / "community-security-skills.md"
    refresh = reverse_skill / "skills" / "scripts" / "refresh-tool-index.sh"
    for path in (skill_path, community_path, refresh):
        if not path.is_file():
            raise SystemExit(f"apply-apk-sidecar: missing {path}")
    skill_path.write_text(
        _upsert(
            skill_path.read_text(encoding="utf-8"),
            SKILL_MARK,
            SKILL_BODY,
            SKILL_ANCHOR,
            after=False,
            style="html",
        ),
        encoding="utf-8",
    )
    community_path.write_text(
        _upsert(
            community_path.read_text(encoding="utf-8"),
            COMMUNITY_MARK,
            COMMUNITY_BODY,
            COMMUNITY_ANCHOR,
            after=False,
            style="html",
        ),
        encoding="utf-8",
    )
    refresh_text = refresh.read_text(encoding="utf-8")
    refresh_text = _upsert(
        refresh_text, TOOLS_MARK, TOOLS_BODY, TOOLS_ANCHOR, after=True, style="hash"
    )
    refresh_text = _upsert(
        refresh_text, HINTS_MARK, HINTS_BODY, HINTS_ANCHOR, after=True, style="hash"
    )
    refresh.write_text(refresh_text, encoding="utf-8")


def _self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        reverse = root / "reverse-skill"
        sidecar = root / "apk-reverse"
        (sidecar / "skills" / "apk-reverse").mkdir(parents=True)
        (sidecar / "skills" / "apk-reverse" / "SKILL.md").write_text("# sidecar\n", encoding="utf-8")
        skill = reverse / "skills" / "apk-reverse" / "SKILL.md"
        community = reverse / "skills" / "references" / "community-security-skills.md"
        refresh = reverse / "skills" / "scripts" / "refresh-tool-index.sh"
        skill.parent.mkdir(parents=True)
        community.parent.mkdir(parents=True)
        refresh.parent.mkdir(parents=True)
        skill.write_text("intro\n" + SKILL_ANCHOR + "tail\n", encoding="utf-8")
        community.write_text("intro\n" + COMMUNITY_ANCHOR + "tail\n", encoding="utf-8")
        refresh.write_text(HINTS_ANCHOR + TOOLS_ANCHOR, encoding="utf-8")
        apply(reverse, sidecar)
        apply(reverse, sidecar)
        skill_text = skill.read_text(encoding="utf-8")
        community_text = community.read_text(encoding="utf-8")
        refresh_text = refresh.read_text(encoding="utf-8")
        if skill_text.count(f"<!-- {SKILL_MARK}:start -->") != 1:
            raise SystemExit("self-test: skill marker duplicated")
        if "6. `ACT`:" not in skill_text or skill_text.count("进入") != 1:
            raise SystemExit("self-test: workflow step was dropped or duplicated")
        if community_text.count(f"<!-- {COMMUNITY_MARK}:start -->") != 1:
            raise SystemExit("self-test: community marker duplicated")
        if not community_text.endswith("## 2. 安全标准与威胁（2025–2026）\ntail\n") and \
                "\n## 2. 安全标准与威胁（2025–2026）\ntail\n" not in community_text:
            raise SystemExit("self-test: community heading moved")
        if refresh_text.count("droidasc|apk-reverse") != 1 or refresh_text.count("linux:droidasc") != 1:
            raise SystemExit("self-test: tool rows duplicated")
        if "apktool|apk-reverse" not in refresh_text or "linux:apktool" not in refresh_text:
            raise SystemExit("self-test: original tool rows dropped")
        broken = reverse / "skills" / "apk-reverse" / "SKILL.md"
        broken.write_text("no anchor\n", encoding="utf-8")
        try:
            apply(reverse, sidecar)
        except SystemExit as exc:
            if exc.code in (0, None):
                raise SystemExit("self-test: missing anchor should fail") from exc
        else:
            raise SystemExit("self-test: missing anchor should fail")
    print("ok   apply-apk-sidecar self-test")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reverse-skill", type=Path)
    parser.add_argument("--apk-reverse", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return _self_test()
    if args.reverse_skill is None or args.apk_reverse is None:
        parser.error("--reverse-skill and --apk-reverse are required")
    apply(args.reverse_skill, args.apk_reverse)
    print(f"apply-apk-sidecar: patched {args.reverse_skill}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
