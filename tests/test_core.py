from twomin.core.timer import Countdown
from twomin.core.store import Store
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
    hist = [steps for _, steps in s.recent_steps(a.id)]
    assert hist == [["Search garages"], ["Open Smith's page", "Find Thu slot"]]  # newest first, deduped
    assert s.recent_steps(a.id, limit=1)[0][1] == ["Search garages"]


def test_close_orphans():
    s = Store(":memory:")
    a = s.add_task("x")
    lost = s.start_session(a.id, ["a"])
    ok = s.start_session(a.id, ["b"]); s.end_session(ok.id, 120, 0, DONE)
    assert s.close_orphans() == 1 and s.close_orphans() == 0
    assert s.db.execute("SELECT outcome FROM sessions WHERE id=?", (lost.id,)).fetchone() == (STOPPED,)
    assert s.starts_since() == 2                      # still counts as a start


if __name__ == "__main__":
    test_countdown(); test_store(); test_recent_steps(); test_close_orphans(); print("ok")
