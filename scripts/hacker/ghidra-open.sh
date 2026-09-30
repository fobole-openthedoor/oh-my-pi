#!/bin/sh
# Import a local binary into a Ghidra project that re-mcp-ghidra can open.
# Layout matches re-mcp-ghidra Session.open: <dir>/ghidra_projects/<basename>.gpr
# Does not write API keys.
set -eu

KIT="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
GHIDRA_HOME="${GHIDRA_INSTALL_DIR:-${GHIDRA_HOME:-$HOME/tools/ghidra}}"
TIMEOUT="${GHIDRA_OPEN_TIMEOUT:-600}"
FORCE=0
ANALYZE=1
DRY=0
BINARY=""

usage() {
  cat <<'EOF'
usage: ghidra-open.sh [--force] [--no-analyze] [--dry-run] [--timeout SECONDS] <binary>

Import <binary> with analyzeHeadless into <dir>/ghidra_projects/<basename>,
the same layout re-mcp-ghidra open_database uses. Then in omp call MCP
open_database with that file_path (run_auto_analysis false if analysis ran).
EOF
}

emit_json() {
  python3 -c 'import json,sys; print(json.dumps(json.loads(sys.argv[1]), ensure_ascii=False, indent=2))' "$1"
}

fail_json() {
  msg="$1"
  emit_json "{\"ok\": false, \"error\": $(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$msg")}"
  exit 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --force|-f) FORCE=1 ;;
    --no-analyze) ANALYZE=0 ;;
    --dry-run) DRY=1 ;;
    --timeout)
      shift
      TIMEOUT="${1:-}"
      [ -n "$TIMEOUT" ] || fail_json "--timeout needs a number"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      fail_json "unknown option $1"
      ;;
    *)
      if [ -n "$BINARY" ]; then
        fail_json "extra argument: $1"
      fi
      BINARY="$1"
      ;;
  esac
  shift
done

[ -n "$BINARY" ] || fail_json "usage: ghidra-open.sh [--force] [--no-analyze] [--dry-run] <binary>"

ABS="$(python3 -c 'import os,sys; print(os.path.realpath(os.path.expanduser(sys.argv[1])))' "$BINARY")"
[ -f "$ABS" ] || fail_json "not a file: $BINARY"

NAME="$(basename "$ABS")"
DIR="$(dirname "$ABS")"
PROJECT_DIR="$DIR/ghidra_projects"
PROJECT_FILE="$PROJECT_DIR/$NAME.gpr"
ANALYZE_BIN="$GHIDRA_HOME/support/analyzeHeadless"

ensure_java() {
  if [ -n "${JAVA_HOME:-}" ] && [ -x "$JAVA_HOME/bin/java" ]; then
    return 0
  fi
  for cand in \
    /usr/lib/jvm/java-21-openjdk-amd64 \
    /usr/lib/jvm/java-21-openjdk \
    /usr/lib/jvm/java-21-openjdk-arm64
  do
    if [ -x "$cand/bin/java" ]; then
      JAVA_HOME="$cand"
      export JAVA_HOME
      return 0
    fi
  done
  if command -v java >/dev/null 2>&1; then
    JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")"
    export JAVA_HOME
    return 0
  fi
  return 1
}

CMD_JSON="$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1:]))' \
  "$ANALYZE_BIN" "$PROJECT_DIR" "$NAME" -import "$ABS" -overwrite \
  -analysisTimeoutPerFile "$TIMEOUT")"

if [ "$ANALYZE" -eq 0 ]; then
  CMD_JSON="$(python3 -c 'import json,sys; a=json.loads(sys.argv[1]); a.append("-noanalysis"); print(json.dumps(a))' "$CMD_JSON")"
fi

if [ "$DRY" -eq 1 ]; then
  emit_json "$(python3 -c '
import json,sys
cmd=json.loads(sys.argv[1])
print(json.dumps({
  "ok": True,
  "dry_run": True,
  "path": sys.argv[2],
  "project_dir": sys.argv[3],
  "project_name": sys.argv[4],
  "project_file": sys.argv[5],
  "analyzed": sys.argv[6]=="1",
  "command": cmd,
  "mcp": {
    "tool": "open_database",
    "file_path": sys.argv[2],
    "run_auto_analysis": sys.argv[6]!="1",
  },
}, ensure_ascii=False))
' "$CMD_JSON" "$ABS" "$PROJECT_DIR" "$NAME" "$PROJECT_FILE" "$ANALYZE")"
  exit 0
fi

if [ -f "$PROJECT_FILE" ] && [ "$FORCE" -eq 0 ]; then
  emit_json "$(python3 -c '
import json,sys
print(json.dumps({
  "ok": True,
  "skipped": True,
  "path": sys.argv[1],
  "project_dir": sys.argv[2],
  "project_name": sys.argv[3],
  "project_file": sys.argv[4],
  "analyzed": True,
  "mcp": {
    "tool": "open_database",
    "file_path": sys.argv[1],
    "run_auto_analysis": False,
  },
  "note": "Existing Ghidra project reused. Next: MCP ghidra open_database with this file_path.",
}, ensure_ascii=False))
' "$ABS" "$PROJECT_DIR" "$NAME" "$PROJECT_FILE")"
  exit 0
fi

[ -x "$ANALYZE_BIN" ] || fail_json "analyzeHeadless not at $ANALYZE_BIN (run $KIT/install-reverse.sh)"
ensure_java || fail_json "JAVA_HOME not found (need JDK 21)"

mkdir -p "$PROJECT_DIR"
LOG="$PROJECT_DIR/$NAME.analyzeHeadless.log"

set +e
python3 -c '
import json, os, subprocess, sys
cmd = json.loads(sys.argv[1])
log_path = sys.argv[2]
os.environ.setdefault("JAVA_HOME", os.environ.get("JAVA_HOME", ""))
with open(log_path, "wb") as log:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert proc.stdout is not None
    for chunk in iter(lambda: proc.stdout.read(4096), b""):
        log.write(chunk)
        sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush()
    raise SystemExit(proc.wait())
' "$CMD_JSON" "$LOG"
STATUS=$?
set -e

if [ "$STATUS" -ne 0 ]; then
  fail_json "analyzeHeadless exited $STATUS (log $LOG)"
fi

[ -f "$PROJECT_FILE" ] || fail_json "analyzeHeadless finished but $PROJECT_FILE is missing (log $LOG)"

emit_json "$(python3 -c '
import json,sys
print(json.dumps({
  "ok": True,
  "skipped": False,
  "path": sys.argv[1],
  "project_dir": sys.argv[2],
  "project_name": sys.argv[3],
  "project_file": sys.argv[4],
  "analyzed": sys.argv[5]=="1",
  "log": sys.argv[6],
  "mcp": {
    "tool": "open_database",
    "file_path": sys.argv[1],
    "run_auto_analysis": sys.argv[5]!="1",
  },
  "note": "Next: MCP ghidra open_database with this file_path. Do not re-run auto analysis unless --no-analyze was used.",
}, ensure_ascii=False))
' "$ABS" "$PROJECT_DIR" "$NAME" "$PROJECT_FILE" "$ANALYZE" "$LOG")"
