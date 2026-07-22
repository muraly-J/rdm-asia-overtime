"""Punch timeline -> sessions -> per-day summaries."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .rules import THRESHOLDS, day_type


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


def pair_sessions(punches: list[datetime], carryover_before_hour: int = 6) -> list[Session]:
    """Pair a chronological punch timeline into (login, logout) sessions.

    Punches must already be collapsed and sorted. Punches are paired
    login/logout in order, but a pairing across midnight is only allowed
    when the logout falls before `carryover_before_hour` on the next day
    (a genuine overnight shift). Otherwise the next punch belongs to a new
    day's session and the current punch dangles with no logout - this
    prevents an evening clock-out from spuriously pairing with the
    following morning's (or a later day's) clock-in after a missed punch.
    An unpaired final punch leaves a dangling session with no logout.
    """
    sessions: list[Session] = []
    i = 0
    while i < len(punches):
        a = punches[i]
        if i + 1 < len(punches):
            b = punches[i + 1]
            same_day = b.date() == a.date()
            carry = b.date() == a.date() + timedelta(days=1) and b.hour < carryover_before_hour
            if same_day or carry:
                sessions.append(Session(a, b))
                i += 2
                continue
        sessions.append(Session(a, None))
        i += 1
    return sessions


@dataclass
class DaySummary:
    employee: str
    date: date
    day_type: str
    sessions: list[Session]
    worked_hours: float
    threshold: float
    overtime_hours: float
    flags: list[str] = field(default_factory=list)
    in_month: bool = True


def summarize_month(
    employee: str,
    punches: list[datetime],
    dates_present: set[date],
    month: tuple[int, int],
    holidays: dict[date, str],
) -> list[DaySummary]:
    """Full pipeline for one employee: collapse -> pair -> attribute -> classify."""
    from .anomalies import day_flags  # local import: anomalies imports Session from us

    sessions = pair_sessions(collapse_punches(punches))
    by_day: dict[date, list[Session]] = {}
    for s in sessions:
        by_day.setdefault(s.login.date(), []).append(s)

    summaries: list[DaySummary] = []
    for d in sorted(dates_present | set(by_day)):
        day_sessions = by_day.get(d, [])
        dtype = day_type(d, holidays)
        worked = sum(s.hours for s in day_sessions)
        threshold = THRESHOLDS[dtype]
        ot = max(0.0, worked - threshold)
        flags = day_flags(day_sessions, had_row=d in dates_present)
        in_month = (d.year, d.month) == month
        if not in_month:
            flags.append("OUT_OF_MONTH")
        summaries.append(DaySummary(employee, d, dtype, day_sessions,
                                    worked, threshold, ot, flags, in_month))
    return summaries


def month_totals(summaries: list[DaySummary]) -> dict:
    """Aggregate one employee's month. Out-of-month days are excluded."""
    t = {"worked": 0.0, "ot_weekday": 0.0, "ot_saturday": 0.0,
         "ot_sunday_ph": 0.0, "ot_total": 0.0, "anomalies": 0}
    bucket = {"weekday": "ot_weekday", "saturday": "ot_saturday",
              "sunday": "ot_sunday_ph", "holiday": "ot_sunday_ph"}
    for s in summaries:
        if not s.in_month:
            continue
        t["worked"] += s.worked_hours
        ot = round(s.overtime_hours, 2)
        t[bucket[s.day_type]] += ot
        if any(f != "NO_PUNCH" for f in s.flags):
            t["anomalies"] += 1
    t["worked"] = round(t["worked"], 2)
    for k in ("ot_weekday", "ot_saturday", "ot_sunday_ph"):
        t[k] = round(t[k], 2)
    t["ot_total"] = round(t["ot_weekday"] + t["ot_saturday"] + t["ot_sunday_ph"], 2)
    return t
