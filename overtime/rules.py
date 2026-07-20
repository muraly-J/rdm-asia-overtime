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
