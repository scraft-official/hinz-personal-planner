"""
Application configuration loaded from environment variables.
"""
import os
from typing import List, Tuple

def _parse_int(val: str | None, default: int) -> int:
    """Parse an integer from string, return default if invalid."""
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default

def _parse_int_list(val: str | None, default: List[int]) -> List[int]:
    """Parse a comma-separated list of integers."""
    if not val:
        return default
    try:
        return [int(x.strip()) for x in val.split(",") if x.strip()]
    except ValueError:
        return default

def _parse_time(val: str | None, default: int) -> int:
    """Parse time in HH:MM format to minutes from midnight."""
    if not val:
        return default
    try:
        parts = val.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return int(val)  # Allow raw minutes
    except ValueError:
        return default


# Day boundaries (in minutes from midnight)
DAY_START_MINUTE = _parse_time(os.getenv("PLANNER_DAY_START"), 7 * 60)  # Default 07:00
DAY_END_MINUTE = _parse_time(os.getenv("PLANNER_DAY_END"), 22 * 60 + 30)  # Default 22:30

# Period boundaries (in minutes from midnight)
PRODUCTION_END = _parse_time(os.getenv("PLANNER_PRODUCTION_END"), 15 * 60)  # Default 15:00
ACTIVITY_END = _parse_time(os.getenv("PLANNER_ACTIVITY_END"), 20 * 60)  # Default 20:00

# Slot configuration
SLOT_MINUTES = _parse_int(os.getenv("PLANNER_SLOT_MINUTES"), 15)
SLOT_HEIGHT_PX = _parse_int(os.getenv("PLANNER_SLOT_HEIGHT_PX"), 12)

# Duration options for block creation (in minutes)
_default_durations = [30, 45, 60, 90, 120, 180, 270, 360]
DURATION_OPTIONS = _parse_int_list(os.getenv("PLANNER_DURATION_OPTIONS"), _default_durations)

# Default plan colors for new plans
PLAN_COLORS = [
    "#0ea5e9",  # Sky blue
    "#22c55e",  # Green
    "#f97316",  # Orange
    "#d946ef",  # Pink
    "#8b5cf6",  # Purple
    "#ef4444",  # Red
    "#f59e0b",  # Amber
    "#14b8a6",  # Teal
]
