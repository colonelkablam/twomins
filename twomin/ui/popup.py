"""The hotkey popup: pick/capture a task, then shrink it to one physical action.

Emits `start(task_id, title, steps)` and `closed()`. Knows nothing about timers.
"""
from __future__ import annotations

import random

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from ..core.models import Task
from ..core.store import Store


def _label(text: str, name: str = "", wrap: bool = True) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


class PickPage(QWidget):
    chosen = Signal(object)  # Task

    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self.tasks: list[Task] = []

        self.edit = QLineEdit(placeholderText="Type it messy — the whole blurry pile is fine")
        self.list = QListWidget()
        self.list.setFocusPolicy(Qt.StrongFocus)

        lay = QVBoxLayout(self)
        lay.addWidget(_label("What are you avoiding?", "title"))
        lay.addWidget(self.edit)
        lay.addWidget(_label("Or carry on with one you've started:", "muted"))
        lay.addWidget(self.list, 1)
        lay.addWidget(_label("Enter choose  ·  ↓ list  ·  Ctrl+R pick for me  ·  Esc close", "hint"))

        self.edit.textChanged.connect(self._filter)
        self.edit.returnPressed.connect(self._enter_from_edit)
        self.list.itemActivated.connect(lambda it: self._choose(it.data(Qt.UserRole)))
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self._random)
        self.edit.installEventFilter(self)
        self.reload()

    def reload(self) -> None:
        self.tasks = self.store.open_tasks()
        self._filter(self.edit.text())

    def _filter(self, text: str) -> None:
        self.list.clear()
        needle = text.strip().lower()
        for t in self.tasks:
            if needle and needle not in t.title.lower():
                continue
            sub = f"last: {t.last_step}  ·  {t.starts} start{'s' * (t.starts != 1)}" if t.starts else "not started yet"
            it = QListWidgetItem(f"{t.title}\n    {sub}")
            it.setData(Qt.UserRole, t)
            self.list.addItem(it)
        if self.list.count():
            self.list.setCurrentRow(0)

    def eventFilter(self, obj, ev):  # ↓ from the text box jumps into the list
        if obj is self.edit and ev.type() == ev.Type.KeyPress and ev.key() == Qt.Key_Down:
            if self.list.count():
                self.list.setFocus()
                return True
        return super().eventFilter(obj, ev)

    def _enter_from_edit(self) -> None:
        text = self.edit.text().strip()
        if not text:
            it = self.list.currentItem()
            if it:
                self._choose(it.data(Qt.UserRole))
            return
        for t in self.tasks:  # exact match → reuse, don't duplicate
            if t.title.lower() == text.lower():
                return self._choose(t)
        self._choose(self.store.add_task(text))

    def _random(self) -> None:
        if self.tasks:
            self._choose(random.choice(self.tasks))

    def _choose(self, task: Task) -> None:
        self.chosen.emit(task)

    def focus(self) -> None:
        self.edit.setFocus()
        self.edit.selectAll()


class ShrinkPage(QWidget):
    go = Signal(list)
    back = Signal()

    def __init__(self, store: Store, seconds: int = 120):
        super().__init__()
        self.store = store
        self.task_lab = _label("", "task")
        self.context = _label("", "hint")
        self.step1 = QLineEdit(placeholderText="e.g. open laptop, search “car service near me”")
        self.step2 = QLineEdit(placeholderText="then… (optional)", objectName="optional")
        self.step3 = QLineEdit(placeholderText="then… (optional)", objectName="optional")
        start = QPushButton(f"Start {seconds // 60}:{seconds % 60:02d}  ▶", objectName="primary")
        back = QPushButton("← Back")

        lay = QVBoxLayout(self)
        lay.addWidget(self.task_lab)
        lay.addWidget(_label("What's the smallest next physical action?", "title"))
        lay.addWidget(self.step1)
        lay.addWidget(_label("If it feels too small to count, you got it right.", "muted"))
        lay.addSpacing(6)
        lay.addWidget(_label("Takes less than 2 min? Line up one or two more:", "hint"))
        lay.addWidget(self.step2)
        lay.addWidget(self.step3)
        lay.addWidget(self.context)
        lay.addStretch(1)
        row = QHBoxLayout()
        row.addWidget(back)
        row.addStretch(1)
        row.addWidget(start)
        lay.addLayout(row)
        lay.addWidget(_label("Enter start  ·  Tab next box  ·  Esc back", "hint"))

        for e in (self.step1, self.step2, self.step3):
            e.returnPressed.connect(self._go)
        start.clicked.connect(self._go)
        back.clicked.connect(self.back)

    def load(self, task: Task) -> None:
        self.task_lab.setText(f"Task: {task.title}")
        for e in (self.step1, self.step2, self.step3):
            e.clear()
        bits = []
        if task.last_step:
            bits.append(f"Last time: {task.last_step}")
        notes = self.store.notes_for(task.id)[-3:]
        if notes:
            bits.append("From your pad: " + "  ·  ".join(notes))
        self.context.setText("\n".join(bits))
        self.context.setVisible(bool(bits))
        self.step1.setFocus()

    def _go(self) -> None:
        steps = [e.text().strip() for e in (self.step1, self.step2, self.step3) if e.text().strip()]
        if not steps:
            self.step1.setFocus()
            self.step1.setPlaceholderText("Just one tiny thing — what do your hands do first?")
            return
        self.go.emit(steps)


class Popup(QWidget):
    start = Signal(int, str, list)  # task_id, title, steps
    closed = Signal()

    def __init__(self, store: Store, seconds: int = 120):
        super().__init__(None, Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Two-Minute Start")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.resize(520, 460)
        self.task: Task | None = None
        self._started = False

        self.pick = PickPage(store)
        self.shrink = ShrinkPage(store, seconds)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.pick)
        self.stack.addWidget(self.shrink)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.addWidget(self.stack)

        self.pick.chosen.connect(self._to_shrink)
        self.shrink.back.connect(self._to_pick)
        self.shrink.go.connect(self._go)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self._escape)

    def present(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.pick.focus()

    def _to_shrink(self, task: Task) -> None:
        self.task = task
        self.shrink.load(task)
        self.stack.setCurrentWidget(self.shrink)

    def _to_pick(self) -> None:
        self.pick.reload()
        self.stack.setCurrentWidget(self.pick)
        self.pick.focus()

    def _escape(self) -> None:
        if self.stack.currentWidget() is self.shrink:
            self._to_pick()
        else:
            self.close()

    def _go(self, steps: list[str]) -> None:
        self._started = True
        self.start.emit(self.task.id, self.task.title, steps)
        self.close()

    def closeEvent(self, ev):
        self.closed.emit()
        super().closeEvent(ev)
