from datetime import date, timedelta

import pytest

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
    # years flatten into one date -> name map; adding a year must not break this
    h = load_holidays("holidays.yml")
    assert h[date(2026, 6, 1)] == "Agong's Birthday"
    assert h[date(2026, 12, 25)] == "Christmas Day"
    assert h[date(2027, 1, 1)] == "New Year's Day"
    assert sum(1 for d in h if d.year == 2026) == 12
    # `len(h) == len(set(h))` cannot fail for a dict - a real duplicate now raises
    # in load_holidays, and is covered by test_a_date_listed_twice_is_rejected


def test_holidays_cover_the_next_six_months():
    """A dated tripwire: fail in the developer's own test run, not in payroll.

    An uncovered year is not a visible error in the data - every public holiday in
    it silently becomes an ordinary 9 h day. This fails roughly six months before
    the file runs out, which is the notice needed to source the next gazette.
    """
    h = load_holidays("holidays.yml")
    horizon = date.today() + timedelta(days=180)
    assert max(h) >= horizon, (
        f"holidays.yml ends {max(h)}, less than six months out — add the next "
        "year's gazetted public holidays before the app has to refuse them")


def test_a_date_under_the_wrong_year_heading_is_rejected(tmp_path):
    # the headings are what the app checks coverage against, so a stray date under
    # one both loses the holiday and reports its year as covered
    f = tmp_path / "h.yml"
    f.write_text("2028:\n  - date: 2027-05-01\n    name: Labour Day\n")
    with pytest.raises(ValueError, match="wrong year"):
        load_holidays(f)


def test_a_date_listed_twice_is_rejected(tmp_path):
    f = tmp_path / "h.yml"
    f.write_text("2026:\n  - date: 2026-05-01\n    name: Labour Day\n"
                 "  - date: 2026-05-01\n    name: Labour Day (observed)\n")
    with pytest.raises(ValueError, match="listed twice"):
        load_holidays(f)


def test_a_year_heading_listed_twice_is_rejected(tmp_path):
    """Appending a second block is the obvious way to add a newly declared holiday.

    Plain YAML lets the last one win, which deletes the rest of that year while
    leaving the year still looking covered to the app.
    """
    f = tmp_path / "h.yml"
    f.write_text("2028:\n  - date: 2028-01-01\n    name: New Year's Day\n"
                 "2028:\n  - date: 2028-10-05\n    name: Special declared holiday\n")
    with pytest.raises(ValueError, match="appears twice"):
        load_holidays(f)


def test_a_quoted_year_heading_is_the_same_heading(tmp_path):
    # '2026': and 2026: are one heading to any reader; only the parser differs
    f = tmp_path / "h.yml"
    f.write_text("'2026':\n  - date: 2026-01-01\n    name: New Year's Day\n")
    assert load_holidays(f) == {date(2026, 1, 1): "New Year's Day"}


def test_a_heading_that_is_not_a_year_says_so(tmp_path):
    f = tmp_path / "h.yml"
    f.write_text("2028 (provisional):\n  - date: 2028-01-01\n    name: New Year's Day\n")
    with pytest.raises(ValueError, match="is not a year"):
        load_holidays(f)


def test_the_error_names_the_file_it_was_given(tmp_path):
    # the message must point at the file the caller passed, not a hardcoded name
    f = tmp_path / "custom-holidays.yml"
    f.write_text("2026:\n  - date: 2027-05-01\n    name: Labour Day\n")
    with pytest.raises(ValueError, match="custom-holidays.yml"):
        load_holidays(f)
