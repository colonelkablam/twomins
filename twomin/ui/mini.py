"""Small, frameless, always-on-top countdown with a sticky pad and the finish choices."""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from ..core.models import DONE, EARLY, STOPPED
from ..core.timer import Countdown


class MiniTimer(QWidget):
    beeped = Signal()
    note = Signal(str)
    finished = Signal(str, float, int)  # outcome, seconds, extensions

    def __init__(self, title: str, steps: list[str], seconds: int = 120):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Two-Minute Start — timer")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFixedWidth(340)
        self.clock = Countdown(seconds)
        self.step_seconds = seconds
        self._beeped = False
        self._drag: QPoint | None = None

        card = QFrame(objectName="card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)
        self.stack = QStackedWidget()
        QVBoxLayout(card).addWidget(self.stack)

        # --- running view
        run = QWidget()
        rl = QVBoxLayout(run)
        rl.setContentsMargins(4, 2, 4, 2)
        t = QLabel(title, objectName="task")
        t.setWordWrap(True)
        rl.addWidget(t)
        s = QLabel(steps[0], objectName="step")
        s.setWordWrap(True)
        rl.addWidget(s)
        if len(steps) > 1:
            more = QLabel("then: " + "  →  ".join(steps[1:]), objectName="muted")
            more.setWordWrap(True)
            rl.addWidget(more)
        self.time_lab = QLabel(objectName="clock")
        self.time_lab.setAlignment(Qt.AlignCenter)
        rl.addWidget(self.time_lab)
        self.bar = QProgressBar(textVisible=False, maximum=1000)
        rl.addWidget(self.bar)
        self.pad = QLineEdit(placeholderText="Offload it here, Enter to save")
        self.pad.hide()
        self.pad.returnPressed.connect(self._save_note)
        rl.addWidget(self.pad)
        self.saved = QLabel("", objectName="hint")
        rl.addWidget(self.saved)
        rl.addWidget(QLabel("N note  ·  Esc stop (still counts)  ·  drag to move", objectName="hint"))

        # --- finish view
        fin = QWidget()
        fl = QVBoxLayout(fin)
        fl.addWidget(QLabel("You started. ✓", objectName="win"))
        msg = QLabel("Stopping now is a win. Keep going only if you want to.", objectName="muted")
        msg.setWordWrap(True)
        fl.addWidget(msg)
        self.keep = QPushButton(f"Keep going +{Countdown.fmt(seconds)}   ⏎", objectName="primary")
        self.stop = QPushButton("Stop here ✓   S")
        self.done = QPushButton("Whole task done ✓   D", objectName="good")
        for b in (self.keep, self.stop, self.done):
            fl.addWidget(b)
        self.keep.clicked.connect(self._keep_going)
        self.stop.clicked.connect(lambda: self._finish(STOPPED))
        self.done.clicked.connect(lambda: self._finish(DONE))

        self.stack.addWidget(run)
        self.stack.addWidget(fin)

        self.setFocusPolicy(Qt.StrongFocus)

        self.ticker = QTimer(self, interval=200, timeout=self._tick)

    # ---- lifecycle
    def begin(self) -> None:
        self.clock.start()
        self.ticker.start()
        self._tick()
        self.adjustSize()
        geo = QGuiApplication.primaryScreen().availableGeometry()
        self.move(geo.right() - self.width() - 24, geo.bottom() - self.height() - 24)
        self.show()
        self.bring_forward()

    def bring_forward(self) -> None:
        self.raise_()
        self.activateWindow()

    def _tick(self) -> None:
        self.time_lab.setText(Countdown.fmt(self.clock.remaining()))
        self.bar.setValue(int(self.clock.fraction_left() * 1000))
        if self.clock.finished() and not self._beeped:
            self._beeped = True
            self.ticker.stop()
            self.stack.setCurrentIndex(1)
            self.adjustSize()
            self.keep.setFocus()
            self.bring_forward()
            self.beeped.emit()

    def keyPressEvent(self, e):
        # Child widgets (the notepad) get keys first, so typing never triggers these.
        k, finished = e.key(), self.stack.currentIndex() == 1
        if k == Qt.Key_Escape:
            self._escape()
        elif k == Qt.Key_N and not finished:
            self._open_pad()
        elif finished and k in (Qt.Key_Return, Qt.Key_Enter):
            self._keep_going()
        elif finished and k == Qt.Key_S:
            self._finish(STOPPED)
        elif finished and k == Qt.Key_D:
            self._finish(DONE)
        else:
            super().keyPressEvent(e)

    # ---- actions
    def _keep_going(self) -> None:
        self.clock.extend(self.step_seconds)
        self._beeped = False
        self.stack.setCurrentIndex(0)
        self.adjustSize()
        self.ticker.start()
        self._tick()

    def _escape(self) -> None:
        if self.pad.isVisible():
            self.pad.clear()
            self.pad.hide()
            self.setFocus()
        elif self.stack.currentIndex() == 0:
            self._finish(EARLY if self.clock.extensions == 0 else STOPPED)
        else:
            self._finish(STOPPED)

    def _open_pad(self) -> None:
        if self.stack.currentIndex() == 0:
            self.pad.show()
            self.adjustSize()
            self.pad.setFocus()

    def _save_note(self) -> None:
        text = self.pad.text().strip()
        if text:
            self.note.emit(text)
            self.saved.setText(f"saved: {text}")
        self.pad.clear()
        self.pad.hide()
        self.adjustSize()
        self.setFocus()

    def _finish(self, outcome: str) -> None:
        self.ticker.stop()
        self.finished.emit(outcome, self.clock.elapsed(), self.clock.extensions)
        self.close()

    # ---- frameless drag
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None
