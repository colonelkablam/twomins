# twomins

A small desktop app for the two-minute start: pick the task you're avoiding, shrink it to the
smallest physical action, run two minutes, and stop guilt-free, or keep going into flow.
Based on the video transcript in `docs/two-minute-start-transcript.txt`.

It is a starting tool, not a to-do list. It counts starts, not completions.

## How a start goes

1. **Super+T.** "What are you avoiding?" Type it messy, or pick one from the list (the few
   tasks you've touched in the last two weeks; type to find older ones). Top right: your
   starts, time and flows for the last 7 days.
   - **At work** (switch, Alt+W, or the tray menu): shows only work tasks; unticked you
     see only personal ones. It starts unticked every time the app starts, and unticks itself
     after the laptop has slept for 4+ hours. **See all** (Alt+A) shows both, just this once.
2. **The actions screen.** The task name is at the top (click it to rename), with a
   Personal/Work chip next to it (click or Alt+W to move the task to the other side). Type the smallest
   next physical action. If it feels too small to count, you got it right.
   - Under two minutes? Line up one or two more in the dashed boxes.
   - ↓↑ or click to reuse an earlier action. F2 renames it (typos), ⇧Del hides it from
     the list; right-click for both. Hidden or renamed, its time still counts.
   - Quiet hints: "Make it physical" for vague steps, "Split it" (Alt+S) for two actions in
     one. Alt+H if the step feels too big: it asks for half of it.
3. **Enter starts the timer.** "Started ✓" straight away: that's the win. The small window
   sits in the corner, always on top. N opens a notepad to offload things.
4. **The beep.** The clock keeps counting while you choose (or ignore it):
   - **Keep going**: the window turns purple and counts up silently. That's flow, and it's
     counted as its own reward.
   - **+2 min**: another round with a beep.
   - **Stop for now** (Esc): always a win. The task stays in your list for next time.
   - **Whole task done** (⇧D, any time): five seconds to undo with U.

Tasks leave the list when they're done, when they fade (untouched for two weeks), or when you
let them go (⇧Del in the list). History is kept either way.

## Keys

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

Stop is Esc, done needs Shift (⇧D), and the beep doesn't take your keyboard, so a stray key
typed into another window can't end a session. Super+T brings a running timer forward.

## Install
    git clone git@github.com:colonelkablam/twomins.git ~/Projects/twomins
    cd ~/Projects/twomins && ./install.sh

Installs system packages (asks for sudo), a venv, the app-menu entry, autostart in the tray,
and the **Super+T** hotkey (change it: `TWOMIN_KEY='<Super><Shift>t' ./install.sh`).

| | Packages | Super+T and tray | Checked |
|---|---|---|---|
| **Fedora** (38+), GNOME | automatic (dnf) | automatic. Tray: log out and back in once after the first install, then run `./install.sh` again | daily use; container test |
| **Ubuntu** (24.04+), GNOME | automatic (apt) | automatic. Ubuntu's tray support is built in | container test |
| Ubuntu 22.04 | | | not supported (Python 3.10; needs 3.11+) |
| Other distros or desktops | skipped, with a list of what to install | menu and autostart work everywhere; set the shortcut by hand (the installer prints the command) | not yet |

## Update
    cd ~/Projects/twomins && git pull
    .venv/bin/twomin --quit; setsid -f .venv/bin/twomin --tray >/dev/null 2>&1

The install is editable, so a restart picks up new code. The database upgrades itself on
first launch. Re-run `./install.sh` only if the installer itself changed.

Quick test without waiting two minutes: `.venv/bin/twomin --quit; .venv/bin/twomin --seconds 10`
(then restart the tray as above).

## Config and data
- `~/.config/twomin/config.toml`: `seconds = 120`
- `~/.local/share/twomin/twomin.db`: SQLite (tasks, sessions, notes)
- Font: Atkinson Hyperlegible Next, bundled (`twomin/assets/`, SIL Open Font License)

## Development
    .venv/bin/python tests/test_core.py

See `CLAUDE.md` for architecture, design principles and the roadmap.
