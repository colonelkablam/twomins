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
| Momentum after the beep | Finish: Keep going +2 / Stop here ✓ / Whole task done ✓ |
| Once started, keeping going is easier than quitting | **v2**: open-ended "keep going" focus mode (see Principles) |
| If-then cues (implementation intentions) | **v3**: "If I [cue] → start [task]" |
| Didn't start? Step wasn't small enough | **v2**: gentle "Cut the step in half?" |
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
│   └── store.py     # SQLite: tasks, sessions, notes; starts_since()
├── ui/
│   ├── popup.py     # PickPage → ShrinkPage; emits start(task_id, title, steps)
│   ├── mini.py      # frameless on-top countdown, notepad, finish view
│   └── style.py     # all colours + QSS in one place
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

## Keys

| Screen | Keys |
|---|---|
| Picker | type + Enter (new or exact match) · ↓ into list · Ctrl+R random · Esc close |
| Shrink | Enter start · Tab next field · ↑/↓ cycle earlier steps for this task (draft kept) · Esc back |
| Timer | N note · D whole task done (any time) · Esc stop (still counts) · drag to move |
| Finish | Enter keep going · S stop · D task done |

Single-letter keys are handled in `MiniTimer.keyPressEvent`, **not** with `QShortcut`.
Otherwise typing in the notepad would trigger them.

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
```

The install is editable (`pip install -e`), so code changes apply the next time it launches.
Run `twomin --quit` first to restart the tray instance.

## Status / roadmap

Work in this order. Each item should be usable before starting the next.

- **v1 (built):** pick → shrink → timer → finish, SQLite log, notepad, single instance,
  tray with "starts this week", autostart, GNOME hotkey, installer.
- **v1.1: verify on real hardware (next).** Work through *Known gaps* below on a real GNOME
  Wayland session and fix what fails. The core promise is "hotkey → typing → timer" with no
  mouse; if focus or always-on-top doesn't work, nothing else matters.
- **v2: keep going + stay small**
  1. Schema versioning (`PRAGMA user_version` + migrations in `store.py`) before any new tables.
  2. **Focus mode.** "Keep going" switches to an open-ended, quiet count-up (elapsed time,
     no further beeps, notepad still on `N`), stopped with Esc/S/D as now. Currently it
     re-arms another 2 minutes and beeps again, which interrupts flow.
  3. **Bigger celebration of the start.** Finish view and notification lead with the start
     (and the running "starts this week" count), whichever outcome was chosen.
  4. **Keep the picker short.** Tasks not started for ~2 weeks drop out of the list quietly
     (still searchable by typing); simple edit/archive. No "overdue" anything.
  5. **Gentle "cut it in half?"** When the popup is closed from the Shrink screen without
     starting, offer once, as an option on the next open, not a blocking dialog.
- **v3: cues.** If-then plans in the user's own words ("If I sit down after lunch → start
  [task]"), triggered by events the computer can see (login, unlock, first wake of the day)
  rather than clock times; a timed `QTimer`/systemd-timer cue is the fallback. One prompt per
  cue, dismissible, never repeated. Tray "pick for me".
- **v4: optional heavy/boring tag + counts-up stats.** Starts per week, per task. If most
  starts are tagged heavy, show one quiet line suggesting that dread needs its own approach
  (and a clinician if it's nearly every task), not a score.

## Known gaps / check on real hardware

- Not yet verified on a real GNOME session: popup focus from the hotkey, always-on-top
  under XWayland, tray icon (needs the AppIndicator extension, plus a logout after first install).
- No migrations yet. If you change the schema, add a `user_version` check in `store.py`.