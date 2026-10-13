"""Shared row → API dict serializers for events and deadlines."""


def evt(e: dict) -> dict:
    return {
        "id": e["id"],
        "title": e["title"],
        "start": e["start_ts"],
        "end": e["end_ts"],
        "kind": e.get("kind", "event"),
        "notes": e.get("notes", ""),
        "deadline_id": e.get("deadline_id"),
    }


def dl(d: dict) -> dict:
    return {
        "id": d["id"],
        "title": d["title"],
        "due": d["due"],
        "context": d.get("context", ""),
        "effort_hours": d.get("effort_hours", 0),
        "hours_logged": d.get("hours_logged", 0),
        "status": d.get("status", "open"),
    }