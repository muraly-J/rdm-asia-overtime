"""Recorded in/out windows -> merged sessions -> per-day summaries."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .rules import THRESHOLDS, day_type

CARRYOVER_BEFORE_HOUR = 6


@dataclass(frozen=True)
class Session:
    login: datetime
    logout: datetime | None  # None = dangling (the paired scan is missing)

    @property
    def hours(self) -> float:
        if self.logout is None:
            return 0.0
        return (self.logout - self.login).total_seconds() / 3600.0


def merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[Session]:
    """Union overlapping or touching windows into non-overlapping sessions.

    The export records most days twice — once as 'work', once as 'site' — with
    the two windows overlapping. Summing them would pay the overlap twice, so
    they are unioned; windows that genuinely do not meet stay separate and add
    up as they should.
    """
    merged: list[list[datetime]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [Session(a, b) for a, b in merged]


def _within_carryover(start: datetime, end: datetime) -> bool:
    """True if `end` is a plausible clock-out for a shift starting at `start`.

    A shift may run past midnight, but only until CARRYOVER_BEFORE_HOUR the
    next morning. A later clock-out means a scan was missed, so the window is
    not treated as worked time.
    """
    if end.date() == start.date():
        return True
    return (end.date() == start.date() + timedelta(days=1)
            and end.hour < CARRYOVER_BEFORE_HOUR)


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
    note: str = ""


def summarize_days(
    employee: str,
    intervals_by_day: dict[date, list[tuple[datetime, datetime]]],
    dangling_by_day: dict[date, list[datetime]],
    dates_present: set[date],
    month: tuple[int, int],
    holidays: dict[date, str],
    notes: dict[date, str] | None = None,
) -> list[DaySummary]:
    """Full pipeline for one employee: merge -> attribute -> classify."""
    from .anomalies import day_flags  # local import: anomalies imports Session from us

    notes = notes or {}
    all_days = sorted(dates_present | set(intervals_by_day) | set(dangling_by_day))

    summaries: list[DaySummary] = []
    for d in all_days:
        paired, unpaired = [], list(dangling_by_day.get(d, []))
        for start, end in intervals_by_day.get(d, []):
            if _within_carryover(start, end):
                paired.append((start, end))
            else:
                unpaired.append(start)  # missed scan, not a multi-day shift

        sessions = merge_intervals(paired)
        sessions.extend(Session(t, None) for t in sorted(unpaired))

        dtype = day_type(d, holidays)
        worked = sum(s.hours for s in sessions)
        threshold = THRESHOLDS[dtype]
        flags = day_flags(sessions, had_row=d in dates_present)
        in_month = (d.year, d.month) == month
        if not in_month:
            flags.append("OUT_OF_MONTH")
        summaries.append(DaySummary(employee, d, dtype, sessions, worked, threshold,
                                    max(0.0, worked - threshold), flags, in_month,
                                    notes.get(d, "")))
    return summaries


def summarize_employee(
    emp,
    month: tuple[int, int],
    holidays: dict[date, str],
) -> list[DaySummary]:
    """Convenience wrapper over an EmployeeAttendance record from the loader."""
    return summarize_days(emp.name, emp.intervals, emp.dangling, emp.dates_present,
                          month, holidays, emp.notes)


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
