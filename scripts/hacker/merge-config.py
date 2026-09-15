#!/usr/bin/env python3
"""Merge kit-owned keys into ~/.omp/agent/config.yml. Never writes API keys."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:
    print("omp-merge-config: PyYAML is required (python3 -m pip install pyyaml)", file=sys.stderr)
    raise SystemExit(1)

# Kit policy. Nested keys win; other user keys in the same mapping are kept.
KIT_OWNED = {
    "compaction": {
        "enabled": True,
        "methodOrder": ["shake"],
        "midTurnEnabled": True,
    },
    "statusLine": {
        "contextLine": "percentage",
    },
    "ttsr": {
        "repeatMode": "after-gap",
        "repeatGap": 2,
    },
    "modelRoles": {
        "vision": "beefsms/deepseek-flash:low",
    },
    "modelProviderOrder": ["beefsms"],
}


def deep_merge_owned(user: dict, owned: dict) -> dict:
    out = dict(user)
    for key, value in owned.items():
        if isinstance(value, dict):
            base = out.get(key) if isinstance(out.get(key), dict) else {}
            merged = dict(base)
            merged.update(value)
            out[key] = merged
        else:
            out[key] = value
    return out


def load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a YAML mapping")
    return data


def dump_yaml(data: dict) -> str:
    return yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )


def merge_file(path: Path, example: Path | None) -> str:
    if not path.is_file():
        if example and example.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(example, path)
            os.chmod(path, 0o600)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")
            os.chmod(path, 0o600)
    user = load_yaml(path)
    merged = deep_merge_owned(user, KIT_OWNED)
    if merged == user:
        return "unchanged"
    text = dump_yaml(merged)
    fd, tmp = tempfile.mkstemp(prefix="omp-config-", suffix=".yml", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            if not text.endswith("\n"):
                handle.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return "merged"


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.yml"
        path.write_text(
            "modelRoles:\n  default: keep-me\ncompaction:\n  enabled: false\n  idleTimeoutSeconds: 60\n",
            encoding="utf-8",
        )
        status = merge_file(path, None)
        if status != "merged":
            print(f"FAIL expected merged, got {status}", file=sys.stderr)
            return 1
        data = load_yaml(path)
        if data.get("modelRoles", {}).get("default") != "keep-me":
            print("FAIL user modelRoles overwritten", file=sys.stderr)
            return 1
        if data.get("modelRoles", {}).get("vision") != "beefsms/deepseek-flash:low":
            print("FAIL modelRoles.vision not beefsms/deepseek-flash:low", file=sys.stderr)
            return 1
        if data.get("modelProviderOrder") != ["beefsms"]:
            print(f"FAIL modelProviderOrder {data.get('modelProviderOrder')}", file=sys.stderr)
            return 1
        compaction = data.get("compaction") or {}
        if compaction.get("enabled") is not True:
            print("FAIL compaction.enabled not true", file=sys.stderr)
            return 1
        if compaction.get("methodOrder") != ["shake"]:
            print(f"FAIL methodOrder {compaction.get('methodOrder')}", file=sys.stderr)
            return 1
        if compaction.get("idleTimeoutSeconds") != 60:
            print("FAIL user compaction key dropped", file=sys.stderr)
            return 1
        if (data.get("statusLine") or {}).get("contextLine") != "percentage":
            print("FAIL statusLine.contextLine missing", file=sys.stderr)
            return 1
        ttsr = data.get("ttsr") or {}
        if ttsr.get("repeatMode") != "after-gap" or ttsr.get("repeatGap") != 2:
            print(f"FAIL ttsr {ttsr}", file=sys.stderr)
            return 1
        again = merge_file(path, None)
        if again != "unchanged":
            print(f"FAIL second merge not idempotent: {again}", file=sys.stderr)
            return 1
    print("omp-merge-config: self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=os.path.join(
            os.environ.get("OMP_AGENT_DIR", str(Path.home() / ".omp" / "agent")),
            "config.yml",
        ),
    )
    parser.add_argument("--example", default="")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    path = Path(args.config)
    example = Path(args.example) if args.example else None
    status = merge_file(path, example)
    print(f"omp-merge-config: {status} {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
