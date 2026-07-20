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
    'an employee': {'worked': 291.85, 'ot_weekday': 58.33, 'ot_saturday': 48.72, 'ot_sunday_ph': 30.73, 'ot_total': 137.78, 'anomalies': 3},
    'an employee': {'worked': 360.98, 'ot_weekday': 138.85, 'ot_saturday': 35.37, 'ot_sunday_ph': 14.98, 'ot_total': 189.2, 'anomalies': 4},
    'an employee': {'worked': 338.22, 'ot_weekday': 158.03, 'ot_saturday': 16.6, 'ot_sunday_ph': 40.52, 'ot_total': 215.15, 'anomalies': 1},
    'an employee': {'worked': 286.5, 'ot_weekday': 78.27, 'ot_saturday': 5.07, 'ot_sunday_ph': 51.98, 'ot_total': 135.32, 'anomalies': 0},
    'an employee': {'worked': 253.12, 'ot_weekday': 115.9, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 115.9, 'anomalies': 2},
    'an employee': {'worked': 393.93, 'ot_weekday': 44.92, 'ot_saturday': 112.18, 'ot_sunday_ph': 81.83, 'ot_total': 238.93, 'anomalies': 5},
    'an employee': {'worked': 148.9, 'ot_weekday': 22.53, 'ot_saturday': 6.4, 'ot_sunday_ph': 7.08, 'ot_total': 36.02, 'anomalies': 0},
    'an employee': {'worked': 249.75, 'ot_weekday': 57.37, 'ot_saturday': 0.0, 'ot_sunday_ph': 17.5, 'ot_total': 74.87, 'anomalies': 0},
    'an employee': {'worked': 260.55, 'ot_weekday': 34.78, 'ot_saturday': 14.75, 'ot_sunday_ph': 11.03, 'ot_total': 60.57, 'anomalies': 0},
    'an employee': {'worked': 412.07, 'ot_weekday': 158.82, 'ot_saturday': 16.97, 'ot_sunday_ph': 54.6, 'ot_total': 230.38, 'anomalies': 2},
    'an employee': {'worked': 200.83, 'ot_weekday': 14.22, 'ot_saturday': 0.0, 'ot_sunday_ph': 6.62, 'ot_total': 20.83, 'anomalies': 0},
    'an employee': {'worked': 445.93, 'ot_weekday': 284.47, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 284.47, 'anomalies': 6},
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
