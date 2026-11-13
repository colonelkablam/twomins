"""Sound + desktop notification. Fire-and-forget; failures are silent."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ASSETS = Path(__file__).parent / "assets"
CHIME = ASSETS / "chime.wav"
ICON = ASSETS / "icon.svg"


def _spawn(cmd: list[str]) -> None:
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def chime() -> None:
    for player in ("pw-play", "paplay", "aplay"):
        if shutil.which(player):
            return _spawn([player, str(CHIME)])


def desktop(title: str, body: str = "") -> None:
    if shutil.which("notify-send"):
        _spawn(["notify-send", "--app-name=twomins", "-i", str(ICON), title, body])
