#!/usr/bin/env python3
"""Apply the fork's bounded decompilation result patch to re-mcp-ghidra."""
from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

MARKER = "def _decompilation_page("

OLD_MODEL = '''class DecompilationResult(BaseModel):
    function_name: str
    address: str
    decompiled_code: str
'''
NEW_MODEL = '''class DecompilationResult(BaseModel):
    function_name: str
    address: str
    decompiled_code: str
    detail: str = "complete"
    offset: int = 0
    limit: int = 0
    total_lines: int = 0
    next_offset: int | None = None
    evidence_path: str = ""
'''

OLD_REGISTER = '''def register(mcp: FastMCP) -> None:
'''
NEW_HELPERS = '''def _save_decompilation(code: str) -> str:
    import hashlib
    import os
    from pathlib import Path

    root = Path(
        os.environ.get(
            "OMP_GHIDRA_EVIDENCE_DIR",
            str(Path.home() / ".omp" / "ghidra-evidence"),
        )
    )
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
    path = root / f"{digest}.c"
    if not path.exists():
        path.write_text(code, encoding="utf-8")
        os.chmod(path, 0o600)
    return str(path)


def _decompilation_page(code: str, detail: str, offset: int, limit: int) -> dict:
    if detail not in {"summary", "complete"}:
        raise GhidraError("detail must be summary or complete", error_type="InvalidArgument")
    if offset < 0:
        raise GhidraError("offset must be non-negative", error_type="InvalidArgument")
    if limit < 1 or limit > 2000:
        raise GhidraError("limit must be between 1 and 2000", error_type="InvalidArgument")
    lines = code.splitlines(keepends=True)
    total_lines = len(lines)
    if detail == "complete":
        return {
            "code": code,
            "offset": 0,
            "limit": total_lines,
            "total_lines": total_lines,
            "next_offset": None,
            "evidence_path": "",
        }
    page = lines[offset : offset + limit]
    consumed = offset + len(page)
    return {
        "code": "".join(page),
        "offset": offset,
        "limit": limit,
        "total_lines": total_lines,
        "next_offset": consumed if consumed < total_lines else None,
        "evidence_path": _save_decompilation(code),
    }


def register(mcp: FastMCP) -> None:
'''

OLD_FUNCTION = '''    @mcp.tool(annotations=ANNO_READ_ONLY, tags={"functions", "decompiler"})
    @session.require_open
    def decompile_function(address: Address) -> DecompilationResult:
        """Decompile a function to C pseudocode using Ghidra's decompiler."""
        from ghidra.app.decompiler import DecompInterface  # noqa: PLC0415
        from ghidra.util.task import TaskMonitor  # noqa: PLC0415

        func = resolve_function(address)
        program = session.program

        decomp = DecompInterface()
        decomp.openProgram(program)

        try:
            results = decomp.decompileFunction(func, 60, TaskMonitor.DUMMY)
            if not results.decompileCompleted():
                error_msg = results.getErrorMessage() or "Decompilation failed"
                raise GhidraError(error_msg, error_type="DecompilationFailed")

            decomp_func = results.getDecompiledFunction()
            if decomp_func is None:
                raise GhidraError(
                    "Decompilation returned no result", error_type="DecompilationFailed"
                )

            code = decomp_func.getC()
            return DecompilationResult(
                function_name=func.getName(),
                address=format_address(func.getEntryPoint().getOffset()),
                decompiled_code=code,
            )
        finally:
            decomp.dispose()
'''
NEW_FUNCTION = '''    @mcp.tool(annotations=ANNO_READ_ONLY, tags={"functions", "decompiler"})
    @session.require_open
    def decompile_function(
        address: Address,
        detail: str = "summary",
        offset: int = 0,
        limit: int = 200,
    ) -> DecompilationResult:
        """Decompile to bounded C pseudocode pages or complete output.

        Summary mode returns at most limit lines and an evidence_path containing
        the complete pseudocode. Read that file for other pages instead of
        decompiling again. Offset is a zero-based line offset. Use complete to
        return everything inline.
        """
        from ghidra.app.decompiler import DecompInterface  # noqa: PLC0415
        from ghidra.util.task import TaskMonitor  # noqa: PLC0415

        func = resolve_function(address)
        program = session.program

        decomp = DecompInterface()
        decomp.openProgram(program)

        try:
            results = decomp.decompileFunction(func, 60, TaskMonitor.DUMMY)
            if not results.decompileCompleted():
                error_msg = results.getErrorMessage() or "Decompilation failed"
                raise GhidraError(error_msg, error_type="DecompilationFailed")

            decomp_func = results.getDecompiledFunction()
            if decomp_func is None:
                raise GhidraError(
                    "Decompilation returned no result", error_type="DecompilationFailed"
                )

            code = decomp_func.getC()
            page = _decompilation_page(code, detail, offset, limit)
            return DecompilationResult(
                function_name=func.getName(),
                address=format_address(func.getEntryPoint().getOffset()),
                decompiled_code=page["code"],
                detail=detail,
                offset=page["offset"],
                limit=page["limit"],
                total_lines=page["total_lines"],
                next_offset=page["next_offset"],
                evidence_path=page["evidence_path"],
            )
        finally:
            decomp.dispose()
'''


def patch_text(text: str) -> tuple[str, bool]:
    if MARKER in text:
        return text, False
    patched = text
    for old, new in (
        (OLD_MODEL, NEW_MODEL),
        (OLD_REGISTER, NEW_HELPERS),
        (OLD_FUNCTION, NEW_FUNCTION),
    ):
        count = patched.count(old)
        if count != 1:
            raise ValueError(f"re-mcp-ghidra source block mismatch: expected 1, found {count}")
        patched = patched.replace(old, new, 1)
    return patched, True


def target_path(launcher: Path) -> Path:
    with launcher.open("r", encoding="utf-8") as handle:
        shebang = handle.readline().strip()
    if not shebang.startswith("#!") or not Path(shebang[2:]).is_absolute():
        raise ValueError(f"Cannot determine Python environment from {launcher}")
    python = shebang[2:]
    code = (
        "import importlib.util; "
        "s=importlib.util.find_spec('re_mcp_ghidra'); "
        "print(list(s.submodule_search_locations)[0] if s else '')"
    )
    root = subprocess.check_output([python, "-c", code], text=True).strip()
    if not root:
        raise ValueError(f"re-mcp-ghidra is not importable through {python}")
    return Path(root) / "tools" / "functions.py"


def apply(path: Path, check: bool = False) -> str:
    original = path.read_text(encoding="utf-8")
    patched, changed = patch_text(original)
    if not changed:
        return "unchanged"
    if check:
        return "needs-patch"
    backup = path.with_suffix(".py.omp-original")
    if not backup.exists():
        shutil.copy2(path, backup)
    fd, tmp = tempfile.mkstemp(prefix="omp-ghidra-", suffix=".py", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(patched)
        os.chmod(tmp, stat.S_IMODE(path.stat().st_mode))
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return "patched"


def self_test() -> int:
    source = OLD_MODEL + "\n" + OLD_REGISTER + OLD_FUNCTION
    patched, changed = patch_text(source)
    if not changed or MARKER not in patched:
        print("FAIL patch did not apply", file=sys.stderr)
        return 1
    if patch_text(patched)[1]:
        print("FAIL patch is not idempotent", file=sys.stderr)
        return 1
    compile(patched, "functions.py", "exec")
    print("patch-re-mcp-ghidra: self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher", type=Path)
    parser.add_argument("--target", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    try:
        path = args.target
        if path is None:
            launcher = args.launcher or shutil.which("re-mcp-ghidra")
            if launcher is None:
                raise ValueError("re-mcp-ghidra launcher not found")
            path = target_path(Path(launcher))
        status = apply(path, args.check)
        print(f"omp-ghidra-patch: {status} {path}")
        return 1 if status == "needs-patch" else 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"omp-ghidra-patch: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
