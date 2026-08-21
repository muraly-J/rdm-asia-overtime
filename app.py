"""RDM Asia overtime calculator — Streamlit UI.

All calculation lives in the overtime/ package; this file is widgets only.
"""
from __future__ import annotations

import io
import re
from collections import Counter
from datetime import date

import pandas as pd
import streamlit as st

from overtime.calc import DaySummary, month_totals, summarize_employee
from overtime.loader import EmployeeAttendance, LoaderError, load_attendance
from overtime.merge import merge_files
from overtime.rules import load_holidays

HOLIDAYS_FILE = "holidays.yml"

FLAG_LEGEND = [
    ("MISSING_PUNCH",
     "Someone scanned in but never scanned out.",
     "**The whole day pays no overtime**, including any complete session that day. "
     "The hours are still shown so you can see what was worked. Correct the missing "
     "scan in the attendance system and the day will pay normally."),
    ("LONG_SESSION",
     "One unbroken stretch longer than 16 hours.",
     "These hours **are** counted and paid. Almost always a forgotten scan-out rather "
     "than a real 16-hour day, so check before paying."),
    ("NO_PUNCH",
     "No scans at all that day.",
     "A rest day, approved leave or an absence. Not an error, and not counted in the "
     "Anomalies column."),
    ("OUT_OF_MONTH",
     "The row is dated outside the month selected above.",
     "Listed so nothing is silently dropped, but excluded from the totals."),
    ("ZERO_LENGTH",
     "Scanned in and out in the same minute.",
     "Defensive only — it should never appear. Tell whoever maintains this if it does."),
]

st.set_page_config(page_title="RDM Asia Overtime", layout="wide")
st.title("RDM Asia — Monthly Overtime")

st.info(
    "**Overtime is hours worked past a daily threshold** — 9 h Mon–Fri, 5 h Saturday, "
    "0 h on Sundays and public holidays, so on a Sunday or public holiday every hour "
    "is overtime. A shift counts against the day it *started*, however late it ends.\n\n"
    "**A flagged day is a withheld day, not a zero day.** Where a scan is missing the "
    "hours are shown but no overtime is paid for that day, so a flagged employee's "
    "total is a *lower bound* until the missing scan is corrected in the attendance "
    "system. Check the Anomalies column and the drilldown below.")

uploads = st.file_uploader(
    "Attendance export (.csv) — all staff in one file",
    type="csv", accept_multiple_files=True,
    help="Upload the monthly attendance export. Several months can be uploaded at once.")

if not uploads:
    st.info("Upload an attendance export to calculate overtime.")
    st.stop()


@st.cache_data(show_spinner="Reading attendance…")
def read_uploads(files: list[tuple[str, bytes]]) -> list[EmployeeAttendance]:
    """Parse each uploaded CSV, merging employees that appear in more than one."""
    parsed: list[tuple[str, list[EmployeeAttendance]]] = []
    for name, blob in files:
        try:
            records = load_attendance(io.BytesIO(blob))
        except LoaderError as e:
            # already a sentence naming a row and a column; only the file is missing
            raise LoaderError(f"{name}: {e}") from e
        except Exception as e:
            raise RuntimeError(f"{name}: {type(e).__name__}: {e}") from e
        parsed.append((name, records))
    return merge_files(parsed)


try:
    holidays = load_holidays(HOLIDAYS_FILE)
    staff = read_uploads([(f.name, f.getvalue()) for f in uploads])
except LoaderError as e:
    st.error(
        f"**Could not read the upload — nothing was calculated.**\n\n{e}\n\n"
        f"None of the {len(uploads)} uploaded file(s) were processed. Fix or remove "
        "that file and upload again.")
    st.stop()
except Exception as e:
    st.error(f"Failed to load data: {type(e).__name__}: {e}")
    st.stop()

if not staff:
    st.error("No employee rows found in the upload.")
    st.stop()

# Month comes from the data, not the filename: the month most rows fall in wins.
seen: Counter[tuple[int, int]] = Counter()
for emp in staff:
    seen.update((d.year, d.month) for d in emp.dates_present)
if not seen:
    st.error("No dated rows found in the upload.")
    st.stop()

options = sorted(seen, reverse=True)
default = max(seen, key=lambda m: (seen[m], m))
month = st.sidebar.selectbox(
    "Month", options, index=options.index(default),
    format_func=lambda m: f"{date(m[0], m[1], 1):%B %Y}")
month_name = f"{date(month[0], month[1], 1):%B %Y}"

# Refuse rather than warn: an uncovered year is not a caveat on the numbers, it is
# wrong numbers that look normal. Every public holiday that year would be measured
# against the 9 h weekday threshold instead of 0 h — on the real June 2026 export
# that is 95.35 h of overtime lost across 9 of the 12 staff, and 120 h moved out of
# the Sun/PH column into the weekday one, which is paid at a different rate.
if month[0] not in {d.year for d in holidays}:
    st.error(
        f"**{HOLIDAYS_FILE} has no public holidays for {month[0]}, so {month_name} "
        "cannot be calculated.** Every public holiday that year would count as an "
        "ordinary working day and its overtime be under-paid.\n\n"
        "If you uploaded more than one month, choose a different month in the sidebar. "
        f"Otherwise {month[0]}'s public holidays need adding to {HOLIDAYS_FILE} first.")
    st.stop()

month_hols = {d: n for d, n in holidays.items() if (d.year, d.month) == month}
if month_hols:
    st.sidebar.markdown("**Public holidays this month**")
    for d, n in sorted(month_hols.items()):
        st.sidebar.write(f"{d:%a %d %b} — {n}")

all_days: dict[str, list[DaySummary]] = {}
rows = []
for emp in staff:
    days = summarize_employee(emp, month, holidays)
    all_days[emp.name] = days
    t = month_totals(days)
    rows.append({"Employee": emp.name, "Badge": emp.badge,
                 "Worked (h)": t["worked"], "Weekday OT": t["ot_weekday"],
                 "Saturday OT": t["ot_saturday"], "Sun/PH OT": t["ot_sunday_ph"],
                 "Total OT": t["ot_total"], "Anomalies": t["anomalies"]})

summary_df = pd.DataFrame(rows)

st.subheader(f"Summary — {month_name}")
st.dataframe(summary_df, hide_index=True)

flagged = int((summary_df["Anomalies"] > 0).sum())
if flagged:
    st.info(
        f"**{flagged} of {len(summary_df)} employees have flagged days this month.** "
        "Their Total OT is a lower bound — some days are withheld pending corrected "
        "scans. Open an employee below to see which days and why.")


def detail_frame(days: list[DaySummary], selected_month_only: bool = True) -> pd.DataFrame:
    recs = []
    for d in days:
        if selected_month_only and not d.in_month:
            continue
        sessions = "; ".join(
            f"{s.login:%H:%M}–{s.logout:%d %H:%M}" if s.logout and s.logout.date() != s.login.date()
            else f"{s.login:%H:%M}–{s.logout:%H:%M}" if s.logout
            else f"{s.login:%H:%M}–?"
            for s in d.sessions)
        recs.append({"Date": f"{d.date:%a %d %b}", "Type": d.day_type,
                     "Sessions": sessions, "Worked (h)": round(d.worked_hours, 2),
                     "Threshold": d.threshold, "OT (h)": round(d.overtime_hours, 2),
                     "Flags": ", ".join(d.flags), "Export note": d.note})
    return pd.DataFrame(recs)


def sheet_title(name: str, used: set[str]) -> str:
    """Excel sheet name: <=31 chars, no reserved characters, unique."""
    clean = re.sub(r"[\[\]:*?/\\]", " ", name).strip("' ") or "Employee"
    title = clean[:31].strip("' ")
    n = 2
    while title in used:
        suffix = f"~{n}"
        title = clean[:31 - len(suffix)].strip("' ") + suffix
        n += 1
    used.add(title)
    return title


st.subheader("Employee drilldown")
who = st.selectbox("Employee", list(all_days))
# An upload spanning several months would otherwise bury the selected month
# under every other month's rows, all flagged OUT_OF_MONTH.
show_all = st.checkbox("Show days outside the selected month", value=False)
st.dataframe(detail_frame(all_days[who], selected_month_only=not show_all),
             hide_index=True)

with st.expander("What the flags mean"):
    for flag, what, effect in FLAG_LEGEND:
        st.markdown(f"**`{flag}`** — {what}  \n{effect}")
    st.caption(
        "**Export note** repeats what the attendance system itself said about the day "
        "(rest day, leave, a short day). Its own overtime figure is deliberately not "
        "shown: it is calculated on different rules, and printing it beside ours put "
        "two conflicting overtime numbers on one line.")

buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as xw:
    summary_df.to_excel(xw, sheet_name="Summary", index=False)

    used_sheets = {"Summary"}
    for name, days in all_days.items():
        detail_frame(days).to_excel(xw, sheet_name=sheet_title(name, used_sheets), index=False)
st.download_button(f"Download {month_name} overtime report (.xlsx)", buf.getvalue(),
                   file_name=f"Overtime {month_name}.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
