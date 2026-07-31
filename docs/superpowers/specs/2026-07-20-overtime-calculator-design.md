# Overtime Calculator — Design

Date: 2026-07-20
Revised: 2026-07-29 — CSV input; day modelled as a union of recorded windows
Status: Approved

## Problem

RDM Asia receives one attendance export per month covering all staff (12 people).
Overtime was calculated by hand. It must be automated, repeatable every month, and
auditable when payroll disputes a number.

The original design read a per-employee-sheet xlsx and reconstructed a punch
timeline from it. That was wrong: the export already pairs each clock-in with its
clock-out, and re-deriving the pairing corrupted days where the same span is
reported twice. The 2026-07-29 revision reads the pairs as given. Sections below
describe the current design; the superseded punch-list reasoning is not retained.

## Overtime rules

Thresholds by day type — overtime is worked hours above the threshold:

| Day type          | Threshold |
| ----------------- | --------- |
| Monday–Friday     | 9 h       |
| Saturday          | 5 h       |
| Sunday            | 0 h       |
| Public holiday    | 0 h       |

Public holiday takes precedence over Saturday.

A shift may run past midnight. Every session is attributed in full to the day it
**started**, however late it ends — there is no cut-off hour. A shift beginning
Saturday 17:00 and ending Sunday 10:00 is 17 h of Saturday work: the 5 h Saturday
threshold applies, giving 12 h of Saturday overtime, and Sunday is untouched. Day
type is likewise determined by the start date.

If a start log has no matching end log, the day is incomplete and **no overtime is
calculated for that day**, including for sessions that did close. Hours are still
reported so the gap is visible; nothing is paid until the scan is fixed at source.
(Revised 2026-07-31, superseding an earlier 06:00 carry-over cut-off that treated
a late clock-out as a missed scan.)

Overtime is reported to two decimal places. No rounding to quarter or half
hours; payroll applies its own rounding downstream if it wants one. Each day's
overtime is rounded to two decimals, and a month's bucket totals are the sums of
those rounded daily figures, so the summary table's Total OT always equals the
sum of its Weekday, Saturday and Sunday/PH columns — the reconciliation payroll
needs when a figure is disputed.

## Input data

One CSV per month covering all staff, uploaded in the app. The Jan–June 2026
back-fill arrived as a single six-month file; both work, because the reporting
month is derived from the data rather than the filename.

Columns: `Branch, Department, Sect., Work Pattern, Badge No., Name, Location,
P.Pos, Day, Date, Time In, In (Map), Time Out, Out (Map), Hours, Group, Leave,
Remark`. The file carries a UTF-8 BOM. `Date` is day-first (`d/m/Y`); `Time In`
and `Time Out` are full `d/m/Y H:M` timestamps.

The `Hours` column is **ignored** — hours are recomputed from the timestamps. It
is not merely redundant but wrong: it reports `25:30:00` on one row and `0:00`
on rows where a scan is missing.

The vendor's overtime total, appended to the remark as `Overtime N Min`, is
**stripped** for the same reason. It answers a different question from ours: it
credits hours worked outside the rostered shift, while we credit hours past a
daily threshold. Over Jan–June 2026 the two figures agreed on 8% of the 1,012
days carrying both, and showing them together placed two overtime numbers on one
report line without saying which was payable. The descriptive part of the remark
is kept. See "Divergence from the vendor's overtime" below.

Employees are keyed on **`Name`**, not `Badge No.` — two staff have no badge
number anywhere in the export.

### Known characteristics of the export

**Each row is an already-paired window.** `Time In` and `Time Out` both appear on
the same row; there is no pairing to reconstruct.

**Most days are reported twice.** One row has `Group=work`, another `Group=site`,
and the two windows overlap — they are two views of the same day, not two stints.
an employee, 5 January 2026:

    work:  08:56 -> 23:44
    site:  10:28 -> 23:44

Across the six-month file the site window lies strictly inside the work window on
1191 of 1326 such days. Summing the rows would pay the overlap twice; the union
is the day's actual span. Where the windows genuinely do not meet — an early site
visit before the office scan — the union keeps them separate and they add up.

**A lone scan is written as `Time In == Time Out`** (remark `No In/Out`, 248 rows).
The employee scanned once and the partner scan is missing.

**Cross-midnight windows are already attributed to the login date** by the export;
186 rows cross midnight and all currently end before 06:00.

**Days with no times at all** carry `Rest day`, `Absent`, `Leave` or `Half Day`
in the `Remark`/`Leave` columns.

**Rows may fall outside the nominal month** when a monthly file has ragged edges.

## Algorithm

1. **Load.** Read each row as a `(Time In, Time Out)` window, skipping the `──`
   employee banner rows and blank padding rows. Rows where in == out become
   *lone scans*; rows with no times only register that the date was reported.

   The `Day` column is checked against the parsed date on every row. A mismatch
   raises rather than silently reinterpreting — this is what catches the export
   flipping from `d/m/Y` to `m/d/Y`, which would otherwise move hours between
   months undetected.
2. **Merge.** For each employee-day, union the windows: sort by start, then
   coalesce any that overlap or touch. This is what stops the `work`/`site`
   duplicate rows being counted twice. There is no gap tolerance — windows merge
   only where they actually meet.

3. **Attribute.** Assign each merged session to `login.date()`, whatever hour it
   ended — a window is never rejected for running long.
4. **Aggregate.** Day worked hours = sum of the merged sessions' durations. Lone
   scans contribute 0 h and raise a flag.
5. **Classify.** Determine day type from the start date and `holidays.yml`.
6. **Compute.** `overtime = max(0, worked_hours - threshold(day_type))` — except
   on a day holding a start log with no end log, where overtime is 0 regardless
   of hours worked.

Days outside the selected month are excluded from totals but listed in the
drilldown with an `OUT_OF_MONTH` flag.

## Public holidays

`holidays.yml` at the repo root, git-tracked, edited by hand once a year:

```yaml
2026:
  - date: 2026-06-01
    name: Agong's Birthday
```

The file is the single source of truth. No network lookup, no holidays library —
company-declared off days must be expressible, and the audit trail matters more
than the convenience.

## Anomalies

Bad data is surfaced, never silently paid and never silently dropped. Flags are
computed per employee-day, shown in the drilldown and counted in the summary:

| Flag            | Condition                             | Effect on hours          |
| --------------- | ------------------------------------- | ------------------------ |
| `MISSING_PUNCH` | a start log with no end log (`No In/Out`) | **whole day's overtime withheld** |
| `ZERO_LENGTH`   | login == logout                       | 0 h                      |
| `LONG_SESSION`  | single merged session > 16 h          | counted, flagged loudly  |
| `NO_PUNCH`      | day reported with no timestamps       | 0 h, informational only  |
| `OUT_OF_MONTH`  | date outside selected month           | excluded from totals     |

A lone scan is never estimated or extrapolated. It reads 0 hours and requires a
human to correct the source data. Where a day holds both a lone scan and a
complete window, the hours are reported but the day pays no overtime: an
unverifiable day is withheld rather than part-paid.

Loader failures — missing column, unparseable timestamp, a `Day` column that
disagrees with the date, a half-open or reversed row — raise a Streamlit error
naming the CSV row. The app never renders a partial total.

## Divergence from the vendor's overtime — OPEN

Audited 2026-07-30 over Jan–June 2026. The export credits overtime on 1,012
employee-days; our figure agrees with it on **8%** of them. Three causes:

| Cause | Days | Direction | Status |
| --- | --- | --- | --- |
| Public holidays | 15 | ours higher by 5–11 h | Correct — the 0 h threshold is the agreed rule |
| Evening / night shifts | 548 | **ours lower**, up to 7.7 h | **Unresolved** |
| Missed-scan days | ~30 | ours higher by 5–11 h | Flagged `LONG_SESSION`, still paid |

The middle row is the open question. We test a day's *total* hours against the
day-type threshold. The vendor pays hours worked outside the rostered shift, which
the `Work Pattern` column (`Option 2`, `Option 3`) identifies and we do not read.
A 16:43→01:59 shift is 9.27 h, so we credit 0.27 h where the vendor credits 8.00 h;
a 20:11→00:09 evening stint we credit nothing at all against the vendor's 6.17 h.

Over six months that is **380.8 h of overtime we do not pay**, concentrated on the
staff who work nights. The holiday and missed-scan causes add 385.9 h back, so the
net across the company is +5.0 h — the two effects very nearly cancel, which is why
monthly totals look reasonable while individual employees are tens of hours out in
opposite directions. Do not read agreeable-looking totals as confirmation.

Resolving this needs a ruling from HR on which definition governs: hours past a
daily threshold, or hours outside the rostered shift. If it is the latter, the
calculation needs the roster as an input and this design changes materially.

## Architecture

```
overtime/
  loader.py      CSV -> list[EmployeeAttendance] (windows, lone scans, notes)
  rules.py       day_type(date), threshold_hours(day_type), holiday loading
  calc.py        windows -> merged sessions -> list[DaySummary]
  anomalies.py   sessions -> list[Flag]
app.py           Streamlit UI only
data/            attendance exports (gitignored; only the golden test reads them)
holidays.yml
tests/
```

The `overtime/` package is pure: plain functions over plain data, no Streamlit
imports, no file dialogs, no global state. `app.py` contains only widgets and
table rendering. This is what makes the rules unit-testable without running a
browser, which matters because the output is payroll money.

`DaySummary` carries: employee, date, day type, merged sessions, worked hours,
threshold, overtime hours, flags, and the export's own `Leave`/`Remark` note for
the day.

## User interface

Upload area: one or more attendance CSVs, held in memory for the session only —
nothing is written to disk. Employees appearing in several files are merged by
name.

Sidebar: month dropdown, derived from the uploaded rows (the month most rows fall
in is preselected), plus the month's public holidays and a warning when
`holidays.yml` has no entries for that year.

Main area:

1. **Monthly summary table** — one row per employee: total worked hours, weekday
   OT, Saturday OT, Sunday/PH OT, total OT, anomaly count.
2. **Per-employee drilldown** — employee selector, then every day of the month:
   day type, sessions, worked hours, threshold, OT, flags.
3. **Export** — download button producing an Excel workbook with the summary on
   one sheet and the full daily detail on another.

## Testing

`pytest` over `loader.py`, `calc.py`, `anomalies.py` and `rules.py`, using
hand-written CSV and interval fixtures. Each real characteristic of the export
becomes a named test:

- A `site` window nested inside a `work` window is paid once, not twice
- Partially overlapping, touching and disjoint windows union correctly
- A `No In/Out` row (in == out) pays 0 h and flags `MISSING_PUNCH`
- A lone scan alongside a genuine window still pays the window
- A Saturday 17:00 → Sunday 10:00 shift is 17 h of Saturday work: 12 h Saturday
  overtime, Sunday untouched
- An end log two days after the start still counts on the start day
- A start log with no end log withholds the whole day's overtime, including any
  session that did close
- Public holiday falling on a Saturday uses the 0 h threshold
- A `Day` column disagreeing with the parsed date raises `LoaderError`
- Dates parse day-first; the BOM is stripped; banner and blank rows are skipped
- Employees are keyed on name, so a blank badge does not split a person in two
- Rest days are listed but do not count as anomalies
- Month bucket totals sum exactly to Total OT (per-day rounding)

`ZERO_LENGTH` remains as a defensive flag but cannot fire, because the loader
routes an in == out row to a lone scan before it ever becomes a session. It is
retained only against future changes to that step.

A golden test asserts the complete Jan–June 2026 totals, all twelve employees
across six months, so future refactors cannot quietly move payroll numbers.
Because `data/` is gitignored, it is marked `pytest.mark.skipif` on the file's
absence; a clean clone still passes, with the fixture-based unit tests carrying
the real coverage.

## Repositories

Private repositories on both hosts, pushed from one local repo with two remotes:

- GitHub — `muraly-J/rdm-asia-overtime`
- GitLab — `muralyJ/rdm-asia-overtime`

Private because the export contains employee names, badge numbers and GPS
location links.

`data/*.csv` and `data/*.xlsx` are gitignored. The repository holds code only;
attendance files stay local, and uploads are never written to disk.

## Out of scope

- Overtime pay rates and monetary amounts — hours only
- Authentication and multi-user access
- Editing or correcting attendance data in the app; corrections happen in the
  source export
- Automatic ingestion from the biometric system
