"""Combining several uploaded exports into one record per employee.

Uploading more than one file is supported on purpose — a six-month back-fill and a
monthly export overlap by design — but only while the files agree about the days
they share. Where they disagree one of them is stale, and there is no safe way to
pick a winner, so the disagreement is refused rather than resolved.

Distinct from calc.merge_intervals, which unions overlapping windows *within* one
employee-day. This module decides whether two files may contribute to a day at all.

Note that merge_files takes ownership of the records passed to it: the first file's
EmployeeAttendance objects are mutated in place and returned.
"""
from __future__ import annotations

from datetime import date

from .calc import merge_intervals
from .loader import EmployeeAttendance, LoaderError


def _day_state(emp: EmployeeAttendance, day: date) -> tuple:
    """Everything one file says about one employee-day, in the form that gets paid.

    Compared through merge_intervals rather than as raw rows, because the export
    writes most days twice — once as 'work', once as 'site' — and how many of those
    rows a given export happens to carry is not a disagreement. In June 2026 there
    are 278 work rows against 250 site rows, so days covered by one row in one file
    and two in another are an ordinary property of this data. What must match is the
    hours the day pays, not the rows it was assembled from.

    A day with no windows at all — leave, a rest day, an absence — states ([], []),
    which is deliberately *not* the same as a day carrying hours. A file that
    retracts a day's punches therefore disagrees with one that still has them.
    """
    return (merge_intervals(emp.intervals.get(day, [])), sorted(emp.dangling.get(day, [])))


def merge_files(
    parsed: list[tuple[str, list[EmployeeAttendance]]],
) -> list[EmployeeAttendance]:
    """Fold each file's records into one list, keyed on employee name."""
    merged: dict[str, EmployeeAttendance] = {}
    for filename, records in parsed:
        for emp in records:
            existing = merged.get(emp.name)
            if existing is None:
                merged[emp.name] = emp
                continue

            # Checked before the days are, so that two same-named people are reported
            # as that rather than as a stale file that does not exist. Blank badges
            # are not a conflict: two of the real staff have no badge at all.
            if existing.badge and emp.badge and existing.badge != emp.badge:
                raise LoaderError(
                    f"{filename} gives {emp.name} badge {emp.badge}, but an earlier "
                    f"file gives badge {existing.badge} — these are probably two "
                    "different people who share a name. Upload the files one at a "
                    "time: each on its own reports the right hours for its own person.")

            # Only days both files actually cover can disagree. A day one of them
            # simply does not reach is not a contradiction, which is what makes a
            # monthly export merge cleanly into a six-month one.
            for d in sorted(existing.dates_present & emp.dates_present):
                if _day_state(existing, d) != _day_state(emp, d):
                    raise LoaderError(
                        f"{filename} disagrees with an earlier file about {emp.name} "
                        f"on {d:%d/%m/%Y} — they record different hours for that day, "
                        "so one of them is out of date. Upload one file per month, "
                        "not a correction alongside the file it corrects.")

            for d in emp.dates_present - existing.dates_present:
                if d in emp.intervals:
                    existing.intervals[d] = list(emp.intervals[d])
                if d in emp.dangling:
                    existing.dangling[d] = list(emp.dangling[d])
            existing.dates_present |= emp.dates_present
            existing.notes.update(emp.notes)
            existing.badge = existing.badge or emp.badge
    return sorted(merged.values(), key=lambda e: e.name)
