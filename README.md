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

Two exceptions, both for scans that carry no information of their own. A lone
scan lying **inside a session that already closed** is a double tap — pressing
'start work' and 'site in' moments apart — and is dropped rather than flagged.
And a night shift recorded as **two lone scans either side of midnight** is
paired back together: the last unmatched scan of the evening closes against the
first lone scan before **07:30** the next morning, and the whole shift is charged
to the day it started. A pair spanning more than 16 h is refused — 06:08 to 04:00
the next day is two forgotten scan-outs, not one shift — and both days stay
withheld. Any scan left over after pairing still withholds its day.

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
.venv/bin/python -m pytest   # 84 tests; golden test auto-skips without the real CSV
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

**Access — the repo and the app are both public.** Anyone with the URL can open
the page and upload a file; no sign-in stands in front of it. App visibility is a
separate setting from repo visibility, in Community Cloud's **Share** panel, and
it does **not** survive a delete-and-redeploy — after any redeploy from scratch,
re-check it by hand before sharing the URL again. Whether this app should be
access-gated at all is a data-policy decision, not a code one; this paragraph
records what is true today, not what is advisable.

**What this changes.** Running locally, attendance never leaves the machine.
Hosted, each uploaded CSV is processed on Streamlit's servers instead. Nothing is
written to disk either way and uploads vanish with the session, but the data does
transit a third party — worth clearing with whoever owns data policy before
sharing the URL.

**Free-tier limits.** Public apps are unlimited (the single-app cap applies to
*private* apps, which this is not), 1 GB RAM, and the app sleeps
after 12 hours idle (the next visitor wakes it, taking a few seconds). The
monthly export is about 1 MB, so the memory ceiling is not a concern.

Redeploys are automatic: pushing to `main` restarts the app with the new code.
A *delete and recreate*, though, resets app visibility — re-check the **Share**
panel afterwards, because nothing in the repo carries that setting.

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
- `ot_sunday` — overtime on Sunday (0 h threshold; all hours are OT)
- `ot_holiday` — overtime on a public holiday (0 h threshold; all hours are OT; reported apart from Sunday because the rates differ)
- `ot_total` — sum of all overtime
- `anomalies` — count of flagged data-quality issues

### Anomaly flags

A non-zero **Anomalies** count means the employee's total is not payable until the flagged days are checked. Flags are:

- **`MISSING_PUNCH`** — a start log with no end log (the export writes it as `Time In == Time Out`, remark `No In/Out`). **The whole day's overtime is withheld**, including any session that did close, because the day cannot be verified. Hours are still displayed; the missing scan must be corrected at source before that day pays. Scans that are explained — a double tap inside a closed session, or the two halves of an overnight shift — are resolved first and never reach this flag
- **`LONG_SESSION`** — a single merged session over 16 h. The hours ARE counted toward the total, so check these before paying
- **`ZERO_LENGTH`** — scan in and out at the same minute (defensive; the loader routes these to `MISSING_PUNCH` before they become a session)
- **`NO_PUNCH`** — no scans that day (rest day, leave or absence); informational, not an error, and not counted in the anomaly total
- **`OUT_OF_MONTH`** — a row dated outside the selected month; listed but excluded from totals

The drilldown also shows the export's own `Leave`/`Remark` text per day, so a
flagged day can usually be judged without opening the CSV.

**The vendor's own overtime total is deliberately not shown.** The remark field
carries one (`Overtime 218 Min`), computed on that system's own rules rather than
the thresholds above. It is not a second source of truth, and printing it beside
our figure put two different overtime numbers on one line with nothing to say
which one payroll should pay. The rest of each remark is kept.

Across the Jan–June 2026 back-fill, three to five of the twelve employees are
anomaly-free in any given month, with 28–69 flagged days per month. Flagged
employees' `ot_total` is a lower bound, not a final figure, until the missing
scans are corrected at source.

## Configuration

Public holidays are configured in `holidays.yml`, currently populated for 2026 and
2027. Edit once a year to reflect the company's observed public holidays.

The app **refuses** to calculate a month whose year has no entries rather than
warning about it: an uncovered year is not a caveat on the figures, it is figures
that look normal and are wrong, because every public holiday in it would be
measured against the 9 h weekday threshold instead of 0 h. On the real June 2026
export that is 95.35 h of overtime lost across 9 of the 12 staff, with 120 h moved
out of the PH column into the weekday one, which is paid at a different rate.

`test_holidays_cover_the_next_six_months` fails in the ordinary test run once the
file is within six months of running out, so the gap surfaces here rather than in
a payroll month. Sourcing the next year's gazetted dates is a manual job that no
code can do — it is the one recurring obligation this app cannot absorb.

Design: `docs/superpowers/specs/2026-07-20-overtime-calculator-design.md`
