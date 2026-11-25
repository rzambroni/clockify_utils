"""Date range helpers shared by the CLI commands."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Optional

RANGE_PRESETS = ("today", "yesterday", "this-week", "this-week-until-today", "last-week", "this-month", "last-month")


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid date '{value}', expected YYYY-MM-DD")


def preset_range(name: str, today: Optional[date] = None) -> tuple:
    """(start, end) dates, both inclusive. Weeks are Monday to Friday, like the menu."""
    today = today or date.today()
    monday = today - timedelta(days=today.weekday())
    if name == "today":
        return today, today
    if name == "yesterday":
        y = today - timedelta(days=1)
        return y, y
    if name == "this-week":
        return monday, monday + timedelta(days=4)
    if name == "this-week-until-today":
        return monday, today
    if name == "last-week":
        last_monday = monday - timedelta(days=7)
        return last_monday, last_monday + timedelta(days=4)
    if name == "this-month":
        return today.replace(day=1), today.replace(day=calendar.monthrange(today.year, today.month)[1])
    if name == "last-month":
        last = today.replace(day=1) - timedelta(days=1)
        return last.replace(day=1), last
    raise ValueError(f"Unknown range '{name}'. Options: {', '.join(RANGE_PRESETS)}")


def resolve_range(range_name: Optional[str], start: Optional[str], end: Optional[str], default: str = "this-week") -> tuple:
    """--range wins; otherwise --from/--to (a lone --from means that single day)."""
    if range_name:
        return preset_range(range_name)
    if start:
        s = parse_date(start)
        e = parse_date(end) if end else s
        if e < s:
            raise ValueError("--to is before --from")
        return s, e
    if end:
        raise ValueError("--to needs --from")
    return preset_range(default)


def days_between(start: date, end: date, weekdays_only: bool = False) -> list:
    out, cur = [], start
    while cur <= end:
        if not weekdays_only or cur.weekday() < 5:
            out.append(cur)
        cur += timedelta(days=1)
    return out
