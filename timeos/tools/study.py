"""Study tools — deadlines, study plans, session booking, flashcards, study-time logging."""

from __future__ import annotations

from datetime import datetime, timedelta

from .. import google_sync
from ..flashcards import generate_flashcards
from ..scheduling import free_slots
from ..timeutil import iso, parse_time
from .serialize import dl, evt


def make_study_tools(store) -> list:
    def add_deadline(title: str, due: str, context: str = "", effort_hours: float = 1.0) -> dict:
        """Track any deliverable with a due date: homework, exam, essay, course, certification, project."""
        deadline = store.add_deadline(title, iso(parse_time(due)), context=context, effort_hours=effort_hours)
        return {"kind": "deadline", "deadline": dl(deadline)}

    def list_deadlines(status: str | None = None, due_within_days: int | None = None) -> dict:
        """List deadlines, optionally filtered by status (open/in_progress/done) or how soon they're due."""
        due_before = iso(datetime.now() + timedelta(days=due_within_days)) if due_within_days is not None else None
        items = store.list_deadlines(status=status, due_before=due_before)
        return {"kind": "deadlines", "items": [dl(d) for d in items]}

    def update_deadline(deadline_id: int, title: str | None = None, due: str | None = None, context: str | None = None, effort_hours: float | None = None, status: str | None = None) -> dict:
        """Update a deadline (title, due date, context, effort, or status)."""
        fields = {"title": title, "due": iso(parse_time(due)) if due else None, "context": context,
                  "effort_hours": effort_hours, "status": status if status in ("open", "in_progress", "done") else None}
        deadline = store.update_deadline(deadline_id, **{k: v for k, v in fields.items() if v is not None})
        if not deadline:
            return {"kind": "error", "error": f"No deadline with id {deadline_id}."}
        return {"kind": "deadline", "deadline": dl(deadline)}

    def create_study_plan(deadline_id: int, minutes_per_session: int = 45) -> dict:
        """Break a deadline into concrete study steps and suggested sessions (does not book them)."""
        deadline = store.get_deadline(deadline_id)
        if not deadline:
            return {"kind": "error", "error": f"No deadline with id {deadline_id}."}
        remaining = max(deadline["effort_hours"] - deadline["hours_logged"], 0.25)
        sessions = max(1, round(remaining * 60 / minutes_per_session))
        steps = [{"step": i + 1, "focus": f"Session {i + 1} of {sessions}", "minutes": minutes_per_session}
                 for i in range(sessions)]
        return {
            "kind": "plan",
            "deadline": dl(deadline),
            "sessions_needed": sessions,
            "minutes_per_session": minutes_per_session,
            "steps": steps,
            "suggested_sessions": free_slots(store, datetime.now(), minutes_per_session),
        }

    def schedule_study(deadline_id: int, sessions: int | None = None, minutes_per_session: int = 45) -> dict:
        """Book study sessions on the real calendar before the deadline, avoiding conflicts. Returns what was booked."""
        deadline = store.get_deadline(deadline_id)
        if not deadline:
            return {"kind": "error", "error": f"No deadline with id {deadline_id}."}
        due_dt = datetime.fromisoformat(deadline["due"])
        remaining = max(deadline["effort_hours"] - deadline["hours_logged"], 0.25)
        count = sessions or max(1, round(remaining * 60 / minutes_per_session))
        booked, attempts = [], 0
        cursor = datetime.now() + timedelta(days=1)
        while len(booked) < count and attempts < 60 and cursor < due_dt:
            attempts += 1
            slot = free_slots(store, cursor, minutes_per_session)
            if slot:
                s = slot[0]
                event = store.add_event(f"Study: {deadline['title']}", s["start"], s["end"], kind="study",
                                        notes=f"Prep for deadline #{deadline_id}", deadline_id=deadline_id)
                booked.append(evt(event))
                google_sync.maybe_push(store, event, "created")
            cursor += timedelta(days=1)
        return {"kind": "scheduled", "deadline": dl(deadline), "booked": booked,
                "remaining": max(0, count - len(booked))}

    def create_flashcards(topic: str, material: str | None = None, count: int = 6) -> dict:
        """Generate study flashcards from pasted material (or a topic). Returns cards the UI renders as flip-cards."""
        return {"kind": "flashcards", "topic": topic, "cards": generate_flashcards(topic, material, count)}

    def log_study_session(minutes: int, deadline_id: int | None = None, note: str = "") -> dict:
        """Record focused study time (credits progress toward a deadline if given)."""
        deadline = store.log_study_hours(deadline_id, minutes) if deadline_id else None
        return {"kind": "logged", "minutes": minutes, "note": note, "deadline": dl(deadline) if deadline else None}

    return [add_deadline, list_deadlines, update_deadline, create_study_plan, schedule_study,
            create_flashcards, log_study_session]