#!/usr/bin/env bash
# Check the installer on clean distros in throwaway containers (podman or docker).
# Runs: ./install.sh --no-desktop, the core tests, and a real X11 (xcb) launch of the popup
# under Xvfb. It can't check the hotkey, tray or focus: those need a real desktop.
#
#   scripts/test-distros.sh                 # all
#   scripts/test-distros.sh ubuntu:24.04    # one image
set -euo pipefail
cd "$(dirname "$0")/.."
ENGINE="$(command -v podman || command -v docker)"
if (($#)); then IMAGES=("$@"); else IMAGES=(ubuntu:24.04 fedora:44); fi

# Inside the container: copy the repo (minus .venv), add an X server for the smoke test only,
# install, test, launch.
read -r -d '' INSIDE <<'SH' || true
set -euo pipefail
mkdir -p /work && cd /src && tar --exclude=.venv --exclude=__pycache__ --exclude=.git -cf - . | tar -xf - -C /work
cd /work
if command -v apt-get >/dev/null; then
  apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq xvfb >/dev/null
else
  dnf install -y -q xorg-x11-server-Xvfb >/dev/null
fi
./install.sh --no-desktop
.venv/bin/python tests/test_core.py
echo "--- Qt xcb plugin: missing libraries (should be none)"
ldd .venv/lib/python3*/site-packages/PySide6/Qt/plugins/platforms/libqxcb.so | grep "not found" || echo "none"
Xvfb :99 -screen 0 1280x800x24 >/dev/null 2>&1 & sleep 2
DISPLAY=:99 QT_QPA_PLATFORM=xcb .venv/bin/python - <<'PY'
from PySide6.QtWidgets import QApplication
from twomin.core.store import Store
from twomin.ui.popup import Popup
from twomin.ui.style import QSS, load_fonts
app = QApplication([]); load_fonts(); app.setStyleSheet(QSS)
p = Popup(Store(":memory:")); p.present(); app.processEvents()
print("xcb launch ok:", p.isVisible(), app.platformName())
PY
SH

fail=0
for img in "${IMAGES[@]}"; do
  echo "=================== $img"
  if "$ENGINE" run --rm -v "$PWD:/src:ro,Z" "$img" bash -c "$INSIDE"; then
    echo "PASS $img"
  else
    echo "FAIL $img"; fail=1
  fi
done
exit $fail
