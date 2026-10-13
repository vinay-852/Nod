"""MCP tool definitions, grouped by responsibility:

- calendar: daily brief, event CRUD, conflicts, suggestions
- study: deadlines, study plans, session booking, flashcards
- sync: iCalendar import/export
"""

from . import calendar, study, sync  # noqa: F401