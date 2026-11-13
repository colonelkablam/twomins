"""The hotkey popup: pick/capture a task, then shrink it to one physical action.

Emits `start(task_id, title, steps)` and `closed()`. Knows nothing about timers.
"""
from __future__ import annotations

import random
from datetime import datetime

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from ..core.models import Task
from ..core.store import Store
from .style import ACCENT, FLOW


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
        self.offered: set[int] = set()     # tasks shown with a "cut it in half?" offer

        self.edit = QLineEdit(placeholderText="Type it messy — the whole blurry pile is fine")
        self.list = QListWidget()
        self.list.setFocusPolicy(Qt.StrongFocus)

        self.week = _label("", "task")              # 10pt muted: visible, not loud
        self.week.setTextFormat(Qt.RichText)

        lay = QVBoxLayout(self)
        lay.addWidget(self.week)
        lay.addWidget(_label("What are you avoiding?", "title"))
        lay.addWidget(self.edit)
        self.list_lab = _label("", "muted")
        lay.addWidget(self.list_lab)
        lay.addWidget(self.list, 1)
        self.status = _label("", "hint")
        lay.addWidget(self.status)
        lay.addWidget(_label("Enter choose  ·  ↓ list  ·  Del let it go  ·  Ctrl+R pick for me  ·  Esc close",
                             "hint"))

        self.edit.textChanged.connect(self._filter)
        self.edit.returnPressed.connect(self._enter_from_edit)
        self.list.itemActivated.connect(lambda it: self._choose(it.data(Qt.UserRole)))
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self._random)
        self.edit.installEventFilter(self)
        self.list.installEventFilter(self)
        self.reload()

    def reload(self) -> None:
        # Short on purpose: only recently touched tasks show. Older ones fade quietly and
        # are still found by typing (search covers every open task).
        self.tasks = self.store.open_tasks()
        self._show_week()
        hidden = self.store.count_open() - len(self.tasks)
        self.list_lab.setText("Or carry on with one you've started"
                              + (" (type to find older ones):" if hidden > 0 else ":"))
        self._filter(self.edit.text())

    def _filter(self, text: str) -> None:
        self.list.clear()
        needle = text.strip()
        for t in (self.store.search_open(needle) if needle else self.tasks):
            sub = _task_line(t)
            it = QListWidgetItem(f"{t.title}\n    {sub}")
            it.setData(Qt.UserRole, t)
            if t.nudge is not None:
                it.setForeground(QColor(ACCENT))
                self.offered.add(t.id)
            self.list.addItem(it)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _show_week(self) -> None:
        n, secs = self.store.starts_since(7), self.store.time_since(7)
        if not n:                                    # never a row of zeros
            self.week.setText("Last 7 days  ·  your next start counts")
            return
        f, _ = self.store.flows_since(7)
        flows = f'  ·  <span style="color:{FLOW}">✦ {f} flow{"s" * (f != 1)}</span>' if f else ""
        self.week.setText(f'Last 7 days  ·  <b style="color:{ACCENT}">{n} start{"s" * (n != 1)}</b>'
                          f"  ·  {_dur(secs)}{flows}")

    def eventFilter(self, obj, ev):
        if ev.type() != ev.Type.KeyPress:
            return super().eventFilter(obj, ev)
        if obj is self.edit and ev.key() == Qt.Key_Down and self.list.count():
            self.list.setFocus()                 # ↓ from the text box jumps into the list
            return True
        if obj is self.list and ev.key() == Qt.Key_Delete and self.list.currentItem():
            task = self.list.currentItem().data(Qt.UserRole)
            QTimer.singleShot(0, lambda: self._let_go(task))   # not mid key-event
            return True
        return super().eventFilter(obj, ev)

    def _let_go(self, task: Task) -> None:
        self.store.let_go(task.id)
        self.status.setText(f"Let go: {task.title}. That's allowed too.")
        self.reload()
        (self.list if self.list.count() else self.edit).setFocus()

    def _enter_from_edit(self) -> None:
        text = self.edit.text().strip()
        if not text:
            it = self.list.currentItem()
            if it:
                self._choose(it.data(Qt.UserRole))
            return
        for t in self.store.search_open(text):  # exact match → reuse, don't duplicate
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


def _when(started: str) -> str:
    """'2026-11-13 09:05:00' -> 'today', 'yesterday', 'Mon', or '3 Nov'."""
    try:
        d = datetime.strptime(started, "%Y-%m-%d %H:%M:%S").date()
    except ValueError:
        return started
    days = (datetime.now().date() - d).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 7:
        return d.strftime("%a")
    return f"{d.day} {d.strftime('%b')}"


def _task_line(t: Task) -> str:
    """Per-task totals, counted up. This week if there's anything this week, else all time."""
    if t.nudge is not None:
        return "✂ try an even smaller step"
    if not t.starts:
        return "not started yet"
    if t.week_starts:
        tally = f"this week: {t.week_starts} start{'s' * (t.week_starts != 1)} · {_dur(t.week_seconds)}"
    else:
        tally = f"{t.starts} start{'s' * (t.starts != 1)} · {_dur(t.seconds)} so far"
    return f"{tally}  ·  last: {t.last_step}"


def _dur(seconds: int | float) -> str:
    m = int(seconds // 60)
    if m < 1:
        return "<1 min" if seconds else "0 min"
    return f"{m} min" if m < 60 else f"{m // 60} h {m % 60:02d} min"


STEP_HINT = "e.g. open laptop, search “car service near me”"


class ShrinkPage(QWidget):
    go = Signal(list)
    back = Signal()

    def __init__(self, store: Store, seconds: int = 120):
        super().__init__()
        self.store = store
        self.context = _label("", "hint")
        self.step1 = QLineEdit(placeholderText=STEP_HINT)
        self.step2 = QLineEdit(placeholderText="then… (optional)", objectName="optional")
        self.step3 = QLineEdit(placeholderText="then… (optional)", objectName="optional")
        # The task title is editable in place: click it (or ⇧Tab from the step box).
        self.task: Task | None = None
        self.title_edit = QLineEdit(objectName="tasktitle")
        self.title_edit.setToolTip("Click to rename this task")
        self.title_edit.returnPressed.connect(self.step1.setFocus)   # Enter here never starts
        self.title_edit.editingFinished.connect(self._rename)
        start = QPushButton(f"Start {seconds // 60}:{seconds % 60:02d}  ▶", objectName="primary")
        back = QPushButton("← Back")

        # Past actions: every earlier start of this task, newest first. Click or ↑/↓ to reuse.
        self.past_lab = _label("", "hint")
        self.past = QListWidget(objectName="past")
        self.past.setFocusPolicy(Qt.NoFocus)           # keys stay in the step boxes
        self.past.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.past.itemClicked.connect(lambda it: self._recall_to(self.past.row(it)))

        lay = QVBoxLayout(self)
        lay.addWidget(_label("Task  ·  click to rename", "hint"))
        lay.addWidget(self.title_edit)
        lay.addWidget(_label("What's the smallest next physical action?", "title"))
        lay.addWidget(_label("If it feels too small to count, you got it right.", "muted"))
        self.nudge_lab = _label("", "nudge")
        self.nudge_lab.hide()
        lay.addWidget(self.nudge_lab)
        lay.addWidget(self.step1)
        lay.addWidget(_label("Takes less than 2 min? Line up one or two more:", "hint"))
        lay.addWidget(self.step2)
        lay.addWidget(self.step3)
        lay.addSpacing(6)
        lay.addWidget(self.past_lab)
        lay.addWidget(self.past)
        lay.addWidget(self.context)
        lay.addStretch(1)
        row = QHBoxLayout()
        row.addWidget(back)
        row.addStretch(1)
        row.addWidget(start)
        lay.addLayout(row)
        lay.addWidget(_label("Enter start  ·  Tab next box  ·  ↑↓ past actions  ·  Esc back", "hint"))

        self.history: list[tuple[str, list[str]]] = []
        self.pos = -1                     # -1 = your own typing; 0.. = history entries
        self.draft: list[str] = ["", "", ""]

        # Deferred: acting on Enter closes the popup, and the line edit must finish handling
        # its key event first (IBus delivers keys late; closing mid-event segfaulted).
        for e in (self.step1, self.step2, self.step3):
            e.returnPressed.connect(lambda: QTimer.singleShot(0, self._go))
            e.installEventFilter(self)
        start.clicked.connect(lambda: QTimer.singleShot(0, self._go))
        back.clicked.connect(self.back)
        QWidget.setTabOrder(self.title_edit, self.step1)   # ⇧Tab from step 1 → rename
        QWidget.setTabOrder(self.step1, self.step2)
        QWidget.setTabOrder(self.step2, self.step3)

    def load(self, task: Task) -> None:
        self.task = task
        self.title_edit.setText(task.title)
        self.title_edit.setCursorPosition(0)
        for e in (self.step1, self.step2, self.step3):
            e.clear()
        self._show_nudge(task)
        self.history = self.store.recent_steps(task.id)
        self.pos = -1
        self._fill_past(task)
        bits = []
        notes = self.store.notes_for(task.id)[-3:]
        if notes:
            bits.append("From your pad: " + "  ·  ".join(notes))
        self.context.setText("\n".join(bits))
        self.context.setVisible(bool(bits))
        self.step1.setFocus()

    # ---- ↑/↓ cycle through earlier steps for this task (like shell history)
    def eventFilter(self, obj, e):
        if e.type() == QEvent.KeyPress and e.key() in (Qt.Key_Up, Qt.Key_Down) and self.history:
            self._recall(+1 if e.key() == Qt.Key_Down else -1)   # ↓ = down the list = older
            return True
        return super().eventFilter(obj, e)

    def _boxes(self) -> tuple[QLineEdit, QLineEdit, QLineEdit]:
        return (self.step1, self.step2, self.step3)

    def _show_nudge(self, task: Task) -> None:
        # Transcript: "If you still didn't start, the step wasn't small enough yet. Cut it in
        # half again." Worded as an invitation, never as a reminder that it didn't happen.
        if task.nudge is None:
            self.nudge_lab.hide()
            self.step1.setPlaceholderText(STEP_HINT)
            return
        if task.nudge:
            text = f"✂ Make it smaller. Last time: “{task.nudge}”. What's half of that?"
        else:
            text = "✂ Make it smaller than feels reasonable: what do your hands do first?"
        self.nudge_lab.setText(text)
        self.nudge_lab.show()
        self.step1.setPlaceholderText("half of it…")

    def _rename(self) -> None:
        new = self.title_edit.text().strip()
        if not self.task or new == self.task.title:
            return
        if not new:                                   # empty: put the old title back
            self.title_edit.setText(self.task.title)
            return
        self.store.rename_task(self.task.id, new)
        self.task.title = new                         # same object the popup starts with

    def _fill_past(self, task: Task) -> None:
        self.past.clear()
        starts, secs = self.store.task_totals(task.id)
        for started, steps, sec, times in self.history:
            extra = f" ×{times}" if times > 1 else ""
            self.past.addItem(f"{_when(started)} · {_dur(sec)}{extra}  —  " + "  →  ".join(steps))
        shown = min(len(self.history), 5)
        self.past.setFixedHeight(shown * self.past.sizeHintForRow(0) + 4 if shown else 0)
        self.past.setVisible(bool(self.history))
        if self.history:
            self.past_lab.setText(f"Past actions  ·  {starts} start{'s' * (starts != 1)}"
                                  f"  ·  {_dur(secs)} on this task  ·  ↓↑ or click to reuse")
        self.past_lab.setVisible(bool(self.history))
        self.past.clearSelection()

    def _recall_to(self, row: int) -> None:
        self._recall(row - self.pos)
        self.step1.setFocus()

    def _recall(self, delta: int) -> None:
        new = max(-1, min(len(self.history) - 1, self.pos + delta))
        if new == self.pos:
            return
        if self.pos == -1:                # leaving your own typing: keep it for ↓
            self.draft = [b.text() for b in self._boxes()]
        self.pos = new
        texts = self.draft if new == -1 else (self.history[new][1] + ["", "", ""])[:3]
        for box, text in zip(self._boxes(), texts):
            box.setText(text)
        self.step1.setFocus()
        self.step1.end(False)
        if new == -1:
            self.past.clearSelection()
        else:
            self.past.setCurrentRow(new)               # highlight what's in the boxes

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
        self._reached: Task | None = None   # last task shown on the actions screen
        self.store = store

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
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=lambda: QTimer.singleShot(0, self._escape))

    def present(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.pick.focus()

    def _to_shrink(self, task: Task) -> None:
        self.task = task
        self._reached = task
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
        if self._started:                 # a second Enter before we closed
            return
        self._started = True
        self.start.emit(self.task.id, self.task.title, steps)
        self.close()

    def closeEvent(self, ev):
        # "Cut it in half?" bookkeeping: any offer shown this time is spent (once only); if we
        # reached the actions screen but didn't start, offer it next time instead.
        self.store.clear_nudges(self.pick.offered)
        # Already offered this time and still not started? Leave it: once means once.
        if (not self._started and self._reached is not None
                and self._reached.id not in self.pick.offered):
            same = self.shrink.task is self._reached
            self.store.set_nudge(self._reached.id, self.shrink.step1.text() if same else "")
        self.closed.emit()
        super().closeEvent(ev)
