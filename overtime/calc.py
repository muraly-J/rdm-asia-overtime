"""Punch timeline -> sessions -> per-day summaries."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Session:
    login: datetime
    logout: datetime | None  # None = dangling (missing logout punch)

    @property
    def hours(self) -> float:
        if self.logout is None:
            return 0.0
        return (self.logout - self.login).total_seconds() / 3600.0


def collapse_punches(punches: list[datetime], tolerance_minutes: int = 2) -> list[datetime]:
    """Sort punches and collapse scanner double-taps.

    A punch within `tolerance_minutes` of the previously *kept* punch is the
    same physical punch recorded twice; keep the earliest.
    """
    tol = timedelta(minutes=tolerance_minutes)
    kept: list[datetime] = []
    for p in sorted(punches):
        if kept and p - kept[-1] <= tol:
            continue
        kept.append(p)
    return kept


def pair_sessions(punches: list[datetime]) -> list[Session]:
    """Pair a chronological punch timeline into (login, logout) sessions.

    Punches must already be collapsed and sorted. An odd count leaves the
    final punch as a dangling session with no logout.
    """
    sessions: list[Session] = []
    for i in range(0, len(punches) - 1, 2):
        sessions.append(Session(punches[i], punches[i + 1]))
    if len(punches) % 2 == 1:
        sessions.append(Session(punches[-1], None))
    return sessions
