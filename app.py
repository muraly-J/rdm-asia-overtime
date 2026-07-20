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
from overtime.loader import load_attendance
from overtime.rules import load_holidays

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
except Exception as e:
    st.error(f"Failed to load data: {type(e).__name__}: {e}")
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
