# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: twomins

Personal desktop app for the **two-minute start**: a technique for starting tasks you've been
avoiding (ADHD task initiation). Pick the task, shrink it to the smallest physical action, run
a 2-minute timer, and stop guilt-free — or keep going.

Repo: `git@github.com:colonelkablam/twomins.git`. Developed as the sandboxed `claudedev` user
in `~/ClaudeProjects/twomins`. Owner: Nick (British English, concise, copy-paste-ready commands).

## Source material

`docs/two-minute-start-transcript.txt` is the transcript of the video this app is based on
(lines are `M:SS | text`, grouped by chapter). Read it before changing UX copy or flow.
Key ideas the app must keep:

| Idea from the video | How the app implements it |
|---|---|
| Starting is costly because of **load** (whole task in your head), **distant reward**, and **relief from avoiding** | Every design choice should lower one of these three costs |
| Write the task down; it's a "blurry pile" | Picker accepts a messy free-text task |
| Ask: "What's the smallest next physical action?" | Shrink screen; hint: "If it feels too small to count, you got it right." |
| If the step takes under 2 min, line up 1–2 more | Two optional extra step fields |
| Real permission to stop when the timer ends | Stopping is **always** a success. No streaks, no failure states, no guilt copy |
| Go straight in, don't think | Enter starts immediately; no confirmation dialogs |
| Offload to a sticky pad | `N` opens a notepad in the timer; notes are saved per task and shown next time |
| Momentum after the beep | Finish: Keep going / Stop here ✓ / Whole task done ✓ |
| Once started, keeping going is easier than quitting | Flow: "Keep going" turns the timer purple and counts up silently; flow time is recorded and celebrated |
| Relief comes from starting, not avoiding | "Started ✓" the moment you press Enter; weekly start count on the timer, finish screen, tray |
| If-then cues (implementation intentions) | **v3**: "If I [cue] → start [task]" |
| Didn't start? Step wasn't small enough | Alt+H on the actions screen ("too big: … what's half of that?"); shortcut only, no button |
| "Specific and concrete, not 'work on it'" | Quiet live hint for vague verbs: "Make it physical" (`core/steps.py`) |
| "Line up one or two more" | Live hint when a step is two actions ("X and Y"): Alt+S splits it into "then…" |
| Heavy (dread) vs boring | **v4**: optional tag; the app points elsewhere, it doesn't try to fix it |

## Principles (read before adding any feature)

**This is a starting tool, not a to-do list.** The video is explicit that the two-minute start
gets you going and *other* systems keep you organised. twomin is the ignition, not the system.

- **Not a to-do app. Non-goals:** due dates, priorities, projects, tags-for-organising,
  reminders-per-task, overdue states, checklists, sync. If a feature makes the app better at
  *storing* tasks rather than *starting* them, it doesn't belong here.
- **The task list must not become a guilt pile.** Avoided tasks lower down the list are load.
  Keep the picker short; old untouched tasks should quietly fade out of sight (not be flagged).
- **Celebrate the start.** The win is pressing Enter, not finishing. Every exit path from a
  session (Esc early, stop at the beep, keep going, done) gets a positive message. Copy says
  "you started", never "you didn't finish". Never show zero-days, ratios, completion rates,
  streaks, or anything that can go down or reset.
- **Stats only count up.** "N starts this week" style totals. Nothing comparing you to a target.
- **Protect focus once it's flowing.** After the beep, "keep going" should be the easiest
  choice, and continuing must not interrupt the person: no repeated beeps or popups every two
  minutes, no prompts mid-flow. The timer gets out of the way and the person stops when they
  choose.
- **Zero friction to start.** No confirmations, no required fields beyond the task and one
  step, no setup screens. Every added click is a cost the video says we're trying to remove.
- **Don't nag.** Prompts the user ignores become one more thing to avoid. Any cue or
  prompt must be easy to dismiss, never repeated in a loop, and never worded as a reminder of
  failure.

Measure **starts**, not completions.

## Stack

- Python 3.11+, **PySide6** (Qt Widgets), SQLite (`sqlite3`), TOML config (`tomllib`)
- Target: **Fedora, GNOME, Wayland** (should also work on X11/KDE)
- No other runtime deps. Sound via `pw-play`/`paplay`, notifications via `notify-send`

## Layout

```
twomin/
├── __main__.py      # CLI (--tray, --quit, --seconds) + single-instance IPC
├── app.py           # Controller: wires store, popup, mini timer, tray
├── notify.py        # chime + desktop notification (fire and forget)
├── core/            # NO Qt imports — keep it testable
│   ├── timer.py     # Countdown (monotonic clock, injectable for tests)
│   ├── models.py    # Task, Session, outcome constants
│   ├── steps.py     # is_vague() / split_step(): hints on a step as it's typed
│   └── store.py     # SQLite + MIGRATIONS (PRAGMA user_version); short list, search, let_go
├── ui/
│   ├── popup.py     # PickPage → ShrinkPage; emits start(task_id, title, steps)
│   ├── mini.py      # on-top timer: RUN (countdown / focus count-up) → FINISH → UNDO
│   └── style.py     # tokens, type scale, font loading, QSS (the one place for the look)
└── assets/          # icon.svg, chime.wav
tests/test_core.py   # core tests (plain asserts; pytest-compatible)
install.sh / uninstall.sh
```

Rules: `core/` never imports Qt. UI screens talk via signals and don't know about the store
beyond what's passed in. Styling only in `ui/style.py`.

## Architecture notes

- **Single instance** via `QLocalServer` named `twomin-<uid>`. JSON-line commands:
  `status`, `raise`, `start`, `show`, `quit`.
- The first process becomes the **instance** (it owns the tray and any running timer).
  The hotkey launches a **new process**, which shows the popup itself (new processes get
  keyboard focus reliably on GNOME), hands `start` to the instance, then exits. If a timer
  is running, the hotkey just raises it.
- **Wayland**: the app sets `QT_QPA_PLATFORM=xcb` (XWayland) automatically, because GNOME
  ignores always-on-top for native Wayland clients. `TWOMIN_NATIVE_WAYLAND=1` disables this.
- Data: `~/.local/share/twomin/twomin.db`. Config: `~/.config/twomin/config.toml` (`seconds = 120`).
- Session outcomes: `task_done`, `stopped`, `stopped_early`. All count as starts.
  `sessions.extensions` is now 1 if the person kept going into focus mode (it used to count +2 rounds).
- **Look** (`ui/style.py`): one hero per screen (picker question, task name on the actions
  screen, the timer clock); type scale `KEYS/META/BODY/PROMPT/HERO/CLOCK`; bundled font
  Atkinson Hyperlegible Next (`assets/`, OFL, loaded by `load_fonts()`); key hints are a quiet
  footer built with `keys()`; dashed boxes = optional; a yellow left bar = selected row.
- **Colours mean states** (all in `ui/style.py`): yellow = starting (countdown, +2 round),
  calm blue = stop (never red: stopping isn't failing), green = whole task done, purple = flow.
  Entering flow sets `FLOW_QSS` on the timer window so the whole window turns purple.
- **Flow is a second reward:** `sessions.flow_seconds` (migration 2) records time in flow;
  `flows_since()` feeds "N starts · M flows this week" (tray, timer, notifications).
- **Task → actions:** a task is the blurry pile; each session is one start holding the 1–3
  physical actions typed for it. Actions are never dismissed: stopping ends the *session*, and the
  Shrink screen lists past actions (`recent_steps()`, distinct step sets with summed time) plus
  `task_totals()` (starts, total time) so they can be picked up again. An earlier action can be
  renamed (`rename_steps`, e.g. typos) or hidden from the list (`sessions.hidden`, migration 4);
  neither deletes anything, so totals never drop.
- **Picker list is short by design:** `open_tasks()` shows at most 5 tasks touched in the last 14
  days. Older ones fade without any flag; `search_open()` (used as soon as you type) covers all open
  tasks. `let_go` hides a task for good without calling it done.
  The picker's top line shows the last 7 days (starts, time, flows) and each task shows its
  totals: this week's if it has any, otherwise all-time "so far". Never a row of zeros.
- **At work / personal** (not "spaces": one switch, no lists to manage). `tasks.work` (migration 5);
  new tasks take the current side. "At work" is held only by the running instance
  (`Controller.at_work`, never saved): unticked on every start, flipped by the picker tick box,
  the tray's "At work" item, or the `set_work` IPC command from a Super+T popup (`status` returns
  it). `_check_sleep()` unticks it after the laptop was asleep > 4 h (a wall-clock jump between
  60 s ticks); inactivity alone doesn't. The picker and search show only the current side; "See
  all" (Alt+A) shows both for that popup only. Weekly totals stay combined.
- **Schema changes:** append to `MIGRATIONS` in `store.py` (never edit a shipped entry). `_migrate()`
  runs them under `BEGIN IMMEDIATE`, because the hotkey process and the instance can open the DB at once.

## Keys

One scheme across the app. Keep new keys inside it.

| Key | Means, on every screen |
|---|---|
| Enter | the main thing: choose · start · save · keep going |
| Esc | one step back or cancel: close · back · cancel a rename · **stop the timer** (shown on the Stop button) · undo "done" |
| ↓↑ | move through a list (picker tasks, earlier actions) |
| F2 | rename the highlighted thing (task, or earlier action) |
| ⇧Del | hide the highlighted thing: "let go" a task, hide an earlier action. Nothing is deleted. Like Shift+Del removing a browser suggestion; only while an action is unedited |
| Alt+H / Alt+S | step tools: half it / split two actions |
| Alt+W / Alt+A | work switch for what's in front of you: "At work" in the picker, the task's Personal/Work chip on the actions screen / see all (this popup only) |
| Ctrl+R | pick a task for me |
| ⇧D / ⇧S | whole task done / stop (⇧S is an alias for Esc). Not Ctrl+D/Ctrl+S: those mean close and save elsewhere and get pressed by reflex |
| N · 2 · U | timer only (no text box there): note · another round · undo |

Single-letter keys are handled in `MiniTimer.keyPressEvent`, **not** with `QShortcut`.
Otherwise typing in the notepad would trigger them. Ending a session (stop/done) needs **Shift**,
and the beep only `raise_()`s the timer (no `activateWindow()`), so stray keys typed into another
window can never end a session. `bring_forward()` (start, hotkey) is the only place that takes focus.

**Never close a window from inside its own key or click handler.** Defer it with
`QTimer.singleShot(0, ...)`. On Fedora, IBus delivers key events late, from Qt's queue of
pending events, so a window closed (and deleted) during `returnPressed` gets freed while
`QLineEdit` is still handling the key, and the app segfaults. Headless tests can't catch this
(no IBus); check on the real desktop. `close_orphans()` tidies starts a crash left open, and must
only run in the process that becomes the instance.

## Commands

```bash
./install.sh                                   # deps (dnf), venv, menu entry, autostart, Super+T, tray
TWOMIN_KEY='<Super><Shift>t' ./install.sh      # different hotkey
.venv/bin/python tests/test_core.py            # core tests (no pytest needed)
.venv/bin/python -m pytest tests/test_core.py::test_store   # single test (pip install pytest first)
QT_QPA_PLATFORM=offscreen .venv/bin/twomin     # headless smoke run
.venv/bin/twomin --quit                        # stop running instance
./uninstall.sh                                 # keeps data
./install.sh --no-desktop                      # packages + venv only (no menu/hotkey/tray)
scripts/test-distros.sh [image…]               # clean-container install + tests + X11 launch (default: ubuntu:24.04 fedora:44)
```

**Installer layout** (`install.sh`): distro adapters (`detect_distro` → `pkgs_/installed_/install_<family>`:
fedora via dnf, debian/ubuntu via apt), then freedesktop-standard menu + autostart, then desktop
adapters (`setup_desktop`: GNOME gets the gsettings hotkey + AppIndicator tray). Anything it can't
do goes into `MANUAL` and is printed at the end; unknown distros/desktops never fail the install.
To add a distro or desktop, add one case. Run `scripts/test-distros.sh` after changing it.
Flatpak was considered and parked: its sandbox fights the global hotkey, always-on-top, tray,
sound and the dev loop.

The install is editable (`pip install -e`), so code changes apply the next time it launches.
Run `twomin --quit` first to restart the tray instance.

## How we work

Two users on one machine. Claude develops as `claudedev` in `~/ClaudeProjects/twomins` (no
access to Nick's desktop session). Nick runs the app as `nickh` from `~/Projects/twomins`, a
clone of the same GitHub repo.

1. **Talk it through first** for anything that changes UX: check it against the transcript and
   the Principles above, give a recommendation, then build.
2. **Build and check here, headless:**
   - core tests: `.venv/bin/python tests/test_core.py` (add a test for new store/core logic);
   - scripted UI runs with `QT_QPA_PLATFORM=offscreen` and `PySide6.QtTest` (`QTest.keyClick`,
     `QTest.qWait`), driving `Controller` / `Popup` against `Store(":memory:")`;
   - screenshots for anything visual: `widget.grab().save(path)` into the scratchpad, then look
     at them and fix what's off before reporting. Call `load_fonts()` and set `QSS` first.
   Headless runs can't show IBus, focus or window stacking; say so rather than claim it works.
3. **Report** what changed and how it was checked, then wait. **Commit and push only when Nick
   says "commit and push".** One commit per round, a descriptive message, then `git push`.
4. **Nick updates and tries it** on the real desktop:
   ```bash
   cd ~/Projects/twomins && git pull
   .venv/bin/twomin --quit; setsid -f .venv/bin/twomin --tray >/dev/null 2>&1
   ```
   `./install.sh` again only when the installer changed (menu name, hotkey, packages).
5. **Debugging his desktop:** ask for command output rather than guessing:
   `pgrep -af twomin`, `coredumpctl list --since today | grep python`, `coredumpctl info <PID>`,
   and session rows via `python3 -c "import sqlite3,os; …"` on `~/.local/share/twomin/twomin.db`.

## Status / roadmap

Work in this order. Each item should be usable before starting the next.

- **v1 (done, verified on Fedora GNOME Wayland):** pick → shrink → timer → finish, SQLite log,
  notepad, single instance, tray, autostart, Super+T, installer. IBus crash fixed.
- **v2 (done):** ↑/↓ step history, D any time + undo, schema migrations, focus mode (silent
  count-up), start celebrated immediately + weekly count, short picker list, let it go.
- **v2.1 (done):** reframing a step, person-pulled. Alt+H ("✂ smaller", shortcut only) keeps the too-big step in
  view and asks for half; live hints for vague steps and two-actions-in-one (Alt+S split). A
  close-based "you didn't start" offer was tried and removed: closing the popup is ambiguous
  (interrupted, wrong task, just looking), and acting on it felt railroady. Migration 3's
  `tasks.nudge` column is left unused (shipped migrations are never edited).
- **v2.2 (done):** At work / personal: one tick box (instance-held, resets on restart or a long
  sleep), per-task Personal/Work chip, see all for one popup. Personal is the default.
- **Next:** v3 cues.
- **v3: cues.** If-then plans in the user's own words ("If I sit down after lunch → start
  [task]"), triggered by events the computer can see (login, unlock, first wake of the day)
  rather than clock times; a timed `QTimer`/systemd-timer cue is the fallback. One prompt per
  cue, dismissible, never repeated. Tray "pick for me".
- **v4: optional heavy/boring tag + counts-up stats.** Starts per week, per task. If most
  starts are tagged heavy, show one quiet line suggesting that dread needs its own approach
  (and a clinician if it's nearly every task), not a score.
- **Installer: more distros/desktops** (Arch, openSUSE; KDE/Cinnamon hotkeys): one adapter each.
- **Maybe:** "reopen" a finished task when its title is typed again (keeps notes + step history).
- **Later: Settings window** (tray menu). Timer length, full reset (wipe the DB, with a backup
  file first), and a deletion tool for tasks (true delete lives here, not in the picker, where
  Del only "lets go"). Keep it out of the start flow.

## Known gaps

- Tray icon needs the AppIndicator extension (installer adds it; log out once after first install).
- Headless tests (`QT_QPA_PLATFORM=offscreen`) can't reproduce IBus/focus/stacking behaviour.
  Check UI changes on the real desktop, and `coredumpctl list --since today | grep python` for crashes.
