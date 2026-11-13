# Two-Minute Start

A tiny desktop app for the two-minute start: pick the task you're avoiding, shrink it to
the smallest physical action, run two minutes, and stop guilt-free (or keep going).

## Install (Fedora GNOME)
    unzip twomin.zip -d ~/dev && cd ~/dev/twomin && ./install.sh

Hotkey: **Super+T** (change: `TWOMIN_KEY='<Super><Shift>t' ./install.sh`).
Tray icon needs the AppIndicator extension, which the installer adds. Log out and back in once.

## Keys
| Where | Keys |
|---|---|
| Picker | type a task + Enter · ↓ into list · Ctrl+R pick for me · Esc close |
| Shrink | Enter start · Tab next step · ↑/↓ earlier steps · Esc back |
| Timer | N note · Esc stop (still counts) · drag to move |
| Finish | Enter keep going · S stop here · D whole task done |

## Config
`~/.config/twomin/config.toml`:

    seconds = 120

## Layout
    twomin/core/   timer, models, SQLite store (no Qt; tested in tests/)
    twomin/ui/     popup (pick → shrink), mini timer, style
    twomin/app.py  wires it together + tray
    twomin/__main__.py  CLI + single-instance IPC

Data: `~/.local/share/twomin/twomin.db` (`sqlite3` it for stats).
Run tests: `.venv/bin/python tests/test_core.py`
