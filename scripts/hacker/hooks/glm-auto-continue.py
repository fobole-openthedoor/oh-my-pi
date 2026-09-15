#!/usr/bin/env python3
"""Classifier: auto-continue when GLM 5.3 ends a turn without tools.

omp's session_stop extension calls this with --classify.
happy/glm-5.3 often: (1) thinking only, (2) a short finding, or
(3) "let me grep X next" — then stop. The TUI waits for 继续.

Continue only when the turn still has an action (empty thinking, short
finding, first-person / concrete next step). Do not continue for a
closed write-up that merely lists remaining questions.

Disable with GLM_AUTO_CONTINUE=0.
Run python3 glm-auto-continue.py --self-test to check the classifier.
Run python3 glm-auto-continue.py --classify < hook-json for omp.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

MAX_STREAK = int(os.environ.get("GLM_AUTO_CONTINUE_MAX", "12"))
SHORT_LIMIT = int(os.environ.get("GLM_AUTO_CONTINUE_SHORT", "800"))
STATE_DIR = Path(os.environ.get("GLM_AUTO_CONTINUE_STATE_DIR", "/tmp/omp-glm-continue"))
LOG_PATH = Path(os.environ.get("GLM_AUTO_CONTINUE_LOG", "/tmp/omp-glm-continue.log"))

# First-person / imperative next step. Not topic nouns (验证/探测/check).
PENDING_ACTION = re.compile(
    r"("
    r"让我|我(先|再|去|来|把|将)|然后我|接下来我|"
    r"继续(推进|挖|打|查|读|看|搜|跑|验证|探测|分析)|"
    r"先(并行|确认|全量|提取|打|读|跑|去|把)|"
    r"稍后(我|去|再)|收尾|补进|写进|"
    r"(下一步|接下来)[：:，, ]*(我|去|是)?[：:，, ]*"
    r"(去|跑|执行|验证|检查|探测|打开|拉取|搜索|反编译|反汇编|grep|pull|curl|读|写|补)|"
    r"还(要|得|需)(去|跑|执行|验证|检查|探测|打开|拉取)|"
    r"let me|gonna|I(?:'ll| will| am going to)|"
    r"(现在|接着)(去|跑|执行|pull|grep|curl)|"
    r"打开\s*https?://|"
    r"\bdocker\s+pull\b|\bgit\s+grep\b"
    r")",
    re.I,
)
# Real questions to the user. Bare ASCII '?' is often rhetorical ("combinations!?").
USER_QUESTION = re.compile(
    r"[？]|请(确认|选择|告诉|问)|"
    r"\b(which (one|option)|should I|do you want|can you confirm)\b|"
    r"(要不要|是不是|对吗|对不对|哪一个)",
    re.I,
)
REPORT_MARK = re.compile(r"^#{1,3}\s|结论|总结|handoff|本次会话新增", re.I | re.M)
CLOSED_TURN = re.compile(
    r"("
    r"结论已.{0,24}(写入|写完|写好|提交|保存)|"
    r"已(完整)?写入并提交|"
    r"文档已(写完|写入|保存|提交)|"
    r"已提交到\s*git|"
    r"已(经)?(完成|改好|写完|保存|搞定|处理好)|"
    r"以上(就是|为)|任务完成|无需再(做|继续)|没有更多"
    r")",
    re.I,
)
FILE_REF = re.compile(
    r"(?:文件|file)\s*[:：].{0,160}|"
    r"`/[^`\n]+\.(?:md|txt|rst)`|"
    r"(?<!\w)/[^\s`]+\.(?:md|txt|rst)",
    re.I,
)
COMMIT_REF = re.compile(
    r"commit\s*[:：]\s*`?[0-9a-f]{7,40}`?|"
    r"提交.{0,16}`?[0-9a-f]{7,40}`?",
    re.I,
)
LIST_MARK = re.compile(r"(^|\n)\s*[-*•]|(^|\n)§|\b\d+\.\d+")
HANDOFF_FLAVOR = re.compile(
    r"(待验证清单|公开渠道穷尽|最终结论|handoff|收官|"
    r"已(写入|写完|提交|保存)|文档包含)",
    re.I,
)
DOCUMENTED_UNKNOWN = re.compile(
    r"(待(验证|确认|查|测)(清单|项|点|列表)?|"
    r"未(验证|确认)|"
    r"公开渠道穷尽|"
    r"remaining questions|open questions)",
    re.I,
)

THINK_ONLY_REASON = (
    "You stopped after thinking and did not call a tool. "
    "The user did not ask you to wait. Continue the same task now: "
    "call the next tool in this turn. Do not summarize a plan and stop."
)
ANNOUNCE_REASON = (
    "You announced a next action and then stopped without calling a tool. "
    "Do that step now: call the tool. Do not announce work again."
)
SHORT_NOTE_REASON = (
    "You wrote a short finding and stopped without calling a tool. "
    "That is not a finished turn. Keep going on the same task: "
    "call the next tool now. Do not repeat the finding."
)


def log(msg: str) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n")
    except Exception:
        pass


def _after_close(text: str) -> str:
    m = CLOSED_TURN.search(text)
    return text[m.end() :] if m else text


def is_closed_handoff(text: str) -> bool:
    if CLOSED_TURN.search(text):
        return True
    return bool(FILE_REF.search(text) and COMMIT_REF.search(text))


def is_structured_close(text: str) -> bool:
    """Bullet/section write-up that records unknowns, not a next action."""
    if PENDING_ACTION.search(text):
        return False
    if not REPORT_MARK.search(text):
        return False
    if not LIST_MARK.search(text):
        return False
    return bool(HANDOFF_FLAVOR.search(text))


def should_continue(hook_input: dict) -> tuple[str | None, str]:
    """Return (reason, kind) or (None, 'allow')."""
    if os.environ.get("GLM_AUTO_CONTINUE", "1") in ("0", "false", "no"):
        return None, "allow"
    last_text = (hook_input.get("last_assistant_message") or "").strip()
    if last_text.startswith("No response requested") or "automatic compaction" in last_text:
        return None, "allow"
    if not last_text:
        return THINK_ONLY_REASON, "think"
    if USER_QUESTION.search(last_text):
        return None, "allow"

    # Closed write-up (file + commit, 结论已写入并提交). Still continue if
    # the text after the close is a first-person next action (让我验证).
    if is_closed_handoff(last_text):
        if PENDING_ACTION.search(_after_close(last_text)):
            return ANNOUNCE_REASON, "announce"
        return None, "allow"

    if is_structured_close(last_text):
        return None, "allow"

    # Long structured write-up: real stop even if it lists 下一步.
    if REPORT_MARK.search(last_text) and len(last_text) > SHORT_LIMIT:
        return None, "allow"

    if PENDING_ACTION.search(last_text):
        return ANNOUNCE_REASON, "announce"

    # Remaining questions in a conclusion are not a next action.
    if DOCUMENTED_UNKNOWN.search(last_text):
        return None, "allow"

    if len(last_text) <= SHORT_LIMIT:
        return SHORT_NOTE_REASON, "short"
    return None, "allow"


def streak_path(session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", session_id or "unknown")[:80]
    return STATE_DIR / f"{safe}.streak"


def bump_streak(session_id: str) -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = streak_path(session_id)
    n = 0
    try:
        n = int(path.read_text().strip() or "0")
    except Exception:
        n = 0
    n += 1
    path.write_text(str(n))
    return n


def clear_streak(session_id: str) -> None:
    try:
        streak_path(session_id).unlink(missing_ok=True)
    except Exception:
        pass


KIND_LABEL = {
    "think": "想完没调工具",
    "announce": "还有下一步没调工具",
    "short": "短结论没调工具",
}

ENT_WRAPUP = """结论已完整写入并提交。

- **文件**: `/root/hacker/safeline-analysis/ENT_IMAGE_HUNT.md`（748 行）
- **commit**: `d9a8506`（ENT镜像狩猎收官）

文档包含全部今日发现：
- §4.5 — china/global 二进制 diff（39679 函数仅 1 个真实差异 + entitlement 公钥机制逆向）
- §4.6 — 公开渠道穷尽探测（Docker Hub/SWR/rivers/checkUpgrade/demo.waf/env var/slkey/manager.py）
- §4.7 — 最终结论 + ENT 分发模型 + 待验证清单
"""

LONG_DOC_DONE = (
    "文档已写完并保存到 `/root/hacker/safeline-analysis/ENT_IMAGE_HUNT.md`。\n\n"
    "**本次会话新增内容**：\n\n"
    "| 段 | 内容 |\n| --- | --- |\n"
    "| §4.5 | china/global diff |\n| §4.6 | 公开渠道穷尽探测 |\n"
    "| §4.7 | 最终结论 + 待验证清单 |\n\n"
    + ("handoff notes. " * 80)
)


def _self_test() -> int:
    cases: list[tuple[str, str, str]] = [
        ("empty", "", "think"),
        ("no-response", "No response requested.", "allow"),
        ("compaction", "Session automatic compaction started.", "allow"),
        ("question", "要不要继续挖 oversea？", "allow"),
        ("ent-wrapup", ENT_WRAPUP, "allow"),
        (
            "written-then-verify",
            "结论已写入 `/root/hacker/safeline-analysis/ENT_IMAGE_HUNT.md` "
            "并提交（d9a8506）。让我验证一下文档内容是否完整。",
            "announce",
        ),
        (
            "continue-push",
            "继续推进。先并行打几个低成本高价值目标："
            "oversea 域名 version.json（从未探测过！）、upgrade_check.py（从未读过！）",
            "announce",
        ),
        (
            "continue-dig",
            "继续挖本地剩余线索：全量 URL 目录 + checkUpgrade 的 base URL 来源（region 分支点）。",
            "announce",
        ),
        (
            "continue-extract",
            "继续打剩余线索。先全量提取二进制中的环境变量名，看是否有 ENT 专属变量。",
            "announce",
        ),
        (
            "patch-doc",
            "先确认文档当前状态，再把最后两块新发现（manager.py 逆向 + 网络探测）补进去。",
            "announce",
        ),
        (
            "telegram-verify",
            "函数表 0 diff = 代码逻辑完全一致。差异只是条件编译的区域常量。验证 ldflags 确认。",
            "short",
        ),
        ("long-doc-done", LONG_DOC_DONE, "allow"),
        ("let-me-pull", "下一步我去 docker pull 官方镜像。", "announce"),
        (
            "unknowns-only",
            "公开渠道已穷尽。未验证项：销售渠道是否另有 registry。待确认：ENT 是否仅走私有分发。",
            "allow",
        ),
        ("let-me-grep", "Let me grep the binary next.", "announce"),
        (
            "remaining-questions",
            "Remaining questions: whether ENT uses a private registry.",
            "allow",
        ),
        ("next-inventory", "下一步：待验证清单", "allow"),
    ]
    failed = 0
    for name, text, expect in cases:
        _reason, kind = should_continue({"last_assistant_message": text})
        if kind != expect:
            print(f"FAIL {name}: got {kind} expected {expect}", file=sys.stderr)
            failed += 1
        else:
            print(f"ok   {name}: {kind}")
    if failed:
        print(f"{failed} failed", file=sys.stderr)
        return 1
    print(f"{len(cases)} passed")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    if "--classify" in sys.argv:
        raw = sys.stdin.read()
        try:
            hook_input = json.loads(raw) if raw.strip() else {}
        except Exception:
            hook_input = {}
        reason, kind = should_continue(hook_input)
        sys.stdout.write(json.dumps({"kind": kind, "reason": reason}, ensure_ascii=False))
        return 0
    raw = sys.stdin.read()
    try:
        hook_input = json.loads(raw) if raw.strip() else {}
    except Exception:
        hook_input = {}
    session_id = hook_input.get("session_id") or "unknown"
    last_text = hook_input.get("last_assistant_message") or ""
    reason, kind = should_continue(hook_input)
    preview = last_text.replace("\n", " ")[:80]
    if not reason:
        clear_streak(session_id)
        log(f"allow session={session_id} mem_len={len(last_text)} mem={preview!r}")
        return 0
    n = bump_streak(session_id)
    if n > MAX_STREAK:
        clear_streak(session_id)
        log(f"cap session={session_id} streak={n} mem_len={len(last_text)}")
        return 0
    round_label = f"第 {n}/{MAX_STREAK} 轮"
    why = KIND_LABEL.get(kind, "想完没调工具")
    payload = {
        "decision": "block",
        "reason": f"[{round_label}] {reason}",
        "systemMessage": f"{round_label}自动续 · {why}",
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    log(
        f"block session={session_id} streak={n} kind={kind} "
        f"mem_len={len(last_text)} mem={preview!r}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
