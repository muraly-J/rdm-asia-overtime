"""Two uploads may cover the same day, but only while they agree about it."""
import io
from pathlib import Path

import pytest

from overtime.calc import merge_intervals
from overtime.loader import LoaderError, load_attendance
from overtime.merge import merge_files

HEADER = ("Branch,Department,Sect.,Work Pattern,Badge No.,Name,Location,P.Pos,Day,Date,"
          "Time In,In (Map),Time Out,Out (Map),Hours,Group,Leave,Remark")


def one_day(tin: str, tout: str, *, name="ALICE WONG", badge="10099",
            d="3/6/2026", day="Wed", group="work", remark=""):
    line = (f"RDM_HQ,TECH,,Opt2,{badge},{name},,Employee,{day},{d},"
            f"{d + ' ' + tin if tin else ''},,{d + ' ' + tout if tout else ''},,"
            f"0:00,{group},,{remark}")
    return load_attendance(io.BytesIO((HEADER + "\n" + line + "\n").encode()))


def lone_scan(at: str = "8:00", **kw):
    """The export writes a missing scan-out as Time In == Time Out."""
    return one_day(at, at, remark="No In/Out", **kw)


def no_punches(**kw):
    """A day the file reports but with no clock times — leave, rest day, absence."""
    return one_day("", "", group="", remark="Absent", **kw)


def two_rows(name="ALICE WONG", d="3/6/2026", day="Wed"):
    """The same day written twice, as 'work' and 'site' — the normal export shape."""
    lines = [f"RDM_HQ,TECH,,Opt2,10099,{name},,Employee,{day},{d},"
             f"{d} 8:00,,{d} 17:30,,0:00,work,,",
             f"RDM_HQ,TECH,,Opt2,10099,{name},,Employee,{day},{d},"
             f"{d} 8:05,,{d} 17:25,,0:00,site,,"]
    return load_attendance(io.BytesIO((HEADER + "\n" + "\n".join(lines) + "\n").encode()))


def hours(merged):
    """Hours as they are actually paid: the work/site windows unioned, not summed."""
    return {e.name: round(sum(s.hours for ivs in e.intervals.values()
                              for s in merge_intervals(ivs)), 2)
            for e in merged}


def test_the_same_file_twice_changes_nothing():
    once = merge_files([("june.csv", one_day("8:00", "17:30"))])
    twice = merge_files([("june.csv", one_day("8:00", "17:30")),
                         ("june.csv", one_day("8:00", "17:30"))])
    assert hours(twice) == hours(once) == {"ALICE WONG": 9.5}


def test_a_stale_file_beside_its_correction_is_refused():
    # unioned instead, the longer window wins and pays 6 h of overtime for 0.5 h
    with pytest.raises(LoaderError, match="disagrees with an earlier file"):
        merge_files([("june.csv", one_day("8:00", "23:00")),
                     ("june corrected.csv", one_day("8:00", "17:30"))])


def test_the_refusal_names_the_file_the_employee_and_the_day():
    with pytest.raises(LoaderError) as e:
        merge_files([("june.csv", one_day("8:00", "23:00")),
                     ("june corrected.csv", one_day("8:00", "17:30"))])
    assert "june corrected.csv" in str(e.value)
    assert "ALICE WONG" in str(e.value)
    assert "03/06/2026" in str(e.value)


def test_disagreement_is_refused_whichever_order_the_files_arrive_in():
    with pytest.raises(LoaderError):
        merge_files([("b.csv", one_day("8:00", "17:30")),
                     ("a.csv", one_day("8:00", "23:00"))])


def test_three_identical_files_still_merge():
    m = merge_files([(f"{i}.csv", one_day("8:00", "17:30")) for i in range(3)])
    assert hours(m) == {"ALICE WONG": 9.5}


def test_different_days_from_different_files_combine():
    m = merge_files([("a.csv", one_day("8:00", "17:30", d="3/6/2026", day="Wed")),
                     ("b.csv", one_day("8:00", "17:30", d="4/6/2026", day="Thu"))])
    assert hours(m) == {"ALICE WONG": 19.0}


REAL = [Path("data/June 2026.csv"), Path("data/Attendance All Staffs (Jan-June'26).csv")]


@pytest.mark.skipif(not all(p.exists() for p in REAL), reason="real exports absent")
def test_the_two_real_overlapping_exports_do_not_disagree():
    """The monthly and six-month exports share June by design — 278 employee-days.

    The guard must refuse only on disagreement, never on mere overlap, or it would
    hard-stop the multi-file upload the app documents.
    """
    from overtime.calc import month_totals, summarize_employee
    from overtime.rules import load_holidays

    hols = load_holidays("holidays.yml")
    june_only = merge_files([(REAL[0].name, load_attendance(REAL[0]))])
    both = merge_files([(p.name, load_attendance(p)) for p in REAL])
    assert len(both) == 12

    # merging the six-month export in must not move a single June figure
    def june(staff):
        return {e.name: month_totals(summarize_employee(e, (2026, 6), hols))
                for e in staff}
    assert june(both) == june(june_only)


# --- the shapes a day can disagree in, beyond differing clock times ----------

@pytest.mark.parametrize("order", ["stale first", "corrected first"])
def test_a_lone_scan_corrected_in_a_later_export_is_refused(order):
    """The correction the app's own flag legend tells her to make.

    The stale file files the day under `dangling`, the corrected one under
    `intervals`. Comparing each store separately sees no collision, merges both,
    and calc then withholds the whole day's overtime — so she fixes the scan,
    uploads the fix, and is told the scan is still missing.
    """
    files = [("stale.csv", lone_scan()), ("corrected.csv", one_day("8:00", "23:00"))]
    if order == "corrected first":
        files.reverse()
    with pytest.raises(LoaderError, match="different hours"):
        merge_files(files)


@pytest.mark.parametrize("order", ["stale first", "corrected first"])
def test_a_day_retracted_to_leave_in_a_later_export_is_refused(order):
    """The silent over-pay: the corrected file has the day with no punches at all.

    Neither store holds the day in the corrected file, so nothing collides and the
    stale hours are paid in full with no anomaly raised.
    """
    files = [("stale.csv", one_day("8:00", "23:00")), ("corrected.csv", no_punches())]
    if order == "corrected first":
        files.reverse()
    with pytest.raises(LoaderError, match="different hours"):
        merge_files(files)


def test_two_files_covering_a_day_with_different_row_counts_still_merge():
    """work+site in one file and work-only in the other pay identically.

    Per-file variation in site coverage is ordinary — June 2026 has 278 work rows
    against 250 site rows — so refusing here would hard-stop a legitimate upload.
    """
    m = merge_files([("full.csv", two_rows()), ("work only.csv", one_day("8:00", "17:30"))])
    assert hours(m) == {"ALICE WONG": 9.5}


def test_two_people_sharing_a_name_across_files_are_refused():
    with pytest.raises(LoaderError, match="two different people who share a name"):
        merge_files([("a.csv", one_day("8:00", "20:00", badge="10099")),
                     ("b.csv", one_day("8:00", "20:00", badge="10200", d="4/6/2026",
                                       day="Thu"))])


def test_a_blank_badge_in_one_file_is_not_a_collision():
    m = merge_files([("a.csv", one_day("8:00", "17:30", badge="")),
                     ("b.csv", one_day("8:00", "17:30", badge="10099"))])
    assert m[0].badge == "10099"


def test_rest_days_agreeing_across_files_still_merge():
    m = merge_files([("a.csv", no_punches()), ("b.csv", no_punches())])
    assert hours(m) == {"ALICE WONG": 0.0}
