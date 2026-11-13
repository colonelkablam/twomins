"""Gentle checks on a step as it's typed. No Qt; used by the actions screen for quiet hints.

From the transcript: a step should be "something specific and concrete, not 'work on it'",
and "if that step takes less than two minutes, line up one or two more". These only ever
produce a hint the person may ignore; nothing here blocks starting.
"""
from __future__ import annotations

import re

# Verbs that describe the whole pile rather than what your hands do.
_VAGUE = re.compile(
    r"^\s*(work on|working on|sort out|sort|deal with|plan|finish|do|organi[sz]e|figure out|"
    r"think about|look into|handle|tackle|get on with|make progress on|progress)\b",
    re.IGNORECASE,
)

# Where one action ends and the next begins, most specific first.
_JOINS = (" and then ", ", then ", "; then ", " then ", " and ", "; ", ", ")


def is_vague(step: str) -> bool:
    return bool(_VAGUE.match(step))


def split_step(step: str) -> tuple[str, str] | None:
    """'search garages and book one' -> ('search garages', 'book one'), else None."""
    low = step.lower()
    for join in _JOINS:
        i = low.find(join)
        if i > 0:
            left, right = step[:i].strip(" ,;"), step[i + len(join):].strip(" ,;")
            if right.lower().startswith("then "):
                right = right[5:]
            if len(left) >= 3 and len(right) >= 3:
                return left, right
    return None
