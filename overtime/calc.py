"""Recorded in/out windows -> merged sessions -> per-day summaries."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from .rules import THRESHOLDS, day_type

# How far into the next morning a shift may run before its closing scan stops
# looking like last night's departure and starts looking like today's arrival.
NEXT_DAY_CUTOFF = time(7, 30)


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
    # local import: anomalies imports Session from us
    from .anomalies import LONG_SESSION_HOURS, day_flags

    notes = notes or {}
    all_days = sorted(dates_present | set(intervals_by_day) | set(dangling_by_day))
    # Lone scans are consumed as days are walked in order: tonight's pairing
    # removes tomorrow's closing scan before tomorrow is summarized.
    pending = {d: sorted(ts) for d, ts in dangling_by_day.items()}

    summaries: list[DaySummary] = []
    for d in all_days:
        # A session belongs to the day it started on, however late it ends: a
        # Saturday 17:00 -> Sunday 10:00 shift is 17 h of Saturday work.
        windows = list(intervals_by_day.get(d, []))
        sessions = merge_intervals(windows)
        # A stray scan that falls inside an already-closed session is a double
        # tap ("start work" then "site in" seconds apart), not a missing punch:
        # the day's hours are fully determined without it, so it is dropped.
        # A stray scan outside every closed window still withholds the day —
        # a 21:00 scan-in after a 09:00–18:00 shift may be real unrecorded work.
        unpaired = [t for t in pending.get(d, [])
                    if not any(s.login <= t <= s.logout for s in sessions)]

        # A night shift can be recorded as two lone scans on either side of
        # midnight, which would otherwise withhold both days. The last open scan
        # tonight pairs with the first lone scan before NEXT_DAY_CUTOFF tomorrow.
        after = pending.get(d + timedelta(days=1))
        if unpaired and after:
            early = [t for t in after if t.time() <= NEXT_DAY_CUTOFF]
            # Beyond LONG_SESSION_HOURS this is not one shift but two forgotten
            # scan-outs, and pairing them would invent paid hours: 06:08 to 04:00
            # the next day is 21.9 h. Refuse, and leave both days withheld.
            if early and early[0] - unpaired[-1] <= timedelta(hours=LONG_SESSION_HOURS):
                windows.append((unpaired.pop(), early[0]))
                after.remove(early[0])
                sessions = merge_intervals(windows)

        # Same double-tap forgiveness across midnight: a scan lying inside a
        # session that started yesterday is an echo of it, not a new punch.
        if after:
            pending[d + timedelta(days=1)] = [
                t for t in after
                if not any(s.login <= t <= s.logout for s in sessions)]

        sessions.extend(Session(t, None) for t in unpaired)

        dtype = day_type(d, holidays)
        worked = sum(s.hours for s in sessions)
        threshold = THRESHOLDS[dtype]
        # A start log with no end log leaves the day incomplete, so no overtime
        # is calculated for it at all - not even on the sessions that did close.
        overtime = 0.0 if unpaired else max(0.0, worked - threshold)
        flags = day_flags(sessions, had_row=d in dates_present)
        in_month = (d.year, d.month) == month
        if not in_month:
            flags.append("OUT_OF_MONTH")
        summaries.append(DaySummary(employee, d, dtype, sessions, worked, threshold,
                                    overtime, flags, in_month, notes.get(d, "")))
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
         "ot_sunday": 0.0, "ot_holiday": 0.0, "ot_total": 0.0, "anomalies": 0}
    # Sundays and public holidays share a 0 h threshold but are paid at
    # different rates, so they are reported apart.
    bucket = {"weekday": "ot_weekday", "saturday": "ot_saturday",
              "sunday": "ot_sunday", "holiday": "ot_holiday"}
    for s in summaries:
        if not s.in_month:
            continue
        t["worked"] += s.worked_hours
        ot = round(s.overtime_hours, 2)
        t[bucket[s.day_type]] += ot
        if any(f != "NO_PUNCH" for f in s.flags):
            t["anomalies"] += 1
    t["worked"] = round(t["worked"], 2)
    for k in ("ot_weekday", "ot_saturday", "ot_sunday", "ot_holiday"):
        t[k] = round(t[k], 2)
    t["ot_total"] = round(t["ot_weekday"] + t["ot_saturday"]
                          + t["ot_sunday"] + t["ot_holiday"], 2)
    return t
