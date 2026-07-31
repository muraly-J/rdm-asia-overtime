from datetime import date, datetime

from overtime.calc import month_totals, summarize_days

HOLIDAYS = {date(2026, 6, 1): "Agong's Birthday", date(2026, 6, 17): "Awal Muharram"}
JUNE = (2026, 6)


def dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def summarize(intervals, dangling=None, dates=None, month=JUNE):
    """Run one employee through the pipeline from raw in/out windows."""
    by_day: dict[date, list[tuple[datetime, datetime]]] = {}
    for a, b in intervals:
        by_day.setdefault(dt(a).date(), []).append((dt(a), dt(b)))
    dang: dict[date, list[datetime]] = {}
    for t in dangling or []:
        dang.setdefault(dt(t).date(), []).append(dt(t))
    present = {date.fromisoformat(d) for d in dates} if dates else set(by_day) | set(dang)
    return summarize_days("X", by_day, dang, present, month, HOLIDAYS)


def find(summaries, d):
    return next(s for s in summaries if s.date == d)


def test_weekday_overtime_after_9h():
    s = summarize([("2026-06-04 09:04", "2026-06-04 19:48")])
    d = find(s, date(2026, 6, 4))
    assert d.day_type == "weekday"
    assert round(d.worked_hours, 2) == 10.73
    assert round(d.overtime_hours, 2) == 1.73


def test_under_threshold_zero_ot():
    s = summarize([("2026-06-03 09:19", "2026-06-03 17:56")])
    assert find(s, date(2026, 6, 3)).overtime_hours == 0.0


def test_saturday_threshold_5h():
    s = summarize([("2026-06-06 09:35", "2026-06-06 22:39")])
    d = find(s, date(2026, 6, 6))
    assert d.day_type == "saturday"
    assert round(d.worked_hours, 2) == 13.07
    assert round(d.overtime_hours, 2) == 8.07


def test_sunday_all_hours_are_ot():
    s = summarize([("2026-06-14 09:36", "2026-06-14 19:41")])
    d = find(s, date(2026, 6, 14))
    assert d.day_type == "sunday"
    assert round(d.worked_hours, 2) == 10.08
    assert d.overtime_hours == d.worked_hours


def test_holiday_all_hours_are_ot():
    s = summarize([("2026-06-17 12:30", "2026-06-17 20:14")])
    d = find(s, date(2026, 6, 17))
    assert d.day_type == "holiday"
    assert round(d.worked_hours, 2) == 7.73
    assert d.overtime_hours == d.worked_hours


def test_overlapping_work_and_site_rows_pay_once():
    # the same day recorded twice; 9h threshold applies to the union, not the sum
    s = summarize([("2026-06-04 09:00", "2026-06-04 20:00"),
                   ("2026-06-04 11:00", "2026-06-04 20:00")])
    d = find(s, date(2026, 6, 4))
    assert d.worked_hours == 11.0
    assert d.overtime_hours == 2.0


def test_cross_midnight_belongs_to_login_date():
    # Fri 09:00 -> Sat 00:21: all Friday, 9h threshold, Saturday untouched
    s = summarize([("2026-06-19 09:00", "2026-06-20 00:21")],
                  dates=["2026-06-19", "2026-06-20"])
    fri, sat = find(s, date(2026, 6, 19)), find(s, date(2026, 6, 20))
    assert round(fri.worked_hours, 2) == 15.35
    assert round(fri.overtime_hours, 2) == 6.35
    assert sat.worked_hours == 0.0 and sat.flags == ["NO_PUNCH"]


def test_shift_belongs_to_its_start_day_however_late_it_ends():
    # Sat 17:00 -> Sun 10:00 is 17 h of Saturday work: 5 h threshold, 12 h OT.
    # Sunday is left untouched.
    s = summarize([("2026-06-06 17:00", "2026-06-07 10:00")],
                  dates=["2026-06-06", "2026-06-07"])
    sat, sun = find(s, date(2026, 6, 6)), find(s, date(2026, 6, 7))
    assert sat.day_type == "saturday"
    assert sat.worked_hours == 17.0
    assert sat.overtime_hours == 12.0
    assert sat.flags == ["LONG_SESSION"]  # over 16 h: paid, but flagged for a check
    assert sun.worked_hours == 0.0 and sun.flags == ["NO_PUNCH"]


def test_end_log_two_days_later_still_counts_on_the_start_day():
    s = summarize([("2026-06-15 17:53", "2026-06-17 08:53")])
    d = find(s, date(2026, 6, 15))
    assert round(d.worked_hours, 2) == 39.0
    assert "LONG_SESSION" in d.flags  # counted, but loudly flagged


def test_lone_scan_pays_nothing_and_is_flagged():
    # the export's 'No In/Out' rows
    s = summarize([], dangling=["2026-06-02 09:14"])
    d = find(s, date(2026, 6, 2))
    assert d.worked_hours == 0.0
    assert d.overtime_hours == 0.0
    assert "MISSING_PUNCH" in d.flags


def test_a_missing_end_log_suppresses_overtime_for_the_whole_day():
    # the day is incomplete, so no OT is calculated for it - not even on the
    # session that did close
    s = summarize([("2026-06-08 09:45", "2026-06-08 21:45")], dangling=["2026-06-08 08:20"])
    d = find(s, date(2026, 6, 8))
    assert d.worked_hours == 12.0     # hours still reported
    assert d.overtime_hours == 0.0    # but no overtime paid
    assert "MISSING_PUNCH" in d.flags


def test_out_of_month_excluded_from_totals_but_listed():
    s = summarize([("2026-07-01 04:11", "2026-07-01 14:40")])
    d = find(s, date(2026, 7, 1))
    assert d.in_month is False
    assert "OUT_OF_MONTH" in d.flags
    assert month_totals(s)["worked"] == 0.0


def test_month_totals_buckets():
    s = summarize([
        ("2026-06-04 09:04", "2026-06-04 19:48"),   # weekday OT 1.73
        ("2026-06-06 09:00", "2026-06-06 16:00"),   # saturday OT 2.0
        ("2026-06-14 10:00", "2026-06-14 14:00"),   # sunday OT 4.0
        ("2026-06-17 12:00", "2026-06-17 15:00"),   # holiday OT 3.0
    ])
    t = month_totals(s)
    assert t["ot_weekday"] == 1.73
    assert t["ot_saturday"] == 2.0
    assert t["ot_sunday_ph"] == 7.0
    assert t["ot_total"] == 10.73
    assert t["anomalies"] == 0


def test_rest_day_is_listed_but_not_an_anomaly():
    s = summarize([("2026-06-04 09:00", "2026-06-04 17:00")],
                  dates=["2026-06-04", "2026-06-07"])
    assert find(s, date(2026, 6, 7)).flags == ["NO_PUNCH"]
    assert month_totals(s)["anomalies"] == 0


def test_totals_reconcile():
    # per-day rounding: buckets must sum exactly to ot_total
    s = summarize([("2026-06-02 09:04", "2026-06-02 19:48"),
                   ("2026-06-03 09:04", "2026-06-03 19:48"),
                   ("2026-06-04 09:04", "2026-06-04 19:48")])
    t = month_totals(s)
    assert t["ot_total"] == round(t["ot_weekday"] + t["ot_saturday"] + t["ot_sunday_ph"], 2)
    assert t["ot_total"] == 5.19
