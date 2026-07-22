from datetime import date, datetime

from overtime.calc import month_totals, summarize_month

HOLIDAYS = {date(2026, 6, 1): "Agong's Birthday", date(2026, 6, 17): "Awal Muharram"}
JUNE = (2026, 6)


def dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def find(summaries, d):
    return next(s for s in summaries if s.date == d)


def test_weekday_overtime_after_9h():
    # in 09:04 out 19:48 = 10.73h -> OT 1.73
    s = summarize_month("X", [dt("2026-06-04 09:04"), dt("2026-06-04 19:48")],
                        {date(2026, 6, 4)}, JUNE, HOLIDAYS)
    d = find(s, date(2026, 6, 4))
    assert d.day_type == "weekday"
    assert round(d.worked_hours, 2) == 10.73
    assert round(d.overtime_hours, 2) == 1.73


def test_under_threshold_zero_ot():
    s = summarize_month("X", [dt("2026-06-03 09:19"), dt("2026-06-03 17:56")],
                        {date(2026, 6, 3)}, JUNE, HOLIDAYS)
    assert find(s, date(2026, 6, 3)).overtime_hours == 0.0


def test_saturday_threshold_5h():
    s = summarize_month("X", [dt("2026-06-06 09:35"), dt("2026-06-06 22:39")],
                        {date(2026, 6, 6)}, JUNE, HOLIDAYS)
    d = find(s, date(2026, 6, 6))
    assert d.day_type == "saturday"
    assert round(d.overtime_hours, 2) == round(d.worked_hours - 5.0, 2)


def test_sunday_all_hours_are_ot():
    s = summarize_month("X", [dt("2026-06-14 09:36"), dt("2026-06-14 19:41")],
                        {date(2026, 6, 14)}, JUNE, HOLIDAYS)
    d = find(s, date(2026, 6, 14))
    assert d.day_type == "sunday"
    assert d.overtime_hours == d.worked_hours


def test_holiday_all_hours_are_ot():
    # Awal Muharram, Wed 17 June
    s = summarize_month("X", [dt("2026-06-17 12:30"), dt("2026-06-17 20:14")],
                        {date(2026, 6, 17)}, JUNE, HOLIDAYS)
    d = find(s, date(2026, 6, 17))
    assert d.day_type == "holiday"
    assert d.overtime_hours == d.worked_hours


def test_cross_midnight_belongs_to_login_date():
    # Fri 09:00 -> Sat 00:21: all Friday, 9h threshold, Saturday untouched
    s = summarize_month("X", [dt("2026-06-19 09:00"), dt("2026-06-20 00:21")],
                        {date(2026, 6, 19), date(2026, 6, 20)}, JUNE, HOLIDAYS)
    fri, sat = find(s, date(2026, 6, 19)), find(s, date(2026, 6, 20))
    assert round(fri.worked_hours, 2) == 15.35
    assert round(fri.overtime_hours, 2) == 6.35
    assert sat.worked_hours == 0.0 and sat.flags == ["NO_PUNCH"]


def test_dangling_session_zero_hours_flagged():
    s = summarize_month("X", [dt("2026-06-02 09:00")], {date(2026, 6, 2)}, JUNE, HOLIDAYS)
    d = find(s, date(2026, 6, 2))
    assert d.worked_hours == 0.0
    assert "MISSING_PUNCH" in d.flags


def test_out_of_month_excluded_from_totals_but_listed():
    s = summarize_month("X", [dt("2026-07-01 04:11"), dt("2026-07-01 14:40")],
                        {date(2026, 7, 1)}, JUNE, HOLIDAYS)
    d = find(s, date(2026, 7, 1))
    assert d.in_month is False
    assert "OUT_OF_MONTH" in d.flags
    assert month_totals(s)["worked"] == 0.0


def test_month_totals_buckets():
    punches = [
        dt("2026-06-04 09:04"), dt("2026-06-04 19:48"),   # weekday OT 1.73
        dt("2026-06-06 09:00"), dt("2026-06-06 16:00"),   # saturday OT 2.0
        dt("2026-06-14 10:00"), dt("2026-06-14 14:00"),   # sunday OT 4.0
        dt("2026-06-17 12:00"), dt("2026-06-17 15:00"),   # holiday OT 3.0
    ]
    days = {date(2026, 6, 4), date(2026, 6, 6), date(2026, 6, 14), date(2026, 6, 17)}
    t = month_totals(summarize_month("X", punches, days, JUNE, HOLIDAYS))
    assert t["ot_weekday"] == 1.73
    assert t["ot_saturday"] == 2.0
    assert t["ot_sunday_ph"] == 7.0
    assert t["ot_total"] == 10.73
    assert t["anomalies"] == 0


def test_evening_out_next_morning_flagged_not_paid():
    # login on a day whose out-punch is missing; next scan is next morning
    punches = [dt("2026-06-08 08:43"), dt("2026-06-08 18:45"), dt("2026-06-09 08:56")]
    s = summarize_month("X", punches, {date(2026, 6, 8), date(2026, 6, 9)}, JUNE, HOLIDAYS)
    d9 = find(s, date(2026, 6, 9))
    assert "MISSING_PUNCH" in d9.flags
    assert d9.worked_hours == 0.0


def test_totals_reconcile():
    # per-day rounding: buckets must sum exactly to ot_total
    punches = [dt("2026-06-02 09:04"), dt("2026-06-02 19:48"),  # 1.7333 -> 1.73
               dt("2026-06-03 09:04"), dt("2026-06-03 19:48"),
               dt("2026-06-04 09:04"), dt("2026-06-04 19:48")]
    days = {date(2026, 6, 2), date(2026, 6, 3), date(2026, 6, 4)}
    t = month_totals(summarize_month("X", punches, days, JUNE, HOLIDAYS))
    assert t["ot_total"] == round(t["ot_weekday"] + t["ot_saturday"] + t["ot_sunday_ph"], 2)
    assert t["ot_total"] == 5.19
