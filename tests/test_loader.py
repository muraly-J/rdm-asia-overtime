import io
from datetime import date, datetime

import pytest

from overtime.loader import LoaderError, load_attendance

HEADER = ("Branch,Department,Sect.,Work Pattern,Badge No.,Name,Location,P.Pos,Day,Date,"
          "Time In,In (Map),Time Out,Out (Map),Hours,Group,Leave,Remark")
BANNER = "── ALICE WONG [Badge: 10099] | TECHNICAL | RDM_HQ,,,,,,,,,,,,,,,,,"


def row(d: str, tin: str, tout: str, *, name="ALICE WONG BINTI X", badge="10099",
        group="work", leave="", remark="", day=None):
    day = day or datetime.strptime(d, "%d/%m/%Y").strftime("%a")
    return (f"RDM_HQ,TECHNICAL,,Option 2,{badge},{name},,Employee,{day},{d},"
            f"{tin},,{tout},,0:00,{group},{leave},{remark}")


def csv_file(*lines, header=HEADER, bom=False):
    text = "\n".join((header, *lines)) + "\n"
    return io.BytesIO((("﻿" if bom else "") + text).encode("utf-8"))


def test_reads_a_paired_row():
    emps = load_attendance(csv_file(BANNER, row("5/1/2026", "5/1/2026 8:56", "5/1/2026 17:30")))
    assert len(emps) == 1
    emp = emps[0]
    assert emp.name == "ALICE WONG BINTI X"
    assert emp.badge == "10099"
    assert emp.intervals == {
        date(2026, 1, 5): [(datetime(2026, 1, 5, 8, 56), datetime(2026, 1, 5, 17, 30))]}
    assert emp.dates_present == {date(2026, 1, 5)}


def test_banner_and_blank_rows_are_skipped():
    emps = load_attendance(csv_file(
        BANNER, ",,,,,,,,,,,,,,,,,",
        row("5/1/2026", "5/1/2026 8:56", "5/1/2026 17:30")))
    assert len(emps) == 1
    assert len(emps[0].intervals[date(2026, 1, 5)]) == 1


def test_bom_is_stripped():
    emps = load_attendance(csv_file(
        row("5/1/2026", "5/1/2026 8:56", "5/1/2026 17:30"), bom=True))
    assert emps[0].name == "ALICE WONG BINTI X"


def test_dates_are_day_first():
    # 5/1/2026 is 5 January, not 1 May
    emps = load_attendance(csv_file(row("5/1/2026", "5/1/2026 8:56", "5/1/2026 17:30")))
    assert list(emps[0].intervals) == [date(2026, 1, 5)]


def test_day_column_mismatch_is_rejected():
    # 5/1/2026 is a Monday; a Day column saying Fri means the export changed format
    with pytest.raises(LoaderError, match="Day column"):
        load_attendance(csv_file(
            row("5/1/2026", "5/1/2026 8:56", "5/1/2026 17:30", day="Fri")))


def test_missing_column_is_rejected():
    with pytest.raises(LoaderError, match="missing expected column"):
        load_attendance(csv_file("RDM,x", header="Branch,Nickname"))


def test_work_and_site_rows_both_kept_for_the_day():
    emps = load_attendance(csv_file(
        row("5/1/2026", "5/1/2026 8:56", "5/1/2026 23:44", group="work"),
        row("5/1/2026", "5/1/2026 10:28", "5/1/2026 23:44", group="site")))
    assert len(emps[0].intervals[date(2026, 1, 5)]) == 2


def test_no_in_out_row_becomes_a_dangling_scan():
    # the export writes a lone scan as Time In == Time Out
    emps = load_attendance(csv_file(
        row("20/1/2026", "20/1/2026 9:14", "20/1/2026 9:14", remark="No In/Out")))
    emp = emps[0]
    assert emp.intervals == {}
    assert emp.dangling == {date(2026, 1, 20): [datetime(2026, 1, 20, 9, 14)]}


def test_rest_day_row_has_no_times_but_marks_the_date():
    emps = load_attendance(csv_file(row("3/1/2026", "", "", remark="Rest day")))
    emp = emps[0]
    assert emp.intervals == {} and emp.dangling == {}
    assert emp.dates_present == {date(2026, 1, 3)}
    assert emp.notes[date(2026, 1, 3)] == "Rest day"


def test_leave_and_remark_are_captured_as_a_note():
    emps = load_attendance(csv_file(row("2/1/2026", "", "", leave="AL ", remark="Leave")))
    assert emps[0].notes[date(2026, 1, 2)] == "AL Leave"


def test_vendor_overtime_total_is_not_reported():
    # the export's own OT figure is computed on different rules; showing it beside
    # ours puts two overtime numbers on one line
    emps = load_attendance(csv_file(
        row("5/1/2026", "5/1/2026 8:56", "5/1/2026 20:30", remark="Overtime 218 Min")))
    assert emps[0].notes == {}


def test_vendor_overtime_stripped_but_the_rest_of_the_remark_kept():
    emps = load_attendance(csv_file(
        row("9/1/2026", "9/1/2026 8:53", "9/1/2026 17:42", remark="Below Duration Overtime 61 Min")))
    assert emps[0].notes[date(2026, 1, 9)] == "Below Duration"


def test_pipe_separated_remark_splits_into_phrases():
    emps = load_attendance(csv_file(
        row("28/2/2026", "28/2/2026 9:44", "28/2/2026 14:32",
            remark="No WorkPattern | >Rest day")))
    assert emps[0].notes[date(2026, 2, 28)] == "No WorkPattern, >Rest day"


def test_same_remark_on_work_and_site_rows_is_not_repeated():
    emps = load_attendance(csv_file(
        row("9/1/2026", "9/1/2026 8:53", "9/1/2026 17:42", group="work", remark="Below Duration"),
        row("9/1/2026", "9/1/2026 16:52", "9/1/2026 17:42", group="site", remark="Below Duration")))
    assert emps[0].notes[date(2026, 1, 9)] == "Below Duration"


def test_distinct_remarks_on_one_day_are_both_kept():
    emps = load_attendance(csv_file(
        row("20/1/2026", "20/1/2026 9:14", "20/1/2026 9:14", group="work", remark="No In/Out"),
        row("20/1/2026", "20/1/2026 10:00", "20/1/2026 18:00", group="site",
            remark="Below Duration")))
    assert emps[0].notes[date(2026, 1, 20)] == "No In/Out, Below Duration"


def test_half_open_row_is_rejected():
    with pytest.raises(LoaderError, match="only one of Time In"):
        load_attendance(csv_file(row("5/1/2026", "5/1/2026 8:56", "")))


def test_reversed_row_is_rejected():
    with pytest.raises(LoaderError, match="before clocking in"):
        load_attendance(csv_file(row("5/1/2026", "5/1/2026 17:30", "5/1/2026 8:56")))


def test_employees_identified_by_name_not_badge():
    # two staff in the real export have no badge number at all
    emps = load_attendance(csv_file(
        row("5/1/2026", "5/1/2026 8:56", "5/1/2026 17:30", name="NO BADGE PERSON", badge=""),
        row("6/1/2026", "6/1/2026 8:56", "6/1/2026 17:30", name="NO BADGE PERSON", badge="")))
    assert len(emps) == 1
    assert emps[0].badge == ""
    assert emps[0].dates_present == {date(2026, 1, 5), date(2026, 1, 6)}


def test_row_number_in_error_is_the_real_csv_row():
    with pytest.raises(LoaderError, match="row 4"):
        load_attendance(csv_file(
            BANNER,
            row("5/1/2026", "5/1/2026 8:56", "5/1/2026 17:30"),
            row("6/1/2026", "not a timestamp", "6/1/2026 17:30")))
