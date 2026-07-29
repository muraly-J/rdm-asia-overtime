"""Read the biometric attendance export: one CSV covering all staff.

Columns: Branch, Department, Sect., Work Pattern, Badge No., Name, Location,
P.Pos, Day, Date, Time In, In (Map), Time Out, Out (Map), Hours, Group, Leave,
Remark. Dates are day-first (d/m/Y); timestamps are 'd/m/Y H:M'.

Each row is one already-paired in/out window. Most employee-days appear twice,
as Group='work' and Group='site' — overlapping views of the same day, not two
separate stints — so the windows are unioned downstream rather than summed.

The vendor 'Hours' column is ignored; hours are recomputed from timestamps.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import IO, Iterable

REQUIRED_COLUMNS = ("Badge No.", "Name", "Day", "Date", "Time In", "Time Out")
BANNER_PREFIX = "──"  # per-employee header row the export injects
DATE_FMT = "%d/%m/%Y"
STAMP_FMT = "%d/%m/%Y %H:%M"


class LoaderError(Exception):
    pass


@dataclass
class EmployeeAttendance:
    """One employee's month, as recorded rather than as interpreted.

    `intervals` holds complete in/out pairs; `dangling` holds lone scans (the
    export writes these with Time In == Time Out, remark 'No In/Out'), which
    pay nothing and are flagged downstream.
    """
    name: str
    badge: str = ""
    intervals: dict[date, list[tuple[datetime, datetime]]] = field(default_factory=dict)
    dangling: dict[date, list[datetime]] = field(default_factory=dict)
    dates_present: set[date] = field(default_factory=set)
    notes: dict[date, str] = field(default_factory=dict)


def _open_text(source: str | Path | IO[bytes] | IO[str]) -> Iterable[str]:
    """Yield decoded lines from a path, a byte stream or an already-decoded one."""
    if isinstance(source, (str, Path)):
        with open(source, encoding="utf-8-sig", newline="") as f:
            yield from f
        return
    data = source.read()
    if isinstance(data, bytes):
        data = data.decode("utf-8-sig")
    else:
        data = data.lstrip("﻿")
    yield from data.splitlines()


def _parse_date(value: str, row_no: int) -> date:
    try:
        return datetime.strptime(value.strip(), DATE_FMT).date()
    except ValueError:
        raise LoaderError(f"row {row_no}: unparseable date {value!r} (expected d/m/YYYY)") from None


def _parse_stamp(value: str, row_no: int, column: str) -> datetime:
    try:
        return datetime.strptime(value.strip(), STAMP_FMT)
    except ValueError:
        raise LoaderError(
            f"row {row_no}: unparseable {column} {value!r} (expected 'd/m/YYYY H:MM')") from None


def load_attendance(source: str | Path | IO[bytes] | IO[str]) -> list[EmployeeAttendance]:
    """Parse the attendance CSV into one record per employee, keyed on name.

    Employees are identified by name, not badge: some staff have no badge
    number in the export.
    """
    reader = csv.DictReader(_open_text(source))
    if reader.fieldnames is None:
        raise LoaderError("empty file")
    missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing:
        raise LoaderError(f"missing expected column(s): {', '.join(missing)}")

    employees: dict[str, EmployeeAttendance] = {}
    for row_no, row in enumerate(reader, start=2):  # row 1 is the header
        if str(row.get("Branch") or "").startswith(BANNER_PREFIX):
            continue
        name = (row.get("Name") or "").strip()
        if not name:
            continue  # blank padding row

        d = _parse_date(row["Date"], row_no)
        weekday = (row.get("Day") or "").strip()
        if weekday and d.strftime("%a") != weekday:
            raise LoaderError(
                f"row {row_no}: date {row['Date'].strip()} is a {d:%a} but the Day column "
                f"says {weekday} — the export's date format may have changed")

        emp = employees.setdefault(name, EmployeeAttendance(name=name))
        if not emp.badge:
            emp.badge = (row.get("Badge No.") or "").strip()
        emp.dates_present.add(d)

        note = " ".join(part for part in
                        ((row.get("Leave") or "").strip(), (row.get("Remark") or "").strip())
                        if part)
        if note and note not in emp.notes.get(d, ""):
            emp.notes[d] = f"{emp.notes[d]}; {note}" if d in emp.notes else note

        raw_in, raw_out = (row.get("Time In") or "").strip(), (row.get("Time Out") or "").strip()
        if not raw_in and not raw_out:
            continue  # rest day, leave or absence
        if not raw_in or not raw_out:
            raise LoaderError(
                f"row {row_no}: {name} on {d:%d/%m/%Y} has only one of Time In / Time Out")

        start = _parse_stamp(raw_in, row_no, "Time In")
        end = _parse_stamp(raw_out, row_no, "Time Out")
        if end < start:
            raise LoaderError(
                f"row {row_no}: {name} on {d:%d/%m/%Y} clocks out ({raw_out}) "
                f"before clocking in ({raw_in})")
        if start == end:
            emp.dangling.setdefault(d, []).append(start)
        else:
            emp.intervals.setdefault(d, []).append((start, end))

    return list(employees.values())
