#!/usr/bin/env python3
# ghidra-prewarm.py — warm the pi-ghidra SHA-256 analysis cache for binaries.
#
# The kimi-code ghidra MCP (pi-ghidra) imports + auto-analyzes a binary on
# first touch (minutes for large samples) and serves later queries from
# /root/pi-ghidra-cache keyed by SHA-256. This driver speaks MCP JSON-RPC to
# the exact same wrapper the agent's MCP server uses, so cache entries it
# produces are the ones the agent will hit. Run it in the background on new
# samples while doing fast triage (file/checksec/rabin2), and the deep pass
# starts warm.
#
# Usage:
#   python3 ghidra-prewarm.py <binary|dir> [...]
#   nohup python3 ghidra-prewarm.py ~/samples/ > /tmp/ghidra-prewarm.log 2>&1 &
#
# Env:
#   PI_GHIDRA_CPUS      analysis parallelism (default 4; MCP clamps 1-4)
#   GHIDRA_MCP_WRAPPER  wrapper path (default kimi-code location)
import json
import os
import subprocess
import sys
import time
from pathlib import Path

WRAPPER = os.environ.get("GHIDRA_MCP_WRAPPER", "/root/.kimi-code/tools/ghidra-mcp.mjs")
ANALYZABLE_MIMES = {
    "application/x-executable",
    "application/x-sharedlib",
    "application/x-dosexec",
    "application/x-mach-binary",
    "application/x-pie-executable",
}


def is_analyzable(path: Path) -> bool:
    try:
        out = subprocess.run(
            ["file", "-b", "--mime-type", str(path)], capture_output=True, text=True, check=False
        )
        return out.stdout.strip() in ANALYZABLE_MIMES
    except OSError:
        return False


def collect(args: list[str]) -> list[Path]:
    found: list[Path] = []
    for arg in args:
        p = Path(arg)
        if p.is_dir():
            found.extend(f for f in sorted(p.rglob("*")) if f.is_file() and f.stat().st_size > 0 and is_analyzable(f))
        elif p.is_file():
            found.append(p)
        else:
            print(f"prewarm: skipping {arg} (not a file/dir)", file=sys.stderr)
    return found


def main() -> int:
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <binary|dir> [...]", file=sys.stderr)
        return 2
    if not Path(WRAPPER).is_file():
        print(f"prewarm: wrapper not found: {WRAPPER}", file=sys.stderr)
        return 1

    targets = collect(sys.argv[1:])
    if not targets:
        print("prewarm: nothing analyzable found", file=sys.stderr)
        return 1
    cpus = os.environ.get("PI_GHIDRA_CPUS", "4")
    print(f"prewarm: {len(targets)} binaries, PI_GHIDRA_CPUS={cpus}")

    env = {**os.environ, "PI_GHIDRA_CPUS": cpus, "NODE_NO_WARNINGS": "1"}
    proc = subprocess.Popen(
        ["node", "--experimental-strip-types", WRAPPER],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=env,
    )
    assert proc.stdin and proc.stdout

    def send(payload: dict) -> None:
        proc.stdin.write(json.dumps(payload) + "\n")
        proc.stdin.flush()

    send({
        "jsonrpc": "2.0", "id": 0, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "ghidra-prewarm", "version": "1.0"}},
    })
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    pending: dict[int, str] = {}
    for i, target in enumerate(targets, start=1):
        pending[i] = str(target.resolve())
        send({"jsonrpc": "2.0", "id": i, "method": "tools/call",
              "params": {"name": "ghidra", "arguments": {"action": "analyze", "binary": pending[i]}}})

    start = time.monotonic()
    failures = 0
    # The wrapper exits on stdin EOF without waiting for in-flight calls, so
    # keep stdin open until every request id has answered.
    while pending:
        line = proc.stdout.readline()
        if not line:
            print("prewarm: wrapper closed stdout early", file=sys.stderr)
            failures += len(pending)
            break
        try:
            resp = json.loads(line)
        except json.JSONDecodeError:
            continue
        rid = resp.get("id")
        if rid not in pending:
            continue
        name = pending.pop(rid)
        result = resp.get("result") or {}
        text = ((result.get("content") or [{}])[0]).get("text", "")
        if result.get("isError"):
            failures += 1
            print(f"prewarm: ERROR {name}: {text[:300]}", file=sys.stderr)
        else:
            print(f"prewarm: ok ({len(targets) - len(pending)}/{len(targets)}) {name}")

    proc.stdin.close()
    proc.wait(timeout=30)
    elapsed = int(time.monotonic() - start)
    print(f"prewarm: done in {elapsed}s, {failures} failed; cache at /root/pi-ghidra-cache")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
