#!/bin/sh
# Install the reverse-engineering stack used with this oh-my-pi fork.
# Idempotent. Does not write API keys. Ghidra is ~570MB — skip with --skip-ghidra.
set -eu

KIT="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$KIT/reverse-versions.env"

TOOLS="${REVERSE_SKILL_TOOLS_DIR:-$HOME/tools}"
REVERSE_SKILL_DIR="${REVERSE_SKILL_DIR:-$TOOLS/reverse-skill}"
GHIDRA_HOME="${GHIDRA_INSTALL_DIR:-${GHIDRA_HOME:-$TOOLS/ghidra}}"
JADX_DIR="${JADX_DIR:-$TOOLS/jadx}"
AGENT_DIR="${OMP_AGENT_DIR:-$HOME/.omp/agent}"
ENV_FILE="${OMP_ENV:-$HOME/.config/omp/env}"
SKIP_GHIDRA=0
SKIP_APT=0

for arg in "$@"; do
  case "$arg" in
    --skip-ghidra) SKIP_GHIDRA=1 ;;
    --skip-apt) SKIP_APT=1 ;;
    --help|-h)
      echo "usage: install-reverse.sh [--skip-ghidra] [--skip-apt]"
      exit 0
      ;;
    *)
      echo "omp-reverse: unknown option $arg" >&2
      exit 2
      ;;
  esac
done

log() { printf 'omp-reverse: %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

need() {
  if ! have "$1"; then
    echo "omp-reverse: missing $1" >&2
    exit 1
  fi
}

apt_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif have sudo; then
    sudo "$@"
  else
    return 1
  fi
}

sha256_ok() {
  file="$1"
  expect="$2"
  got="$(sha256sum "$file" | awk '{print $1}')"
  if [ "$got" != "$expect" ]; then
    echo "omp-reverse: sha256 mismatch for $file" >&2
    echo "omp-reverse: got $got want $expect" >&2
    return 1
  fi
}

download() {
  url="$1"
  dest="$2"
  log "download $url"
  curl -fL --retry 3 --retry-delay 2 -o "$dest" "$url"
}

ensure_java_home() {
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
      return 0
    fi
  done
  if have java; then
    JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")"
    return 0
  fi
  echo "omp-reverse: JAVA_HOME not found (need JDK 21)" >&2
  exit 1
}

link_into_path() {
  src="$1"
  name="$2"
  if [ -w /usr/local/bin ] || mkdir -p /usr/local/bin 2>/dev/null; then
    if [ -w /usr/local/bin ]; then
      ln -sfn "$src" "/usr/local/bin/$name"
      log "link /usr/local/bin/$name → $src"
      return 0
    fi
  fi
  mkdir -p "$HOME/.local/bin"
  ln -sfn "$src" "$HOME/.local/bin/$name"
  log "link $HOME/.local/bin/$name → $src"
}

ensure_env() {
  key="$1"
  value="$2"
  mkdir -p "$(dirname "$ENV_FILE")"
  if [ ! -f "$ENV_FILE" ]; then
    return 0
  fi
  if grep -q "^export ${key}=" "$ENV_FILE" 2>/dev/null; then
    return 0
  fi
  printf '\nexport %s="%s"\n' "$key" "$value" >>"$ENV_FILE"
}

need git
need curl
need python3
need unzip
have sha256sum || need sha256sum

mkdir -p "$TOOLS" "$HOME/.local/bin" "$AGENT_DIR/skills/reverse-skill"

if [ "$SKIP_APT" -eq 0 ]; then
  PKGS="git curl wget ca-certificates unzip tar jq python3 python3-venv python3-pip pipx openjdk-21-jdk radare2 apktool binwalk gdb gdb-multiarch ffuf nmap sqlmap hashcat file binutils strace ltrace xxd p7zip-full adb build-essential"
  MISSING=""
  for p in $PKGS; do
    if have dpkg; then
      if ! dpkg -s "$p" >/dev/null 2>&1; then
        MISSING="$MISSING $p"
      fi
    fi
  done
  if [ -n "$MISSING" ]; then
    log "apt install$MISSING"
    if ! apt_root apt-get update; then
      log "apt update failed — install these by hand:$MISSING"
    elif ! apt_root apt-get install -y $MISSING; then
      log "apt install failed — continue with user-space tools"
    fi
  else
    log "apt packages already present (or dpkg unavailable)"
  fi
fi

if have pipx; then
  pipx ensurepath >/dev/null 2>&1 || true
else
  log "pipx missing; python3 -m pip install --user pipx"
  python3 -m pip install --user pipx
  python3 -m pipx ensurepath >/dev/null 2>&1 || true
  export PATH="$HOME/.local/bin:$PATH"
  have pipx || need pipx
fi

pipx_spec() {
  spec="$1"
  pkg="${spec%%=*}"
  if pipx list --short 2>/dev/null | awk '{print $1}' | grep -qx "$pkg"; then
    log "pipx $pkg already installed"
    return 0
  fi
  log "pipx install $spec"
  pipx install "$spec"
}

pipx_spec "$RE_MCP_GHIDRA_SPEC"
pipx_spec "$FRIDA_TOOLS_SPEC"
pipx_spec "$OBJECTION_SPEC"
pipx_spec "$PWNTOOLS_SPEC"

if [ -d "$REVERSE_SKILL_DIR/.git" ]; then
  log "reverse-skill already at $REVERSE_SKILL_DIR"
  git -C "$REVERSE_SKILL_DIR" fetch --prune --quiet || true
else
  log "clone reverse-skill → $REVERSE_SKILL_DIR"
  git clone --depth 1 "$REVERSE_SKILL_REPO" "$REVERSE_SKILL_DIR"
fi

if [ "$SKIP_GHIDRA" -eq 0 ]; then
  unpacked="$TOOLS/$GHIDRA_DIR_NAME"
  if [ -x "$unpacked/support/analyzeHeadless" ] || [ -x "$GHIDRA_HOME/support/analyzeHeadless" ]; then
    log "ghidra already installed"
  else
    zip="$TOOLS/$GHIDRA_ZIP"
    if [ ! -f "$zip" ]; then
      download "$GHIDRA_URL" "$zip"
    fi
    sha256_ok "$zip" "$GHIDRA_SHA256"
    log "unzip $zip → $TOOLS"
    unzip -q -o "$zip" -d "$TOOLS"
    rm -f "$zip"
  fi
  if [ -d "$TOOLS/$GHIDRA_DIR_NAME" ]; then
    ln -sfn "$TOOLS/$GHIDRA_DIR_NAME" "$TOOLS/ghidra"
    GHIDRA_HOME="$TOOLS/ghidra"
  fi
else
  log "skipping ghidra download"
fi

if [ -x "$JADX_DIR/bin/jadx" ]; then
  log "jadx already at $JADX_DIR"
else
  zip="$TOOLS/$JADX_ZIP"
  mkdir -p "$JADX_DIR"
  if [ ! -f "$zip" ]; then
    download "$JADX_URL" "$zip"
  fi
  sha256_ok "$zip" "$JADX_SHA256"
  log "unzip $zip → $JADX_DIR"
  unzip -q -o "$zip" -d "$JADX_DIR"
  rm -f "$zip"
fi
if [ -x "$JADX_DIR/bin/jadx" ]; then
  link_into_path "$JADX_DIR/bin/jadx" jadx
fi

ensure_java_home
export JAVA_HOME
export GHIDRA_INSTALL_DIR="$GHIDRA_HOME"
export GHIDRA_HOME
export REVERSE_SKILL_ROOT="$REVERSE_SKILL_DIR"
export PATH="$GHIDRA_HOME:$GHIDRA_HOME/support:$JADX_DIR/bin:$HOME/.local/bin:$PATH"

if [ -f "$REVERSE_SKILL_DIR/skills/scripts/refresh-tool-index.sh" ]; then
  log "refresh reverse-skill tool index"
  bash "$REVERSE_SKILL_DIR/skills/scripts/refresh-tool-index.sh" || \
    log "tool-index refresh failed (non-fatal)"
fi

ensure_env GHIDRA_INSTALL_DIR "$GHIDRA_HOME"
ensure_env GHIDRA_HOME "$GHIDRA_HOME"
ensure_env JAVA_HOME "$JAVA_HOME"
ensure_env REVERSE_SKILL_ROOT "$REVERSE_SKILL_DIR"

MCP_CMD="$(command -v re-mcp-ghidra 2>/dev/null || true)"
if [ -z "$MCP_CMD" ] && [ -x "$HOME/.local/bin/re-mcp-ghidra" ]; then
  MCP_CMD="$HOME/.local/bin/re-mcp-ghidra"
fi
if [ -n "$MCP_CMD" ] && [ -x "$GHIDRA_HOME/support/analyzeHeadless" ]; then
  python3 "$KIT/wire-ghidra-mcp.py" \
    "$AGENT_DIR/mcp.json" "$MCP_CMD" "$GHIDRA_HOME" "$JAVA_HOME"
  if [ -f "$KIT/skills/reverse-skill/SKILL.md" ]; then
    mkdir -p "$AGENT_DIR/skills/reverse-skill"
    cp "$KIT/skills/reverse-skill/SKILL.md" \
      "$AGENT_DIR/skills/reverse-skill/SKILL.md"
  fi
  if [ -f "$KIT/AGENTS.md.example" ] && [ ! -f "$AGENT_DIR/AGENTS.md" ]; then
    sed \
      -e "s|__REVERSE_SKILL_ROOT__|$REVERSE_SKILL_DIR|g" \
      -e "s|__GHIDRA_HOME__|$GHIDRA_HOME|g" \
      -e "s|__OMP_FORK_ROOT__|${OMP_FORK_ROOT:-$HOME/oh-my-pi}|g" \
      -e "s|__CLAUDE_RED_ROOT__|${CLAUDE_RED_ROOT:-$HOME/tools/claude-red}|g" \
      "$KIT/AGENTS.md.example" >"$AGENT_DIR/AGENTS.md"
    chmod 600 "$AGENT_DIR/AGENTS.md"
  fi
else
  log "ghidra MCP not wired (need re-mcp-ghidra + analyzeHeadless)"
fi

log "done"
log "Ghidra $GHIDRA_HOME"
log "jadx $JADX_DIR"
log "reverse-skill $REVERSE_SKILL_DIR"
log "JAVA_HOME $JAVA_HOME"
log "verify: $KIT/verify-reverse.sh"
