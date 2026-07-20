from datetime import datetime

from overtime.calc import Session, collapse_punches, pair_sessions


def dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def test_collapse_scanner_double_tap():
    # an employee 3 June: 17:55 and 17:56 are one physical punch
    punches = [dt("2026-06-03 09:19"), dt("2026-06-03 17:55"), dt("2026-06-03 17:56")]
    assert collapse_punches(punches) == [dt("2026-06-03 09:19"), dt("2026-06-03 17:55")]


def test_collapse_keeps_9_minute_gap():
    # an employee 8 June: 09:18 / 09:27 are distinct punches
    punches = [dt("2026-06-08 09:18"), dt("2026-06-08 09:27")]
    assert collapse_punches(punches) == punches


def test_collapse_sorts_and_dedupes_exact():
    punches = [dt("2026-06-03 17:55"), dt("2026-06-03 09:19"), dt("2026-06-03 09:19")]
    assert collapse_punches(punches) == [dt("2026-06-03 09:19"), dt("2026-06-03 17:55")]


def test_pair_simple_day():
    s = pair_sessions([dt("2026-06-02 08:54"), dt("2026-06-02 18:55")])
    assert s == [Session(dt("2026-06-02 08:54"), dt("2026-06-02 18:55"))]
    assert round(s[0].hours, 2) == 10.02


def test_pair_cross_midnight_chain():
    # an employee 4–5 June: 00:48 closes Jun 4 and must NOT reopen Jun 5
    punches = [dt("2026-06-04 09:03"), dt("2026-06-05 00:48"),
               dt("2026-06-05 09:06"), dt("2026-06-06 00:52")]
    s = pair_sessions(punches)
    assert s == [Session(dt("2026-06-04 09:03"), dt("2026-06-05 00:48")),
                 Session(dt("2026-06-05 09:06"), dt("2026-06-06 00:52"))]


def test_pair_zarif_four_punch_day():
    # an employee 10 June: 04:30, 11:41, 16:58, 01:38(+1d)
    punches = [dt("2026-06-10 04:30"), dt("2026-06-10 11:41"),
               dt("2026-06-10 16:58"), dt("2026-06-11 01:38")]
    s = pair_sessions(punches)
    assert s == [Session(dt("2026-06-10 04:30"), dt("2026-06-10 11:41")),
                 Session(dt("2026-06-10 16:58"), dt("2026-06-11 01:38"))]


def test_pair_odd_count_dangles():
    s = pair_sessions([dt("2026-06-02 08:54"), dt("2026-06-02 18:55"), dt("2026-06-03 09:00")])
    assert s[-1] == Session(dt("2026-06-03 09:00"), None)
    assert s[-1].hours == 0.0
