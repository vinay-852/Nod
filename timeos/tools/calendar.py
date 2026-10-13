"""Calendar tools — the schedule core: daily brief, event CRUD, conflicts, overlap policy, suggestions."""

from __future__ import annotations

from datetime import datetime, timedelta

from .. import google_sync
from ..scheduling import duration_of, find_conflicts, free_slots
from ..timeutil import iso, parse_time, today_range
from .serialize import dl, evt

DEFAULT_DURATION_MIN = {"meeting": 60, "class": 60, "study": 45, "personal": 60, "event": 60}
OVERLAP_POLICIES = ("ask", "allow", "disallow")


def make_calendar_tools(store) -> list:
    def get_daily_brief(day: str | None = None) -> dict:
        """Morning briefing: today's events, deadlines due soon, and any scheduling conflicts."""
        now = datetime.now()
        day_start, day_end = today_range(now)
        if day:
            day_start = parse_time(day + " 00:00")
            day_end = day_start + timedelta(days=1)
        events = store.list_events(iso(day_start), iso(day_end))
        deadlines = store.list_deadlines(due_before=iso(day_end))
        conflicts = []
        for e in events:
            for c in find_conflicts(store, e["start_ts"], e["end_ts"], exclude_id=e["id"]):
                conflicts.append({"event": evt(e), "with": evt(c)})
        google_sync.maybe_pull(store)
        return {
            "kind": "brief",
            "day": day_start.strftime("%Y-%m-%d"),
            "events": [evt(e) for e in events],
            "deadlines": [dl(d) for d in deadlines if d["status"] != "done"],
            "conflicts": conflicts,
        }

    def _policy(allow_overlap: bool | None) -> str:
        if allow_overlap is not None:
            return "allow" if allow_overlap else "disallow"
        return store.get_meta("overlap_policy", "ask")

    def _clash(draft: dict, conflicts: list, suggestions: list) -> dict:
        """Complete data for the agent to negotiate (nothing was created): the draft, the policy, every conflict with movability + linked deadline, and verified-free slots."""
        enriched = []
        for c in conflicts:
            info = evt(c)
            info["movable"] = c["kind"] == "study"  # study sessions can move; everything else needs explicit user consent
            deadline = store.get_deadline(c["deadline_id"]) if c.get("deadline_id") else None
            info["deadline"] = dl(deadline) if deadline else None
            enriched.append(info)
        return {
            "kind": "clash",
            "operation": "update_event" if "event_id" in draft else "add_event",
            "draft": draft,
            "policy": store.get_meta("overlap_policy", "ask"),
            "conflicts": enriched,
            "suggestions": suggestions,  # each verified free at this moment
        }

    def add_event(title: str, start: str, end: str | None = None, kind: str = "event", notes: str = "",
                  allow_overlap: bool | None = None) -> dict:
        """Add a commitment. When the slot is busy and overlap is not allowed, returns a 'clash' with conflicts and suggestions and creates nothing. The agent asks the user, then re-calls with allow_overlap=true, a suggested slot, or after moving the conflicting event."""
        start_dt = parse_time(start)
        end_dt = parse_time(end) if end else start_dt + timedelta(minutes=DEFAULT_DURATION_MIN.get(kind, 60))
        if end_dt <= start_dt:
            return {"kind": "error", "error": "End time must be after start time."}
        conflicts = find_conflicts(store, iso(start_dt), iso(end_dt))
        draft = {"title": title, "start": iso(start_dt), "end": iso(end_dt), "kind": kind, "notes": notes}
        if conflicts and _policy(allow_overlap) != "allow":
            suggestions = free_slots(store, start_dt, duration_of(draft["start"], draft["end"]))
            return _clash(draft, conflicts, suggestions)
        event = store.add_event(title, iso(start_dt), iso(end_dt), kind=kind, notes=notes)
        google_sync.maybe_push(store, event, "created")
        return {"kind": "event", "event": evt(event), "conflicts": [evt(c) for c in conflicts]}

    def update_event(event_id: int, title: str | None = None, start: str | None = None, end: str | None = None,
                     kind: str | None = None, notes: str | None = None, allow_overlap: bool | None = None) -> dict:
        """Edit an existing event. New times that clash are returned as a 'clash' (nothing changed) unless overlap is allowed."""
        cur = store.get_event(event_id)
        if not cur:
            return {"kind": "error", "error": f"No event with id {event_id}."}
        fields = {k: v for k, v in {"title": title, "kind": kind, "notes": notes}.items() if v is not None}
        start_dt = parse_time(start) if start else datetime.fromisoformat(cur["start_ts"])
        end_dt = parse_time(end) if end else datetime.fromisoformat(cur["end_ts"])
        if end_dt <= start_dt:
            return {"kind": "error", "error": "End time must be after start time."}
        conflicts = find_conflicts(store, iso(start_dt), iso(end_dt), exclude_id=event_id)
        draft = {"event_id": event_id, "title": fields.get("title", cur["title"]), "start": iso(start_dt), "end": iso(end_dt),
                 "kind": fields.get("kind", cur["kind"]), "notes": fields.get("notes", cur["notes"])}
        if conflicts and _policy(allow_overlap) != "allow":
            suggestions = free_slots(store, start_dt, duration_of(draft["start"], draft["end"]))
            return _clash(draft, conflicts, suggestions)
        fields["start_ts"], fields["end_ts"] = iso(start_dt), iso(end_dt)
        event = store.update_event(event_id, **fields)
        google_sync.maybe_push(store, event, "updated")
        return {"kind": "event", "event": evt(event), "conflicts": [evt(c) for c in conflicts]}

    def delete_event(event_id: int) -> dict:
        """Remove an event from the calendar."""
        event = store.get_event(event_id)
        if not event:
            return {"kind": "error", "error": f"No event with id {event_id}."}
        store.delete_event(event_id)
        google_sync.maybe_push(store, event, "deleted")
        return {"kind": "deleted", "id": event_id, "title": event["title"]}

    def get_calendar(start: str | None = None, end: str | None = None) -> dict:
        """List events in a time window (default: today)."""
        now = datetime.now()
        day_start, day_end = today_range(now)
        if start:
            day_start = parse_time(start + " 00:00") if len(start) <= 10 else parse_time(start)
        if end:
            day_end = parse_time(end + " 00:00") if len(end) <= 10 else parse_time(end)
        google_sync.maybe_pull(store)
        events = store.list_events(iso(day_start), iso(day_end))
        return {"kind": "calendar", "start": iso(day_start), "end": iso(day_end), "events": [evt(e) for e in events]}

    def suggest_slots(duration_minutes: int, day: str | None = None, end_hour: int = 22, start_hour: int = 8) -> dict:
        """Find free time slots on a day (default: today)."""
        if duration_minutes <= 0 or not 0 <= start_hour < end_hour <= 23:
            return {"kind": "error", "error": "Specify a positive duration and valid earliest/latest hours."}
        day_start = datetime.combine(parse_time(day or "today").date(), datetime.min.time())
        slots = free_slots(store, day_start, duration_minutes, end_hour, start_hour)
        return {"kind": "slots", "day": day_start.strftime("%Y-%m-%d"), "duration_minutes": duration_minutes, "slots": slots}

    def set_overlap_policy(policy: str) -> dict:
        """Set how conflicts are handled: 'ask' (default — return questions), 'allow' (add anyway), 'disallow' (refuse overlapping events)."""
        policy = (policy or "").strip().lower()
        if policy not in OVERLAP_POLICIES:
            return {"kind": "error", "error": f"Policy must be one of: {', '.join(OVERLAP_POLICIES)}."}
        store.set_meta("overlap_policy", policy)
        return {"kind": "policy", "policy": policy}

    return [get_daily_brief, add_event, update_event, delete_event,
            get_calendar, suggest_slots, set_overlap_policy]