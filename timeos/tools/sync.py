"""Sync tools — iCalendar import/export (the bridge to real Google/Apple/Outlook calendars)."""

from __future__ import annotations

from ..ics import events_to_ics, parse_ics
from ..scheduling import find_conflicts
from .serialize import evt


def make_sync_tools(store) -> list:
    def export_ics() -> dict:
        """Export the full calendar as iCalendar text (also available at GET /calendar.ics)."""
        return {"kind": "ics", "ics": events_to_ics(store.list_events(), store.list_deadlines())}

    def import_ics(ics_text: str) -> dict:
        """Import events from iCalendar text; conflicts are reported per event."""
        added, conflicts = [], []
        for p in parse_ics(ics_text):
            c = find_conflicts(store, p["start"], p["end"])
            event = store.add_event(p["title"], p["start"], p["end"], kind="event")
            added.append(evt(event))
            if c:
                conflicts.append({"event": evt(event), "with": [evt(x) for x in c]})
        return {"kind": "imported", "added": added, "conflicts": conflicts}

    return [export_ics, import_ics]