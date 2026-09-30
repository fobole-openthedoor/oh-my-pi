#!/bin/sh
# Android APK sidecar and the dex tools it expects.
# Called from install.sh, update.sh, and install-reverse.sh. Idempotent.
# Does not download Ghidra. Clones reverse-skill when it is missing so the
# symptom-index gate has a tree to patch.
set -eu

KIT="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$KIT/reverse-versions.env"

TOOLS="${REVERSE_SKILL_TOOLS_DIR:-$HOME/tools}"
REVERSE_SKILL_DIR="${REVERSE_SKILL_DIR:-$TOOLS/reverse-skill}"
APK_REVERSE_DIR="${APK_REVERSE_DIR:-$TOOLS/apk-reverse}"
ENV_FILE="${OMP_ENV:-$HOME/.config/omp/env}"
SKIP_APT=0

for arg in "$@"; do
  case "$arg" in
    --skip-apt) SKIP_APT=1 ;;
    --help|-h)
      echo "usage: install-apk.sh [--skip-apt]"
      exit 0
      ;;
    *)
      echo "omp-apk: unknown option $arg" >&2
      exit 2
      ;;
  esac
done

log() { printf 'omp-apk: %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }
need() {
  if ! have "$1"; then
    echo "omp-apk: missing $1" >&2
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
    echo "omp-apk: sha256 mismatch for $file" >&2
    echo "omp-apk: got $got want $expect" >&2
    return 1
  fi
}

download() {
  url="$1"
  dest="$2"
  log "download $url"
  curl -fL --retry 3 --retry-delay 2 -o "$dest" "$url"
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
have sha256sum || need sha256sum

mkdir -p "$TOOLS" "$HOME/.local/bin"

if [ "$SKIP_APT" -eq 0 ] && have dpkg; then
  MISSING=""
  for p in apksigner zipalign; do
    if ! dpkg -s "$p" >/dev/null 2>&1; then
      MISSING="$MISSING $p"
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
    log "apksigner and zipalign already installed"
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
export PATH="$HOME/.local/bin:$PATH"

if pipx list --short 2>/dev/null | awk '{print $1}' | grep -qx "${DROIDASC_SPEC%%=*}"; then
  log "pipx droidasc already installed"
else
  log "pipx install $DROIDASC_SPEC"
  pipx install "$DROIDASC_SPEC"
fi

if [ -d "$REVERSE_SKILL_DIR/.git" ]; then
  log "reverse-skill already at $REVERSE_SKILL_DIR"
  git -C "$REVERSE_SKILL_DIR" fetch --prune --quiet || true
else
  if [ -e "$REVERSE_SKILL_DIR" ]; then
    echo "omp-apk: $REVERSE_SKILL_DIR exists and is not a git checkout" >&2
    exit 1
  fi
  log "clone reverse-skill → $REVERSE_SKILL_DIR"
  git clone --depth 1 "$REVERSE_SKILL_REPO" "$REVERSE_SKILL_DIR"
fi

if [ -d "$APK_REVERSE_DIR/.git" ]; then
  log "apk-reverse sidecar already at $APK_REVERSE_DIR"
  git -C "$APK_REVERSE_DIR" fetch --prune --quiet || true
elif [ -e "$APK_REVERSE_DIR" ]; then
  echo "omp-apk: $APK_REVERSE_DIR exists and is not a git checkout" >&2
  exit 1
else
  log "clone apk-reverse sidecar → $APK_REVERSE_DIR"
  git clone --depth 1 "$APK_REVERSE_REPO" "$APK_REVERSE_DIR"
fi

install_ddc() {
  arch="$(uname -m)"
  if [ "$arch" != "x86_64" ]; then
    log "ddc pin is linux-x64; skip on $arch"
    return 0
  fi
  dest="$TOOLS/ddc/ddc"
  mkdir -p "$TOOLS/ddc"
  if [ -x "$dest" ] && [ "$(sha256sum "$dest" | awk '{print $1}')" = "$DDC_SHA256_X64" ]; then
    link_into_path "$dest" ddc
    log "ddc already at $dest"
    return 0
  fi
  tmp="$TOOLS/ddc/ddc.partial"
  download "$DDC_URL_X64" "$tmp"
  sha256_ok "$tmp" "$DDC_SHA256_X64"
  chmod 755 "$tmp"
  mv "$tmp" "$dest"
  link_into_path "$dest" ddc
}

install_ddc
python3 "$KIT/apply-apk-sidecar.py" \
  --reverse-skill "$REVERSE_SKILL_DIR" \
  --apk-reverse "$APK_REVERSE_DIR"

if [ -f "$REVERSE_SKILL_DIR/skills/scripts/refresh-tool-index.sh" ]; then
  log "refresh reverse-skill tool index"
  bash "$REVERSE_SKILL_DIR/skills/scripts/refresh-tool-index.sh" || \
    log "tool-index refresh failed (non-fatal)"
fi

ensure_env REVERSE_SKILL_ROOT "$REVERSE_SKILL_DIR"
ensure_env APK_REVERSE_ROOT "$APK_REVERSE_DIR"

log "done"
log "apk-reverse $APK_REVERSE_DIR"
log "reverse-skill $REVERSE_SKILL_DIR"
