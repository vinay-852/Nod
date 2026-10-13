"""Scheduling domain logic — conflict detection and free-slot suggestions.

Operates on the Store's event lists; the MCP tools call these helpers. This is
the shared module for anything time-arithmetic, so calendar and study tools
never re-implement overlap math.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from .timeutil import iso

MAX_SUGGESTIONS = 5


def find_conflicts(store, start_ts: str, end_ts: str, exclude_id: int | None = None) -> list[dict]:
    """Events overlapping the half-open window [start_ts, end_ts), minus exclude_id."""
    events = store.list_events(start_ts, end_ts)
    if exclude_id is not None:
        events = [e for e in events if e["id"] != exclude_id]
    return events


def suggest_slots(store, day_start: datetime, duration_minutes: int, start_hour=8, end_hour=22, step=30,
                  not_before: datetime | None = None) -> list[dict]:
    """Free slots on the whole day containing day_start, skipping busy time, capped at MAX_SUGGESTIONS."""
    if duration_minutes <= 0 or step <= 0 or not 0 <= start_hour < end_hour <= 23:
        raise ValueError("Use a positive duration/step and hours satisfying 0 <= start < end <= 23.")
    day = day_start.date()
    window_start = datetime.combine(day, time.min)          # whole day, not from day_start
    window_end = window_start + timedelta(days=1)
    busy = [(datetime.fromisoformat(e["start_ts"]), datetime.fromisoformat(e["end_ts"]))
            for e in store.list_events(iso(window_start), iso(window_end))]
    slots = []
    cursor = window_start.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    hard_end = window_start.replace(hour=end_hour, minute=0)
    while cursor + timedelta(minutes=duration_minutes) <= hard_end and len(slots) < MAX_SUGGESTIONS:
        slot_end = cursor + timedelta(minutes=duration_minutes)
        if (not_before is None or cursor >= not_before) and not any(b_start < slot_end and b_end > cursor for b_start, b_end in busy):
            slots.append({"start": iso(cursor), "end": iso(slot_end)})
        cursor += timedelta(minutes=step)
    return slots


def free_slots(store, day: datetime, minutes: int, end_hour: int = 22, start_hour: int = 8) -> list[dict]:
    """First free slots of the day — the 'suggest an alternative' helper."""
    return suggest_slots(store, day, minutes, start_hour=start_hour, end_hour=end_hour, not_before=datetime.now())


def duration_of(start_ts: str, end_ts: str) -> int:
    """Minutes between two ISO timestamps."""
    return int((datetime.fromisoformat(end_ts) - datetime.fromisoformat(start_ts)).total_seconds() // 60)