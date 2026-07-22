"""Golden test: full June 2026 totals for all 12 employees.

Freezes real payroll numbers so refactors cannot silently move them.
Requires the real (gitignored) data file; skipped on clean clones.
"""
import os

import pytest

from overtime.calc import month_totals, summarize_month
from overtime.loader import load_attendance
from overtime.rules import load_holidays

DATA = "data/June 2026.xlsx"

EXPECTED = {
    'an employee': {'worked': 206.53, 'ot_weekday': 14.09, 'ot_saturday': 25.92, 'ot_sunday_ph': 28.7, 'ot_total': 68.71, 'anomalies': 8},
    'an employee': {'worked': 164.23, 'ot_weekday': 4.57, 'ot_saturday': 0.0, 'ot_sunday_ph': 1.15, 'ot_total': 5.72, 'anomalies': 5},
    'an employee': {'worked': 116.05, 'ot_weekday': 8.75, 'ot_saturday': 5.05, 'ot_sunday_ph': 6.72, 'ot_total': 20.52, 'anomalies': 4},
    'an employee': {'worked': 239.58, 'ot_weekday': 58.79, 'ot_saturday': 9.75, 'ot_sunday_ph': 11.76, 'ot_total': 80.3, 'anomalies': 6},
    'an employee': {'worked': 70.33, 'ot_weekday': 1.01, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 1.01, 'anomalies': 10},
    'an employee': {'worked': 237.37, 'ot_weekday': 28.11, 'ot_saturday': 26.78, 'ot_sunday_ph': 23.54, 'ot_total': 78.43, 'anomalies': 7},
    'an employee': {'worked': 129.67, 'ot_weekday': 9.61, 'ot_saturday': 5.05, 'ot_sunday_ph': 7.09, 'ot_total': 21.75, 'anomalies': 2},
    'an employee': {'worked': 249.75, 'ot_weekday': 57.35, 'ot_saturday': 0.0, 'ot_sunday_ph': 17.5, 'ot_total': 74.85, 'anomalies': 0},
    'an employee': {'worked': 260.55, 'ot_weekday': 34.78, 'ot_saturday': 14.75, 'ot_sunday_ph': 11.03, 'ot_total': 60.56, 'anomalies': 0},
    'an employee': {'worked': 305.73, 'ot_weekday': 75.17, 'ot_saturday': 5.85, 'ot_sunday_ph': 39.71, 'ot_total': 120.73, 'anomalies': 2},
    'an employee': {'worked': 200.83, 'ot_weekday': 14.21, 'ot_saturday': 0.0, 'ot_sunday_ph': 6.62, 'ot_total': 20.83, 'anomalies': 0},
    'an employee': {'worked': 159.1, 'ot_weekday': 5.78, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 5.78, 'anomalies': 5},
}


@pytest.mark.skipif(not os.path.exists(DATA), reason="real data file absent")
def test_june_2026_totals():
    holidays = load_holidays("holidays.yml")
    actual = {}
    for emp in load_attendance(DATA):
        actual[emp.short_name] = month_totals(
            summarize_month(emp.short_name, emp.punches, emp.dates_present,
                            (2026, 6), holidays))
    assert actual == EXPECTED
