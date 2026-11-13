"""SQLite persistence. One file, no ORM."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from .models import DONE, STOPPED, Session, Task

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


# Ordered schema changes. SCHEMA above is version 0; entry i takes the DB to version i+1.
# Append only, never edit an entry that has shipped.
MIGRATIONS = [
    "ALTER TABLE tasks ADD COLUMN let_go INTEGER NOT NULL DEFAULT 0",  # 1: "let it go"
    "ALTER TABLE sessions ADD COLUMN flow_seconds INTEGER NOT NULL DEFAULT 0",  # 2: time in flow
]

# Open tasks, newest-touched first. "touched" = last start, or creation if never started.
_OPEN = """
    SELECT * FROM (
        SELECT t.id, t.title,
               (SELECT steps FROM sessions s WHERE s.task_id=t.id ORDER BY s.id DESC LIMIT 1),
               (SELECT COUNT(*) FROM sessions s WHERE s.task_id=t.id),
               COALESCE((SELECT MAX(started) FROM sessions s WHERE s.task_id=t.id),
                        t.created) AS touched
        FROM tasks t WHERE t.done=0 AND t.let_go=0 AND {where}
    ) WHERE touched >= ? ORDER BY touched DESC LIMIT ?
"""


def default_path() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "twomin" / "twomin.db"


class Store:
    def __init__(self, path: Path | str | None = None):
        path = Path(path) if path else default_path()
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), timeout=5)
        self.db.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        # IMMEDIATE lock + re-read: the hotkey process and the instance may open the DB at once.
        self.db.execute("BEGIN IMMEDIATE")
        try:
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            for i, sql in enumerate(MIGRATIONS[version:], start=version):
                self.db.execute(sql)
                self.db.execute(f"PRAGMA user_version = {i + 1}")
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    # ---- tasks
    def add_task(self, title: str) -> Task:
        cur = self.db.execute("INSERT INTO tasks(title) VALUES (?)", (title.strip(),))
        self.db.commit()
        return Task(cur.lastrowid, title.strip())

    def _query_open(self, where: str, args: tuple, fresh_days: int | None, limit: int) -> list[Task]:
        since = "" if fresh_days is None else _ago(fresh_days)
        rows = self.db.execute(_OPEN.format(where=where), (*args, since, limit)).fetchall()
        return [Task(r[0], r[1], (r[2] or "").split("\n")[0] or None, r[3]) for r in rows]

    def open_tasks(self, limit: int = 5, fresh_days: int | None = 14) -> list[Task]:
        """The short list the picker shows: recently touched open tasks only.

        Older ones quietly fade from view (never flagged) but stay findable by typing.
        """
        return self._query_open("1", (), fresh_days, limit)

    def search_open(self, text: str, limit: int = 20) -> list[Task]:
        """All open tasks whose title contains `text` (case-insensitive), faded ones included."""
        like = "%" + text.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        return self._query_open("t.title LIKE ? ESCAPE '\\'", (like,), None, limit)

    def count_open(self) -> int:
        return self.db.execute(
            "SELECT COUNT(*) FROM tasks WHERE done=0 AND let_go=0").fetchone()[0]

    def let_go(self, task_id: int) -> None:
        """Drop a task you no longer want to start. Not 'done', not a failure; history kept."""
        self.db.execute("UPDATE tasks SET let_go=1 WHERE id=?", (task_id,))
        self.db.commit()

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

    def recent_steps(self, task_id: int, limit: int = 10) -> list[tuple[str, list[str], int, int]]:
        """Past actions for a task: each distinct step set, newest first.

        Returns (last_started, steps, total_seconds, times) per distinct step set. Nothing is
        ever dismissed: a stopped action is still here to pick up again.
        """
        out: dict[str, list] = {}
        for started, steps, secs in self.db.execute(
            "SELECT started, steps, COALESCE(seconds, 0) FROM sessions WHERE task_id=? "
            "ORDER BY id DESC", (task_id,)
        ):
            if not steps:
                continue
            if steps in out:
                out[steps][2] += secs
                out[steps][3] += 1
            elif len(out) < limit:
                out[steps] = [started, steps.split("\n"), secs, 1]
        return [tuple(v) for v in out.values()]

    def task_totals(self, task_id: int) -> tuple[int, int]:
        """(starts, total seconds) for a task. Only ever goes up."""
        n, secs = self.db.execute(
            "SELECT COUNT(*), COALESCE(SUM(seconds), 0) FROM sessions WHERE task_id=?",
            (task_id,)).fetchone()
        return n, secs

    def end_session(self, session_id: int, seconds: float, extensions: int, outcome: str,
                    flow_seconds: float = 0) -> None:
        self.db.execute(
            """UPDATE sessions SET ended=datetime('now','localtime'),
               seconds=?, extensions=?, outcome=?, flow_seconds=? WHERE id=?""",
            (int(seconds), extensions, outcome, int(flow_seconds), session_id),
        )
        if outcome == DONE:
            self.db.execute(
                "UPDATE tasks SET done=1 WHERE id=(SELECT task_id FROM sessions WHERE id=?)",
                (session_id,),
            )
        self.db.commit()

    def close_orphans(self) -> int:
        """End sessions left open by a crash or logout. They still count as starts.

        Only call this from the process that owns timers (the instance) at startup,
        or it would close a timer that is still running in another process.
        """
        cur = self.db.execute(
            "UPDATE sessions SET ended=started, outcome=? WHERE ended IS NULL", (STOPPED,))
        self.db.commit()
        return cur.rowcount

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
    def flows_since(self, days: int = 7) -> tuple[int, int]:
        """(sessions that reached flow, total seconds in flow). A second reward, counted up."""
        n, secs = self.db.execute(
            "SELECT COUNT(*), COALESCE(SUM(flow_seconds), 0) FROM sessions "
            "WHERE flow_seconds > 0 AND started >= ?", (_ago(days),)).fetchone()
        return n, secs

    def starts_since(self, days: int = 7) -> int:
        since = _ago(days)
        return self.db.execute(
            "SELECT COUNT(*) FROM sessions WHERE started >= ?", (since,)
        ).fetchone()[0]


def _ago(days: int) -> str:
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
