# RDM Asia — Overtime Calculator

Streamlit app that reads the monthly attendance export (one CSV covering all
staff) and calculates overtime.

## Rules

| Day | OT starts after |
| --- | --- |
| Mon–Fri | 9 h |
| Saturday | 5 h |
| Sunday / public holiday | 0 h (all hours are OT) |

Shifts crossing midnight count entirely toward the **login** date, but only when
the clock-out lands before **06:00** the next morning. A later "logout" means a
scan was missed — that window is flagged `MISSING_PUNCH` and pays 0 h rather
than inventing a multi-day shift. Public holidays live in `holidays.yml` — edit
once a year.

The export reports most days **twice**, once as `Group=work` and once as
`Group=site`, with the two windows overlapping. These are two views of the same
day, not two separate stints, so the day's hours are the **union** of its
windows, never the sum. Windows that genuinely do not overlap — a site visit
outside office hours — still add up. The vendor's own `Hours` column is ignored;
hours are recomputed from the timestamps.

## Monthly routine

1. `.venv/bin/python -m streamlit run app.py`
2. Upload the attendance export (`.csv`) in the browser. Several files can be
   uploaded at once — employees appearing in more than one are merged.
3. The month is read from the data (the month most rows fall in); override it in
   the sidebar if needed.
4. Check any flagged anomalies in the drilldown, download the report.

Uploads are held in memory for the session only — nothing is written to disk.
Files kept in `data/` are gitignored and used only by the golden test.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest   # 60 tests; golden test auto-skips without the real CSV
```

## Regenerating the golden totals

After an intentional rules change, run this from the repo root:

```bash
PYTHONPATH=. .venv/bin/python scripts/golden_dump.py
```

Paste the printed `EXPECTED` dict into `tests/test_golden_2026.py`. The `PYTHONPATH` prefix is required — a bare invocation fails because Python puts the script's own directory on `sys.path`, not the current working directory.

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

- **`MISSING_PUNCH`** — a lone scan: the export recorded a clock-in with no clock-out (written as `Time In == Time Out`, remark `No In/Out`), or a window running past the 06:00 cut-off. That scan counts 0 h; the real time must be supplied at source before it can be paid. A day can hold both a lone scan and a genuine window — the window is still paid, and the day is still flagged
- **`LONG_SESSION`** — a single merged session over 16 h. The hours ARE counted toward the total, so check these before paying
- **`ZERO_LENGTH`** — scan in and out at the same minute (defensive; the loader routes these to `MISSING_PUNCH` before they become a session)
- **`NO_PUNCH`** — no scans that day (rest day, leave or absence); informational, not an error, and not counted in the anomaly total
- **`OUT_OF_MONTH`** — a row dated outside the selected month; listed but excluded from totals

The drilldown also shows the export's own `Leave`/`Remark` text per day, so a
flagged day can usually be judged without opening the CSV.

Across the Jan–June 2026 back-fill, three to five of the twelve employees are
anomaly-free in any given month, with 28–69 flagged days per month. Flagged
employees' `ot_total` is a lower bound, not a final figure, until the missing
scans are corrected at source.

## Configuration

Public holidays are configured in `holidays.yml` (currently populated for 2026). Edit once a year to reflect the company's observed public holidays. The app warns if you select a month whose year has no entries.

Design: `docs/superpowers/specs/2026-07-20-overtime-calculator-design.md`
