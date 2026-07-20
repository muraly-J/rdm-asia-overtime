from datetime import date

from overtime.rules import THRESHOLDS, day_type, load_holidays

HOLIDAYS = {date(2026, 6, 1): "Agong's Birthday", date(2026, 6, 17): "Awal Muharram",
            date(2026, 8, 8): "Fake Saturday PH"}


def test_weekday():
    assert day_type(date(2026, 6, 2), HOLIDAYS) == "weekday"  # Tue


def test_saturday():
    assert day_type(date(2026, 6, 6), HOLIDAYS) == "saturday"


def test_sunday():
    assert day_type(date(2026, 6, 7), HOLIDAYS) == "sunday"


def test_holiday_on_weekday():
    assert day_type(date(2026, 6, 17), HOLIDAYS) == "holiday"  # Wed PH


def test_holiday_beats_saturday():
    # 2026-08-08 is a Saturday; holiday wins
    assert day_type(date(2026, 8, 8), HOLIDAYS) == "holiday"


def test_thresholds():
    assert THRESHOLDS == {"weekday": 9.0, "saturday": 5.0, "sunday": 0.0, "holiday": 0.0}


def test_load_holidays_real_file():
    h = load_holidays("holidays.yml")
    assert h[date(2026, 6, 1)] == "Agong's Birthday"
    assert h[date(2026, 12, 25)] == "Christmas Day"
    assert len(h) == 12
