"""SQLite persistence. One file, no ORM."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from .models import DONE, Session, Task

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    created TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    done INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    steps TEXT NOT NULL,                 -- newline-separated
    started TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    ended TEXT,
    seconds INTEGER,
    extensions INTEGER DEFAULT 0,
    outcome TEXT
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    session_id INTEGER REFERENCES sessions(id),
    text TEXT NOT NULL,
    created TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
"""


def default_path() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "twomin" / "twomin.db"


class Store:
    def __init__(self, path: Path | str | None = None):
        path = Path(path) if path else default_path()
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.executescript(SCHEMA)

    # ---- tasks
    def add_task(self, title: str) -> Task:
        cur = self.db.execute("INSERT INTO tasks(title) VALUES (?)", (title.strip(),))
        self.db.commit()
        return Task(cur.lastrowid, title.strip())

    def open_tasks(self, limit: int = 20) -> list[Task]:
        rows = self.db.execute(
            """
            SELECT t.id, t.title,
                   (SELECT steps FROM sessions s WHERE s.task_id=t.id
                     ORDER BY s.id DESC LIMIT 1),
                   (SELECT COUNT(*) FROM sessions s WHERE s.task_id=t.id),
                   COALESCE((SELECT MAX(started) FROM sessions s WHERE s.task_id=t.id),
                            t.created) AS touched
            FROM tasks t WHERE t.done=0
            ORDER BY touched DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            Task(r[0], r[1], (r[2] or "").split("\n")[0] or None, r[3]) for r in rows
        ]

    def mark_done(self, task_id: int) -> None:
        self.db.execute("UPDATE tasks SET done=1 WHERE id=?", (task_id,))
        self.db.commit()

    # ---- sessions
    def start_session(self, task_id: int, steps: list[str]) -> Session:
        cur = self.db.execute(
            "INSERT INTO sessions(task_id, steps) VALUES (?, ?)",
            (task_id, "\n".join(steps)),
        )
        self.db.commit()
        return Session(cur.lastrowid, task_id, steps)

    def end_session(self, session_id: int, seconds: float, extensions: int, outcome: str) -> None:
        self.db.execute(
            """UPDATE sessions SET ended=datetime('now','localtime'),
               seconds=?, extensions=?, outcome=? WHERE id=?""",
            (int(seconds), extensions, outcome, session_id),
        )
        if outcome == DONE:
            self.db.execute(
                "UPDATE tasks SET done=1 WHERE id=(SELECT task_id FROM sessions WHERE id=?)",
                (session_id,),
            )
        self.db.commit()

    # ---- notes (the sticky pad)
    def add_note(self, task_id: int, session_id: int | None, text: str) -> None:
        self.db.execute(
            "INSERT INTO notes(task_id, session_id, text) VALUES (?,?,?)",
            (task_id, session_id, text.strip()),
        )
        self.db.commit()

    def notes_for(self, task_id: int) -> list[str]:
        return [r[0] for r in self.db.execute(
            "SELECT text FROM notes WHERE task_id=? ORDER BY id", (task_id,))]

    # ---- stats: count STARTS, not completions
    def starts_since(self, days: int = 7) -> int:
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        return self.db.execute(
            "SELECT COUNT(*) FROM sessions WHERE started >= ?", (since,)
        ).fetchone()[0]
