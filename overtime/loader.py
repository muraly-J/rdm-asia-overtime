"""Read the biometric attendance export: one sheet per employee.

Columns (1-based): E=Badge, F=Name, I=Day, J=Date, K=Time In, M=Time Out.
Row 1 header, row 2 separator, data from row 3. The Hours column is ignored;
hours are recomputed from timestamps downstream.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import IO

import openpyxl

COL_NAME = 5      # 0-based index into row tuple: F
COL_DATE = 9      # J
COL_TIME_IN = 10  # K
COL_TIME_OUT = 12 # M


class LoaderError(Exception):
    pass


@dataclass
class EmployeeSheet:
    short_name: str
    full_name: str
    punches: list[datetime] = field(default_factory=list)
    dates_present: set[date] = field(default_factory=set)


def load_attendance(source: str | Path | IO[bytes]) -> list[EmployeeSheet]:
    """Read a workbook from a path or an in-memory file object (e.g. an upload)."""
    wb = openpyxl.load_workbook(source, data_only=True, read_only=True)
    employees: list[EmployeeSheet] = []
    for ws in wb.worksheets:
        rows = ws.iter_rows(values_only=True)
        try:
            header = next(rows)
        except StopIteration:
            raise LoaderError(f"sheet {ws.title!r}: empty sheet") from None
        if len(header) <= COL_TIME_OUT or header[COL_DATE] != "Date" \
                or header[COL_TIME_IN] != "Time In" or header[COL_TIME_OUT] != "Time Out":
            raise LoaderError(
                f"sheet {ws.title!r}: unexpected header layout "
                f"(expected Date/Time In/Time Out in columns J/K/M)")
        emp = EmployeeSheet(short_name=ws.title, full_name="")
        for i, r in enumerate(rows, start=2):
            d = r[COL_DATE] if len(r) > COL_DATE else None
            if not isinstance(d, datetime):
                continue  # separator / junk row
            if not emp.full_name and isinstance(r[COL_NAME], str):
                emp.full_name = r[COL_NAME].strip()
            emp.dates_present.add(d.date())
            for col in (COL_TIME_IN, COL_TIME_OUT):
                v = r[col] if len(r) > col else None
                if isinstance(v, datetime):
                    emp.punches.append(v)
                elif v is not None:
                    raise LoaderError(
                        f"sheet {ws.title!r} row {i}: unparseable timestamp {v!r}")
        employees.append(emp)
    wb.close()
    return employees
