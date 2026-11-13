#!/usr/bin/env bash
# Removes menu entry, autostart, icon and hotkey. Keeps your data (~/.local/share/twomin).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
KB_SCHEMA="org.gnome.settings-daemon.plugins.media-keys"
KB_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/twomin/"

"$DIR/.venv/bin/twomin" --quit 2>/dev/null || true
rm -f "$HOME/.local/share/applications/twomin.desktop" \
      "$HOME/.config/autostart/twomin.desktop" \
      "$HOME/.local/share/icons/hicolor/scalable/apps/twomin.svg"

current="$(gsettings get "$KB_SCHEMA" custom-keybindings)"
updated="$(python3 - "$current" "$KB_PATH" <<'PY'
import ast, sys
paths = [p for p in ast.literal_eval(sys.argv[1].replace("@as ", "")) if p != sys.argv[2]]
print(str(paths))
PY
)"
gsettings set "$KB_SCHEMA" custom-keybindings "$updated"
gsettings reset-recursively "$KB_SCHEMA.custom-keybinding:$KB_PATH" 2>/dev/null || true
echo "Uninstalled. Delete $DIR/.venv and ~/.local/share/twomin to remove everything."
