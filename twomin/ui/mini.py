"""Small, frameless, always-on-top timer: countdown → finish choices → optional focus mode.

Views (one QStackedWidget):
  RUN     the two-minute countdown; in focus mode the same view counts *up*, silently
  FINISH  after the beep: time keeps counting while you choose (or ignore it)
          keep going / +2 min / stop / whole task done
  UNDO    a few seconds after "done", so a stray press can be taken back

Stop and done need Shift (⇧S, ⇧D): the timer pops up at the beep, and a plain letter typed
into another window must never end a session by accident.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame, QLabel, QLineEdit, QProgressBar, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from ..core.models import DONE, EARLY, STOPPED
from ..core.timer import Countdown
from .style import FLOW_QSS, keys

RUN, FINISH, UNDO = 0, 1, 2
UNDO_MS = 5000
FLASH_MS = 1800


def _lab(text: str, name: str, wrap: bool = True) -> QLabel:
    lab = QLabel(text, objectName=name)
    lab.setWordWrap(wrap)
    if name == "keys":
        lab.setTextFormat(Qt.RichText)
    return lab


def _btn(text: str, name: str = "", slot=None) -> QPushButton:
    b = QPushButton(text, objectName=name)
    b.setFocusPolicy(Qt.NoFocus)        # keys always go to the timer itself
    if slot:
        b.clicked.connect(slot)
    return b


class MiniTimer(QWidget):
    beeped = Signal()
    note = Signal(str)
    finished = Signal(str, float, int, float)  # outcome, seconds, extra rounds/flow, flow seconds

    def __init__(self, title: str, steps: list[str], seconds: int = 120,
                 week: str = "1 start this week"):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Two-Minute Start — timer")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFixedWidth(340)
        self.clock = Countdown(seconds)
        self.round_seconds = seconds
        self.focus_mode = False          # after "keep going": flow. Count up, never beep again
        self._flow_from = 0.0
        self._beeped = False
        self._ending = False
        self._before_undo = RUN
        self._drag: QPoint | None = None

        card = QFrame(objectName="card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)
        self.stack = QStackedWidget()
        QVBoxLayout(card).addWidget(self.stack)

        # --- RUN: countdown, or silent count-up in focus mode
        run = QWidget()
        rl = QVBoxLayout(run)
        rl.setContentsMargins(4, 2, 4, 2)
        self.flash = _lab("Started ✓", "win")      # the win is pressing Enter: say so at once
        rl.addWidget(self.flash)
        rl.addWidget(_lab(title, "task"))
        rl.addWidget(_lab(steps[0], "step"))
        if len(steps) > 1:
            rl.addWidget(_lab("then: " + "  →  ".join(steps[1:]), "muted"))
        self.time_lab = QLabel(objectName="clock")
        self.time_lab.setAlignment(Qt.AlignCenter)
        rl.addWidget(self.time_lab)
        self.flow_lab = _lab("✦ in the flow · stop whenever you like", "flow")
        self.flow_lab.setAlignment(Qt.AlignCenter)
        self.flow_lab.hide()
        rl.addWidget(self.flow_lab)
        self.bar = QProgressBar(textVisible=False, maximum=1000)
        rl.addWidget(self.bar)
        self.pad = QLineEdit(placeholderText="Offload it here, Enter to save")
        self.pad.hide()
        self.pad.returnPressed.connect(self._save_note)
        rl.addWidget(self.pad)
        self.saved = _lab("", "hint")
        rl.addWidget(self.saved)
        rl.addWidget(_btn("Stop ✓   ⇧S", "stop", self._stop))
        rl.addWidget(_btn("Whole task done ✓   ⇧D", "good", self._done))
        rl.addWidget(_lab(keys(("N", "note"), ("Esc", "stop, still counts"), ("drag", "move")), "keys"))
        self.week_lab = _lab(week, "meta")
        rl.addWidget(self.week_lab)

        # --- FINISH: after the beep. The clock keeps counting here.
        fin = QWidget()
        fl = QVBoxLayout(fin)
        fl.addWidget(_lab("You started. ✓", "win"))
        fl.addWidget(_lab(f"That's {week}. Stopping now is a win; "
                          "keep going only if you want to.", "muted"))
        self.over_lab = _lab("", "step")
        self.over_lab.setAlignment(Qt.AlignCenter)
        fl.addWidget(self.over_lab)
        fl.addWidget(_btn("✦ Keep going   ⏎", "flow", self._keep_going))
        rnd = f"{seconds // 60} min" if seconds % 60 == 0 else Countdown.fmt(seconds)
        fl.addWidget(_btn(f"+{rnd}   2", "round", self._another_round))
        fl.addWidget(_btn("Stop here ✓   ⇧S", "stop", self._stop))
        fl.addWidget(_btn("Whole task done ✓   ⇧D", "good", self._done))
        fl.addWidget(_lab(keys(("⏎", "keep going, no more beeps"), ("2", "another round")), "keys"))

        # --- UNDO: a short grace period after "done"
        und = QWidget()
        ul = QVBoxLayout(und)
        ul.addWidget(_lab("Started and finished ✓", "win"))
        ul.addWidget(_lab(f"Whole task done. {week}.", "muted"))
        ul.addWidget(_btn("Undo   U", slot=self._undo))
        ul.addWidget(_lab(keys(("U", "undo"), ("⏎", "close now")) + "&nbsp;&nbsp;&nbsp;&nbsp;closes in a moment", "keys"))
        self.undo_timer = QTimer(self, singleShot=True, interval=UNDO_MS,
                                 timeout=lambda: self._finish(DONE))

        for w in (run, fin, und):
            self.stack.addWidget(w)
        self.setFocusPolicy(Qt.StrongFocus)
        self.ticker = QTimer(self, interval=200, timeout=self._tick)

    # ---- lifecycle
    def begin(self) -> None:
        self.clock.start()
        self.ticker.start()
        self._tick()
        QTimer.singleShot(FLASH_MS, self, self._hide_flash)   # context: safe if closed first
        self._resize()
        geo = QGuiApplication.primaryScreen().availableGeometry()
        self.move(geo.right() - self.width() - 24, geo.bottom() - self.height() - 24)
        self.show()
        self.bring_forward()

    def bring_forward(self) -> None:
        """Raise and take keyboard focus: only when the person asked (start, hotkey)."""
        self.raise_()
        self.activateWindow()

    def _resize(self) -> None:
        # Keep the bottom edge where it is, so the window grows/shrinks upwards in its corner.
        bottom = self.geometry().bottom() if self.isVisible() else None
        self.adjustSize()
        if bottom is not None:
            self.move(self.x(), bottom - self.height() + 1)

    def _hide_flash(self) -> None:
        self.flash.hide()
        self._resize()

    def _tick(self) -> None:
        view = self.stack.currentIndex()
        if view == UNDO:
            return                                  # paused on screen; time still runs
        if view == FINISH:
            self.over_lab.setText(f"{Countdown.fmt(self.clock.elapsed())} so far · still counting")
            return
        if self.focus_mode:
            self.time_lab.setText(Countdown.fmt(self.clock.elapsed()))
            return
        self.time_lab.setText(Countdown.fmt(self.clock.remaining()))
        self.bar.setValue(int(self.clock.fraction_left() * 1000))
        if self.clock.finished() and not self._beeped:
            self._beeped = True
            self._show(FINISH)
            self._tick()
            self.raise_()          # visible, but don't steal focus from what you're typing in
            self.beeped.emit()

    def _show(self, view: int) -> None:
        self.stack.setCurrentIndex(view)
        self._resize()

    # ---- keys (single letters live here, not in QShortcut, so the notepad can type them)
    def keyPressEvent(self, e):
        if self._ending:
            return
        k, view = e.key(), self.stack.currentIndex()
        shift = bool(e.modifiers() & Qt.ShiftModifier)
        enter = k in (Qt.Key_Return, Qt.Key_Enter)
        if view == UNDO:
            if k == Qt.Key_U:
                self._undo()
            elif enter or k == Qt.Key_Escape or (shift and k == Qt.Key_D):
                self._finish(DONE)
        elif k == Qt.Key_Escape:
            self._escape()
        elif shift and k == Qt.Key_D:
            self._done()
        elif shift and k == Qt.Key_S:
            self._stop()
        elif view == RUN and k == Qt.Key_N:
            self._open_pad()
        elif view == FINISH and enter:
            self._keep_going()
        elif view == FINISH and k in (Qt.Key_2, Qt.Key_Plus, Qt.Key_Equal):
            self._another_round()
        else:
            super().keyPressEvent(e)

    # ---- actions
    def _keep_going(self) -> None:
        """Flow: a quiet count-up in purple. No more beeps; stop whenever."""
        self.focus_mode = True
        self._flow_from = self.clock.elapsed()
        self.setStyleSheet(FLOW_QSS)             # the whole window turns purple
        self.bar.hide()
        self.flow_lab.show()
        self._show(RUN)
        self.setFocus()
        self._tick()

    def _another_round(self) -> None:
        """+2 min: another countdown from now, with a beep at the end."""
        self.clock.extend(self.round_seconds)
        self._beeped = False
        self._show(RUN)
        self.setFocus()
        self._tick()

    def _stop(self) -> None:
        early = (self.stack.currentIndex() == RUN and not self.focus_mode
                 and not self._beeped and self.clock.extensions == 0)
        self._finish(EARLY if early else STOPPED)

    def _escape(self) -> None:
        if self.pad.isVisible():
            self.pad.clear()
            self.pad.hide()
            self._resize()
            self.setFocus()
        else:
            self._stop()

    def _done(self) -> None:
        if self.stack.currentIndex() == UNDO:
            return
        self._before_undo = self.stack.currentIndex()
        self.pad.hide()
        self._show(UNDO)
        self.setFocus()
        self.undo_timer.start()

    def _undo(self) -> None:
        self.undo_timer.stop()
        self._show(self._before_undo)
        self.setFocus()
        self._tick()

    def _open_pad(self) -> None:
        self.pad.show()
        self._resize()
        self.pad.setFocus()

    def _save_note(self) -> None:
        text = self.pad.text().strip()
        if text:
            self.note.emit(text)
            self.saved.setText(f"saved: {text}")
        self.pad.clear()
        self.pad.hide()
        self._resize()
        self.setFocus()

    def _finish(self, outcome: str) -> None:
        # Deferred so we never close (and delete) the window from inside its own key or
        # click handling; doing that segfaulted under IBus. The guard stops a double press.
        if self._ending:
            return
        self._ending = True
        self.ticker.stop()
        self.undo_timer.stop()
        elapsed = self.clock.elapsed()
        flow = elapsed - self._flow_from if self.focus_mode else 0.0
        result = (outcome, elapsed, self.clock.extensions + int(self.focus_mode), flow)

        def done() -> None:
            self.finished.emit(*result)
            self.close()
        QTimer.singleShot(0, done)

    # ---- frameless drag
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None
