"""Runnable check (no framework): the scheduling invariants TimeOS depends on.

Run: uv run python tests/test_scheduling.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from timeos.scheduling import find_conflicts, suggest_slots  # noqa: E402
from timeos.store import Store  # noqa: E402
from timeos.timeutil import iso  # noqa: E402

DAY = datetime(2026, 10, 12, 12, 0)  # a Monday, midday


def fresh_store() -> Store:
    import tempfile

    return Store(tempfile.mkdtemp() + "/t.db")


def test_slots_never_overlap_booked_events() -> None:
    store = fresh_store()
    # Booked: 09:00-10:00 and 11:00-12:00 on DAY
    store.add_event("Standup", iso(datetime(2026, 10, 12, 9, 0)), iso(datetime(2026, 10, 12, 10, 0)), kind="meeting")
    store.add_event("Class", iso(datetime(2026, 10, 12, 11, 0)), iso(datetime(2026, 10, 12, 12, 0)), kind="class")

    slots = suggest_slots(store, DAY, 45)

    assert slots, "expected at least one free slot"
    for s in slots:
        s_start, s_end = datetime.fromisoformat(s["start"]), datetime.fromisoformat(s["end"])
        for b in [("2026-10-12T09:00", "2026-10-12T10:00"), ("2026-10-12T11:00", "2026-10-12T12:00")]:
            b_start, b_end = datetime.fromisoformat(b[0]), datetime.fromisoformat(b[1])
            assert not (b_start < s_end and b_end > s_start), f"slot {s} overlaps booked {b}"
    # The 08:00-08:45 slot must be present
    assert slots[0] == {"start": "2026-10-12T08:00", "end": "2026-10-12T08:45"}, slots[0]


def test_conflicts_detected_and_excludable() -> None:
    store = fresh_store()
    store.add_event("Standup", iso(datetime(2026, 10, 12, 9, 0)), iso(datetime(2026, 10, 12, 10, 0)), kind="meeting")
    assert len(find_conflicts(store, "2026-10-12T09:30", "2026-10-12T10:30")) == 1
    ev = store.add_event("Dentist", iso(datetime(2026, 10, 12, 9, 30)), iso(datetime(2026, 10, 12, 10, 30)), kind="meeting")
    # the new event itself overlaps the standup
    assert len(find_conflicts(store, "2026-10-12T09:30", "2026-10-12T10:30", exclude_id=ev["id"])) == 1


def test_day_boundary_uses_whole_day() -> None:
    """suggest_slots must consider morning events even when called with an afternoon day_start."""
    store = fresh_store()
    store.add_event("Standup", iso(datetime(2026, 10, 12, 9, 0)), iso(datetime(2026, 10, 12, 10, 0)), kind="meeting")
    afternoon = datetime(2026, 10, 12, 17, 0)  # the bug: window started at 17:00 and missed the 09:00 event
    slots = suggest_slots(store, afternoon, 60)
    assert all(
        not (datetime.fromisoformat("2026-10-12T09:00") < datetime.fromisoformat(s["end"])
             and datetime.fromisoformat("2026-10-12T10:00") > datetime.fromisoformat(s["start"]))
        for s in slots
    ), "an afternoon query must still respect the morning meeting"


if __name__ == "__main__":
    test_slots_never_overlap_booked_events()
    test_conflicts_detected_and_excludable()
    test_day_boundary_uses_whole_day()
    print("scheduling checks passed")