"""iCalendar (.ics) export and import — the bridge to Google/Apple/Outlook calendars.

Times are emitted as local floating times (no Z / no TZID), which every major
calendar client interprets as the user's local time — the right behavior for a
self-hosted, single-household server.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

PRODID = "-//TimeOS//Schedule & Study Assistant//EN"


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def events_to_ics(events: list[dict], deadlines: list[dict] | None = None) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
    ]
    for e in events:
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{e['id']}@timeos.local")
        lines.append(f"DTSTAMP:{_fmt(datetime.now())}")
        lines.append(f"DTSTART:{_fmt(datetime.fromisoformat(e['start_ts']))}")
        lines.append(f"DTEND:{_fmt(datetime.fromisoformat(e['end_ts']))}")
        lines.append(f"SUMMARY:{_escape(e['title'])}")
        if e.get("notes"):
            lines.append(f"DESCRIPTION:{_escape(e['notes'])}")
        lines.append(f"CATEGORIES:{_escape(e.get('kind', 'event'))}")
        lines.append("END:VEVENT")
    for d in deadlines or []:
        due = datetime.fromisoformat(d["due"])
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:dl-{d['id']}@timeos.local")
        lines.append(f"DTSTAMP:{_fmt(datetime.now())}")
        lines.append(f"DTSTART:{_fmt(due)}")
        lines.append(f"DTEND:{_fmt(due + timedelta(hours=1))}")
        lines.append(f"SUMMARY:[Due] {_escape(d['title'])}")
        lines.append(f"CATEGORIES:deadline-{_escape(d.get('context', '') or 'task')}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def parse_ics(text: str) -> list[dict]:
    """Minimal parser: pull SUMMARY/DTSTART/DTEND out of each VEVENT block."""
    events = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S):
        def field(name: str) -> str | None:
            m = re.search(rf"^{name}:(.*)$", block, re.M)
            return m.group(1).strip() if m else None

        summary = field("SUMMARY")
        start = field("DTSTART")
        end = field("DTEND")
        if not summary or not start:
            continue
        try:
            start_dt = datetime.strptime(start.strip()[:15], "%Y%m%dT%H%M%S")
        except ValueError:
            continue
        end_dt = start_dt + timedelta(hours=1)
        if end:
            try:
                end_dt = datetime.strptime(end.strip()[:15], "%Y%m%dT%H%M%S")
            except ValueError:
                pass
        events.append({
            "title": summary.replace("\\,", ",").replace("\\n", " "),
            "start": start_dt.strftime("%Y-%m-%dT%H:%M"),
            "end": end_dt.strftime("%Y-%m-%dT%H:%M"),
        })
    return events