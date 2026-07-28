"""RDM Asia overtime calculator — Streamlit UI.

All calculation lives in the overtime/ package; this file is widgets only.
"""
from __future__ import annotations

import io
from collections import Counter
from datetime import date, datetime

import pandas as pd
import streamlit as st

from overtime.calc import DaySummary, month_totals, summarize_month
from overtime.loader import EmployeeSheet, load_attendance
from overtime.rules import load_holidays

HOLIDAYS_FILE = "holidays.yml"

st.set_page_config(page_title="RDM Asia Overtime", layout="wide")
st.title("RDM Asia — Monthly Overtime")

uploads = st.file_uploader(
    "Attendance export (.xlsx) — one sheet per employee",
    type="xlsx", accept_multiple_files=True,
    help="Upload the monthly biometric export. Several files are merged by employee.")

if not uploads:
    st.info("Upload an attendance export to calculate overtime.")
    st.stop()


@st.cache_data(show_spinner="Reading attendance…")
def read_uploads(files: list[tuple[str, bytes]]) -> list[EmployeeSheet]:
    """Parse each uploaded workbook, merging employees that appear in more than one."""
    merged: dict[str, EmployeeSheet] = {}
    for name, blob in files:
        try:
            sheets = load_attendance(io.BytesIO(blob))
        except Exception as e:
            raise RuntimeError(f"{name}: {type(e).__name__}: {e}") from e
        for emp in sheets:
            existing = merged.get(emp.short_name)
            if existing is None:
                merged[emp.short_name] = emp
                continue
            existing.punches.extend(emp.punches)
            existing.dates_present |= emp.dates_present
            existing.full_name = existing.full_name or emp.full_name
    return list(merged.values())


try:
    holidays = load_holidays(HOLIDAYS_FILE)
    sheets = read_uploads([(f.name, f.getvalue()) for f in uploads])
except Exception as e:
    st.error(f"Failed to load data: {type(e).__name__}: {e}")
    st.stop()

if not sheets:
    st.error("No employee sheets found in the upload.")
    st.stop()

# Month comes from the data, not the filename: the month most rows fall in wins.
seen: Counter[tuple[int, int]] = Counter()
for emp in sheets:
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

if month[0] not in {d.year for d in holidays}:
    st.warning(
        f"{HOLIDAYS_FILE} has no entries for {month[0]} — public holidays that month "
        "will be treated as ordinary days and their overtime under-counted. "
        "Add the year to the file before paying these numbers.")

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

    used_sheets = {"Summary"}
    for name, days in all_days.items():
        # Generate collision-safe sheet name (max 31 chars)
        sheet_name = name[:31]
        if sheet_name not in used_sheets:
            used_sheets.add(sheet_name)
        else:
            # Collision: append numeric suffix, re-truncate to stay <= 31 chars
            suffix_num = 2
            while True:
                suffix = f"~{suffix_num}"
                sheet_name = name[:31 - len(suffix)] + suffix
                if sheet_name not in used_sheets:
                    used_sheets.add(sheet_name)
                    break
                suffix_num += 1

        detail_frame(days).to_excel(xw, sheet_name=sheet_name, index=False)
st.download_button(f"Download {month_name} overtime report (.xlsx)", buf.getvalue(),
                   file_name=f"Overtime {month_name}.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
