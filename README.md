# RDM Asia — Overtime Calculator

Streamlit app that reads the monthly attendance export (one CSV covering all
staff) and calculates overtime.

## Rules

| Day | OT starts after |
| --- | --- |
| Mon–Fri | 9 h |
| Saturday | 5 h |
| Sunday / public holiday | 0 h (all hours are OT) |

A shift counts entirely toward the day it **started**, however late it ends. Log
in Saturday 17:00 and out Sunday 10:00 and that is 17 h of Saturday work: past
the 5 h Saturday threshold, so 12 h of Saturday overtime, and Sunday is untouched.

If a start log has **no end log**, the day is incomplete: it is flagged
`MISSING_PUNCH` and **no overtime is calculated for that day at all** — not even
on the sessions that did close. The hours are still shown, but nothing is paid
until the missing scan is corrected at source.

Public holidays live in `holidays.yml` — edit once a year.

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
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest   # 55 tests; golden test auto-skips without the real CSV
```

`requirements.txt` holds only what the app needs at runtime, so a deployment does
not install pytest. `requirements-dev.txt` includes it for local work.

## Hosting it (Streamlit Community Cloud)

The app needs no files on disk — attendance comes in by upload — so a fresh
clone plus `requirements.txt` is enough to run it anywhere. To put it online at
a URL colleagues can open:

1. Sign in at [share.streamlit.io](https://share.streamlit.io) with the GitHub
   account that owns this repo, and authorise access to private repositories.
2. **Create app** → pick this repo, branch `main`, main file `app.py`.
3. Under **Advanced settings**, set the Python version to **3.14** (what the app
   is tested on; 3.13 also works). Community Cloud defaults to 3.12.
4. Deploy.

**Access.** The app inherits the repo's permissions: because this repo is
private, the app is private too. Anyone you invite views it after signing in
with Google or a single-use emailed link, and only repo admins can redeploy or
delete it. Invited viewers get the app, not the repository.

**What this changes.** Running locally, attendance never leaves the machine.
Hosted, each uploaded CSV is processed on Streamlit's servers instead. Nothing is
written to disk either way and uploads vanish with the session, but the data does
transit a third party — worth clearing with whoever owns data policy before
sharing the URL.

**Free-tier limits.** One private app at a time, 1 GB RAM, and the app sleeps
after 12 hours idle (the next visitor wakes it, taking a few seconds). The
monthly export is about 1 MB, so the memory ceiling is not a concern.

Redeploys are automatic: pushing to `main` restarts the app with the new code.

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

- **`MISSING_PUNCH`** — a start log with no end log (the export writes it as `Time In == Time Out`, remark `No In/Out`). **The whole day's overtime is withheld**, including any session that did close, because the day cannot be verified. Hours are still displayed; the missing scan must be corrected at source before that day pays
- **`LONG_SESSION`** — a single merged session over 16 h. The hours ARE counted toward the total, so check these before paying
- **`ZERO_LENGTH`** — scan in and out at the same minute (defensive; the loader routes these to `MISSING_PUNCH` before they become a session)
- **`NO_PUNCH`** — no scans that day (rest day, leave or absence); informational, not an error, and not counted in the anomaly total
- **`OUT_OF_MONTH`** — a row dated outside the selected month; listed but excluded from totals

The drilldown also shows the export's own `Leave`/`Remark` text per day, so a
flagged day can usually be judged without opening the CSV.

**The vendor's own overtime total is deliberately not shown.** The remark field
carries one (`Overtime 218 Min`), but it is computed on different rules: it pays
hours worked outside the rostered shift, where we pay hours past a daily
threshold. Over Jan–Jun 2026 the two agreed on only 8% of days, and printing both
put two different overtime figures on one line with nothing to say which one
payroll should pay. The rest of each remark is kept.

Across the Jan–June 2026 back-fill, three to five of the twelve employees are
anomaly-free in any given month, with 28–69 flagged days per month. Flagged
employees' `ot_total` is a lower bound, not a final figure, until the missing
scans are corrected at source.

## Configuration

Public holidays are configured in `holidays.yml` (currently populated for 2026). Edit once a year to reflect the company's observed public holidays. The app warns if you select a month whose year has no entries.

Design: `docs/superpowers/specs/2026-07-20-overtime-calculator-design.md`
