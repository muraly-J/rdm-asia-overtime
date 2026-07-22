# RDM Asia — Overtime Calculator

Streamlit app that reads the monthly biometric attendance export (one xlsx,
one sheet per employee) and calculates overtime.

## Rules

| Day | OT starts after |
| --- | --- |
| Mon–Fri | 9 h |
| Saturday | 5 h |
| Sunday / public holiday | 0 h (all hours are OT) |

Shifts crossing midnight count entirely toward the **login** date, but only when
the clock-out lands before **06:00** the next morning. A later "logout" means a
scan was missed — that session is flagged `MISSING_PUNCH` and pays 0 h rather
than inventing a multi-day shift. Public holidays live in `holidays.yml` — edit
once a year.

## Monthly routine

1. Drop the export into `data/` named `<Month Year>.xlsx` (e.g. `July 2026.xlsx`).
2. `.venv/bin/python -m streamlit run app.py`
3. Pick the month, check any flagged anomalies in the drilldown, download the report.

Attendance files are gitignored — they never leave this machine.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest   # 40 tests; golden test auto-skips without June 2026.xlsx
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

- **`MISSING_PUNCH`** — an odd number of scans (someone forgot to scan out, or a mid-day scan is missing). That session counts 0 h; the real time must be supplied at source before it can be paid. This is the common flag — missing scans are frequent in the raw data
- **`LONG_SESSION`** — a single **same-day** session over 16 h. The hours ARE counted toward the total, so check these before paying
- **`ZERO_LENGTH`** — scan in and out at the same minute (defensive; does not occur once near-duplicate scans are merged)
- **`NO_PUNCH`** — no scans that day (rest day or leave); informational, not an error, and not counted in the anomaly total
- **`OUT_OF_MONTH`** — a row dated outside the selected month; listed but excluded from totals

In the June 2026 data only an employee, an employee and an employee are free of anomalies. The
other nine each have `MISSING_PUNCH` days whose hours cannot be paid until the
missing scans are corrected at source — so their `ot_total` is a lower bound, not
a final figure. Two same-day `LONG_SESSION` days (an employee 6 Jun 16.97 h, an employee
20 Jun 20.58 h) are counted and need a manual check.

## Configuration

Public holidays are configured in `holidays.yml` (currently populated for 2026). Edit once a year to reflect the company's observed public holidays.

Design: `docs/superpowers/specs/2026-07-20-overtime-calculator-design.md`
