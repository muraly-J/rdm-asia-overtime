"""Golden test: Jan-June 2026 totals for every employee, from the real export.

Freezes real payroll numbers so refactors cannot silently move them.
Requires the real (gitignored) CSV; skipped on clean clones.

Regenerate after an intentional rules change:
    PYTHONPATH=. .venv/bin/python scripts/golden_dump.py
"""
import os

import pytest

from overtime.calc import month_totals, summarize_employee
from overtime.loader import load_attendance
from overtime.rules import load_holidays

DATA = "data/Attendance All Staffs (Jan-June'26).csv"

EXPECTED = {
    (2026, 1): {
        'emp-e3a8636105': {'worked': 180.18, 'ot_weekday': 18.46, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 18.46, 'anomalies': 1},
        'emp-9fb7dd1be7': {'worked': 0.0, 'ot_weekday': 0.0, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 0.0, 'anomalies': 0},
        'emp-a6eac3b874': {'worked': 186.88, 'ot_weekday': 7.41, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 7.41, 'anomalies': 0},
        'emp-3b77f2677b': {'worked': 116.67, 'ot_weekday': 11.46, 'ot_saturday': 12.02, 'ot_sunday_ph': 0.0, 'ot_total': 23.48, 'anomalies': 2},
        "emp-8829911c06": {'worked': 184.25, 'ot_weekday': 18.45, 'ot_saturday': 0.0, 'ot_sunday_ph': 7.8, 'ot_total': 26.25, 'anomalies': 4},
        'emp-5709d98bb7': {'worked': 0.0, 'ot_weekday': 0.0, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 0.0, 'anomalies': 0},
        'emp-599ec0979d': {'worked': 175.07, 'ot_weekday': 4.49, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 4.49, 'anomalies': 1},
        'emp-ca49f89f33': {'worked': 259.4, 'ot_weekday': 67.79, 'ot_saturday': 15.75, 'ot_sunday_ph': 7.87, 'ot_total': 91.41, 'anomalies': 0},
        'emp-76892e4701': {'worked': 215.75, 'ot_weekday': 29.37, 'ot_saturday': 2.77, 'ot_sunday_ph': 0.0, 'ot_total': 32.14, 'anomalies': 2},
        'emp-5a20126feb': {'worked': 308.42, 'ot_weekday': 53.4, 'ot_saturday': 17.53, 'ot_sunday_ph': 11.55, 'ot_total': 82.48, 'anomalies': 8},
        'emp-4ae39072ff': {'worked': 317.93, 'ot_weekday': 66.36, 'ot_saturday': 42.25, 'ot_sunday_ph': 0.0, 'ot_total': 108.61, 'anomalies': 11},
        'emp-ad987e0f1a': {'worked': 221.0, 'ot_weekday': 64.49, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 64.49, 'anomalies': 4},
    },
    (2026, 2): {
        'emp-e3a8636105': {'worked': 156.13, 'ot_weekday': 4.77, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 4.77, 'anomalies': 0},
        'emp-9fb7dd1be7': {'worked': 176.97, 'ot_weekday': 24.13, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 24.13, 'anomalies': 1},
        'emp-a6eac3b874': {'worked': 141.55, 'ot_weekday': 2.24, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 2.24, 'anomalies': 4},
        'emp-3b77f2677b': {'worked': 244.4, 'ot_weekday': 40.57, 'ot_saturday': 45.05, 'ot_sunday_ph': 26.76, 'ot_total': 112.38, 'anomalies': 11},
        "emp-8829911c06": {'worked': 164.08, 'ot_weekday': 19.87, 'ot_saturday': 9.68, 'ot_sunday_ph': 14.13, 'ot_total': 43.68, 'anomalies': 2},
        'emp-5709d98bb7': {'worked': 126.08, 'ot_weekday': 6.89, 'ot_saturday': 7.07, 'ot_sunday_ph': 0.0, 'ot_total': 13.96, 'anomalies': 0},
        'emp-599ec0979d': {'worked': 157.45, 'ot_weekday': 6.28, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 6.28, 'anomalies': 0},
        'emp-ca49f89f33': {'worked': 192.28, 'ot_weekday': 48.53, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 48.53, 'anomalies': 2},
        'emp-76892e4701': {'worked': 198.28, 'ot_weekday': 33.3, 'ot_saturday': 0.0, 'ot_sunday_ph': 7.77, 'ot_total': 41.07, 'anomalies': 1},
        'emp-5a20126feb': {'worked': 184.72, 'ot_weekday': 31.48, 'ot_saturday': 5.63, 'ot_sunday_ph': 38.85, 'ot_total': 75.96, 'anomalies': 4},
        'emp-4ae39072ff': {'worked': 316.38, 'ot_weekday': 85.3, 'ot_saturday': 50.35, 'ot_sunday_ph': 0.0, 'ot_total': 135.65, 'anomalies': 7},
        'emp-ad987e0f1a': {'worked': 152.55, 'ot_weekday': 32.43, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 32.43, 'anomalies': 1},
    },
    (2026, 3): {
        'emp-e3a8636105': {'worked': 126.93, 'ot_weekday': 4.11, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 4.11, 'anomalies': 1},
        'emp-9fb7dd1be7': {'worked': 238.38, 'ot_weekday': 47.68, 'ot_saturday': 4.62, 'ot_sunday_ph': 20.73, 'ot_total': 73.03, 'anomalies': 0},
        'emp-a6eac3b874': {'worked': 142.68, 'ot_weekday': 15.84, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 15.84, 'anomalies': 3},
        'emp-3b77f2677b': {'worked': 167.47, 'ot_weekday': 34.48, 'ot_saturday': 27.01, 'ot_sunday_ph': 18.98, 'ot_total': 80.47, 'anomalies': 13},
        "emp-8829911c06": {'worked': 186.18, 'ot_weekday': 5.96, 'ot_saturday': 5.22, 'ot_sunday_ph': 24.17, 'ot_total': 35.35, 'anomalies': 4},
        'emp-5709d98bb7': {'worked': 161.2, 'ot_weekday': 2.12, 'ot_saturday': 0.62, 'ot_sunday_ph': 0.0, 'ot_total': 2.74, 'anomalies': 0},
        'emp-599ec0979d': {'worked': 185.63, 'ot_weekday': 17.74, 'ot_saturday': 0.9, 'ot_sunday_ph': 3.15, 'ot_total': 21.79, 'anomalies': 0},
        'emp-ca49f89f33': {'worked': 189.43, 'ot_weekday': 54.42, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 54.42, 'anomalies': 1},
        'emp-76892e4701': {'worked': 206.75, 'ot_weekday': 26.32, 'ot_saturday': 0.0, 'ot_sunday_ph': 10.75, 'ot_total': 37.07, 'anomalies': 1},
        'emp-5a20126feb': {'worked': 251.75, 'ot_weekday': 49.04, 'ot_saturday': 4.1, 'ot_sunday_ph': 13.58, 'ot_total': 66.72, 'anomalies': 8},
        'emp-4ae39072ff': {'worked': 311.18, 'ot_weekday': 97.11, 'ot_saturday': 24.09, 'ot_sunday_ph': 0.0, 'ot_total': 121.2, 'anomalies': 2},
        'emp-ad987e0f1a': {'worked': 212.9, 'ot_weekday': 39.52, 'ot_saturday': 0.0, 'ot_sunday_ph': 11.38, 'ot_total': 50.9, 'anomalies': 1},
    },
    (2026, 4): {
        'emp-e3a8636105': {'worked': 184.63, 'ot_weekday': 4.63, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 4.63, 'anomalies': 0},
        'emp-9fb7dd1be7': {'worked': 256.82, 'ot_weekday': 58.8, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 58.8, 'anomalies': 0},
        'emp-a6eac3b874': {'worked': 223.05, 'ot_weekday': 27.01, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 27.01, 'anomalies': 4},
        'emp-3b77f2677b': {'worked': 302.35, 'ot_weekday': 54.27, 'ot_saturday': 30.53, 'ot_sunday_ph': 42.64, 'ot_total': 127.44, 'anomalies': 9},
        "emp-8829911c06": {'worked': 257.1, 'ot_weekday': 32.29, 'ot_saturday': 7.53, 'ot_sunday_ph': 41.93, 'ot_total': 81.75, 'anomalies': 6},
        'emp-5709d98bb7': {'worked': 207.45, 'ot_weekday': 10.27, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 10.27, 'anomalies': 0},
        'emp-599ec0979d': {'worked': 211.58, 'ot_weekday': 27.39, 'ot_saturday': 0.0, 'ot_sunday_ph': 7.2, 'ot_total': 34.59, 'anomalies': 2},
        'emp-ca49f89f33': {'worked': 330.67, 'ot_weekday': 76.5, 'ot_saturday': 21.2, 'ot_sunday_ph': 14.06, 'ot_total': 111.76, 'anomalies': 2},
        'emp-76892e4701': {'worked': 233.3, 'ot_weekday': 40.63, 'ot_saturday': 9.15, 'ot_sunday_ph': 0.0, 'ot_total': 49.78, 'anomalies': 1},
        'emp-5a20126feb': {'worked': 331.32, 'ot_weekday': 72.91, 'ot_saturday': 17.6, 'ot_sunday_ph': 26.82, 'ot_total': 117.33, 'anomalies': 3},
        'emp-4ae39072ff': {'worked': 354.9, 'ot_weekday': 116.17, 'ot_saturday': 25.73, 'ot_sunday_ph': 0.0, 'ot_total': 141.9, 'anomalies': 1},
        'emp-ad987e0f1a': {'worked': 252.47, 'ot_weekday': 57.89, 'ot_saturday': 0.0, 'ot_sunday_ph': 17.83, 'ot_total': 75.72, 'anomalies': 0},
    },
    (2026, 5): {
        'emp-e3a8636105': {'worked': 156.92, 'ot_weekday': 3.9, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 3.9, 'anomalies': 1},
        'emp-9fb7dd1be7': {'worked': 214.12, 'ot_weekday': 41.99, 'ot_saturday': 2.5, 'ot_sunday_ph': 11.63, 'ot_total': 56.12, 'anomalies': 0},
        'emp-a6eac3b874': {'worked': 196.17, 'ot_weekday': 28.55, 'ot_saturday': 18.07, 'ot_sunday_ph': 19.4, 'ot_total': 66.02, 'anomalies': 6},
        'emp-3b77f2677b': {'worked': 262.43, 'ot_weekday': 54.46, 'ot_saturday': 44.83, 'ot_sunday_ph': 26.05, 'ot_total': 125.34, 'anomalies': 10},
        "emp-8829911c06": {'worked': 236.77, 'ot_weekday': 29.3, 'ot_saturday': 28.45, 'ot_sunday_ph': 33.97, 'ot_total': 91.72, 'anomalies': 15},
        'emp-5709d98bb7': {'worked': 189.78, 'ot_weekday': 11.68, 'ot_saturday': 6.1, 'ot_sunday_ph': 0.0, 'ot_total': 17.78, 'anomalies': 0},
        'emp-599ec0979d': {'worked': 158.43, 'ot_weekday': 20.12, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 20.12, 'anomalies': 0},
        'emp-ca49f89f33': {'worked': 289.85, 'ot_weekday': 89.88, 'ot_saturday': 22.4, 'ot_sunday_ph': 22.57, 'ot_total': 134.85, 'anomalies': 4},
        'emp-76892e4701': {'worked': 250.9, 'ot_weekday': 41.07, 'ot_saturday': 10.88, 'ot_sunday_ph': 23.58, 'ot_total': 75.53, 'anomalies': 1},
        'emp-5a20126feb': {'worked': 238.8, 'ot_weekday': 12.58, 'ot_saturday': 44.87, 'ot_sunday_ph': 13.05, 'ot_total': 70.5, 'anomalies': 22},
        'emp-4ae39072ff': {'worked': 265.07, 'ot_weekday': 97.19, 'ot_saturday': 15.95, 'ot_sunday_ph': 0.0, 'ot_total': 113.14, 'anomalies': 9},
        'emp-ad987e0f1a': {'worked': 282.32, 'ot_weekday': 95.7, 'ot_saturday': 0.0, 'ot_sunday_ph': 15.62, 'ot_total': 111.32, 'anomalies': 1},
    },
    (2026, 6): {
        'emp-e3a8636105': {'worked': 186.57, 'ot_weekday': 15.74, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 15.74, 'anomalies': 1},
        'emp-9fb7dd1be7': {'worked': 306.02, 'ot_weekday': 71.33, 'ot_saturday': 16.45, 'ot_sunday_ph': 26.78, 'ot_total': 114.56, 'anomalies': 2},
        'emp-a6eac3b874': {'worked': 212.33, 'ot_weekday': 10.41, 'ot_saturday': 14.07, 'ot_sunday_ph': 9.58, 'ot_total': 34.06, 'anomalies': 0},
        'emp-3b77f2677b': {'worked': 244.1, 'ot_weekday': 37.71, 'ot_saturday': 47.91, 'ot_sunday_ph': 23.55, 'ot_total': 109.17, 'anomalies': 13},
        "emp-8829911c06": {'worked': 234.57, 'ot_weekday': 19.17, 'ot_saturday': 25.94, 'ot_sunday_ph': 28.73, 'ot_total': 73.84, 'anomalies': 5},
        'emp-5709d98bb7': {'worked': 185.95, 'ot_weekday': 7.82, 'ot_saturday': 0.0, 'ot_sunday_ph': 0.0, 'ot_total': 7.82, 'anomalies': 0},
        'emp-599ec0979d': {'worked': 200.92, 'ot_weekday': 14.31, 'ot_saturday': 0.0, 'ot_sunday_ph': 6.62, 'ot_total': 20.93, 'anomalies': 0},
        'emp-ca49f89f33': {'worked': 327.22, 'ot_weekday': 74.46, 'ot_saturday': 21.52, 'ot_sunday_ph': 39.75, 'ot_total': 135.73, 'anomalies': 2},
        'emp-76892e4701': {'worked': 286.9, 'ot_weekday': 67.79, 'ot_saturday': 16.47, 'ot_sunday_ph': 26.75, 'ot_total': 111.01, 'anomalies': 3},
        'emp-5a20126feb': {'worked': 210.9, 'ot_weekday': 21.81, 'ot_saturday': 20.86, 'ot_sunday_ph': 33.9, 'ot_total': 76.57, 'anomalies': 11},
        'emp-4ae39072ff': {'worked': 260.67, 'ot_weekday': 34.87, 'ot_saturday': 14.76, 'ot_sunday_ph': 11.03, 'ot_total': 60.66, 'anomalies': 0},
        'emp-ad987e0f1a': {'worked': 249.8, 'ot_weekday': 57.38, 'ot_saturday': 0.0, 'ot_sunday_ph': 17.51, 'ot_total': 74.89, 'anomalies': 0},
    },
}


@pytest.mark.skipif(not os.path.exists(DATA), reason="real data file absent")
@pytest.mark.parametrize("month", sorted(EXPECTED))
def test_monthly_totals(month):
    holidays = load_holidays("holidays.yml")
    actual = {emp.name: month_totals(summarize_employee(emp, month, holidays))
              for emp in load_attendance(DATA)}
    assert actual == EXPECTED[month]
