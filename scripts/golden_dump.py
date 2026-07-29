"""Print Jan-June 2026 totals per employee, formatted as a Python dict literal.

Usage: PYTHONPATH=. .venv/bin/python scripts/golden_dump.py
Paste the output into tests/test_golden_2026.py EXPECTED.
"""
from overtime.calc import month_totals, summarize_employee
from overtime.loader import load_attendance
from overtime.rules import load_holidays

DATA = "data/Attendance All Staffs (Jan-June'26).csv"
MONTHS = [(2026, m) for m in range(1, 7)]

holidays = load_holidays("holidays.yml")
staff = sorted(load_attendance(DATA), key=lambda e: e.name)

print("EXPECTED = {")
for month in MONTHS:
    print(f"    {month!r}: {{")
    for emp in staff:
        t = month_totals(summarize_employee(emp, month, holidays))
        print(f"        {emp.name!r}: {t!r},")
    print("    },")
print("}")
