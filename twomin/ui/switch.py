"""A small on/off switch: a QCheckBox underneath (same signals, keys and API), painted as a
sliding pill. The knob slides when toggled — motion that answers the person's action."""
from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QCheckBox

from .style import INK, LINE, MUTED, RAISED, TEXT

TRACK_W, TRACK_H, GAP = 32, 18, 8


class Switch(QCheckBox):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 0.0                                 # 0 = off, 1 = on (animated)
        self._anim = QPropertyAnimation(self, b"knob", self, duration=140,
                                        easingCurve=QEasingCurve.OutCubic)
        self.toggled.connect(self._slide)

    # ---- animated knob position
    def _get_knob(self) -> float:
        return self._pos

    def _set_knob(self, value: float) -> None:
        self._pos = value
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def _slide(self, on: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def setChecked(self, on: bool) -> None:            # programmatic: jump, don't slide
        super().setChecked(on)
        self._anim.stop()
        self._pos = 1.0 if on else 0.0
        self.update()

    # ---- size / hit area: the whole thing (switch + label) is clickable
    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        return QSize(TRACK_W + GAP + fm.horizontalAdvance(self.text()) + 2,
                     max(TRACK_H, fm.height()) + 4)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def hitButton(self, pos) -> bool:
        return self.rect().contains(pos)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        y = (self.height() - TRACK_H) / 2
        track = QRectF(0.5, y + 0.5, TRACK_W - 1, TRACK_H - 1)
        on = self._pos
        # Track: dark and outlined when off, light when on (blended while sliding).
        off_c, on_c = QColor(RAISED), QColor(TEXT)
        fill = QColor(
            int(off_c.red() + (on_c.red() - off_c.red()) * on),
            int(off_c.green() + (on_c.green() - off_c.green()) * on),
            int(off_c.blue() + (on_c.blue() - off_c.blue()) * on))
        p.setPen(QPen(QColor(LINE if on < 0.5 else TEXT), 1))
        p.setBrush(fill)
        p.drawRoundedRect(track, TRACK_H / 2, TRACK_H / 2)
        # Knob
        d = TRACK_H - 6
        x = 3 + (TRACK_W - 6 - d) * on
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(INK if on >= 0.5 else MUTED))
        p.drawEllipse(QRectF(x, y + 3, d, d))
        # Label
        p.setPen(QColor(TEXT if self.isChecked() else MUTED))
        p.setFont(self.font())
        p.drawText(QRectF(TRACK_W + GAP, 0, self.width() - TRACK_W - GAP, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, self.text())
        p.end()
