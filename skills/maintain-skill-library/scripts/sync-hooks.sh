#!/bin/bash
# Copy the guard hooks from this repo to ~/.agents/hooks, only after the contract tests pass.
# The installed guards are mode 500 and immutable (chflags uchg); this script lifts and restores that flag.
set -euo pipefail

SRC="$(cd "$(dirname "$0")/hooks" && pwd)"
DEST="${HOME}/.agents/hooks"
FILES=(guard-shell.py deny-env-read.py session-budget.py lint-dirty.py test_guard.py)
LOCKED=(guard-shell.py deny-env-read.py)

/usr/bin/python3 "$SRC/test_guard.py" "$SRC"
/usr/bin/python3 "$SRC/session-budget.py" --selftest
/usr/bin/python3 "$SRC/lint-dirty.py" --selftest

mkdir -p "$DEST"
chmod 700 "$DEST"
for f in "${FILES[@]}"; do
  if [ -e "$DEST/$f" ]; then
    chflags nouchg "$DEST/$f"
    chmod 700 "$DEST/$f"
  fi
  cp "$SRC/$f" "$DEST/$f"
  chmod 500 "$DEST/$f"
done
for f in "${LOCKED[@]}"; do
  chflags uchg "$DEST/$f"
done

/usr/bin/python3 "$DEST/test_guard.py" "$DEST"
echo "synced ${#FILES[@]} hook files to $DEST"
