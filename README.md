# twomins

A small desktop app for the two-minute start: pick the task you're avoiding, shrink it to the
smallest physical action, run two minutes, and stop guilt-free, or keep going into flow.
Based on the video transcript in `docs/two-minute-start-transcript.txt`.

It is a starting tool, not a to-do list. It counts starts, not completions.

## How a start goes

1. **Super+T.** "What are you avoiding?" Type it messy, or pick one from *Carry on* (the few
   tasks you've touched in the last two weeks; type to find older ones). Top right: your
   starts, time and flows for the last 7 days.
2. **The actions screen.** The task name is at the top (click it to rename). Type the smallest
   next physical action. If it feels too small to count, you got it right.
   - Under two minutes? Line up one or two more in the dashed boxes.
   - ↓↑ or click to reuse an earlier action; nothing is ever dismissed.
   - Quiet hints: "Make it physical" for vague steps, "Split it" (Alt+S) for two actions in
     one. Alt+H if the step feels too big: it asks for half of it.
3. **Enter starts the timer.** "Started ✓" straight away: that's the win. The small window
   sits in the corner, always on top. N opens a notepad to offload things.
4. **The beep.** The clock keeps counting while you choose (or ignore it):
   - **Keep going**: the window turns purple and counts up silently. That's flow, and it's
     counted as its own reward.
   - **+2 min**: another round with a beep.
   - **Stop here** (⇧S or Esc): always a win.
   - **Whole task done** (⇧D, any time): five seconds to undo with U.

Tasks leave the list when they're done, when they fade (untouched for two weeks), or when you
let them go (Del in the list). History is kept either way.

## Keys
| Where | Keys |
|---|---|
| Picker | type + Enter · ↓ into list · Del let it go · Ctrl+R pick for me · Esc close |
| Actions | Enter start · Tab next box · ↓ older / ↑ newer earlier action · Alt+H smaller · Alt+S split · ⇧Tab rename · Esc back |
| Timer | N note · ⇧S or Esc stop (still counts) · ⇧D whole task done · drag to move |
| After the beep | Enter keep going (flow) · 2 another round · ⇧S stop · ⇧D done |
| After ⇧D | U undo (5 s) · Enter close now |

Stop and done need Shift, and the beep doesn't take your keyboard, so a stray key typed into
another window can't end a session. Super+T brings a running timer forward.

## Install (Fedora GNOME)
    git clone git@github.com:colonelkablam/twomins.git ~/Projects/twomins
    cd ~/Projects/twomins && ./install.sh

Installs system packages (asks for sudo), a venv, the app-menu entry, autostart in the tray,
and the **Super+T** hotkey (change it: `TWOMIN_KEY='<Super><Shift>t' ./install.sh`). The tray
icon needs the AppIndicator extension, which the installer adds: log out and back in once,
then run `./install.sh` again.

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
