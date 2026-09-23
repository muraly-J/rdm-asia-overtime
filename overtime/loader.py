"""Read the biometric attendance export: one CSV covering all staff.

Columns: Branch, Department, Sect., Work Pattern, Badge No., Name, Location,
P.Pos, Day, Date, Time In, In (Map), Time Out, Out (Map), Hours, Group, Leave,
Remark. Dates and timestamps render in whatever format the export was configured
for - day-first (d/m/Y) and ISO (Y-m-d) have both been seen - so both are read.

Each row is one already-paired in/out window. Most employee-days appear twice,
as Group='work' and Group='site' — overlapping views of the same day, not two
separate stints — so the windows are unioned downstream rather than summed.

The vendor 'Hours' column is ignored; hours are recomputed from timestamps.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import IO, Iterable

REQUIRED_COLUMNS = ("Badge No.", "Name", "Day", "Date", "Time In", "Time Out", "Group")
BANNER_PREFIX = "──"  # per-employee header row the export injects
# Accepted renderings of one date. Deliberately excludes month-first (m/d/Y):
# it is indistinguishable from day-first on the first twelve days of every month,
# so accepting it would silently misread those dates rather than reject them. The
# Day column cross-check below is what catches an order we have not anticipated.
DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d")
DATE_LABEL = "d/m/YYYY or YYYY-MM-DD"
STAMP_FORMATS = (
    "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S",
    "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S",
    # The export can also be configured for 12-hour clocks ("08:58 AM"). The AM/PM
    # marker makes these unambiguous against the 24-hour renderings above.
    "%d/%m/%Y %I:%M %p", "%d/%m/%Y %I:%M:%S %p",
    "%Y-%m-%d %I:%M %p", "%Y-%m-%d %I:%M:%S %p",
)
STAMP_LABEL = "'d/m/YYYY H:MM' or 'YYYY-MM-DD H:MM', 24-hour or with AM/PM"

# The export's remarks carry the vendor's own overtime total, e.g. "Overtime 218
# Min". It is computed on different rules from ours - it pays hours outside the
# rostered shift rather than hours past a daily threshold - so reporting it beside
# our figure puts two different overtime numbers on one line with nothing to say
# which one payroll should pay. Strip it; keep the descriptive rest of the remark.
VENDOR_OVERTIME = re.compile(r"\s*Overtime \d+ Min\s*")


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


class _StampParser:
    """Parses one column's timestamps, tolerating whichever format the export used.

    An export renders every row the same way, so the format that worked last is
    tried first and the rest are only reached on the first row of a file.
    """

    def __init__(self, formats: tuple[str, ...], label: str) -> None:
        self._formats = formats
        self._label = label
        self._preferred = formats[0]

    def parse(self, value: str, row_no: int, column: str) -> datetime:
        text = value.strip()
        for fmt in (self._preferred, *self._formats):
            try:
                parsed = datetime.strptime(text, fmt)
            except ValueError:
                continue
            self._preferred = fmt
            return parsed
        raise LoaderError(
            f"row {row_no}: unparseable {column} {text!r} (expected {self._label})")


def note_atoms(leave: str, remark: str) -> list[str]:
    """Split one row's Leave/Remark into descriptive phrases, dropping vendor overtime.

    The remark packs several phrases into one field separated by '|', and may
    append the vendor's overtime total to one of them ("Below Duration Overtime
    61 Min"). Returns the phrases worth showing, in order; a row whose only
    content was the overtime total returns nothing.
    """
    out: list[str] = []
    for part in remark.split("|"):
        cleaned = VENDOR_OVERTIME.sub(" ", part).strip()
        if cleaned:
            out.append(cleaned)
    leave = leave.strip()
    if leave:
        # the code qualifies the remark it came with: "AL" + "Leave" -> "AL Leave"
        out[:1] = [f"{leave} {out[0]}"] if out else [leave]
    return out


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
    dates = _StampParser(DATE_FORMATS, DATE_LABEL)
    stamps = _StampParser(STAMP_FORMATS, STAMP_LABEL)
    # Phrases per employee-day, deduplicated: the work and site rows of one day
    # usually repeat the same remark, and printing it twice reads as two findings.
    atoms: dict[tuple[str, date], list[str]] = {}
    echoes: list[tuple[int, str, date, datetime, datetime]] = []
    for row in reader:
        # the file's own line number, so it matches the row a spreadsheet shows:
        # counting records instead drifts once the export has blank lines in it
        row_no = reader.line_num
        if str(row.get("Branch") or "").startswith(BANNER_PREFIX):
            continue
        name = (row.get("Name") or "").strip()
        if not name:
            # Padding rows are empty and harmless; one carrying clock times is a
            # worked day that cannot be credited to anybody, so it must not vanish.
            if (row.get("Time In") or "").strip() or (row.get("Time Out") or "").strip():
                raise LoaderError(
                    f"row {row_no}: a row with clock times has no Name, so its hours "
                    "cannot be credited to anyone")
            continue  # blank padding row

        d = dates.parse(row["Date"], row_no, "date").date()
        # The weekday is the guard on the parse above: read a date in the wrong
        # order and this disagrees, so an export in an unanticipated format fails
        # loudly here rather than quietly moving hours into the wrong month.
        weekday = (row.get("Day") or "").strip()
        if not weekday:
            raise LoaderError(
                f"row {row_no}: the Day column is empty — it is the cross-check that "
                f"makes {row['Date'].strip()!r} safe to read in more than one date format")
        if weekday.lower() not in (d.strftime("%a").lower(), d.strftime("%A").lower()):
            raise LoaderError(
                f"row {row_no}: date {row['Date'].strip()} is a {d:%a} but the Day column "
                f"says {weekday} — the export's date format may have changed")

        emp = employees.setdefault(name, EmployeeAttendance(name=name))
        badge = (row.get("Badge No.") or "").strip()
        # Employees are keyed on name, so two people sharing one would silently
        # become one person with one set of hours. A badge that changes under a
        # name is the only evidence of that the export carries. It cannot catch a
        # collision between two staff who have no badge at all - some have none.
        if emp.badge and badge and emp.badge != badge:
            raise LoaderError(
                f"row {row_no}: {name} carries badge {badge} here but {emp.badge} "
                "earlier — probably two different people sharing a name, which this "
                "report cannot tell apart. The name needs correcting in the "
                "attendance system before the month can be paid.")
        emp.badge = emp.badge or badge
        emp.dates_present.add(d)

        seen = atoms.setdefault((name, d), [])
        for phrase in note_atoms(row.get("Leave") or "", row.get("Remark") or ""):
            if phrase not in seen:
                seen.append(phrase)

        raw_in, raw_out = (row.get("Time In") or "").strip(), (row.get("Time Out") or "").strip()
        if not raw_in and not raw_out:
            continue  # rest day, leave or absence
        if not raw_in or not raw_out:
            raise LoaderError(
                f"row {row_no}: {name} on {d:%d/%m/%Y} has only one of Time In / Time Out")

        start = stamps.parse(raw_in, row_no, "Time In")
        end = stamps.parse(raw_out, row_no, "Time Out")

        # The windows are unioned on the understanding that 'work' and 'site' are
        # two views of the same day rather than two separate stints; a third kind
        # of window would be folded into the same hours with nothing to say whether
        # that is right. One exception, seen in the real export: an echo row with a
        # blank Group (remark 'No WorkPattern'). As a lone scan (in == out) it holds
        # no hours, so it lands as a dangling scan and flags the day like any other.
        # As a full window it repeats that day's work or site row; it is checked
        # against them once the file is read, since it can come before them.
        group = (row.get("Group") or "").strip()
        if group not in ("work", "site", ""):
            raise LoaderError(
                f"row {row_no}: unrecognised Group {group!r} on a row with clock times "
                "— only 'work' and 'site' windows are known to combine")
        # A shift is charged to the day it started and the Date column decides that.
        # Were the export ever to date a night shift by the day it ended, hours would
        # move between day types - and across months - with nothing to show for it.
        if start.date() != d:
            raise LoaderError(
                f"row {row_no}: {name}'s Time In ({raw_in}) is not on the day the Date "
                f"column gives ({d:%d/%m/%Y}) — a shift is charged to the day it started")
        if end < start:
            raise LoaderError(
                f"row {row_no}: {name} on {d:%d/%m/%Y} clocks out ({raw_out}) "
                f"before clocking in ({raw_in})")
        if start == end:
            emp.dangling.setdefault(d, []).append(start)
        elif not group:
            echoes.append((row_no, name, d, start, end))
        else:
            emp.intervals.setdefault(d, []).append((start, end))

    # An echo that no work or site row of the same day covers would be hours
    # nothing else vouches for; adding them could pay time never worked twice over.
    for row_no, name, d, start, end in echoes:
        if not any(s <= start and end <= e for s, e in employees[name].intervals.get(d, [])):
            raise LoaderError(
                f"row {row_no}: {name} on {d:%d/%m/%Y} has a window with no Group that "
                "does not repeat that day's work or site record, so it is not known "
                "whether its hours should count")

    for (name, d), phrases in atoms.items():
        if phrases:
            employees[name].notes[d] = ", ".join(phrases)
    return list(employees.values())
