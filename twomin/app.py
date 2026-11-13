"""Wires store + popup + mini timer + tray. The 'instance' process owns timers."""
from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import notify
from .core.models import DONE, EARLY, STOPPED
from .core.store import Store
from .ui.mini import MiniTimer
from .ui.popup import Popup


class Controller(QObject):
    def __init__(self, app: QApplication, store: Store, seconds: int = 120,
                 tray: bool = True, resident: bool = False):
        super().__init__()
        self.resident = resident  # --tray: stay running even with no tray icon
        self.app = app
        self.store = store
        self.seconds = seconds
        self.mini: MiniTimer | None = None
        self.popup: Popup | None = None
        self.session_id: int | None = None
        self.tray = self._make_tray() if tray else None
        self._refresh_stats()

    # ---- state the IPC layer asks about
    @property
    def busy(self) -> bool:
        return self.mini is not None

    def keep_alive(self) -> bool:
        return self.busy or self.resident or (self.tray is not None and self.tray.isVisible())

    # ---- popup (only used when this process is the one the hotkey launched)
    def show_popup(self, on_start=None) -> None:
        if self.busy:
            return self.mini.bring_forward()
        if self.popup is None:
            self.popup = Popup(self.store, self.seconds)
            self.popup.start.connect(on_start or self.start)
            self.popup.closed.connect(self._popup_closed)
        self.popup.present()

    def _popup_closed(self) -> None:
        self.popup = None
        if not self.keep_alive():
            self.app.quit()

    # ---- timer
    def start(self, task_id: int, title: str, steps: list[str]) -> None:
        if self.busy:
            return self.mini.bring_forward()
        self.session_id = self.store.start_session(task_id, steps).id
        self.mini = MiniTimer(title, steps, self.seconds, week=week_text(self.store))
        self._refresh_stats()
        self.mini.note.connect(lambda text: self.store.add_note(task_id, self.session_id, text))
        self.mini.beeped.connect(self._beep)
        self.mini.finished.connect(self._finished)
        self.mini.begin()

    def _beep(self) -> None:
        notify.chime()
        notify.desktop("Two minutes — you started ✓", "Stop here, or keep going if you want to.")

    def _finished(self, outcome: str, seconds: float, extra: int, flow: float) -> None:
        self.store.end_session(self.session_id, seconds, extra, outcome, flow)
        self.mini = None
        self.session_id = None
        week = week_text(self.store) + "."
        flowed = f"✦ {_mins(flow)} in the flow. " if flow else ""
        # Every ending leads with the start; flow is a second reward, named when it happened.
        # The beep already said "you started" on a plain stop, so that one stays quiet.
        if outcome == DONE:
            notify.desktop("Started and finished ✓", flowed + week)
        elif outcome == EARLY:
            notify.desktop("Started ✓ That's the win.", f"Saved for next time. {week}")
        elif flow:
            notify.desktop("Started ✓ and found the flow ✦", flowed + week)
        elif extra:
            notify.desktop("Started ✓", f"You kept going for {_mins(seconds)}. {week}")
        self._refresh_stats()
        if not self.keep_alive():
            self.app.quit()

    # ---- tray (GNOME needs the AppIndicator extension; app works without it)
    def _make_tray(self) -> QSystemTrayIcon | None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        tray = QSystemTrayIcon(QIcon(str(notify.ICON)), self)
        tray.setToolTip("twomins")
        menu = QMenu()
        go = QAction("Start twomins", menu, triggered=lambda: self.show_popup())
        self._stats = QAction("", menu, enabled=False)
        quit_ = QAction("Quit", menu, triggered=self.app.quit)
        menu.addAction(go)
        menu.addSeparator()
        menu.addAction(self._stats)
        menu.addSeparator()
        menu.addAction(quit_)
        menu.aboutToShow.connect(self._refresh_stats)
        tray.setContextMenu(menu)
        tray.activated.connect(
            lambda r: self.show_popup() if r == QSystemTrayIcon.Trigger else None)
        self._menu = menu  # keep a reference
        tray.show()
        return tray

    def _refresh_stats(self) -> None:
        if self.tray is None and not hasattr(self, "_stats"):
            return
        text = week_text(self.store)
        self._stats.setText(text)
        if self.tray is not None:
            self.tray.setToolTip(f"twomins · {text}")


def week_text(store: Store) -> str:
    """'5 starts · 2 flows this week': both rewards, counted up, never a ratio."""
    n = store.starts_since(7)
    f, _ = store.flows_since(7)
    flows = f" · {f} flow{'s' * (f != 1)}" if f else ""
    return f"{n} start{'s' * (n != 1)}{flows} this week"


def _mins(seconds: float) -> str:
    m = int(seconds // 60)
    return f"{m} min" if m else "under a minute"
