"""Pure-Python countdown. No Qt here: the UI polls `remaining()`.

Uses a monotonic clock so suspend/clock changes don't break it.
"""
from __future__ import annotations

import time
from typing import Callable

Clock = Callable[[], float]


class Countdown:
    def __init__(self, seconds: int = 120, clock: Clock = time.monotonic):
        self._clock = clock
        self.duration = float(seconds)
        self._start: float | None = None
        self.extensions = 0

    def start(self) -> None:
        self._start = self._clock()

    @property
    def running(self) -> bool:
        return self._start is not None

    def elapsed(self) -> float:
        return 0.0 if self._start is None else self._clock() - self._start

    def remaining(self) -> float:
        return max(0.0, self.duration - self.elapsed())

    def finished(self) -> bool:
        return self.running and self.remaining() <= 0

    def fraction_left(self) -> float:
        return self.remaining() / self.duration if self.duration else 0.0

    def extend(self, seconds: int = 120) -> None:
        """Keep going: add time on from *now*, even if already finished."""
        overshoot = max(0.0, self.elapsed() - self.duration)
        self.duration += overshoot + seconds
        self.extensions += 1

    @staticmethod
    def fmt(seconds: float) -> str:
        s = int(seconds + 0.999)  # round up so it shows 2:00 at the start
        return f"{s // 60}:{s % 60:02d}"
