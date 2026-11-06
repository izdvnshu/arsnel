#!/usr/bin/env bash
# ARSNEL installer for Linux and macOS.
# Installs into ~/.arsnel inside a virtual environment. Never uses sudo.
# Options (environment variables):
#   ARSNEL_REF=main          branch, tag or commit to install (pin a tag for repeatable installs)
#   ARSNEL_REPO=<https url>  repository to install from
#   ARSNEL_MODEL=llama3.2    model to pull with ollama
#   ARSNEL_SKIP_MODEL=1      do not pull a model
#   ARSNEL_DRY_RUN=1         print what would happen and change nothing
set -euo pipefail

REPO="${ARSNEL_REPO:-https://github.com/YOUR_USERNAME/arsnel.git}"
REF="${ARSNEL_REF:-main}"
MODEL="${ARSNEL_MODEL:-llama3.2}"
HOME_DIR="${ARSNEL_HOME:-$HOME/.arsnel}"
VENV="$HOME_DIR/venv"
BIN="${ARSNEL_BIN:-$HOME/.local/bin}"
DRY="${ARSNEL_DRY_RUN:-0}"

say() { printf '%s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }
run() {
  if [ "$DRY" = "1" ]; then say "[dry-run] $*"; else "$@"; fi
}

case "$REPO" in
  *YOUR_USERNAME*) die "Replace YOUR_USERNAME with your GitHub username (or set ARSNEL_REPO)." ;;
  https://*|file://*) ;;
  *) die "ARSNEL_REPO must start with https:// (got: $REPO)" ;;
esac

command -v git >/dev/null 2>&1 || die "git is required. Install it from https://git-scm.com/downloads"

PY=""
for candidate in python3.12 python3.11 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PY="$candidate"
    break
  fi
done
[ -n "$PY" ] || die "Python 3.11 or newer is required. Install it from https://www.python.org/downloads/"

say "Installing ARSNEL ($REF) into $HOME_DIR using $PY"
run mkdir -p "$HOME_DIR" "$BIN"
run "$PY" -m venv "$VENV"
run "$VENV/bin/python" -m pip install --quiet --upgrade pip
run "$VENV/bin/python" -m pip install --quiet "git+${REPO}@${REF}"
run ln -sf "$VENV/bin/arsnel" "$BIN/arsnel"

if command -v ollama >/dev/null 2>&1; then
  if [ "${ARSNEL_SKIP_MODEL:-0}" = "1" ]; then
    say "Skipping model download."
  else
    run ollama pull "$MODEL"
  fi
else
  say "ollama is not installed. Get it from https://ollama.com, then run: ollama pull $MODEL"
fi

case ":$PATH:" in
  *":$BIN:"*) ;;
  *) say "Add this to your shell profile, then open a new terminal:  export PATH=\"$BIN:\$PATH\"" ;;
esac

say "Done. Try: arsnel --help"
