"""Per-day data-quality flags. Bad data is surfaced, never silently paid or dropped."""
from __future__ import annotations

from .calc import Session

LONG_SESSION_HOURS = 16.0


def day_flags(sessions: list[Session], had_row: bool) -> list[str]:
    flags: list[str] = []
    if not sessions:
        if had_row:
            flags.append("NO_PUNCH")
        return flags
    if any(s.logout is None for s in sessions):
        flags.append("MISSING_PUNCH")
    if any(s.logout is not None and s.logout == s.login for s in sessions):
        flags.append("ZERO_LENGTH")
    if any(s.hours > LONG_SESSION_HOURS for s in sessions):
        flags.append("LONG_SESSION")
    return flags
