# Overtime Calculator — Design

Date: 2026-07-20
Status: Approved

## Problem

RDM Asia receives one Excel attendance export per month, containing one sheet per
employee (12 for June 2026). Overtime is currently calculated by hand. It must be
automated, repeatable every month, and auditable when payroll disputes a number.

## Overtime rules

Thresholds by day type — overtime is worked hours above the threshold:

| Day type          | Threshold |
| ----------------- | --------- |
| Monday–Friday     | 9 h       |
| Saturday          | 5 h       |
| Sunday            | 0 h       |
| Public holiday    | 0 h       |

Public holiday takes precedence over Saturday.

A shift may run past midnight. Every session is attributed in full to its **login
date**: a session starting Friday 09:00 and ending Saturday 00:21 counts entirely
as Friday, at the 9 h weekday threshold. Day type is likewise determined by the
login date.

Overtime is reported to two decimal places. No rounding to quarter or half
hours; payroll applies its own rounding downstream if it wants one. Each day's
overtime is rounded to two decimals, and a month's bucket totals are the sums of
those rounded daily figures, so the summary table's Total OT always equals the
sum of its Weekday, Saturday and Sunday/PH columns — the reconciliation payroll
needs when a figure is disputed.

## Input data

Source file: `data/<Month Year>.xlsx`, e.g. `data/June 2026.xlsx`.

One worksheet per employee, sheet name being the employee's short name. Row 1 is
the header, row 2 a separator, data from row 3. Relevant columns:

| Column | Field       |
| ------ | ----------- |
| E      | Badge No.   |
| F      | Name        |
| I      | Day         |
| J      | Date        |
| K      | Time In     |
| M      | Time Out    |
| O      | Hours       |

The `Hours` column is **ignored** — hours are recomputed from the timestamps.

### Known characteristics of the export

The biometric scanner emits multiple rows per day. These are not independent
sessions; they are alternative pairings of the same underlying punch list. an employee,
10 June 2026 illustrates this:

    row 1:  04:30 -> 16:58
    row 2:  11:41 -> 01:38 (+1 day)

The underlying punches are `04:30, 11:41, 16:58, 01:38(+1d)`.

A carry-over logout can also reappear as a Time In on the following day's row.
an employee, 4–5 June 2026:

    Jun 4 row:  09:03 -> 00:48 (+1d)
    Jun 5 row:  00:48 -> 09:06,  09:06 -> 00:52 (+1d)

The `00:48` belongs to Jun 4's session and must not open a second Jun 5 session.

Sheets may contain dates outside the nominal month (an employee's June sheet includes
2026-07-01).

## Algorithm

1. **Load.** For each sheet, read every non-empty `Time In` and `Time Out`
   timestamp into a flat list of punch instants for that employee.
2. **Normalise.** Sort ascending, then collapse punches within **2 minutes** of
   each other into one, keeping the earliest. The result is one chronological
   punch timeline per employee for the whole month.

   The 2-minute window is required, not cosmetic. The scanner routinely records
   the same physical punch twice a minute apart (`17:55` and `17:56`); collapsing
   only exactly-equal timestamps leaves six of the twelve June 2026 employees
   with an odd punch count and a month of spurious `MISSING_PUNCH` flags. Two
   minutes absorbs the double-taps while never swallowing a genuine step-out —
   a wider gap such as an employee's `09:18`/`09:27` stays two distinct punches and, if
   it leaves the count odd, is flagged for human review rather than guessed at.
3. **Pair.** Walk the timeline pairing consecutive punches into
   `(login, logout)` sessions. This is what makes the an employee case correct: `00:48`
   is consumed as Jun 4's logout, so Jun 5 opens at `09:06`.

   **Carry-over cutoff.** A session may cross midnight only when its logout
   falls **before 06:00** on the following day. If the next punch is on a later
   day, or on the next day at 06:00 or later, the login is treated as a missing
   punch — it becomes a dangling session (0 h, `MISSING_PUNCH`) and the next
   punch opens a fresh session.

   Without this cutoff a single forgotten scan corrupts the entire rest of the
   month. Pairing is positional (1st–2nd, 3rd–4th, …); one missing punch shifts
   every later punch by one, so an evening clock-out marries the *next morning's*
   clock-in. In the real June 2026 data this produced 77 spurious weekend- and
   overnight-spanning "sessions" (e.g. an employee Fri 5 Jun 18:45 → Mon 8 Jun 08:56 =
   62 h) and inflated total overtime roughly threefold. The cutoff is grounded
   in the data: every genuine past-midnight logout falls between 00:00 and 05:11,
   nothing legitimate falls between 06:00 and 08:00, and the spurious sessions
   all "log out" at 08:00–09:00 — arrival time, not departure. Sessions caught by
   the cutoff are flagged for a human to supply the real missing scan at source;
   their hours are never estimated.
4. **Attribute.** Assign each session to `login.date()`.
5. **Aggregate.** Day worked hours = sum of durations of sessions logging in that
   day.
6. **Classify.** Determine day type from the login date and `holidays.yml`.
7. **Compute.** `overtime = max(0, worked_hours - threshold(day_type))`.

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

| Flag            | Condition                        | Effect on hours          |
| --------------- | -------------------------------- | ------------------------ |
| `MISSING_PUNCH` | odd punch count; dangling session | dangling session = 0 h   |
| `ZERO_LENGTH`   | login == logout                  | 0 h                      |
| `LONG_SESSION`  | single session > 16 h            | counted, flagged loudly  |
| `NO_PUNCH`      | day present with no timestamps   | 0 h, informational only  |
| `OUT_OF_MONTH`  | date outside selected month      | excluded from totals     |

A dangling session is never estimated or extrapolated. It reads 0 hours and
requires a human to correct the source data.

Loader failures — missing expected column, unparseable sheet — raise a Streamlit
error naming the sheet and row. The app never renders a partial total.

## Architecture

```
overtime/
  loader.py      xlsx -> dict[employee, list[datetime]]
  rules.py       day_type(date), threshold_hours(day_type), holiday loading
  calc.py        punches -> list[DaySummary]
  anomalies.py   DaySummary -> list[Flag]
app.py           Streamlit UI only
data/            monthly xlsx files (gitignored)
holidays.yml
tests/
```

The `overtime/` package is pure: plain functions over plain data, no Streamlit
imports, no file dialogs, no global state. `app.py` contains only widgets and
table rendering. This is what makes the rules unit-testable without running a
browser, which matters because the output is payroll money.

`DaySummary` carries: employee, date, day type, day name, sessions (list of
login/logout pairs), worked hours, threshold, overtime hours, flags.

## User interface

Sidebar: month dropdown, populated by scanning `data/` for `*.xlsx` and parsing
`<Month Year>` from the filename.

Main area:

1. **Monthly summary table** — one row per employee: total worked hours, weekday
   OT, Saturday OT, Sunday/PH OT, total OT, anomaly count.
2. **Per-employee drilldown** — employee selector, then every day of the month:
   day type, sessions, worked hours, threshold, OT, flags.
3. **Export** — download button producing an Excel workbook with the summary on
   one sheet and the full daily detail on another.

## Testing

`pytest` over `calc.py` and `rules.py`, using hand-written punch fixtures. Each
real edge case observed in June 2026 becomes a named test:

- an employee 10 June — four punches, cross-midnight, chained correctly
- an employee 4–5 June — boundary punch consumed by Jun 4, does not restart Jun 5
- An evening clock-out paired against the next morning's clock-in does NOT
  carry over: the login dangles as `MISSING_PUNCH`, 0 h (the 06:00 cutoff)
- A logout before 06:00 the next day DOES carry over and is paid in full
- Friday → Saturday carry-over retains the 9 h weekday threshold
- Public holiday falling on a Saturday uses the 0 h threshold
- Odd punch count produces `MISSING_PUNCH` and 0 hours
- an employee 3 June — `17:55`/`17:56` double-tap collapses to one punch
- an employee 8 June — `09:18`/`09:27` are nine minutes apart and stay separate
- Month bucket totals sum exactly to Total OT (per-day rounding)

`ZERO_LENGTH` remains as a defensive flag but cannot fire on data that has
passed the 2-minute collapse (an in==out pair is 0 minutes apart and always
collapses to a single punch); it is retained only against future changes to the
collapse step.

A golden test asserts the complete June 2026 twelve-employee totals so future
refactors cannot quietly move payroll numbers. Because `data/` is gitignored, it
is marked `pytest.mark.skipif` on the file's absence; a clean clone still passes,
with the fixture-based unit tests carrying the real coverage.

## Repositories

Private repositories on both hosts, pushed from one local repo with two remotes:

- GitHub — `muraly-J/rdm-asia-overtime`
- GitLab — `muralyJ/rdm-asia-overtime`

Private because the export contains employee names, badge numbers and GPS
location links.

`data/*.xlsx` is gitignored. The repository holds code only; attendance files
stay local. `data/` ships with a `.gitkeep` and a README explaining the
`<Month Year>.xlsx` naming convention.

## Out of scope

- Overtime pay rates and monetary amounts — hours only
- Authentication and multi-user access
- Editing or correcting attendance data in the app; corrections happen in the
  source export
- Automatic ingestion from the biometric system
