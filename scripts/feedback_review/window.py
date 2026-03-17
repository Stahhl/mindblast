"""Weekly UTC reporting window helpers."""

from __future__ import annotations

import datetime as dt

from .types import WeeklyWindow


def build_previous_completed_days_window(
    run_date: dt.date,
    *,
    days: int = 7,
) -> WeeklyWindow:
    if days < 1:
        raise ValueError("days must be >= 1.")
    end_date = run_date - dt.timedelta(days=1)
    start_date = end_date - dt.timedelta(days=days - 1)
    return WeeklyWindow(start_date=start_date, end_date=end_date)
