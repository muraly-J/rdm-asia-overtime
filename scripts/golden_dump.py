"""Print June 2026 totals per employee, formatted as a Python dict literal.

Usage: .venv/bin/python scripts/golden_dump.py
Paste the output into tests/test_golden_june_2026.py EXPECTED.
"""
from overtime.calc import month_totals, summarize_month
from overtime.loader import load_attendance
from overtime.rules import load_holidays

holidays = load_holidays("holidays.yml")
print("EXPECTED = {")
for emp in load_attendance("data/June 2026.xlsx"):
    t = month_totals(summarize_month(emp.short_name, emp.punches,
                                     emp.dates_present, (2026, 6), holidays))
    print(f"    {emp.short_name!r}: {t!r},")
print("}")
