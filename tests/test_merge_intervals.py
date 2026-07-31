from datetime import datetime

from overtime.calc import Session, merge_intervals


def dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def test_site_window_inside_work_window_is_not_double_counted():
    # a real day — work 08:56-23:44, site 10:28-23:44 — the same day seen twice
    sessions = merge_intervals([(dt("2026-01-05 08:56"), dt("2026-01-05 23:44")),
                                (dt("2026-01-05 10:28"), dt("2026-01-05 23:44"))])
    assert sessions == [Session(dt("2026-01-05 08:56"), dt("2026-01-05 23:44"))]
    assert round(sessions[0].hours, 2) == 14.8


def test_partially_overlapping_windows_union():
    sessions = merge_intervals([(dt("2026-01-05 09:00"), dt("2026-01-05 14:00")),
                                (dt("2026-01-05 13:00"), dt("2026-01-05 18:00"))])
    assert sessions == [Session(dt("2026-01-05 09:00"), dt("2026-01-05 18:00"))]
    assert sessions[0].hours == 9.0


def test_touching_windows_merge():
    sessions = merge_intervals([(dt("2026-01-05 09:00"), dt("2026-01-05 13:00")),
                                (dt("2026-01-05 13:00"), dt("2026-01-05 17:00"))])
    assert sessions == [Session(dt("2026-01-05 09:00"), dt("2026-01-05 17:00"))]


def test_disjoint_windows_stay_separate_and_add_up():
    sessions = merge_intervals([(dt("2026-01-05 09:00"), dt("2026-01-05 12:00")),
                                (dt("2026-01-05 14:00"), dt("2026-01-05 17:00"))])
    assert len(sessions) == 2
    assert sum(s.hours for s in sessions) == 6.0


def test_unsorted_input_is_ordered():
    sessions = merge_intervals([(dt("2026-01-05 14:00"), dt("2026-01-05 17:00")),
                                (dt("2026-01-05 09:00"), dt("2026-01-05 12:00"))])
    assert [s.login for s in sessions] == [dt("2026-01-05 09:00"), dt("2026-01-05 14:00")]


def test_no_intervals_gives_no_sessions():
    assert merge_intervals([]) == []


def test_nested_window_does_not_shorten_the_outer_one():
    sessions = merge_intervals([(dt("2026-01-05 08:00"), dt("2026-01-05 20:00")),
                                (dt("2026-01-05 10:00"), dt("2026-01-05 11:00"))])
    assert sessions == [Session(dt("2026-01-05 08:00"), dt("2026-01-05 20:00"))]
