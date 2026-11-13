from twomin.core.timer import Countdown
import sqlite3

from twomin.core.store import MIGRATIONS, Store
from twomin.core.models import DONE, STOPPED


def test_countdown():
    t = [0.0]
    c = Countdown(120, clock=lambda: t[0])
    c.start()
    assert c.fmt(c.remaining()) == "2:00"
    t[0] = 119.5; assert not c.finished() and c.fmt(c.remaining()) == "0:01"
    t[0] = 125; assert c.finished()
    c.extend(120)                      # +2 from now, overshoot absorbed
    assert abs(c.remaining() - 120) < 1e-9 and c.extensions == 1


def test_store():
    s = Store(":memory:")
    a = s.add_task("Book car service")
    b = s.add_task("Sort laundry")
    sess = s.start_session(a.id, ["Search service centres near me", "Write top 2 on pad"])
    s.add_note(a.id, sess.id, "Smith's Garage - online booking")
    s.end_session(sess.id, 130, 0, STOPPED)
    tasks = s.open_tasks()
    assert tasks[0].id == a.id and tasks[0].last_step == "Search service centres near me"
    assert s.starts_since(7) == 1 and s.notes_for(a.id) == ["Smith's Garage - online booking"]
    sess2 = s.start_session(b.id, ["Pick up 5 socks"])
    s.end_session(sess2.id, 120, 1, DONE)
    assert [t.id for t in s.open_tasks()] == [a.id] and s.starts_since() == 2


def test_recent_steps():
    s = Store(":memory:")
    a = s.add_task("Book car service")
    for steps in (["Search garages"], ["Open Smith's page", "Find Thu slot"], ["Search garages"]):
        s.start_session(a.id, steps)
    sess = [r[0] for r in s.db.execute("SELECT id FROM sessions ORDER BY id")]
    for sid, secs in zip(sess, (120, 300, 60)):
        s.end_session(sid, secs, 0, STOPPED)
    hist = s.recent_steps(a.id)
    assert [h[1] for h in hist] == [["Search garages"], ["Open Smith's page", "Find Thu slot"]]
    assert (hist[0][2], hist[0][3]) == (180, 2)          # repeats merged: time summed, count 2
    assert s.recent_steps(a.id, limit=1)[0][1] == ["Search garages"]
    assert s.task_totals(a.id) == (3, 480)


def test_close_orphans():
    s = Store(":memory:")
    a = s.add_task("x")
    lost = s.start_session(a.id, ["a"])
    ok = s.start_session(a.id, ["b"]); s.end_session(ok.id, 120, 0, DONE)
    assert s.close_orphans() == 1 and s.close_orphans() == 0
    assert s.db.execute("SELECT outcome FROM sessions WHERE id=?", (lost.id,)).fetchone() == (STOPPED,)
    assert s.starts_since() == 2                      # still counts as a start


def test_migrates_old_db():
    import os, tempfile
    path = os.path.join(tempfile.mkdtemp(), "old.db")
    old = sqlite3.connect(path)               # a v1 database: no let_go column, user_version 0
    old.executescript("""CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL,
        created TEXT NOT NULL DEFAULT (datetime('now','localtime')), done INTEGER NOT NULL DEFAULT 0);
        INSERT INTO tasks(title) VALUES ('Old task');""")
    old.commit(); old.close()
    s = Store(path)
    assert s.db.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)
    assert [t.title for t in s.open_tasks()] == ["Old task"]
    Store(path)                                # reopening is a no-op, not a duplicate ALTER


def test_short_list_search_and_let_go():
    s = Store(":memory:")
    ids = [s.add_task(f"Task {i}").id for i in range(7)]
    s.db.execute("UPDATE tasks SET created='2020-01-01 00:00:00' WHERE id=?", (ids[0],))  # stale
    shown = s.open_tasks()
    assert len(shown) == 5 and ids[0] not in [t.id for t in shown]       # capped, stale faded
    assert [t.id for t in s.search_open("task 0")] == [ids[0]]           # but findable by typing
    assert s.search_open("50%") == [] and s.count_open() == 7
    s.let_go(ids[1])
    assert ids[1] not in [t.id for t in s.search_open("Task")] and s.count_open() == 6


def test_flows_counted():
    s = Store(":memory:")
    a = s.add_task("x")
    one = s.start_session(a.id, ["a"]); s.end_session(one.id, 600, 1, STOPPED, flow_seconds=480)
    two = s.start_session(a.id, ["b"]); s.end_session(two.id, 120, 0, STOPPED)
    assert s.flows_since(7) == (1, 480) and s.starts_since(7) == 2


def test_week_totals():
    s = Store(":memory:")
    a = s.add_task("x")
    old = s.start_session(a.id, ["a"]); s.end_session(old.id, 300, 0, STOPPED)
    s.db.execute("UPDATE sessions SET started='2020-01-01 00:00:00' WHERE id=?", (old.id,))
    new = s.start_session(a.id, ["b"]); s.end_session(new.id, 120, 0, STOPPED)
    t = s.open_tasks()[0]
    assert (t.starts, t.seconds, t.week_starts, t.week_seconds) == (2, 420, 1, 120)
    assert s.time_since(7) == 120 and s.starts_since(7) == 1
    s.rename_task(a.id, "  Renamed  ")
    assert s.open_tasks()[0].title == "Renamed"


if __name__ == "__main__":
    test_countdown(); test_store(); test_recent_steps(); test_close_orphans()
    test_migrates_old_db(); test_short_list_search_and_let_go(); test_flows_counted(); test_week_totals(); print("ok")
