#!/usr/bin/env bash
# Two-Minute Start installer for Fedora + GNOME (Wayland or X11).
# Re-run any time; it's idempotent. Override the hotkey with: TWOMIN_KEY='<Super><Shift>t' ./install.sh
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
KEY="${TWOMIN_KEY:-<Super>t}"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/scalable/apps"
AUTOSTART="$HOME/.config/autostart"
BIN="$DIR/.venv/bin/twomin"
KB_SCHEMA="org.gnome.settings-daemon.plugins.media-keys"
KB_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/twomin/"
APPIND="appindicatorsupport@rgcjonas.gmail.com"

say() { printf '\033[1;33m==>\033[0m %s\n' "$*"; }

# 1. System packages (xcb-util-cursor is needed by Qt under XWayland)
need=()
for p in xcb-util-cursor libnotify pipewire-utils gnome-shell-extension-appindicator; do
  rpm -q "$p" &>/dev/null || need+=("$p")
done
if ((${#need[@]})); then
  say "Installing: ${need[*]}"
  sudo dnf install -y "${need[@]}"
fi

# 2. Python venv + app (editable, so your code changes apply on next launch)
say "Setting up venv"
[[ -d "$DIR/.venv" ]] || python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install -q --upgrade pip
"$DIR/.venv/bin/pip" install -q -e "$DIR"

# 3. Icon + app-menu entry
say "Adding app-menu entry"
mkdir -p "$APPS" "$ICONS" "$AUTOSTART"
cp "$DIR/twomin/assets/icon.svg" "$ICONS/twomin.svg"
cat > "$APPS/twomin.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Two-Minute Start
Comment=Start the task you're avoiding — just two minutes
Exec=$BIN
Icon=twomin
Terminal=false
Categories=Utility;
Keywords=timer;adhd;focus;procrastination;
StartupWMClass=twomin
EOF
update-desktop-database "$APPS" 2>/dev/null || true
gtk-update-icon-cache -q "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

# 4. Autostart (hidden in tray)
say "Enabling autostart"
sed -e "s|^Exec=.*|Exec=$BIN --tray|" "$APPS/twomin.desktop" > "$AUTOSTART/twomin.desktop"
echo "X-GNOME-Autostart-enabled=true" >> "$AUTOSTART/twomin.desktop"

# 5. Global hotkey via GNOME custom shortcut
say "Binding $KEY"
current="$(gsettings get "$KB_SCHEMA" custom-keybindings)"
updated="$(python3 - "$current" "$KB_PATH" <<'PY'
import ast, sys
cur, path = sys.argv[1].replace("@as ", ""), sys.argv[2]
paths = ast.literal_eval(cur)
if path not in paths:
    paths.append(path)
print(str(paths))
PY
)"
gsettings set "$KB_SCHEMA" custom-keybindings "$updated"
gsettings set "$KB_SCHEMA.custom-keybinding:$KB_PATH" name "Two-Minute Start"
gsettings set "$KB_SCHEMA.custom-keybinding:$KB_PATH" command "$BIN"
gsettings set "$KB_SCHEMA.custom-keybinding:$KB_PATH" binding "$KEY"

# 6. Tray support
if gnome-extensions info "$APPIND" &>/dev/null; then
  gnome-extensions enable "$APPIND" || true
  tray_note=""
else
  tray_note="(Log out and back in once so GNOME picks up the tray extension, then re-run this script.)"
fi

# 7. (Re)start in the tray
"$BIN" --quit 2>/dev/null || true
setsid -f "$BIN" --tray >/dev/null 2>&1

say "Done. Press $KEY to start. $tray_note"
