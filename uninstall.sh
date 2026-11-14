#!/usr/bin/env bash
# Removes menu entry, autostart, icon and (on GNOME) the hotkey. Keeps your data
# (~/.local/share/twomin) and the system packages.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"

"$DIR/.venv/bin/twomin" --quit 2>/dev/null || true
rm -f "$HOME/.local/share/applications/twomin.desktop" \
      "$HOME/.config/autostart/twomin.desktop" \
      "$HOME/.local/share/icons/hicolor/scalable/apps/twomin.svg"

if [[ ":${XDG_CURRENT_DESKTOP:-}:" == *:GNOME:* ]]; then
  schema="org.gnome.settings-daemon.plugins.media-keys"
  path="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/twomin/"
  current="$(gsettings get "$schema" custom-keybindings)"
  updated="$(python3 - "$current" "$path" <<'PY'
import ast, sys
paths = [p for p in ast.literal_eval(sys.argv[1].replace("@as ", "")) if p != sys.argv[2]]
print(str(paths))
PY
)"
  gsettings set "$schema" custom-keybindings "$updated"
  gsettings reset-recursively "$schema.custom-keybinding:$path" 2>/dev/null || true
else
  echo "Remove the twomins keyboard shortcut in your desktop's settings, if you added one."
fi
echo "Uninstalled. Delete $DIR/.venv and ~/.local/share/twomin to remove everything."
