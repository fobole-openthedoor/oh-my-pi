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
        "methodOrder": ["shake", "soft"],
        "thresholdPercent": 50,
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
        "default": "beefsms/happy/Deepseek-v4.1-Flash-1017",
        "smol": "beefsms/deepseek-flash",
        "compact": "beefsms/deepseek-flash",
        "vision": "beefsms/deepseek-flash:low",
    },
    "modelProviderOrder": ["beefsms"],
    "task": {
        "maxConcurrency": 4,
        "eager": "always",
    },
}

# Roles the kit must not preset. Dropped on merge even if the user file has them.
KIT_DROP_ROLES = ("slow",)

COMPACTION_MODEL = "beefsms/deepseek-flash"


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


def drop_kit_roles(data: dict) -> dict:
    roles = data.get("modelRoles")
    if not isinstance(roles, dict):
        return data
    next_roles = dict(roles)
    for role in KIT_DROP_ROLES:
        next_roles.pop(role, None)
    if next_roles == roles:
        return data
    out = dict(data)
    out["modelRoles"] = next_roles
    return out


def apply_kit_policy(user: dict) -> dict:
    return drop_kit_roles(deep_merge_owned(user, KIT_OWNED))


def apply_compaction_model(data: dict) -> dict:
    """Point beefsms models at the compact role's model. Never touches apiKey."""
    providers = data.get("providers")
    if not isinstance(providers, dict):
        return data
    beefsms = providers.get("beefsms")
    if not isinstance(beefsms, dict):
        return data
    models = beefsms.get("models")
    if not isinstance(models, list):
        return data
    next_models = []
    changed = False
    for model in models:
        if not isinstance(model, dict):
            next_models.append(model)
            continue
        if model.get("compactionModel") == COMPACTION_MODEL:
            next_models.append(model)
            continue
        patched = dict(model)
        patched["compactionModel"] = COMPACTION_MODEL
        next_models.append(patched)
        changed = True
    if not changed:
        return data
    next_provider = dict(beefsms)
    next_provider["models"] = next_models
    next_providers = dict(providers)
    next_providers["beefsms"] = next_provider
    out = dict(data)
    out["providers"] = next_providers
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


def apply_beefsms_model_catalog(data: dict, example: Path | None) -> dict:
    if example is None or not example.is_file():
        return data
    template = load_yaml(example)
    template_models = (template.get("providers") or {}).get("beefsms", {}).get("models")
    if not isinstance(template_models, list):
        return data
    providers = data.get("providers")
    if not isinstance(providers, dict):
        return data
    beefsms = providers.get("beefsms")
    if not isinstance(beefsms, dict) or beefsms.get("models") == template_models:
        return data
    next_provider = dict(beefsms)
    next_provider["models"] = template_models
    next_providers = dict(providers)
    next_providers["beefsms"] = next_provider
    out = dict(data)
    out["providers"] = next_providers
    return out


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
    merged = apply_kit_policy(user)
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


def merge_models_file(path: Path, example: Path | None = None) -> str:
    if not path.is_file():
        return "missing"
    user = load_yaml(path)
    merged = apply_beefsms_model_catalog(apply_compaction_model(user), example)
    if merged == user:
        return "unchanged"
    text = dump_yaml(merged)
    fd, tmp = tempfile.mkstemp(prefix="omp-models-", suffix=".yml", dir=str(path.parent))
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
            "modelRoles:\n  default: keep-me\n  commit: keep-commit\n  slow: beefsms/happy/glm-5.3\ncompaction:\n  enabled: false\n  idleTimeoutSeconds: 60\n",
            encoding="utf-8",
        )
        status = merge_file(path, None)
        if status != "merged":
            print(f"FAIL expected merged, got {status}", file=sys.stderr)
            return 1
        data = load_yaml(path)
        if data.get("modelRoles", {}).get("default") != "beefsms/happy/Deepseek-v4.1-Flash-1017":
            print("FAIL modelRoles.default not beefsms/happy/Deepseek-v4.1-Flash-1017", file=sys.stderr)
            return 1
        if data.get("modelRoles", {}).get("commit") != "keep-commit":
            print("FAIL user modelRoles.commit overwritten", file=sys.stderr)
            return 1
        if data.get("modelRoles", {}).get("vision") != "beefsms/deepseek-flash:low":
            print("FAIL modelRoles.vision not beefsms/deepseek-flash:low", file=sys.stderr)
            return 1
        if data.get("modelRoles", {}).get("smol") != "beefsms/deepseek-flash":
            print("FAIL modelRoles.smol not beefsms/deepseek-flash", file=sys.stderr)
            return 1
        if data.get("modelRoles", {}).get("compact") != "beefsms/deepseek-flash":
            print("FAIL modelRoles.compact not beefsms/deepseek-flash", file=sys.stderr)
            return 1
        if "slow" in (data.get("modelRoles") or {}):
            print("FAIL modelRoles.slow was preset", file=sys.stderr)
            return 1
        if data.get("modelProviderOrder") != ["beefsms"]:
            print(f"FAIL modelProviderOrder {data.get('modelProviderOrder')}", file=sys.stderr)
            return 1
        if (data.get("task") or {}).get("maxConcurrency") != 4:
            print("FAIL task.maxConcurrency not 4", file=sys.stderr)
            return 1
        if (data.get("task") or {}).get("eager") != "always":
            print("FAIL task.eager not always", file=sys.stderr)
            return 1
        compaction = data.get("compaction") or {}
        if compaction.get("enabled") is not True:
            print("FAIL compaction.enabled not true", file=sys.stderr)
            return 1
        if compaction.get("methodOrder") != ["shake", "soft"]:
            print(f"FAIL methodOrder {compaction.get('methodOrder')}", file=sys.stderr)
            return 1
        if compaction.get("thresholdPercent") != 50:
            print(f"FAIL thresholdPercent {compaction.get('thresholdPercent')}", file=sys.stderr)
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
        models_path = Path(tmp) / "models.yml"
        models_path.write_text(
            "providers:\n  beefsms:\n    apiKey: KEEP_ME\n    models:\n      - id: happy/glm-5.3-plus\n        name: GLM\n      - id: deepseek-flash\n        compactionModel: beefsms/deepseek-flash\n",
            encoding="utf-8",
        )
        models_example = Path(tmp) / "models-example.yml"
        shutil.copyfile(Path(__file__).with_name("models.yml.example"), models_example)
        models_status = merge_models_file(models_path, models_example)
        if models_status != "merged":
            print(f"FAIL expected models merged, got {models_status}", file=sys.stderr)
            return 1
        models = load_yaml(models_path)
        beefsms = (models.get("providers") or {}).get("beefsms") or {}
        if beefsms.get("apiKey") != "KEEP_ME":
            print("FAIL models.yml apiKey overwritten", file=sys.stderr)
            return 1
        expected_ids = [
            "happy/Deepseek-v4.1-Flash-1017",
            "happy/Daybreak-Latest",
            "happy/glm-5.3-plus",
            "deepseek-flash",
        ]
        actual_ids = [row.get("id") for row in beefsms.get("models") or [] if isinstance(row, dict)]
        if actual_ids != expected_ids:
            print(f"FAIL beefsms model catalog {actual_ids}", file=sys.stderr)
            return 1
        ids = {row.get("id"): row for row in beefsms.get("models") or [] if isinstance(row, dict)}
        if ids.get("happy/glm-5.3-plus", {}).get("compactionModel") != COMPACTION_MODEL:
            print("FAIL glm-5.3-plus compactionModel missing", file=sys.stderr)
            return 1
        if ids.get("deepseek-flash", {}).get("compactionModel") != COMPACTION_MODEL:
            print("FAIL deepseek-flash compactionModel missing", file=sys.stderr)
            return 1
        again_models = merge_models_file(models_path, models_example)
        if again_models != "unchanged":
            print(f"FAIL models merge not idempotent: {again_models}", file=sys.stderr)
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
    parser.add_argument(
        "--models",
        default=os.path.join(
            os.environ.get("OMP_AGENT_DIR", str(Path.home() / ".omp" / "agent")),
            "models.yml",
        ),
    )
    parser.add_argument("--models-example", default="")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    path = Path(args.config)
    example = Path(args.example) if args.example else None
    status = merge_file(path, example)
    print(f"omp-merge-config: {status} {path}")
    models_example = Path(args.models_example) if args.models_example else None
    models_status = merge_models_file(Path(args.models), models_example)
    print(f"omp-merge-config: models {models_status} {args.models}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
