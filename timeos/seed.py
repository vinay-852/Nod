"""Demo seed data — a realistic starting day so the demo video opens on a full calendar."""

from __future__ import annotations

from datetime import datetime, timedelta

from .timeutil import iso


def seed_demo(store, now: datetime | None = None) -> None:
    now = now or datetime.now()
    if store.list_events():
        return  # already seeded
    today = now.date()

    study = None
    for title, day, h, m, dur, kind in [
        ("Team standup", today, 9, 0, 60, "meeting"),
        ("Spanish class", today, 11, 0, 60, "class"),
        ("Study session: Spanish test", today, 17, 0, 45, "study"),
        ("Dinner", today, 19, 0, 60, "personal"),
    ]:
        start = datetime.combine(day, datetime.min.time().replace(hour=h, minute=m))
        evt = store.add_event(title, iso(start), iso(start + timedelta(minutes=dur)), kind=kind)
        if kind == "study":
            study = evt

    fri = today + timedelta(days=(4 - today.weekday()) % 7 or 7)
    tue = today + timedelta(days=(1 - today.weekday()) % 7 or 7)
    spanish = store.add_deadline("Spanish vocabulary test", iso(datetime.combine(fri, datetime.min.time())), "exam", 4.0)
    store.add_deadline("History essay: causes of WWI", iso(datetime.combine(tue, datetime.min.time())), "school", 6.0)
    if study:
        store.update_event(study["id"], deadline_id=spanish["id"])  # demo clash payloads show the linked deadline