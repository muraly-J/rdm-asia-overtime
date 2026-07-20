# Overtime Calculator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Streamlit app that reads a monthly attendance xlsx (one sheet per employee) and reports overtime hours per the RDM Asia rules.

**Architecture:** Pure-Python `overtime/` package (loader → punch timeline → session chain → day summaries → month totals), tested with pytest; `app.py` is a thin Streamlit shell doing only widgets, tables and Excel export.

**Tech Stack:** Python 3.14 (existing `.venv`), openpyxl, PyYAML, pandas, streamlit, pytest.

**Spec:** `docs/superpowers/specs/2026-07-20-overtime-calculator-design.md` — read it before starting.

## Global Constraints

- OT thresholds: weekday 9 h, Saturday 5 h, Sunday 0 h, public holiday 0 h; holiday beats Saturday.
- A session is attributed entirely to its **login date**; day type also comes from the login date.
- Punches within **2 minutes** of the previous kept punch collapse (keep earliest).
- Dangling session (odd punch count) = 0 h + `MISSING_PUNCH` flag; never estimated.
- Hours reported exact, rounded to 2 dp only at presentation/aggregation.
- `data/*.xlsx` is gitignored; never commit attendance files.
- The xlsx `Hours` column is ignored; hours recomputed from timestamps.
- Interpreter: `.venv/bin/python`, tests via `.venv/bin/python -m pytest`.
- Commit with `git -c user.email=asiaadmin@resourcedm.com -c user.name="RDM Asia" commit ...`.

---

### Task 1: Scaffold + rules.py (day types, thresholds, holidays)

**Files:**
- Create: `requirements.txt`, `overtime/__init__.py`, `overtime/rules.py`, `data/.gitkeep`, `data/README.md`
- Test: `tests/test_rules.py`

**Interfaces:**
- Produces: `rules.load_holidays(path: str | Path) -> dict[date, str]`; `rules.day_type(d: date, holidays: dict[date, str]) -> str` returning one of `"weekday" | "saturday" | "sunday" | "holiday"`; `rules.THRESHOLDS: dict[str, float]`.

- [ ] **Step 1: requirements + package + data dir**

`requirements.txt`:
```
streamlit
openpyxl
pandas
PyYAML
pytest
```

`overtime/__init__.py`: empty file.

`data/README.md`:
```markdown
# data/

Drop monthly attendance exports here, named `<Month Year>.xlsx`, e.g. `June 2026.xlsx`.
Files in this folder are gitignored — attendance data never goes to GitHub/GitLab.
```

`data/.gitkeep`: empty file. Then:

Run: `.venv/bin/pip install -r requirements.txt`
Expected: installs without error. Move the existing `June 2026.xlsx` into `data/`:
`mv "June 2026.xlsx" data/`

- [ ] **Step 2: Write failing tests**

`tests/test_rules.py`:
```python
from datetime import date

from overtime.rules import THRESHOLDS, day_type, load_holidays

HOLIDAYS = {date(2026, 6, 1): "Agong's Birthday", date(2026, 6, 17): "Awal Muharram",
            date(2026, 8, 8): "Fake Saturday PH"}


def test_weekday():
    assert day_type(date(2026, 6, 2), HOLIDAYS) == "weekday"  # Tue


def test_saturday():
    assert day_type(date(2026, 6, 6), HOLIDAYS) == "saturday"


def test_sunday():
    assert day_type(date(2026, 6, 7), HOLIDAYS) == "sunday"


def test_holiday_on_weekday():
    assert day_type(date(2026, 6, 17), HOLIDAYS) == "holiday"  # Wed PH


def test_holiday_beats_saturday():
    # 2026-08-08 is a Saturday; holiday wins
    assert day_type(date(2026, 8, 8), HOLIDAYS) == "holiday"


def test_thresholds():
    assert THRESHOLDS == {"weekday": 9.0, "saturday": 5.0, "sunday": 0.0, "holiday": 0.0}


def test_load_holidays_real_file():
    h = load_holidays("holidays.yml")
    assert h[date(2026, 6, 1)] == "Agong's Birthday"
    assert h[date(2026, 12, 25)] == "Christmas Day"
    assert len(h) == 12
```

- [ ] **Step 3: Run tests, verify failure**

Run: `.venv/bin/python -m pytest tests/test_rules.py -v`
Expected: FAIL — `ModuleNotFoundError` / `ImportError` on `overtime.rules`.

- [ ] **Step 4: Implement `overtime/rules.py`**

```python
"""Day classification and overtime thresholds."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

# Hours of work before overtime starts, by day type.
THRESHOLDS: dict[str, float] = {
    "weekday": 9.0,
    "saturday": 5.0,
    "sunday": 0.0,
    "holiday": 0.0,
}


def load_holidays(path: str | Path) -> dict[date, str]:
    """Read holidays.yml -> {date: holiday name}, flattened across years."""
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    holidays: dict[date, str] = {}
    for entries in raw.values():
        for entry in entries:
            d = entry["date"]
            if not isinstance(d, date):
                d = date.fromisoformat(str(d))
            holidays[d] = entry["name"]
    return holidays


def day_type(d: date, holidays: dict[date, str]) -> str:
    """Classify a date. Public holiday beats Saturday/Sunday."""
    if d in holidays:
        return "holiday"
    if d.weekday() == 5:
        return "saturday"
    if d.weekday() == 6:
        return "sunday"
    return "weekday"
```

- [ ] **Step 5: Run tests, verify pass**

Run: `.venv/bin/python -m pytest tests/test_rules.py -v`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt overtime tests data/README.md data/.gitkeep
git -c user.email=asiaadmin@resourcedm.com -c user.name="RDM Asia" commit -m "feat: rules module — day types, thresholds, holiday loading"
```

---

### Task 2: calc.py — punch collapse and session pairing

**Files:**
- Create: `overtime/calc.py`
- Test: `tests/test_calc_sessions.py`

**Interfaces:**
- Produces:
  - `calc.Session` — frozen dataclass, fields `login: datetime`, `logout: datetime | None`; property `hours -> float` (0.0 when dangling).
  - `calc.collapse_punches(punches: list[datetime], tolerance_minutes: int = 2) -> list[datetime]` — sorted, deduped.
  - `calc.pair_sessions(punches: list[datetime]) -> list[Session]` — consecutive in/out pairs; odd count leaves a final dangling `Session(login, None)`.

- [ ] **Step 1: Write failing tests**

`tests/test_calc_sessions.py`:
```python
from datetime import datetime

from overtime.calc import Session, collapse_punches, pair_sessions


def dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def test_collapse_scanner_double_tap():
    # an employee 3 June: 17:55 and 17:56 are one physical punch
    punches = [dt("2026-06-03 09:19"), dt("2026-06-03 17:55"), dt("2026-06-03 17:56")]
    assert collapse_punches(punches) == [dt("2026-06-03 09:19"), dt("2026-06-03 17:55")]


def test_collapse_keeps_9_minute_gap():
    # an employee 8 June: 09:18 / 09:27 are distinct punches
    punches = [dt("2026-06-08 09:18"), dt("2026-06-08 09:27")]
    assert collapse_punches(punches) == punches


def test_collapse_sorts_and_dedupes_exact():
    punches = [dt("2026-06-03 17:55"), dt("2026-06-03 09:19"), dt("2026-06-03 09:19")]
    assert collapse_punches(punches) == [dt("2026-06-03 09:19"), dt("2026-06-03 17:55")]


def test_pair_simple_day():
    s = pair_sessions([dt("2026-06-02 08:54"), dt("2026-06-02 18:55")])
    assert s == [Session(dt("2026-06-02 08:54"), dt("2026-06-02 18:55"))]
    assert round(s[0].hours, 2) == 10.02


def test_pair_cross_midnight_chain():
    # an employee 4–5 June: 00:48 closes Jun 4 and must NOT reopen Jun 5
    punches = [dt("2026-06-04 09:03"), dt("2026-06-05 00:48"),
               dt("2026-06-05 09:06"), dt("2026-06-06 00:52")]
    s = pair_sessions(punches)
    assert s == [Session(dt("2026-06-04 09:03"), dt("2026-06-05 00:48")),
                 Session(dt("2026-06-05 09:06"), dt("2026-06-06 00:52"))]


def test_pair_zarif_four_punch_day():
    # an employee 10 June: 04:30, 11:41, 16:58, 01:38(+1d)
    punches = [dt("2026-06-10 04:30"), dt("2026-06-10 11:41"),
               dt("2026-06-10 16:58"), dt("2026-06-11 01:38")]
    s = pair_sessions(punches)
    assert s == [Session(dt("2026-06-10 04:30"), dt("2026-06-10 11:41")),
                 Session(dt("2026-06-10 16:58"), dt("2026-06-11 01:38"))]


def test_pair_odd_count_dangles():
    s = pair_sessions([dt("2026-06-02 08:54"), dt("2026-06-02 18:55"), dt("2026-06-03 09:00")])
    assert s[-1] == Session(dt("2026-06-03 09:00"), None)
    assert s[-1].hours == 0.0
```

- [ ] **Step 2: Run tests, verify failure**

Run: `.venv/bin/python -m pytest tests/test_calc_sessions.py -v`
Expected: FAIL — `ModuleNotFoundError: overtime.calc`.

- [ ] **Step 3: Implement `overtime/calc.py`**

```python
"""Punch timeline -> sessions -> per-day summaries."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Session:
    login: datetime
    logout: datetime | None  # None = dangling (missing logout punch)

    @property
    def hours(self) -> float:
        if self.logout is None:
            return 0.0
        return (self.logout - self.login).total_seconds() / 3600.0


def collapse_punches(punches: list[datetime], tolerance_minutes: int = 2) -> list[datetime]:
    """Sort punches and collapse scanner double-taps.

    A punch within `tolerance_minutes` of the previously *kept* punch is the
    same physical punch recorded twice; keep the earliest.
    """
    tol = timedelta(minutes=tolerance_minutes)
    kept: list[datetime] = []
    for p in sorted(punches):
        if kept and p - kept[-1] <= tol:
            continue
        kept.append(p)
    return kept


def pair_sessions(punches: list[datetime]) -> list[Session]:
    """Pair a chronological punch timeline into (login, logout) sessions.

    Punches must already be collapsed and sorted. An odd count leaves the
    final punch as a dangling session with no logout.
    """
    sessions: list[Session] = []
    for i in range(0, len(punches) - 1, 2):
        sessions.append(Session(punches[i], punches[i + 1]))
    if len(punches) % 2 == 1:
        sessions.append(Session(punches[-1], None))
    return sessions
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv/bin/python -m pytest tests/test_calc_sessions.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add overtime/calc.py tests/test_calc_sessions.py
git -c user.email=asiaadmin@resourcedm.com -c user.name="RDM Asia" commit -m "feat: punch collapse and chronological session pairing"
```

---

### Task 3: anomalies.py — day-level flags

**Files:**
- Create: `overtime/anomalies.py`
- Test: `tests/test_anomalies.py`

**Interfaces:**
- Consumes: `calc.Session`.
- Produces: `anomalies.day_flags(sessions: list[Session], had_row: bool) -> list[str]` — subset of `["NO_PUNCH", "MISSING_PUNCH", "ZERO_LENGTH", "LONG_SESSION"]`, in that order. (`OUT_OF_MONTH` is set by `summarize_month` in Task 4, not here — it depends on the selected month, which this module doesn't know.)

- [ ] **Step 1: Write failing tests**

`tests/test_anomalies.py`:
```python
from datetime import datetime

from overtime.anomalies import day_flags
from overtime.calc import Session


def dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def test_no_punch_day():
    assert day_flags([], had_row=True) == ["NO_PUNCH"]


def test_normal_day_no_flags():
    s = [Session(dt("2026-06-02 08:54"), dt("2026-06-02 18:55"))]
    assert day_flags(s, had_row=True) == []


def test_dangling_session_flags_missing_punch():
    s = [Session(dt("2026-06-03 09:00"), None)]
    assert day_flags(s, had_row=True) == ["MISSING_PUNCH"]


def test_zero_length_session():
    s = [Session(dt("2026-06-04 08:48"), dt("2026-06-04 08:48"))]
    assert day_flags(s, had_row=True) == ["ZERO_LENGTH"]


def test_long_session_over_16h():
    # an employee-style 21h chain: counted but flagged
    s = [Session(dt("2026-06-10 04:30"), dt("2026-06-11 01:38"))]
    assert day_flags(s, had_row=True) == ["LONG_SESSION"]


def test_16h_exactly_not_flagged():
    s = [Session(dt("2026-06-10 06:00"), dt("2026-06-10 22:00"))]
    assert day_flags(s, had_row=True) == []
```

- [ ] **Step 2: Run tests, verify failure**

Run: `.venv/bin/python -m pytest tests/test_anomalies.py -v`
Expected: FAIL — `ModuleNotFoundError: overtime.anomalies`.

- [ ] **Step 3: Implement `overtime/anomalies.py`**

```python
"""Per-day data-quality flags. Bad data is surfaced, never silently paid or dropped."""
from __future__ import annotations

from .calc import Session

LONG_SESSION_HOURS = 16.0


def day_flags(sessions: list[Session], had_row: bool) -> list[str]:
    flags: list[str] = []
    if not sessions:
        if had_row:
            flags.append("NO_PUNCH")
        return flags
    if any(s.logout is None for s in sessions):
        flags.append("MISSING_PUNCH")
    if any(s.logout is not None and s.logout == s.login for s in sessions):
        flags.append("ZERO_LENGTH")
    if any(s.hours > LONG_SESSION_HOURS for s in sessions):
        flags.append("LONG_SESSION")
    return flags
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv/bin/python -m pytest tests/test_anomalies.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add overtime/anomalies.py tests/test_anomalies.py
git -c user.email=asiaadmin@resourcedm.com -c user.name="RDM Asia" commit -m "feat: day-level anomaly flags"
```

---

### Task 4: calc.py — DaySummary, summarize_month, month_totals

**Files:**
- Modify: `overtime/calc.py` (append)
- Test: `tests/test_summarize.py`

**Interfaces:**
- Consumes: `rules.day_type`, `rules.THRESHOLDS`, `anomalies.day_flags`, Task 2's `Session`/`collapse_punches`/`pair_sessions`.
- Produces:
  - `calc.DaySummary` — dataclass: `employee: str`, `date: date`, `day_type: str`, `sessions: list[Session]`, `worked_hours: float`, `threshold: float`, `overtime_hours: float`, `flags: list[str]`, `in_month: bool`.
  - `calc.summarize_month(employee: str, punches: list[datetime], dates_present: set[date], month: tuple[int, int], holidays: dict[date, str]) -> list[DaySummary]` — sorted by date; collapses + pairs internally.
  - `calc.month_totals(summaries: list[DaySummary]) -> dict` — keys `worked`, `ot_weekday`, `ot_saturday`, `ot_sunday_ph`, `ot_total`, `anomalies`; hours rounded 2 dp; only `in_month` days; `anomalies` counts days having any flag other than `NO_PUNCH`.

- [ ] **Step 1: Write failing tests**

`tests/test_summarize.py`:
```python
from datetime import date, datetime

from overtime.calc import month_totals, summarize_month

HOLIDAYS = {date(2026, 6, 1): "Agong's Birthday", date(2026, 6, 17): "Awal Muharram"}
JUNE = (2026, 6)


def dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def find(summaries, d):
    return next(s for s in summaries if s.date == d)


def test_weekday_overtime_after_9h():
    # in 09:04 out 19:48 = 10.73h -> OT 1.73
    s = summarize_month("X", [dt("2026-06-04 09:04"), dt("2026-06-04 19:48")],
                        {date(2026, 6, 4)}, JUNE, HOLIDAYS)
    d = find(s, date(2026, 6, 4))
    assert d.day_type == "weekday"
    assert round(d.worked_hours, 2) == 10.73
    assert round(d.overtime_hours, 2) == 1.73


def test_under_threshold_zero_ot():
    s = summarize_month("X", [dt("2026-06-03 09:19"), dt("2026-06-03 17:56")],
                        {date(2026, 6, 3)}, JUNE, HOLIDAYS)
    assert find(s, date(2026, 6, 3)).overtime_hours == 0.0


def test_saturday_threshold_5h():
    s = summarize_month("X", [dt("2026-06-06 09:35"), dt("2026-06-06 22:39")],
                        {date(2026, 6, 6)}, JUNE, HOLIDAYS)
    d = find(s, date(2026, 6, 6))
    assert d.day_type == "saturday"
    assert round(d.overtime_hours, 2) == round(d.worked_hours - 5.0, 2)


def test_sunday_all_hours_are_ot():
    s = summarize_month("X", [dt("2026-06-14 09:36"), dt("2026-06-14 19:41")],
                        {date(2026, 6, 14)}, JUNE, HOLIDAYS)
    d = find(s, date(2026, 6, 14))
    assert d.day_type == "sunday"
    assert d.overtime_hours == d.worked_hours


def test_holiday_all_hours_are_ot():
    # Awal Muharram, Wed 17 June
    s = summarize_month("X", [dt("2026-06-17 12:30"), dt("2026-06-17 20:14")],
                        {date(2026, 6, 17)}, JUNE, HOLIDAYS)
    d = find(s, date(2026, 6, 17))
    assert d.day_type == "holiday"
    assert d.overtime_hours == d.worked_hours


def test_cross_midnight_belongs_to_login_date():
    # Fri 09:00 -> Sat 00:21: all Friday, 9h threshold, Saturday untouched
    s = summarize_month("X", [dt("2026-06-19 09:00"), dt("2026-06-20 00:21")],
                        {date(2026, 6, 19), date(2026, 6, 20)}, JUNE, HOLIDAYS)
    fri, sat = find(s, date(2026, 6, 19)), find(s, date(2026, 6, 20))
    assert round(fri.worked_hours, 2) == 15.35
    assert round(fri.overtime_hours, 2) == 6.35
    assert sat.worked_hours == 0.0 and sat.flags == ["NO_PUNCH"]


def test_dangling_session_zero_hours_flagged():
    s = summarize_month("X", [dt("2026-06-02 09:00")], {date(2026, 6, 2)}, JUNE, HOLIDAYS)
    d = find(s, date(2026, 6, 2))
    assert d.worked_hours == 0.0
    assert "MISSING_PUNCH" in d.flags


def test_out_of_month_excluded_from_totals_but_listed():
    s = summarize_month("X", [dt("2026-07-01 04:11"), dt("2026-07-01 14:40")],
                        {date(2026, 7, 1)}, JUNE, HOLIDAYS)
    d = find(s, date(2026, 7, 1))
    assert d.in_month is False
    assert "OUT_OF_MONTH" in d.flags
    assert month_totals(s)["worked"] == 0.0


def test_month_totals_buckets():
    punches = [
        dt("2026-06-04 09:04"), dt("2026-06-04 19:48"),   # weekday OT 1.73
        dt("2026-06-06 09:00"), dt("2026-06-06 16:00"),   # saturday OT 2.0
        dt("2026-06-14 10:00"), dt("2026-06-14 14:00"),   # sunday OT 4.0
        dt("2026-06-17 12:00"), dt("2026-06-17 15:00"),   # holiday OT 3.0
    ]
    days = {date(2026, 6, 4), date(2026, 6, 6), date(2026, 6, 14), date(2026, 6, 17)}
    t = month_totals(summarize_month("X", punches, days, JUNE, HOLIDAYS))
    assert t["ot_weekday"] == 1.73
    assert t["ot_saturday"] == 2.0
    assert t["ot_sunday_ph"] == 7.0
    assert t["ot_total"] == 10.73
    assert t["anomalies"] == 0
```

- [ ] **Step 2: Run tests, verify failure**

Run: `.venv/bin/python -m pytest tests/test_summarize.py -v`
Expected: FAIL — `ImportError: cannot import name 'summarize_month'`.

- [ ] **Step 3: Append to `overtime/calc.py`**

Add imports at top of file (`date`, `field`, rules, anomalies):
```python
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .anomalies import day_flags
from .rules import THRESHOLDS, day_type
```
(Merge with the existing import lines; `anomalies` imports `calc.Session`, so import `anomalies` lazily inside `summarize_month` if a circular import bites — see body below, which imports at module level from `.anomalies`; since `anomalies.py` imports only `Session` from `.calc`, break the cycle by moving `from .anomalies import day_flags` INSIDE `summarize_month`.)

Append:
```python
@dataclass
class DaySummary:
    employee: str
    date: date
    day_type: str
    sessions: list[Session]
    worked_hours: float
    threshold: float
    overtime_hours: float
    flags: list[str] = field(default_factory=list)
    in_month: bool = True


def summarize_month(
    employee: str,
    punches: list[datetime],
    dates_present: set[date],
    month: tuple[int, int],
    holidays: dict[date, str],
) -> list[DaySummary]:
    """Full pipeline for one employee: collapse -> pair -> attribute -> classify."""
    from .anomalies import day_flags  # local import: anomalies imports Session from us

    sessions = pair_sessions(collapse_punches(punches))
    by_day: dict[date, list[Session]] = {}
    for s in sessions:
        by_day.setdefault(s.login.date(), []).append(s)

    summaries: list[DaySummary] = []
    for d in sorted(dates_present | set(by_day)):
        day_sessions = by_day.get(d, [])
        dtype = day_type(d, holidays)
        worked = sum(s.hours for s in day_sessions)
        threshold = THRESHOLDS[dtype]
        ot = max(0.0, worked - threshold)
        flags = day_flags(day_sessions, had_row=d in dates_present)
        in_month = (d.year, d.month) == month
        if not in_month:
            flags.append("OUT_OF_MONTH")
        summaries.append(DaySummary(employee, d, dtype, day_sessions,
                                    worked, threshold, ot, flags, in_month))
    return summaries


def month_totals(summaries: list[DaySummary]) -> dict:
    """Aggregate one employee's month. Out-of-month days are excluded."""
    t = {"worked": 0.0, "ot_weekday": 0.0, "ot_saturday": 0.0,
         "ot_sunday_ph": 0.0, "ot_total": 0.0, "anomalies": 0}
    bucket = {"weekday": "ot_weekday", "saturday": "ot_saturday",
              "sunday": "ot_sunday_ph", "holiday": "ot_sunday_ph"}
    for s in summaries:
        if not s.in_month:
            continue
        t["worked"] += s.worked_hours
        t[bucket[s.day_type]] += s.overtime_hours
        t["ot_total"] += s.overtime_hours
        if any(f != "NO_PUNCH" for f in s.flags):
            t["anomalies"] += 1
    for k in ("worked", "ot_weekday", "ot_saturday", "ot_sunday_ph", "ot_total"):
        t[k] = round(t[k], 2)
    return t
```
Note: keep only the local `day_flags` import (inside the function); do not also add it at module level.

- [ ] **Step 4: Run full suite, verify pass**

Run: `.venv/bin/python -m pytest -v`
Expected: all tests pass (rules 7, sessions 7, anomalies 6, summarize 9).

- [ ] **Step 5: Commit**

```bash
git add overtime/calc.py tests/test_summarize.py
git -c user.email=asiaadmin@resourcedm.com -c user.name="RDM Asia" commit -m "feat: day summaries and monthly totals"
```

---

### Task 5: loader.py — xlsx → punch timelines

**Files:**
- Create: `overtime/loader.py`
- Test: `tests/test_loader.py` (builds a synthetic xlsx fixture in tmp_path — no real employee data in the repo)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces:
  - `loader.EmployeeSheet` — dataclass: `short_name: str` (sheet name), `full_name: str`, `punches: list[datetime]` (raw, uncollapsed), `dates_present: set[date]`.
  - `loader.LoaderError(Exception)` — message names sheet and problem.
  - `loader.load_attendance(path: str | Path) -> list[EmployeeSheet]` — one entry per sheet, sheet order preserved.

- [ ] **Step 1: Write failing tests**

`tests/test_loader.py`:
```python
from datetime import date, datetime

import openpyxl
import pytest

from overtime.loader import EmployeeSheet, LoaderError, load_attendance

HEADER = ["Branch", "Department", "Sect.", "Work Pattern", "Badge No.", "Name",
          "Location", "P.Pos", "Day", "Date", "Time In", "In (Map)",
          "Time Out", "Out (Map)", "Hours"]


def make_xlsx(tmp_path, rows, header=HEADER, sheet="Alice"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(header)
    ws.append(["── ALICE WONG"] + [None] * 14)  # separator row, as in the real export
    for r in rows:
        ws.append(r)
    p = tmp_path / "test.xlsx"
    wb.save(p)
    return p


def row(d, tin, tout, name="ALICE WONG BINTI X"):
    return ["RDM", "TECH", None, "Option 2", "10099", name, None, "Employee",
            d.strftime("%a"), datetime(d.year, d.month, d.day), tin, None, tout, None, None]


def test_loads_punches_and_dates(tmp_path):
    p = make_xlsx(tmp_path, [
        row(date(2026, 6, 2), datetime(2026, 6, 2, 8, 54), datetime(2026, 6, 2, 18, 55)),
        row(date(2026, 6, 3), None, None),  # no-punch day
    ])
    [emp] = load_attendance(p)
    assert isinstance(emp, EmployeeSheet)
    assert emp.short_name == "Alice"
    assert emp.full_name == "ALICE WONG BINTI X"
    assert emp.punches == [datetime(2026, 6, 2, 8, 54), datetime(2026, 6, 2, 18, 55)]
    assert emp.dates_present == {date(2026, 6, 2), date(2026, 6, 3)}


def test_duplicate_rows_yield_duplicate_punches_verbatim(tmp_path):
    # loader does NOT dedupe — that's calc.collapse_punches' job
    r = row(date(2026, 6, 2), datetime(2026, 6, 2, 8, 54), datetime(2026, 6, 2, 18, 55))
    p = make_xlsx(tmp_path, [r, r])
    [emp] = load_attendance(p)
    assert len(emp.punches) == 4


def test_bad_header_raises_with_sheet_name(tmp_path):
    p = make_xlsx(tmp_path, [], header=["Wrong"] * 15)
    with pytest.raises(LoaderError, match="Alice"):
        load_attendance(p)


def test_real_june_file_if_present():
    path = "data/June 2026.xlsx"
    import os
    if not os.path.exists(path):
        pytest.skip("real data file absent")
    sheets = load_attendance(path)
    assert len(sheets) == 12
    assert sheets[0].short_name == "an employee"
    assert all(s.punches for s in sheets)
```

- [ ] **Step 2: Run tests, verify failure**

Run: `.venv/bin/python -m pytest tests/test_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: overtime.loader`.

- [ ] **Step 3: Implement `overtime/loader.py`**

```python
"""Read the biometric attendance export: one sheet per employee.

Columns (1-based): E=Badge, F=Name, I=Day, J=Date, K=Time In, M=Time Out.
Row 1 header, row 2 separator, data from row 3. The Hours column is ignored;
hours are recomputed from timestamps downstream.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import openpyxl

COL_NAME = 5      # 0-based index into row tuple: F
COL_DATE = 9      # J
COL_TIME_IN = 10  # K
COL_TIME_OUT = 12 # M


class LoaderError(Exception):
    pass


@dataclass
class EmployeeSheet:
    short_name: str
    full_name: str
    punches: list[datetime] = field(default_factory=list)
    dates_present: set[date] = field(default_factory=set)


def load_attendance(path: str | Path) -> list[EmployeeSheet]:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    employees: list[EmployeeSheet] = []
    for ws in wb.worksheets:
        rows = ws.iter_rows(values_only=True)
        try:
            header = next(rows)
        except StopIteration:
            raise LoaderError(f"sheet {ws.title!r}: empty sheet") from None
        if len(header) <= COL_TIME_OUT or header[COL_DATE] != "Date" \
                or header[COL_TIME_IN] != "Time In" or header[COL_TIME_OUT] != "Time Out":
            raise LoaderError(
                f"sheet {ws.title!r}: unexpected header layout "
                f"(expected Date/Time In/Time Out in columns J/K/M)")
        emp = EmployeeSheet(short_name=ws.title, full_name="")
        for i, r in enumerate(rows, start=2):
            d = r[COL_DATE] if len(r) > COL_DATE else None
            if not isinstance(d, datetime):
                continue  # separator / junk row
            if not emp.full_name and isinstance(r[COL_NAME], str):
                emp.full_name = r[COL_NAME].strip()
            emp.dates_present.add(d.date())
            for col in (COL_TIME_IN, COL_TIME_OUT):
                v = r[col] if len(r) > col else None
                if isinstance(v, datetime):
                    emp.punches.append(v)
                elif v is not None:
                    raise LoaderError(
                        f"sheet {ws.title!r} row {i + 1}: unparseable timestamp {v!r}")
        employees.append(emp)
    wb.close()
    return employees
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv/bin/python -m pytest tests/test_loader.py -v`
Expected: 4 passed (the real-file test passes since `data/June 2026.xlsx` exists locally).

- [ ] **Step 5: Commit**

```bash
git add overtime/loader.py tests/test_loader.py
git -c user.email=asiaadmin@resourcedm.com -c user.name="RDM Asia" commit -m "feat: attendance xlsx loader"
```

---

### Task 6: Golden test — freeze June 2026 totals

**Files:**
- Create: `scripts/golden_dump.py`, `tests/test_golden_june_2026.py`

**Interfaces:**
- Consumes: `loader.load_attendance`, `calc.summarize_month`, `calc.month_totals`, `rules.load_holidays`.

- [ ] **Step 1: Write the dump script**

`scripts/golden_dump.py`:
```python
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
```

- [ ] **Step 2: Run it and sanity-check**

Run: `.venv/bin/python scripts/golden_dump.py`
Expected: 12 lines, one per employee. Sanity checks before freezing:
- an employee `ot_weekday` > 0 (he has several 10–11 h weekdays).
- an employee and an employee have `anomalies` ≥ 1 (their long cross-midnight chains exceed 16 h).
- Everyone's `ot_sunday_ph` > 0 if they worked Jun 1, Jun 17, or any Sunday.
- No negative numbers anywhere.

- [ ] **Step 3: Write the golden test with the frozen output**

`tests/test_golden_june_2026.py` — paste the printed `EXPECTED` dict verbatim into the marked spot:
```python
"""Golden test: full June 2026 totals for all 12 employees.

Freezes real payroll numbers so refactors cannot silently move them.
Requires the real (gitignored) data file; skipped on clean clones.
"""
import os

import pytest

from overtime.calc import month_totals, summarize_month
from overtime.loader import load_attendance
from overtime.rules import load_holidays

DATA = "data/June 2026.xlsx"

# <paste the EXPECTED dict printed by scripts/golden_dump.py here>


@pytest.mark.skipif(not os.path.exists(DATA), reason="real data file absent")
def test_june_2026_totals():
    holidays = load_holidays("holidays.yml")
    actual = {}
    for emp in load_attendance(DATA):
        actual[emp.short_name] = month_totals(
            summarize_month(emp.short_name, emp.punches, emp.dates_present,
                            (2026, 6), holidays))
    assert actual == EXPECTED
```

- [ ] **Step 4: Run full suite, verify pass**

Run: `.venv/bin/python -m pytest -v`
Expected: all pass, golden test included.

- [ ] **Step 5: Commit**

```bash
git add scripts/golden_dump.py tests/test_golden_june_2026.py
git -c user.email=asiaadmin@resourcedm.com -c user.name="RDM Asia" commit -m "test: golden June 2026 payroll totals"
```

---

### Task 7: app.py — Streamlit UI with export

**Files:**
- Create: `app.py`

**Interfaces:**
- Consumes: `loader.load_attendance`, `loader.LoaderError`, `calc.summarize_month`, `calc.month_totals`, `calc.DaySummary`, `rules.load_holidays`.

No pytest here — the logic under the UI is already tested; this task's test is a manual smoke check (Step 2).

- [ ] **Step 1: Implement `app.py`**

```python
"""RDM Asia overtime calculator — Streamlit UI.

All calculation lives in the overtime/ package; this file is widgets only.
"""
from __future__ import annotations

import io
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from overtime.calc import DaySummary, month_totals, summarize_month
from overtime.loader import LoaderError, load_attendance
from overtime.rules import THRESHOLDS, load_holidays

DATA_DIR = Path("data")
HOLIDAYS_FILE = "holidays.yml"

st.set_page_config(page_title="RDM Asia Overtime", layout="wide")
st.title("RDM Asia — Monthly Overtime")


def discover_months() -> dict[str, Path]:
    """Map 'June 2026' -> path, newest first, for files named '<Month Year>.xlsx'."""
    found = {}
    for p in sorted(DATA_DIR.glob("*.xlsx")):
        m = re.fullmatch(r"([A-Za-z]+) (\d{4})", p.stem)
        if not m:
            continue
        try:
            key = datetime.strptime(p.stem, "%B %Y")
        except ValueError:
            continue
        found[p.stem] = (key, p)
    ordered = sorted(found.items(), key=lambda kv: kv[1][0], reverse=True)
    return {name: path for name, (_, path) in ordered}


months = discover_months()
if not months:
    st.error(f"No attendance files found. Drop '<Month Year>.xlsx' into {DATA_DIR}/.")
    st.stop()

month_name = st.sidebar.selectbox("Month", list(months))
month_dt = datetime.strptime(month_name, "%B %Y")
month = (month_dt.year, month_dt.month)

try:
    holidays = load_holidays(HOLIDAYS_FILE)
    sheets = load_attendance(months[month_name])
except (LoaderError, OSError, KeyError) as e:
    st.error(f"Failed to load data: {e}")
    st.stop()

month_hols = {d: n for d, n in holidays.items() if (d.year, d.month) == month}
if month_hols:
    st.sidebar.markdown("**Public holidays this month**")
    for d, n in sorted(month_hols.items()):
        st.sidebar.write(f"{d:%a %d %b} — {n}")

all_days: dict[str, list[DaySummary]] = {}
rows = []
for emp in sheets:
    days = summarize_month(emp.short_name, emp.punches, emp.dates_present, month, holidays)
    all_days[emp.short_name] = days
    t = month_totals(days)
    rows.append({"Employee": emp.short_name, "Full name": emp.full_name,
                 "Worked (h)": t["worked"], "Weekday OT": t["ot_weekday"],
                 "Saturday OT": t["ot_saturday"], "Sun/PH OT": t["ot_sunday_ph"],
                 "Total OT": t["ot_total"], "Anomalies": t["anomalies"]})

summary_df = pd.DataFrame(rows)

st.subheader(f"Summary — {month_name}")
st.dataframe(summary_df, use_container_width=True, hide_index=True)
if summary_df["Anomalies"].sum():
    st.warning("Some days carry anomaly flags — check the drilldown before paying these numbers.")


def detail_frame(days: list[DaySummary]) -> pd.DataFrame:
    recs = []
    for d in days:
        sessions = "; ".join(
            f"{s.login:%H:%M}–{s.logout:%d %H:%M}" if s.logout and s.logout.date() != s.login.date()
            else f"{s.login:%H:%M}–{s.logout:%H:%M}" if s.logout
            else f"{s.login:%H:%M}–?"
            for s in d.sessions)
        recs.append({"Date": f"{d.date:%a %d %b}", "Type": d.day_type,
                     "Sessions": sessions, "Worked (h)": round(d.worked_hours, 2),
                     "Threshold": d.threshold, "OT (h)": round(d.overtime_hours, 2),
                     "Flags": ", ".join(d.flags)})
    return pd.DataFrame(recs)


st.subheader("Employee drilldown")
who = st.selectbox("Employee", list(all_days))
st.dataframe(detail_frame(all_days[who]), use_container_width=True, hide_index=True)

buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as xw:
    summary_df.to_excel(xw, sheet_name="Summary", index=False)
    for name, days in all_days.items():
        detail_frame(days).to_excel(xw, sheet_name=name[:31], index=False)
st.download_button(f"Download {month_name} overtime report (.xlsx)", buf.getvalue(),
                   file_name=f"Overtime {month_name}.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
```

- [ ] **Step 2: Manual smoke test**

Run: `.venv/bin/python -m streamlit run app.py --server.headless true`
Open the printed local URL and verify:
- Month dropdown shows "June 2026".
- Sidebar lists Agong's Birthday (Mon 01 Jun) and Awal Muharram (Wed 17 Jun).
- Summary shows 12 rows; an employee/an employee show anomaly counts > 0.
- Drilldown for an employee: Jun 4 ≈ 15.75 h worked, Jun 5 starts 09:06 (not 00:48).
- Download button yields an xlsx with a Summary sheet + 12 detail sheets.
Stop the server with Ctrl-C.

- [ ] **Step 3: Commit**

```bash
git add app.py
git -c user.email=asiaadmin@resourcedm.com -c user.name="RDM Asia" commit -m "feat: Streamlit UI with summary, drilldown and Excel export"
```

---

### Task 8: README + publish to GitHub and GitLab

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
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
.venv/bin/python -m pytest   # 30+ tests; golden test auto-skips without real data
```

Design: `docs/superpowers/specs/2026-07-20-overtime-calculator-design.md`
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git -c user.email=asiaadmin@resourcedm.com -c user.name="RDM Asia" commit -m "docs: README"
```

- [ ] **Step 3: Create private repos and push both remotes**

```bash
git branch -M main
gh repo create rdm-asia-overtime --private --source . --remote origin --push
glab repo create rdm-asia-overtime --private
git remote add gitlab https://gitlab.com/muralyJ/rdm-asia-overtime.git
git push -u gitlab main
```
Expected: `origin` → github.com/muraly-J/rdm-asia-overtime (private), `gitlab` → gitlab.com/muralyJ/rdm-asia-overtime (private), both showing the full commit history. If `glab repo create` already added a remote named `origin`, it may instead be named differently — check with `git remote -v` and adjust so GitHub is `origin` and GitLab is `gitlab`.

- [ ] **Step 4: Verify nothing sensitive was pushed**

```bash
git ls-files | grep -i xlsx
```
Expected: no output (no attendance files tracked).
