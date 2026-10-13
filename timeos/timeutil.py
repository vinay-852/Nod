"""Lenient datetime parsing/formatting helpers (local naive time)."""

from __future__ import annotations

import re
from datetime import datetime, time, timedelta

_DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DAY_NAMES = tuple(_DAY_NAMES)  # public vocabulary for intent parsers
DAY_WORDS = frozenset(("today", "tomorrow") + DAY_NAMES)

_TIME_RE = re.compile(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$")
_ISO_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[t ](\d{1,2}):(\d{2}))?$")


def parse_time(s: str, now: datetime | None = None) -> datetime:
    """Parse a human time string into a local datetime.

    Accepts ISO (2026-10-12T17:00, 2026-10-12 17:00), bare dates (2026-10-12),
    relative days (today, tomorrow, monday, next friday), and time-only ("5pm",
    "17:00", "9am"). Unknown input falls back to "now".
    """
    now = now or datetime.now()
    s = s.strip().lower()
    if not s:
        return now

    m = _ISO_RE.match(s)
    if m:
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
        if m[4]:
            return datetime(y, mo, d, int(m[4]), int(m[5] or 0))
        return datetime(y, mo, d)

    day_delta = 0
    rest = s
    if s.startswith("today"):
        day_delta, rest = 0, s[len("today"):].strip()
    elif s.startswith("tomorrow"):
        day_delta, rest = 1, s[len("tomorrow"):].strip()
    elif s.startswith("next "):
        rest = s[len("next "):].strip()
        day_delta = _next_weekday(now, rest.split()[0]) if rest else 7
    else:
        for i, name in enumerate(_DAY_NAMES):
            if s.startswith(name):
                rest = s[len(name):].strip()
                day_delta = (i - now.weekday()) % 7 or 7
                break

    base = (now + timedelta(days=day_delta)).date()
    return datetime.combine(base, _parse_clock(rest))


def _parse_clock(s: str) -> time:
    m = _TIME_RE.match(s.strip())
    if not m:
        return time(9, 0)
    h = int(m.group(1))
    minute = int(m.group(2) or 0)
    ampm = m.group(3)
    if ampm == "pm" and h < 12:
        h += 12
    elif ampm == "am" and h == 12:
        h = 0
    elif not ampm and h < 7:  # bare "5" means 5pm
        h += 12
    return time(min(h, 23), minute)


def _next_weekday(now: datetime, name: str) -> int:
    for i, n in enumerate(_DAY_NAMES):
        if n.startswith(name):
            return (i - now.weekday()) % 7 or 7
    return 7


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def human(dt: datetime) -> str:
    return dt.strftime("%a %b %d, %I:%M %p").replace(" 0", " ")


def today_range(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.now()
    day = now.date()
    return datetime.combine(day, time.min), datetime.combine(day + timedelta(days=1), time.min)