from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Task:
    id: int
    title: str
    last_step: str | None = None
    starts: int = 0
    seconds: int = 0          # all time on this task
    week_starts: int = 0      # last 7 days
    week_seconds: int = 0
    nudge: str | None = None  # "cut it in half?" offer: last step typed before backing out


@dataclass
class Session:
    id: int
    task_id: int
    steps: list[str]


# Outcomes — every one of them counts as a start.
DONE = "task_done"        # whole task finished
STOPPED = "stopped"       # stopped when the timer ended (that's success)
EARLY = "stopped_early"   # stopped before the beep (still started)
