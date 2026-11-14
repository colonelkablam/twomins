"""Settings: kept out of the start flow. For now, one job: reset all data, safely.

Reset always writes a backup copy first, and only unlocks after typing "clear data".
Window-modal (open(), not exec()) and never closed from inside its own handlers.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from ..core.store import Store

CONFIRM = "clear data"


def _tidy(path) -> str:
    """Show paths under your home folder as ~/…"""
    p, home = str(path), str(Path.home())
    return "~" + p[len(home):] if p.startswith(home) else p


def _lab(text: str, name: str) -> QLabel:
    lab = QLabel(text, objectName=name)
    lab.setWordWrap(True)
    lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return lab


class Settings(QDialog):
    data_reset = Signal()

    def __init__(self, store: Store, parent=None):
        super().__init__(parent, Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("twomins settings")
        self.setMinimumWidth(460)
        self.store = store

        self.confirm = QLineEdit(placeholderText=f"type {CONFIRM}")
        self.reset_btn = QPushButton("Reset all data", objectName="danger")
        self.reset_btn.setEnabled(False)
        self.result = _lab("", "meta")
        self.result.hide()
        close = QPushButton("Close", objectName="quiet")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 18)
        lay.setSpacing(8)
        lay.addWidget(_lab("Settings", "hero"))
        lay.addSpacing(6)
        lay.addWidget(_lab("Your data", "prompt"))
        lay.addWidget(_lab(_tidy(store.path), "meta"))
        lay.addSpacing(10)
        lay.addWidget(_lab("Reset all data", "prompt"))
        lay.addWidget(_lab(
            "Deletes every task, start, note and flow. twomins starts again empty. "
            f"A backup copy is saved first, to {_tidy(store.backup_dir())}.", "meta"))
        lay.addWidget(_lab(f"Type “{CONFIRM}” to unlock the button.", "meta"))
        row = QHBoxLayout()
        row.addWidget(self.confirm, 1)
        row.addWidget(self.reset_btn)
        lay.addLayout(row)
        lay.addWidget(self.result)
        lay.addStretch(1)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(close)
        lay.addLayout(bottom)

        self.confirm.textChanged.connect(
            lambda t: self.reset_btn.setEnabled(t.strip().lower() == CONFIRM))
        self.confirm.returnPressed.connect(lambda: QTimer.singleShot(0, self._reset))
        self.reset_btn.clicked.connect(lambda: QTimer.singleShot(0, self._reset))
        close.clicked.connect(lambda: QTimer.singleShot(0, self.accept))

    def _reset(self) -> None:
        if self.confirm.text().strip().lower() != CONFIRM:
            return
        backup = self.store.reset()
        self.confirm.clear()
        self.result.setText(f"All data cleared. Backup saved: {_tidy(backup)}")
        self.result.show()
        self.data_reset.emit()
