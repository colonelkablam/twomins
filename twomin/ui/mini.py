"""Small, frameless, always-on-top timer: countdown → finish choices → optional focus mode.

Views (one QStackedWidget):
  RUN     the two-minute countdown; in focus mode the same view counts *up*, silently
  FINISH  after the beep: keep going / stop here / whole task done
  UNDO    a few seconds after "done", so a stray D can be taken back
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame, QLabel, QLineEdit, QProgressBar, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from ..core.models import DONE, EARLY, STOPPED
from ..core.timer import Countdown

RUN, FINISH, UNDO = 0, 1, 2
UNDO_MS = 5000
FLASH_MS = 1800


def _starts(n: int) -> str:
    return f"{n} start{'s' * (n != 1)} this week"


def _lab(text: str, name: str, wrap: bool = True) -> QLabel:
    lab = QLabel(text, objectName=name)
    lab.setWordWrap(wrap)
    return lab


class MiniTimer(QWidget):
    beeped = Signal()
    note = Signal(str)
    finished = Signal(str, float, int)  # outcome, seconds, kept_going (0/1)

    def __init__(self, title: str, steps: list[str], seconds: int = 120, starts_week: int = 1):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Two-Minute Start — timer")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFixedWidth(340)
        self.clock = Countdown(seconds)
        self.focus_mode = False          # after "keep going": count up, never beep again
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
        self.flow_lab = _lab("in the flow · stop whenever you like", "muted")
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
        done_run = QPushButton("Whole task done ✓   D", objectName="good")
        done_run.setFocusPolicy(Qt.NoFocus)          # keep keys on the timer, not the button
        done_run.clicked.connect(lambda: self._done())
        rl.addWidget(done_run)
        self.run_hint = _lab("N note  ·  D done  ·  Esc stop (still counts)  ·  drag", "hint")
        rl.addWidget(self.run_hint)
        self.week_lab = _lab(_starts(starts_week), "hint")
        rl.addWidget(self.week_lab)

        # --- FINISH: after the beep
        fin = QWidget()
        fl = QVBoxLayout(fin)
        fl.addWidget(_lab("You started. ✓", "win"))
        fl.addWidget(_lab(f"That's {_starts(starts_week)}. Stopping now is a win; "
                          "keep going only if you want to.", "muted"))
        self.keep = QPushButton("Keep going   ⏎", objectName="primary")
        self.stop = QPushButton("Stop here ✓   S")
        self.done_btn = QPushButton("Whole task done ✓   D", objectName="good")
        for b in (self.keep, self.stop, self.done_btn):
            fl.addWidget(b)
        self.keep.clicked.connect(self._keep_going)
        self.stop.clicked.connect(lambda: self._finish(STOPPED))
        self.done_btn.clicked.connect(lambda: self._done())

        # --- UNDO: a short grace period after "done"
        und = QWidget()
        ul = QVBoxLayout(und)
        ul.addWidget(_lab("Started and finished ✓", "win"))
        ul.addWidget(_lab(f"Whole task done. {_starts(starts_week)}.", "muted"))
        undo = QPushButton("Undo   U")
        undo.clicked.connect(self._undo)
        ul.addWidget(undo)
        ul.addWidget(_lab("Closes in a moment  ·  U undo  ·  Enter close now", "hint"))
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
        if self.stack.currentIndex() == UNDO:
            return                                  # paused on screen; time still runs
        if self.focus_mode:
            self.time_lab.setText(Countdown.fmt(self.clock.elapsed()))
            return
        self.time_lab.setText(Countdown.fmt(self.clock.remaining()))
        self.bar.setValue(int(self.clock.fraction_left() * 1000))
        if self.clock.finished() and not self._beeped:
            self._beeped = True
            self.ticker.stop()
            self._show(FINISH)
            self.keep.setFocus()
            self.bring_forward()
            self.beeped.emit()

    def _show(self, view: int) -> None:
        self.stack.setCurrentIndex(view)
        self._resize()

    # ---- keys (single letters live here, not in QShortcut, so the notepad can type them)
    def keyPressEvent(self, e):
        if self._ending:
            return
        k, view = e.key(), self.stack.currentIndex()
        enter = k in (Qt.Key_Return, Qt.Key_Enter)
        if view == UNDO:
            if k == Qt.Key_U:
                self._undo()
            elif enter or k in (Qt.Key_Escape, Qt.Key_D):
                self._finish(DONE)
        elif k == Qt.Key_Escape:
            self._escape()
        elif k == Qt.Key_D:                         # whole task done: any time
            self._done()
        elif view == RUN and k == Qt.Key_N:
            self._open_pad()
        elif view == RUN and k == Qt.Key_S and self.focus_mode:
            self._finish(STOPPED)
        elif view == FINISH and enter:
            self._keep_going()
        elif view == FINISH and k == Qt.Key_S:
            self._finish(STOPPED)
        else:
            super().keyPressEvent(e)

    # ---- actions
    def _keep_going(self) -> None:
        """Focus mode: switch to a quiet count-up. No more beeps; stop whenever."""
        self.focus_mode = True
        self.bar.hide()
        self.flow_lab.show()
        self.run_hint.setText("N note  ·  S or Esc stop ✓  ·  D done  ·  drag")
        self._show(RUN)
        self.setFocus()
        self.ticker.start()
        self._tick()

    def _escape(self) -> None:
        if self.pad.isVisible():
            self.pad.clear()
            self.pad.hide()
            self._resize()
            self.setFocus()
        elif self.stack.currentIndex() == RUN and not self.focus_mode:
            self._finish(EARLY)
        else:
            self._finish(STOPPED)

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
        result = (outcome, self.clock.elapsed(), int(self.focus_mode))

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
