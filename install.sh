#!/usr/bin/env bash
# Lailaba CLI per-user installer for Linux, macOS, WSL, EC2, and Termux.
# Installs an isolated virtual environment and a `lailaba-cli` command without sudo.
set -Eeuo pipefail

APP_NAME="lailaba-cli"
INSTALL_ROOT="${LAILABA_INSTALL_ROOT:-${HOME}/.local/share/lailaba-cli}"
BIN_DIR="${LAILABA_BIN_DIR:-${HOME}/.local/bin}"
VENV="${INSTALL_ROOT}/venv"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

say() { printf '\033[1;37m[Lailaba CLI]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[Lailaba CLI warning]\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31m[Lailaba CLI error]\033[0m %s\n' "$*" >&2; exit 1; }

[[ -n "${HOME:-}" && -d "$HOME" ]] || die 'HOME is not set to a valid directory.'
[[ -f "$SCRIPT_DIR/pyproject.toml" && -d "$SCRIPT_DIR/src/lailaba_cli" ]] || die 'Run install.sh from the extracted Lailaba CLI project directory; pyproject.toml and src/lailaba_cli must be beside it.'

PYTHON=""

# Search both generic and versioned interpreters. On Amazon Linux, for example,
# `python3` may be older while `python3.11` is installed alongside it.
find_python() {
  local candidate version major minor
  for candidate in python3.14 python3.13 python3.12 python3.11 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      version="$("$candidate" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || true)"
      major="${version%%.*}"; minor="${version#*.}"
      if [[ "$major" =~ ^[0-9]+$ && "$minor" =~ ^[0-9]+$ ]] && (( major > 3 || (major == 3 && minor >= 11) )); then
        PYTHON="$(command -v "$candidate")"
        return 0
      fi
    fi
  done
  return 1
}

install_system_python() {
  # Best-effort package installation. Continue to the portable uv fallback if
  # this distribution's repositories do not provide Python 3.11+.
  if [[ "$(id -u 2>/dev/null || echo 1)" == "0" ]]; then
    if command -v dnf >/dev/null 2>&1; then
      say 'Attempting to install Python 3.11 using dnf'
      dnf install -y python3.11 python3.11-pip >/dev/null 2>&1 || true
    elif command -v apt-get >/dev/null 2>&1; then
      say 'Attempting to install Python 3.11 using apt'
      export DEBIAN_FRONTEND=noninteractive
      apt-get update -y >/dev/null 2>&1 || true
      apt-get install -y python3.11 python3.11-venv python3-pip >/dev/null 2>&1 || true
    elif command -v yum >/dev/null 2>&1; then
      say 'Attempting to install Python 3.11 using yum'
      yum install -y python3.11 python3.11-pip >/dev/null 2>&1 || true
    elif command -v apk >/dev/null 2>&1; then
      say 'Attempting to install Python 3 using apk'
      apk add --no-cache python3 py3-pip >/dev/null 2>&1 || true
    elif command -v pacman >/dev/null 2>&1; then
      say 'Attempting to install Python using pacman'
      pacman -Sy --noconfirm python python-pip >/dev/null 2>&1 || true
    fi
  fi
  find_python
}

install_uv_python() {
  local uv_bin="$HOME/.local/bin/uv"
  if ! command -v uv >/dev/null 2>&1 && [[ ! -x "$uv_bin" ]]; then
    command -v curl >/dev/null 2>&1 || command -v wget >/dev/null 2>&1 || return 1
    say 'Installing uv as a fallback to obtain Python 3.11+' 
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL https://astral.sh/uv/install.sh -o /tmp/lailaba-uv-install.sh || return 1
    else
      wget -q https://astral.sh/uv/install.sh -O /tmp/lailaba-uv-install.sh || return 1
    fi
    sh /tmp/lailaba-uv-install.sh >/dev/null || return 1
    rm -f /tmp/lailaba-uv-install.sh
  fi
  local uv_cmd
  if command -v uv >/dev/null 2>&1; then uv_cmd="$(command -v uv)"; else uv_cmd="$uv_bin"; fi
  "$uv_cmd" python install 3.11 >/dev/null || return 1
  PYTHON="$("$uv_cmd" python find 3.11 2>/dev/null | head -n 1)"
  [[ -x "$PYTHON" ]] || return 1
  return 0
}

if ! find_python; then
  install_system_python || true
fi
if [[ -z "$PYTHON" ]]; then
  install_uv_python || true
fi
[[ -n "$PYTHON" ]] || die 'Could not obtain Python 3.11+. Install Python 3.11 or newer manually, or ensure this server can reach its OS package repositories and https://astral.sh, then rerun install.sh.'

say "Using $($PYTHON --version 2>&1)"
mkdir -p "$INSTALL_ROOT" "$BIN_DIR"
chmod 700 "$INSTALL_ROOT" 2>/dev/null || true

# Create an isolated environment; never modify system Python. Rebuild an older
# environment instead of accidentally reusing a Python 3.9/3.10 virtualenv.
VENV_OK=0
if [[ -x "$VENV/bin/python" ]]; then
  VENV_VERSION="$("$VENV/bin/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || true)"
  VENV_MAJOR="${VENV_VERSION%%.*}"; VENV_MINOR="${VENV_VERSION#*.}"
  if [[ "$VENV_MAJOR" =~ ^[0-9]+$ && "$VENV_MINOR" =~ ^[0-9]+$ ]] && (( VENV_MAJOR > 3 || (VENV_MAJOR == 3 && VENV_MINOR >= 11) )); then
    VENV_OK=1
  else
    warn "Existing virtual environment uses Python ${VENV_VERSION:-unknown}; rebuilding it with Python 3.11+."
    rm -rf "$VENV"
  fi
fi
if (( VENV_OK == 0 )); then
  say "Creating isolated environment at $VENV"
  "$PYTHON" -m venv "$VENV" || {
    if command -v uv >/dev/null 2>&1; then
      uv venv --python "$PYTHON" "$VENV" || die 'Could not create a virtual environment. Install the Python venv package for your distribution and retry.'
    else
      die 'Could not create a virtual environment. On Debian/Ubuntu install python3.11-venv; on Fedora/Amazon Linux install the matching Python venv package, then retry.'
    fi
  }
fi

say 'Installing Lailaba CLI and its dependencies'
if ! "$VENV/bin/python" -m pip install --disable-pip-version-check --upgrade pip setuptools wheel; then
  warn 'Could not upgrade packaging tools; attempting installation with the existing tools.'
fi
if ! "$VENV/bin/python" -m pip install --disable-pip-version-check --upgrade --no-build-isolation "$SCRIPT_DIR"; then
  warn 'Standard package installation failed; retrying with build isolation enabled.'
  "$VENV/bin/python" -m pip install --disable-pip-version-check --upgrade "$SCRIPT_DIR" || die 'Package installation failed. Check network access and Python build tools, then rerun install.sh.'
fi

ENTRY="$VENV/bin/lailaba-cli"
[[ -x "$ENTRY" ]] || die 'Package installed but the lailaba-cli entry point was not created.'
ln -sfn "$ENTRY" "$BIN_DIR/lailaba-cli"
chmod 700 "$BIN_DIR/lailaba-cli" 2>/dev/null || true

# Add the user bin directory to common shell profiles only when needed.
path_line='export PATH="$HOME/.local/bin:$PATH"'
# Ensure at least the POSIX login profile exists, including on minimal Termux installs.
touch "$HOME/.profile"
for profile in "$HOME/.profile" "$HOME/.bashrc" "$HOME/.zshrc"; do
  [[ -e "$profile" ]] || continue
  if ! grep -Fq '.local/bin' "$profile" 2>/dev/null; then
    printf '\n# Lailaba CLI user commands\n%s\n' "$path_line" >> "$profile"
  fi
done

say 'Installation completed.'
printf '\n'
"$ENTRY" --version
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  warn "$BIN_DIR is not in this shell's PATH yet. Run: export PATH=\"\$HOME/.local/bin:\$PATH\""
  warn 'Also open a new terminal or run: source ~/.profile'
fi

if [[ "${LAILABA_SKIP_SETUP:-0}" != "1" ]]; then
  printf '\n'
  say 'Next, choose Lailaba AI or configure a third-party OpenAI-compatible provider.'
  if "$ENTRY" setup key; then
    say 'Setup step completed.'
  else
    warn 'The app is installed, but key setup or connectivity verification did not complete.'
    warn 'Retry later with: lailaba-cli setup key'
  fi
else
  say 'Skipped interactive key setup (LAILABA_SKIP_SETUP=1). Run: lailaba-cli setup key'
fi

printf '\nQuick start:\n  lailaba-cli                 # start the autonomous agent in this directory\n  lailaba-cli setup key       # configure or change provider and API key
  lailaba-cli setup provider  # switch provider or update credentials
  lailaba-cli provider show   # show active provider settings\n  lailaba-cli run "inspect this project and report issues"\n  lailaba-cli doctor          # diagnose installation and API connectivity\n  lailaba-cli --help          # list all commands\n\n'
