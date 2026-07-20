from datetime import date, datetime

import openpyxl
import pytest

from overtime.loader import EmployeeSheet, LoaderError, load_attendance

HEADER = ["Branch", "Department", "Sect.", "Work Pattern", "Badge No.", "Name",
          "Location", "P.Pos", "Day", "Date", "Time In", "In (Map)",
          "Time Out", "Out (Map)", "Hours"]


def make_xlsx(tmp_path, rows, header=HEADER, sheet="Alice"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(header)
    ws.append(["── ALICE WONG"] + [None] * 14)  # separator row, as in the real export
    for r in rows:
        ws.append(r)
    p = tmp_path / "test.xlsx"
    wb.save(p)
    return p


def row(d, tin, tout, name="ALICE WONG BINTI X"):
    return ["RDM", "TECH", None, "Option 2", "10099", name, None, "Employee",
            d.strftime("%a"), datetime(d.year, d.month, d.day), tin, None, tout, None, None]


def test_loads_punches_and_dates(tmp_path):
    p = make_xlsx(tmp_path, [
        row(date(2026, 6, 2), datetime(2026, 6, 2, 8, 54), datetime(2026, 6, 2, 18, 55)),
        row(date(2026, 6, 3), None, None),  # no-punch day
    ])
    [emp] = load_attendance(p)
    assert isinstance(emp, EmployeeSheet)
    assert emp.short_name == "Alice"
    assert emp.full_name == "ALICE WONG BINTI X"
    assert emp.punches == [datetime(2026, 6, 2, 8, 54), datetime(2026, 6, 2, 18, 55)]
    assert emp.dates_present == {date(2026, 6, 2), date(2026, 6, 3)}


def test_duplicate_rows_yield_duplicate_punches_verbatim(tmp_path):
    # loader does NOT dedupe — that's calc.collapse_punches' job
    r = row(date(2026, 6, 2), datetime(2026, 6, 2, 8, 54), datetime(2026, 6, 2, 18, 55))
    p = make_xlsx(tmp_path, [r, r])
    [emp] = load_attendance(p)
    assert len(emp.punches) == 4


def test_bad_header_raises_with_sheet_name(tmp_path):
    p = make_xlsx(tmp_path, [], header=["Wrong"] * 15)
    with pytest.raises(LoaderError, match="Alice"):
        load_attendance(p)


def test_error_names_the_actual_row(tmp_path):
    good = row(date(2026, 6, 2), datetime(2026, 6, 2, 8, 54), datetime(2026, 6, 2, 18, 55))
    bad = row(date(2026, 6, 3), "not-a-timestamp", None)
    p = make_xlsx(tmp_path, [good, bad])  # good = row 3, bad = row 4
    with pytest.raises(LoaderError, match="row 4"):
        load_attendance(p)


def test_real_june_file_if_present():
    path = "data/June 2026.xlsx"
    import os
    if not os.path.exists(path):
        pytest.skip("real data file absent")
    sheets = load_attendance(path)
    assert len(sheets) == 12
    assert sheets[0].short_name == "an employee"
    assert all(s.punches for s in sheets)
