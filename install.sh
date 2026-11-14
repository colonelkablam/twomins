#!/usr/bin/env bash
# twomins installer. Supported: Fedora and Ubuntu (24.04+), GNOME desktop (Wayland or X11).
# Other distros/desktops: it does what it safely can and prints the rest as manual steps.
#
#   ./install.sh                 full install (packages, venv, menu, autostart, Super+T, tray)
#   ./install.sh --no-desktop    packages + venv only (used by scripts/test-distros.sh)
#   TWOMIN_KEY='<Super><Shift>t' ./install.sh    a different hotkey
#
# Re-run any time; it's idempotent. To add a distro: a case in detect_distro() and a
# pkgs_<family>/installed_<family>/install_<family> trio. To add a desktop: a case in setup_desktop().
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
KEY="${TWOMIN_KEY:-<Super>t}"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/scalable/apps"
AUTOSTART="$HOME/.config/autostart"
BIN="$DIR/.venv/bin/twomin"
DESKTOP=1
[[ "${1:-}" == "--no-desktop" ]] && DESKTOP=0

say()  { printf '\033[1;33m==>\033[0m %s\n' "$*"; }
note() { printf '\033[1;36m   ·\033[0m %s\n' "$*"; }
SUDO=""; [[ $EUID -ne 0 ]] && SUDO="sudo"
MANUAL=()   # steps we couldn't do automatically, printed at the end

# ---------------------------------------------------------------- distro: system packages
# What the app needs from the system (Qt itself comes from pip):
#   Qt's X11/XWayland plugin libraries (xcb-cursor is the one desktops usually lack; the rest
#   are normally there already, so listing them is a no-op on a desktop and fills gaps on a
#   minimal install), notify-send, an audio player for the chime, and Python's venv module.
pkgs_fedora()      { echo python3 xcb-util-cursor xcb-util-wm xcb-util-keysyms libxkbcommon-x11 \
                          mesa-libEGL fontconfig libnotify pipewire-utils; }
installed_fedora() { rpm -q "$1" &>/dev/null; }
install_fedora()   { $SUDO dnf install -y "$@"; }

pkgs_debian()      { echo python3-venv libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 \
                          libxcb-keysyms1 libxcb-shape0 libxcb-xkb1 libegl1 libfontconfig1 \
                          libnotify-bin pulseaudio-utils; }
installed_debian() { dpkg -s "$1" &>/dev/null; }
install_debian()   { $SUDO apt-get update -qq && $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"; }

detect_distro() {
  local id="" like=""
  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release; id="${ID:-}"; like="${ID_LIKE:-}"
  fi
  case " $id $like " in
    *" fedora "*)                 echo fedora ;;
    *" ubuntu "*|*" debian "*)    echo debian ;;
    *)                            echo unknown ;;
  esac
}

install_packages() {
  local family; family="$(detect_distro)"
  if [[ $family == unknown ]]; then
    say "Unrecognised distro: skipping system packages"
    MANUAL+=("Install with your package manager: Python 3.11+ with venv, libxcb-cursor (Qt's xcb cursor library), notify-send, and pw-play or paplay.")
    return
  fi
  local need=() p
  for p in $("pkgs_$family"); do "installed_$family" "$p" || need+=("$p"); done
  # GNOME on Fedora needs the tray extension as a package; Ubuntu ships its own, enabled.
  if [[ $family == fedora && $DESKTOP == 1 ]] && is_gnome; then
    installed_fedora gnome-shell-extension-appindicator || need+=(gnome-shell-extension-appindicator)
  fi
  if ((${#need[@]})); then
    say "Installing ($family): ${need[*]}"
    "install_$family" "${need[@]}"
  fi
}

check_python() {
  python3 - <<'PY' || { echo "twomins needs Python 3.11 or newer (Ubuntu 24.04+, Fedora 38+)." >&2; exit 1; }
import sys; sys.exit(sys.version_info < (3, 11))
PY
}

# ---------------------------------------------------------------- app: venv (same everywhere)
setup_venv() {
  say "Setting up venv"
  [[ -d "$DIR/.venv" ]] || python3 -m venv "$DIR/.venv"
  "$DIR/.venv/bin/pip" install -q --upgrade pip
  "$DIR/.venv/bin/pip" install -q -e "$DIR"      # editable: code changes apply on next launch
}

# ---------------------------------------------------------------- freedesktop standards
# Menu entry and autostart are standard .desktop files: every desktop reads them.
setup_menu_and_autostart() {
  say "Adding app-menu entry and autostart"
  mkdir -p "$APPS" "$ICONS" "$AUTOSTART"
  cp "$DIR/twomin/assets/icon.svg" "$ICONS/twomin.svg"
  cat > "$APPS/twomin.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=twomins
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
  sed -e "s|^Exec=.*|Exec=$BIN --tray|" "$APPS/twomin.desktop" > "$AUTOSTART/twomin.desktop"
  echo "X-GNOME-Autostart-enabled=true" >> "$AUTOSTART/twomin.desktop"
}

# ---------------------------------------------------------------- desktop: hotkey + tray
is_gnome() { [[ ":${XDG_CURRENT_DESKTOP:-}:" == *:GNOME:* ]]; }   # Ubuntu reports ubuntu:GNOME

gnome_hotkey() {
  local schema="org.gnome.settings-daemon.plugins.media-keys"
  local path="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/twomin/"
  say "Binding $KEY"
  local current updated
  current="$(gsettings get "$schema" custom-keybindings)"
  updated="$(python3 - "$current" "$path" <<'PY'
import ast, sys
cur, path = sys.argv[1].replace("@as ", ""), sys.argv[2]
paths = ast.literal_eval(cur)
if path not in paths:
    paths.append(path)
print(str(paths))
PY
)"
  gsettings set "$schema" custom-keybindings "$updated"
  gsettings set "$schema.custom-keybinding:$path" name "twomins"
  gsettings set "$schema.custom-keybinding:$path" command "$BIN"
  gsettings set "$schema.custom-keybinding:$path" binding "$KEY"
}

gnome_tray() {
  # Fedora: the package installed above. Ubuntu: its own built-in copy, normally already on.
  local uuid
  for uuid in ubuntu-appindicators@ubuntu.com appindicatorsupport@rgcjonas.gmail.com; do
    if gnome-extensions info "$uuid" &>/dev/null; then
      gnome-extensions enable "$uuid" 2>/dev/null || true
      return
    fi
  done
  MANUAL+=("Log out and back in once so GNOME loads the tray extension, then run ./install.sh again.")
}

setup_desktop() {
  case ":${XDG_CURRENT_DESKTOP:-}:" in
    *:GNOME:*)
      gnome_hotkey
      gnome_tray ;;
    *)
      say "Desktop '${XDG_CURRENT_DESKTOP:-unknown}': hotkey not set automatically"
      MANUAL+=("Add a keyboard shortcut (e.g. Super+T) in your desktop's settings that runs: $BIN") ;;
  esac
}

# ---------------------------------------------------------------- run
command -v python3 >/dev/null && check_python    # fail early, before installing anything
install_packages
check_python
setup_venv
if [[ $DESKTOP == 1 ]]; then
  setup_menu_and_autostart
  setup_desktop
  "$BIN" --quit 2>/dev/null || true
  setsid -f "$BIN" --tray >/dev/null 2>&1
fi

if ((${#MANUAL[@]})); then
  say "Nearly done. By hand:"
  for m in "${MANUAL[@]}"; do note "$m"; done
fi
if [[ $DESKTOP == 1 ]]; then
  say "Done. Press $KEY to start."
else
  say "Done (no desktop setup). Run: $BIN"
fi
