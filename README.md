# RDM Asia — Overtime Calculator

Streamlit app that reads the monthly biometric attendance export (one xlsx,
one sheet per employee) and calculates overtime.

## Rules

| Day | OT starts after |
| --- | --- |
| Mon–Fri | 9 h |
| Saturday | 5 h |
| Sunday / public holiday | 0 h (all hours are OT) |

Shifts crossing midnight count entirely toward the **login** date.
Public holidays live in `holidays.yml` — edit once a year.

## Monthly routine

1. Drop the export into `data/` named `<Month Year>.xlsx` (e.g. `July 2026.xlsx`).
2. `.venv/bin/python -m streamlit run app.py`
3. Pick the month, check any flagged anomalies in the drilldown, download the report.

Attendance files are gitignored — they never leave this machine.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest   # 35 tests; golden test auto-skips without June 2026.xlsx
```

## Regenerating the golden totals

After an intentional rules change, run this from the repo root:

```bash
PYTHONPATH=. .venv/bin/python scripts/golden_dump.py
```

Paste the printed `EXPECTED` dict into `tests/test_golden_june_2026.py`. The `PYTHONPATH` prefix is required — a bare invocation fails because Python puts the script's own directory on `sys.path`, not the current working directory.

## Reading the results

Overtime hours are reported exact to 2 decimal places. Each employee's row shows:

- `worked` — total hours in the month
- `ot_weekday` — overtime on Mon–Fri (after 9 h/day)
- `ot_saturday` — overtime on Saturday (after 5 h/day)
- `ot_sunday_ph` — overtime on Sunday or public holiday (0 h threshold; all hours are OT)
- `ot_total` — sum of all overtime
- `anomalies` — count of flagged data-quality issues

### Anomaly flags

A non-zero **Anomalies** count means the employee's total is not payable until the flagged days are checked. Flags are:

- **`MISSING_PUNCH`** — someone forgot to scan out; that session counts 0 h and needs correcting at source
- **`ZERO_LENGTH`** — scan in and out at the same minute; likely a mispress
- **`LONG_SESSION`** — a single session over 16 h, almost always a missed punch. The hours ARE counted toward the total, so these must be checked before paying
- **`NO_PUNCH`** — no scans that day (rest day or leave); informational, not an error
- **`OUT_OF_MONTH`** — a row dated outside the selected month; listed but excluded from totals

In the June 2026 data, an employee has sessions of 68.8 h, 44.6 h, and 34.2 h from missed punches — his total is inflated until those are corrected at source.

## Configuration

Public holidays are configured in `holidays.yml` (currently populated for 2026). Edit once a year to reflect the company's observed public holidays.

Design: `docs/superpowers/specs/2026-07-20-overtime-calculator-design.md`
