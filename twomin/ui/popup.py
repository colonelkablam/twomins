"""The hotkey popup: pick/capture a task, then shrink it to one physical action.

Emits `start(task_id, title, steps)` and `closed()`. Knows nothing about timers.
"""
from __future__ import annotations

import random
from datetime import datetime

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from ..core.models import Task
from ..core.steps import is_vague, split_step
from ..core.store import Store
from .style import ACCENT, FLOW, keys


def _label(text: str, name: str = "", wrap: bool = True) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def _score() -> QLabel:
    """Small right-aligned tally in a screen's top corner: counts up, never zeros."""
    lab = QLabel(objectName="score")
    lab.setTextFormat(Qt.RichText)
    lab.setAlignment(Qt.AlignRight | Qt.AlignTop)
    return lab


def _headed(left: QWidget, right: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(12)
    row.addWidget(left, 1, Qt.AlignBottom)
    row.addWidget(right, 0, Qt.AlignBottom)
    return row


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' * (n != 1)}"


class PickPage(QWidget):
    chosen = Signal(object)  # Task

    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self.tasks: list[Task] = []

        self.edit = QLineEdit(placeholderText="Type it messy. The whole blurry pile is fine.",
                              objectName="ask")
        self.list = QListWidget()
        self.list.setFocusPolicy(Qt.StrongFocus)
        self.week = _score()
        self.older = _label("", "meta")
        self.older.setAlignment(Qt.AlignRight)
        self.status = _label("", "meta")
        footer = _label(keys(("⏎", "choose"), ("↓", "list"), ("Del", "let it go"),
                             ("Ctrl+R", "pick for me"), ("Esc", "close")), "keys")
        footer.setTextFormat(Qt.RichText)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.addLayout(_headed(_label("What are you avoiding?", "hero"), self.week))
        lay.addWidget(self.edit)
        lay.addSpacing(8)
        lay.addLayout(_headed(_label("Carry on", "section"), self.older))
        lay.addWidget(self.list, 1)
        lay.addWidget(self.status)
        lay.addWidget(footer)

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
        self.older.setText("type to find older ones" if hidden > 0 else "")
        self._filter(self.edit.text())

    def _filter(self, text: str) -> None:
        self.list.clear()
        needle = text.strip()
        for t in (self.store.search_open(needle) if needle else self.tasks):
            row = QWidget(objectName="row")
            rl = QVBoxLayout(row)
            rl.setContentsMargins(12, 8, 12, 8)
            rl.setSpacing(2)
            rl.addWidget(_label(t.title, "rowtitle", wrap=False))
            rl.addWidget(_label(_task_line(t), "rowmeta", wrap=False))
            it = QListWidgetItem()
            it.setData(Qt.UserRole, t)
            it.setSizeHint(row.sizeHint())
            self.list.addItem(it)
            self.list.setItemWidget(it, row)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _show_week(self) -> None:
        n, secs = self.store.starts_since(7), self.store.time_since(7)
        if not n:                                    # never a row of zeros
            self.week.setText("Your next start counts")
            return
        f, _ = self.store.flows_since(7)
        flows = f'&nbsp;&nbsp;<span style="color:{FLOW}">✦ {_plural(f, "flow")}</span>' if f else ""
        self.week.setText(f'<b style="color:{ACCENT}">{_plural(n, "start")}</b>{flows}<br>'
                          f"{_dur(secs)} in the last 7 days")

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
    if not t.starts:
        return "not started yet"
    if t.week_starts:
        tally = f"{_plural(t.week_starts, 'start')} this week, {_dur(t.week_seconds)}"
    else:
        tally = f"{_plural(t.starts, 'start')}, {_dur(t.seconds)} so far"
    return f"{tally}.  Last: {t.last_step}"


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
        self.context = _label("", "meta")
        self.step1 = QLineEdit(placeholderText=STEP_HINT, objectName="ask")
        self.step2 = QLineEdit(placeholderText="then… (optional)", objectName="optional")
        self.step3 = QLineEdit(placeholderText="then… (optional)", objectName="optional")
        # The task title is editable in place: click it (or ⇧Tab from the step box).
        self.task: Task | None = None
        self.title_edit = QLineEdit(objectName="tasktitle")
        self.title_edit.setToolTip("Click to rename this task")
        self.title_edit.returnPressed.connect(self.step1.setFocus)   # Enter here never starts
        self.title_edit.editingFinished.connect(self._rename)
        start = QPushButton(f"Start {seconds // 60}:{seconds % 60:02d}  ▶", objectName="primary")
        back = QPushButton("← Back", objectName="quiet")
        self.tally = _score()

        # Past actions: every earlier start of this task, newest first. Click or ↑/↓ to reuse.
        self.past_head = QWidget()
        ph = _headed(_label("Earlier actions", "section"), _label("↓↑ or click to reuse", "meta"))
        ph.setContentsMargins(0, 0, 0, 0)
        self.past_head.setLayout(ph)
        self.past = QListWidget(objectName="past")
        self.past.setFocusPolicy(Qt.NoFocus)           # keys stay in the step boxes
        self.past.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.past.itemClicked.connect(lambda it: self._recall_to(self.past.row(it)))

        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        lay.addLayout(_headed(self.title_edit, self.tally))      # the task is the hero here
        lay.addSpacing(10)
        lay.addWidget(_label("What's the smallest next physical action?", "prompt"))
        lay.addWidget(_label("If it feels too small to count, you got it right.", "meta"))
        # ✂ Alt+H: when *you* feel the step is too big, halve it (transcript ch.7). Shortcut only:
        # the question above already asks for the smallest action; a button just repeated it.
        self.cut_lab = _label("", "nudge")
        self.cut_lab.hide()
        lay.addWidget(self.cut_lab)
        lay.addWidget(self.step1)
        # Quiet live hints while typing: "make it physical" / "that's two actions"
        self.step_hint = _label("", "nudge")
        self.step_hint.setTextFormat(Qt.RichText)
        self.step_hint.linkActivated.connect(lambda _: self._split())
        self.step_hint.hide()
        lay.addWidget(self.step_hint)
        lay.addSpacing(4)
        lay.addWidget(_label("Under two minutes? Line up one or two more.", "meta"))
        lay.addWidget(self.step2)
        lay.addWidget(self.step3)
        lay.addSpacing(10)
        lay.addWidget(self.past_head)
        lay.addWidget(self.past)
        lay.addWidget(self.context)
        lay.addStretch(1)
        row = QHBoxLayout()
        row.addWidget(back)
        row.addStretch(1)
        row.addWidget(start)
        lay.addLayout(row)
        footer = _label(keys(("⏎", "start"), ("Tab", "next box"), ("↓↑", "earlier"),
                             ("Alt+H", "smaller"), ("Alt+S", "split"), ("Esc", "back")), "keys")
        footer.setTextFormat(Qt.RichText)
        lay.addWidget(footer)

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
        self.step1.textChanged.connect(self._check_step)
        for b in (self.step2, self.step3):         # a filled "then…" box changes what's offered
            b.textChanged.connect(lambda _: self._check_step(self.step1.text()))
        QShortcut(QKeySequence("Alt+H"), self, activated=self._smaller)
        QShortcut(QKeySequence("Alt+S"), self, activated=self._split)

    def load(self, task: Task) -> None:
        self.task = task
        self.title_edit.setText(task.title)
        self.title_edit.setCursorPosition(0)
        for e in (self.step1, self.step2, self.step3):
            e.clear()
        self.cut_lab.hide()
        self.step1.setPlaceholderText(STEP_HINT)
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

    # ---- reframing a step, only when the person wants it
    def _smaller(self) -> None:
        """✂ Cut it in half: keep the too-big step in view and ask for half of it."""
        big = self.step1.text().strip()
        self.cut_lab.setText(f"✂ Too big: “{big}”. What's half of that?" if big else
                             "✂ Smaller than feels reasonable: what do your hands do first?")
        self.cut_lab.show()
        self.step1.clear()
        self.step1.setPlaceholderText("half of it…")
        self.step1.setFocus()

    def _check_step(self, text: str) -> None:
        if is_vague(text):
            self.step_hint.setText("Make it physical: what do your hands do first? "
                                   "(open, type, pick up, write…)")
        elif split_step(text) and self._free_box():
            self.step_hint.setText('That looks like two actions. <a href="split" style="color:'
                                   f'{ACCENT}">Split it</a> (Alt+S): the second goes into “then…”.')
        else:
            self.step_hint.hide()
            return
        self.step_hint.show()

    def _free_box(self) -> QLineEdit | None:
        return next((b for b in (self.step2, self.step3) if not b.text().strip()), None)

    def _split(self) -> None:
        parts, box = split_step(self.step1.text()), self._free_box()
        if not parts or not box:
            return
        self.step1.setText(parts[0])
        box.setText(parts[1])
        self.step1.setFocus()

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
            self.past.addItem(f"{_when(started)}, {_dur(sec)}{extra}:  " + "  →  ".join(steps))
        shown = min(len(self.history), 5)
        self.past.setFixedHeight(shown * self.past.sizeHintForRow(0) + 4 if shown else 0)
        self.past.setVisible(bool(self.history))
        self.tally.setText(f'<b style="color:{ACCENT}">{_plural(starts, "start")}</b><br>'
                           f"{_dur(secs)} so far" if starts else "new")
        self.past_head.setVisible(bool(self.history))
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
        self.resize(560, 600)
        self.task: Task | None = None
        self._started = False

        self.pick = PickPage(store)
        self.shrink = ShrinkPage(store, seconds)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.pick)
        self.stack.addWidget(self.shrink)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 16)
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
        self.closed.emit()
        super().closeEvent(ev)
