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


class _NoDuplicateKeys(yaml.SafeLoader):
    """A YAML loader that refuses a key repeated at the same level.

    Plain YAML lets the last one win, silently. In this file that means appending
    a second `2028:` heading — the obvious way to add a newly declared holiday —
    deletes every other holiday that year while leaving the year still *looking*
    covered to the caller. The rest of that year is then measured against the 9 h
    weekday threshold instead of 0 h, and nothing anywhere reports it.
    """

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise ValueError(
                    f"{key!r} appears twice at the same level — "
                    "merge the entries into one block")
            seen.add(key)
        return super().construct_mapping(node, deep)


def load_holidays(path: str | Path) -> dict[date, str]:
    """Read holidays.yml -> {date: holiday name}, flattened across years.

    Raises ValueError on the ways this file is realistically mis-edited. Each of
    them costs a public holiday its 0 h threshold, which is invisible in the
    output: the month simply comes out lower than it should.
    """
    with open(path, encoding="utf-8") as f:
        try:
            # safe_load with one extra check: _NoDuplicateKeys subclasses SafeLoader,
            # so it inherits the same restricted set of constructors and cannot build
            # arbitrary Python objects. It is not yaml.load's unsafe default loader.
            raw = yaml.load(f, _NoDuplicateKeys) or {}
        except ValueError as e:
            raise ValueError(f"{path}: {e}") from None
    holidays: dict[date, str] = {}
    for year, entries in raw.items():
        # `2026:` and `'2026':` are the same heading to any reader; only the parser
        # tells them apart, handing back int for one and str for the other. The
        # heading never reaches a calculation, so reading both as the year they
        # plainly state cannot move an hour — it only decides what is accepted.
        try:
            year = int(year)
        except (TypeError, ValueError):
            raise ValueError(
                f"{path}: top-level key {year!r} is not a year — "
                "headings must be plain years, like 2026:") from None
        for entry in entries:
            d = entry["date"]
            if not isinstance(d, date):
                d = date.fromisoformat(str(d))
            # Catches a mistyped year inside a date. Filed under the wrong heading
            # it is lost from the year it was meant for, leaving that year one
            # holiday short with nothing on the page to say so.
            if d.year != year:
                raise ValueError(
                    f"{path}: the {year} block contains {d} — wrong year; "
                    "fix the date or move the entry into its own year")
            if d in holidays:
                raise ValueError(
                    f"{path}: {d} is listed twice "
                    f"({holidays[d]!r} and {entry['name']!r})")
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
