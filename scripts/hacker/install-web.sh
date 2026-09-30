#!/bin/sh
# Web pentest toolchain the offensive-* skills already call.
# Idempotent. Does not install Burp, Metasploit, or a Kali image.
set -eu

KIT="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$KIT/web-versions.env"

SKIP_APT=0
for arg in "$@"; do
  case "$arg" in
    --skip-apt) SKIP_APT=1 ;;
    --help|-h)
      echo "usage: install-web.sh [--skip-apt]"
      exit 0
      ;;
    *)
      echo "omp-web: unknown option $arg" >&2
      exit 2
      ;;
  esac
done

log() { printf 'omp-web: %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

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
    echo "omp-web: sha256 mismatch for $file" >&2
    echo "omp-web: got $got want $expect" >&2
    return 1
  fi
}

bin_dir() {
  if [ -w /usr/local/bin ] || mkdir -p /usr/local/bin 2>/dev/null; then
    if [ -w /usr/local/bin ]; then
      printf '/usr/local/bin\n'
      return 0
    fi
  fi
  mkdir -p "$HOME/.local/bin"
  printf '%s\n' "$HOME/.local/bin"
}

version_matches() {
  name="$1"
  want="$2"
  if ! have "$name"; then
    return 1
  fi
  got="$("$name" -version 2>&1 || true)"
  printf '%s\n' "$got" | grep -q "$want"
}

install_zip_bin() {
  name="$1"
  version="$2"
  url="$3"
  zipname="$4"
  sha="$5"
  dest="$6"
  if version_matches "$name" "$version"; then
    log "$name $version already installed"
    return 0
  fi
  tmp="$(mktemp -d)"
  # shellcheck disable=SC2064
  trap "rm -rf '$tmp'" EXIT
  log "download $url"
  curl -fL --retry 3 --retry-delay 2 -o "$tmp/$zipname" "$url"
  sha256_ok "$tmp/$zipname" "$sha"
  mkdir -p "$tmp/out"
  unzip -q -o "$tmp/$zipname" -d "$tmp/out"
  if [ ! -f "$tmp/out/$name" ]; then
    echo "omp-web: $zipname has no $name binary" >&2
    return 1
  fi
  install -m 755 "$tmp/out/$name" "$dest/$name"
  log "installed $dest/$name ($version)"
  rm -rf "$tmp"
  trap - EXIT
}

ensure_seclists() {
  dir="$SECLISTS_DIR"
  # shellcheck disable=SC2086
  set -- $SECLISTS_SPARSE
  if [ ! -d "$dir/.git" ]; then
    log "clone SecLists (sparse) → $dir"
    mkdir -p "$(dirname "$dir")"
    git clone --depth 1 --filter=blob:none --sparse "$SECLISTS_REPO" "$dir"
  else
    log "SecLists already at $dir"
    git -C "$dir" fetch --depth 1 --prune origin || true
  fi
  git -C "$dir" sparse-checkout set --cone "$@"
  git -C "$dir" checkout --quiet
  if [ ! -f "$dir/Discovery/Web-Content/common.txt" ]; then
    echo "omp-web: SecLists checkout has no Discovery/Web-Content/common.txt" >&2
    return 1
  fi
  if [ ! -e /usr/share/seclists ] && [ -w /usr/share ]; then
    ln -sfn "$dir" /usr/share/seclists
    log "link /usr/share/seclists → $dir"
  fi
  log "wordlists → $dir"
}

if [ "$SKIP_APT" -eq 0 ] && have apt-get; then
  PKGS="gobuster hydra john whatweb wfuzz dirb"
  MISSING=""
  for pkg in $PKGS; do
    if have dpkg && ! dpkg -s "$pkg" >/dev/null 2>&1; then
      MISSING="$MISSING $pkg"
    fi
  done
  if [ -n "$MISSING" ]; then
    log "apt install$MISSING"
    export DEBIAN_FRONTEND=noninteractive
    if ! apt_root apt-get update; then
      log "apt update failed — install these by hand:$MISSING"
    elif ! apt_root apt-get install -y $MISSING; then
      log "apt install failed — continue with GitHub binaries"
    fi
  else
    log "apt packages already present"
  fi
fi

DEST="$(bin_dir)"
case "$(uname -m)" in
  x86_64|amd64)
    install_zip_bin nuclei "$NUCLEI_VERSION" "$NUCLEI_URL" "$NUCLEI_ZIP" "$NUCLEI_SHA256" "$DEST"
    install_zip_bin httpx "$HTTPX_VERSION" "$HTTPX_URL" "$HTTPX_ZIP" "$HTTPX_SHA256" "$DEST"
    install_zip_bin subfinder "$SUBFINDER_VERSION" "$SUBFINDER_URL" "$SUBFINDER_ZIP" "$SUBFINDER_SHA256" "$DEST"
    ;;
  *)
    log "pinned nuclei/httpx/subfinder builds are linux amd64; skipped on $(uname -m)"
    ;;
esac

ensure_seclists

if have nuclei; then
  log "update nuclei templates"
  # -disable-update-check also skips the first template install.
  if ! nuclei -update-templates; then
    log "nuclei template update failed (non-fatal)"
  elif [ ! -d "$HOME/nuclei-templates" ]; then
    log "nuclei-templates directory missing after update"
  fi
fi

INDEX="$HOME/tools/reverse-skill/skills/scripts/refresh-tool-index.sh"
if [ -f "$INDEX" ]; then
  log "refresh reverse-skill tool index"
  bash "$INDEX" || log "tool-index refresh failed (non-fatal)"
fi

log "done"
