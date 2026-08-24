"""Golden test: Jan-June 2026 totals for every employee, from the real export.

Freezes real payroll numbers so refactors cannot silently move them.
Requires the real (gitignored) CSV; skipped on clean clones.

Employees are keyed by pseudonym rather than name - this repository is public and
the totals are payroll data. See overtime/anonymise.py.

Regenerate after an intentional rules change:
    PYTHONPATH=. .venv/bin/python scripts/golden_dump.py
"""
import os

import pytest

from overtime.anonymise import employee_id
from overtime.calc import month_totals, summarize_employee
from overtime.loader import load_attendance
from overtime.rules import load_holidays

DATA = "data/Attendance All Staffs (Jan-June'26).csv"

EXPECTED = {
    (2026, 1): {
        'emp-3b77f2677b': {'worked': 116.67, 'ot_weekday': 11.46, 'ot_saturday': 12.02, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 23.48, 'anomalies': 2},
        'emp-4ae39072ff': {'worked': 317.93, 'ot_weekday': 86.66, 'ot_saturday': 42.25, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 128.91, 'anomalies': 9},
        'emp-5709d98bb7': {'worked': 0.0, 'ot_weekday': 0.0, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 0.0, 'anomalies': 0},
        'emp-599ec0979d': {'worked': 175.07, 'ot_weekday': 4.84, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 4.84, 'anomalies': 0},
        'emp-5a20126feb': {'worked': 308.42, 'ot_weekday': 67.3, 'ot_saturday': 17.53, 'ot_sunday': 24.15, 'ot_holiday': 0.0, 'ot_total': 108.98, 'anomalies': 2},
        'emp-76892e4701': {'worked': 215.75, 'ot_weekday': 29.37, 'ot_saturday': 2.77, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 32.14, 'anomalies': 1},
        'emp-8829911c06': {'worked': 184.25, 'ot_weekday': 18.45, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 7.8, 'ot_total': 26.25, 'anomalies': 3},
        'emp-9fb7dd1be7': {'worked': 0.0, 'ot_weekday': 0.0, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 0.0, 'anomalies': 0},
        'emp-a6eac3b874': {'worked': 186.88, 'ot_weekday': 7.41, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 7.41, 'anomalies': 0},
        'emp-ad987e0f1a': {'worked': 221.0, 'ot_weekday': 64.49, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 64.49, 'anomalies': 4},
        'emp-ca49f89f33': {'worked': 259.4, 'ot_weekday': 67.79, 'ot_saturday': 15.75, 'ot_sunday': 7.87, 'ot_holiday': 0.0, 'ot_total': 91.41, 'anomalies': 0},
        'emp-e3a8636105': {'worked': 180.18, 'ot_weekday': 18.46, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 18.46, 'anomalies': 1},
    },
    (2026, 2): {
        'emp-3b77f2677b': {'worked': 244.4, 'ot_weekday': 40.57, 'ot_saturday': 45.05, 'ot_sunday': 18.68, 'ot_holiday': 8.08, 'ot_total': 112.38, 'anomalies': 11},
        'emp-4ae39072ff': {'worked': 316.38, 'ot_weekday': 85.3, 'ot_saturday': 50.35, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 135.65, 'anomalies': 7},
        'emp-5709d98bb7': {'worked': 126.08, 'ot_weekday': 6.89, 'ot_saturday': 7.07, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 13.96, 'anomalies': 0},
        'emp-599ec0979d': {'worked': 157.45, 'ot_weekday': 6.28, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 6.28, 'anomalies': 0},
        'emp-5a20126feb': {'worked': 184.72, 'ot_weekday': 37.73, 'ot_saturday': 5.63, 'ot_sunday': 28.2, 'ot_holiday': 10.65, 'ot_total': 82.21, 'anomalies': 0},
        'emp-76892e4701': {'worked': 198.28, 'ot_weekday': 33.3, 'ot_saturday': 0.0, 'ot_sunday': 7.77, 'ot_holiday': 0.0, 'ot_total': 41.07, 'anomalies': 1},
        'emp-8829911c06': {'worked': 164.08, 'ot_weekday': 19.87, 'ot_saturday': 9.68, 'ot_sunday': 12.63, 'ot_holiday': 1.5, 'ot_total': 43.68, 'anomalies': 2},
        'emp-9fb7dd1be7': {'worked': 176.97, 'ot_weekday': 24.13, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 24.13, 'anomalies': 1},
        'emp-a6eac3b874': {'worked': 141.55, 'ot_weekday': 2.24, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 2.24, 'anomalies': 2},
        'emp-ad987e0f1a': {'worked': 152.55, 'ot_weekday': 32.43, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 32.43, 'anomalies': 1},
        'emp-ca49f89f33': {'worked': 192.28, 'ot_weekday': 48.53, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 48.53, 'anomalies': 2},
        'emp-e3a8636105': {'worked': 156.13, 'ot_weekday': 4.77, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 4.77, 'anomalies': 0},
    },
    (2026, 3): {
        'emp-3b77f2677b': {'worked': 167.47, 'ot_weekday': 34.48, 'ot_saturday': 27.01, 'ot_sunday': 18.98, 'ot_holiday': 0.0, 'ot_total': 80.47, 'anomalies': 13},
        'emp-4ae39072ff': {'worked': 311.18, 'ot_weekday': 97.11, 'ot_saturday': 24.09, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 121.2, 'anomalies': 2},
        'emp-5709d98bb7': {'worked': 161.2, 'ot_weekday': 2.12, 'ot_saturday': 0.62, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 2.74, 'anomalies': 0},
        'emp-599ec0979d': {'worked': 185.63, 'ot_weekday': 17.74, 'ot_saturday': 0.9, 'ot_sunday': 3.15, 'ot_holiday': 0.0, 'ot_total': 21.79, 'anomalies': 0},
        'emp-5a20126feb': {'worked': 251.75, 'ot_weekday': 55.72, 'ot_saturday': 4.1, 'ot_sunday': 13.58, 'ot_holiday': 0.0, 'ot_total': 73.4, 'anomalies': 3},
        'emp-76892e4701': {'worked': 206.75, 'ot_weekday': 26.32, 'ot_saturday': 4.62, 'ot_sunday': 10.75, 'ot_holiday': 0.0, 'ot_total': 41.69, 'anomalies': 0},
        'emp-8829911c06': {'worked': 186.18, 'ot_weekday': 9.74, 'ot_saturday': 5.22, 'ot_sunday': 24.17, 'ot_holiday': 0.0, 'ot_total': 39.13, 'anomalies': 1},
        'emp-9fb7dd1be7': {'worked': 238.38, 'ot_weekday': 47.68, 'ot_saturday': 4.62, 'ot_sunday': 20.73, 'ot_holiday': 0.0, 'ot_total': 73.03, 'anomalies': 0},
        'emp-a6eac3b874': {'worked': 142.68, 'ot_weekday': 15.84, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 15.84, 'anomalies': 3},
        'emp-ad987e0f1a': {'worked': 212.9, 'ot_weekday': 39.52, 'ot_saturday': 0.0, 'ot_sunday': 11.38, 'ot_holiday': 0.0, 'ot_total': 50.9, 'anomalies': 1},
        'emp-ca49f89f33': {'worked': 189.43, 'ot_weekday': 54.42, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 54.42, 'anomalies': 1},
        'emp-e3a8636105': {'worked': 126.93, 'ot_weekday': 4.11, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 4.11, 'anomalies': 1},
    },
    (2026, 4): {
        'emp-3b77f2677b': {'worked': 302.35, 'ot_weekday': 54.27, 'ot_saturday': 30.53, 'ot_sunday': 42.64, 'ot_holiday': 0.0, 'ot_total': 127.44, 'anomalies': 8},
        'emp-4ae39072ff': {'worked': 354.9, 'ot_weekday': 116.17, 'ot_saturday': 25.73, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 141.9, 'anomalies': 1},
        'emp-5709d98bb7': {'worked': 207.45, 'ot_weekday': 10.27, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 10.27, 'anomalies': 0},
        'emp-599ec0979d': {'worked': 211.58, 'ot_weekday': 27.39, 'ot_saturday': 0.0, 'ot_sunday': 7.2, 'ot_holiday': 0.0, 'ot_total': 34.59, 'anomalies': 2},
        'emp-5a20126feb': {'worked': 331.32, 'ot_weekday': 72.91, 'ot_saturday': 17.6, 'ot_sunday': 26.82, 'ot_holiday': 0.0, 'ot_total': 117.33, 'anomalies': 3},
        'emp-76892e4701': {'worked': 233.3, 'ot_weekday': 40.63, 'ot_saturday': 9.15, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 49.78, 'anomalies': 1},
        'emp-8829911c06': {'worked': 257.1, 'ot_weekday': 32.92, 'ot_saturday': 7.53, 'ot_sunday': 41.93, 'ot_holiday': 0.0, 'ot_total': 82.38, 'anomalies': 5},
        'emp-9fb7dd1be7': {'worked': 256.82, 'ot_weekday': 58.8, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 58.8, 'anomalies': 0},
        'emp-a6eac3b874': {'worked': 223.05, 'ot_weekday': 30.21, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 30.21, 'anomalies': 2},
        'emp-ad987e0f1a': {'worked': 252.47, 'ot_weekday': 57.89, 'ot_saturday': 0.0, 'ot_sunday': 17.83, 'ot_holiday': 0.0, 'ot_total': 75.72, 'anomalies': 0},
        'emp-ca49f89f33': {'worked': 330.67, 'ot_weekday': 77.38, 'ot_saturday': 21.2, 'ot_sunday': 14.06, 'ot_holiday': 0.0, 'ot_total': 112.64, 'anomalies': 1},
        'emp-e3a8636105': {'worked': 184.63, 'ot_weekday': 4.63, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 4.63, 'anomalies': 0},
    },
    (2026, 5): {
        'emp-3b77f2677b': {'worked': 262.43, 'ot_weekday': 54.46, 'ot_saturday': 44.83, 'ot_sunday': 26.05, 'ot_holiday': 0.0, 'ot_total': 125.34, 'anomalies': 9},
        'emp-4ae39072ff': {'worked': 265.07, 'ot_weekday': 104.11, 'ot_saturday': 15.95, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 120.06, 'anomalies': 8},
        'emp-5709d98bb7': {'worked': 189.78, 'ot_weekday': 11.68, 'ot_saturday': 6.1, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 17.78, 'anomalies': 0},
        'emp-599ec0979d': {'worked': 158.43, 'ot_weekday': 20.12, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 20.12, 'anomalies': 0},
        'emp-5a20126feb': {'worked': 238.8, 'ot_weekday': 31.3, 'ot_saturday': 44.87, 'ot_sunday': 34.93, 'ot_holiday': 0.0, 'ot_total': 111.1, 'anomalies': 14},
        'emp-76892e4701': {'worked': 250.9, 'ot_weekday': 41.07, 'ot_saturday': 10.88, 'ot_sunday': 22.77, 'ot_holiday': 13.18, 'ot_total': 87.9, 'anomalies': 0},
        'emp-8829911c06': {'worked': 236.77, 'ot_weekday': 35.96, 'ot_saturday': 28.45, 'ot_sunday': 33.97, 'ot_holiday': 0.0, 'ot_total': 98.38, 'anomalies': 9},
        'emp-9fb7dd1be7': {'worked': 214.12, 'ot_weekday': 41.99, 'ot_saturday': 2.5, 'ot_sunday': 11.63, 'ot_holiday': 0.0, 'ot_total': 56.12, 'anomalies': 0},
        'emp-a6eac3b874': {'worked': 196.17, 'ot_weekday': 28.55, 'ot_saturday': 18.07, 'ot_sunday': 19.4, 'ot_holiday': 0.0, 'ot_total': 66.02, 'anomalies': 6},
        'emp-ad987e0f1a': {'worked': 282.32, 'ot_weekday': 95.7, 'ot_saturday': 0.0, 'ot_sunday': 6.9, 'ot_holiday': 8.72, 'ot_total': 111.32, 'anomalies': 1},
        'emp-ca49f89f33': {'worked': 289.85, 'ot_weekday': 89.88, 'ot_saturday': 22.4, 'ot_sunday': 9.62, 'ot_holiday': 12.95, 'ot_total': 134.85, 'anomalies': 4},
        'emp-e3a8636105': {'worked': 156.92, 'ot_weekday': 3.9, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 3.9, 'anomalies': 1},
    },
    (2026, 6): {
        'emp-3b77f2677b': {'worked': 244.1, 'ot_weekday': 44.63, 'ot_saturday': 47.91, 'ot_sunday': 12.37, 'ot_holiday': 11.18, 'ot_total': 116.09, 'anomalies': 12},
        'emp-4ae39072ff': {'worked': 260.67, 'ot_weekday': 34.87, 'ot_saturday': 14.76, 'ot_sunday': 0.0, 'ot_holiday': 11.03, 'ot_total': 60.66, 'anomalies': 0},
        'emp-5709d98bb7': {'worked': 185.95, 'ot_weekday': 7.82, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 7.82, 'anomalies': 0},
        'emp-599ec0979d': {'worked': 200.92, 'ot_weekday': 14.31, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 6.62, 'ot_total': 20.93, 'anomalies': 0},
        'emp-5a20126feb': {'worked': 210.9, 'ot_weekday': 28.09, 'ot_saturday': 20.86, 'ot_sunday': 22.58, 'ot_holiday': 24.72, 'ot_total': 96.25, 'anomalies': 9},
        'emp-76892e4701': {'worked': 286.9, 'ot_weekday': 71.91, 'ot_saturday': 16.47, 'ot_sunday': 13.75, 'ot_holiday': 13.0, 'ot_total': 115.13, 'anomalies': 2},
        'emp-8829911c06': {'worked': 234.57, 'ot_weekday': 22.8, 'ot_saturday': 25.94, 'ot_sunday': 21.0, 'ot_holiday': 7.73, 'ot_total': 77.47, 'anomalies': 2},
        'emp-9fb7dd1be7': {'worked': 306.02, 'ot_weekday': 75.45, 'ot_saturday': 16.45, 'ot_sunday': 13.8, 'ot_holiday': 12.98, 'ot_total': 118.68, 'anomalies': 1},
        'emp-a6eac3b874': {'worked': 212.33, 'ot_weekday': 10.41, 'ot_saturday': 14.07, 'ot_sunday': 9.58, 'ot_holiday': 0.0, 'ot_total': 34.06, 'anomalies': 0},
        'emp-ad987e0f1a': {'worked': 249.8, 'ot_weekday': 57.38, 'ot_saturday': 0.0, 'ot_sunday': 6.18, 'ot_holiday': 11.33, 'ot_total': 74.89, 'anomalies': 0},
        'emp-ca49f89f33': {'worked': 327.22, 'ot_weekday': 75.96, 'ot_saturday': 21.52, 'ot_sunday': 18.32, 'ot_holiday': 21.43, 'ot_total': 137.23, 'anomalies': 1},
        'emp-e3a8636105': {'worked': 186.57, 'ot_weekday': 15.74, 'ot_saturday': 0.0, 'ot_sunday': 0.0, 'ot_holiday': 0.0, 'ot_total': 15.74, 'anomalies': 0},
    },
}


@pytest.mark.skipif(not os.path.exists(DATA), reason="real data file absent")
@pytest.mark.parametrize("month", sorted(EXPECTED))
def test_monthly_totals(month):
    holidays = load_holidays("holidays.yml")
    actual = {employee_id(emp.name): month_totals(summarize_employee(emp, month, holidays))
              for emp in load_attendance(DATA)}
    assert actual == EXPECTED[month]
