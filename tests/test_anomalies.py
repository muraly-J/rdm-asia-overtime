from datetime import datetime

from overtime.anomalies import day_flags
from overtime.calc import Session


def dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def test_no_punch_day():
    assert day_flags([], had_row=True) == ["NO_PUNCH"]


def test_normal_day_no_flags():
    s = [Session(dt("2026-06-02 08:54"), dt("2026-06-02 18:55"))]
    assert day_flags(s, had_row=True) == []


def test_dangling_session_flags_missing_punch():
    s = [Session(dt("2026-06-03 09:00"), None)]
    assert day_flags(s, had_row=True) == ["MISSING_PUNCH"]


def test_zero_length_session():
    s = [Session(dt("2026-06-04 08:48"), dt("2026-06-04 08:48"))]
    assert day_flags(s, had_row=True) == ["ZERO_LENGTH"]


def test_long_session_over_16h():
    # a 21 h chain: counted but flagged
    s = [Session(dt("2026-06-10 04:30"), dt("2026-06-11 01:38"))]
    assert day_flags(s, had_row=True) == ["LONG_SESSION"]


def test_16h_exactly_not_flagged():
    s = [Session(dt("2026-06-10 06:00"), dt("2026-06-10 22:00"))]
    assert day_flags(s, had_row=True) == []
