"""MCP server wiring — registers tools and HTTP routes on an MCPServer (spec 2025-11-25, Streamable HTTP)."""

from __future__ import annotations

from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from mcp.server.mcpserver import MCPServer

from . import google_sync, mcp_apps
from .ics import events_to_ics
from .tools import calendar, study, sync

WEB_DIR = Path(__file__).resolve().parent / "web"

INSTRUCTIONS = """You are the TimeOS coordinator, a scheduling + study assistant.

Rules:
1. Always start a session by calling get_daily_brief to see today's plan, deadlines, and conflicts.
2. When the user mentions any commitment (meeting, class, appointment, exam, essay, course, deadline, personal goal), record it: add_event for time-bound commitments, add_deadline for deliverables with a due date.
3. Use ISO 8601 local times (e.g. 2026-10-12T17:00) for every date/time argument.
4. Overlap handling — follow this procedure exactly when add_event or update_event returns a 'clash':
   a. Never book over anything silently, and never choose a time or move an event on your own. The clash payload has the draft, the current policy, every conflicting event (with its times and 'movable' flag), and verified-free suggested slots.
   b. Tell the user what collides, then ask ONE clear question with the concrete options:
      - "Accept the overlap?" → re-call the same tool with allow_overlap=true.
      - "Use one of these free slots: [times]?" → re-call with the slot they pick.
      - "Move the conflicting event?" → only propose moving events whose 'movable' is true, or events the user explicitly agrees to move. Suggest an exact destination from the slots; a destination is only valid if it is in the future, is currently free (re-run suggest_slots to confirm), and for a study session still ends before its 'deadline.due'. Then: update_event the moved event, then re-call the original tool.
   c. If the user chooses nothing, change nothing.
   d. If a suggested slot is no longer free when you try it, say so, re-run suggest_slots, and offer fresh slots.
5. For any deadline, offer to schedule study sessions (schedule_study) and generate flashcards (create_flashcards).
6. Be proactive: surface upcoming deadlines and free time in your replies. Keep answers short and warm, like a home assistant.
7. Never invent events or deadlines the user did not mention. Verify times by restating them before making changes.
"""


def create_server(store) -> MCPServer:
    server = MCPServer(
        name="TimeOS",
        title="TimeOS — Schedule & Study Assistant",
        version="0.1.0",
        instructions=INSTRUCTIONS,
    )

    tools = calendar.make_calendar_tools(store) + study.make_study_tools(store) + sync.make_sync_tools(store)
    for fn in tools:
        meta = {"ui": {"resourceUri": mcp_apps.URI}} if fn.__name__ in mcp_apps.CARD_TOOLS else None
        server.add_tool(fn, meta=meta)

    # MCP Apps view — the server ships the UI, the host renders it (incl. Alexa+).
    @server.resource(mcp_apps.URI, name=mcp_apps.NAME, title=mcp_apps.NAME,
                     description="Card UI rendered inline after TimeOS tool calls", mime_type=mcp_apps.MIME)
    def timeos_view() -> str:
        return mcp_apps.VIEW_HTML

    # HTTP routes (same calendar, every surface: web, kiosk, live ICS, health)
    @server.custom_route("/calendar.ics", methods=["GET"])
    async def ics_export(request: Request) -> Response:
        return Response(content=events_to_ics(store.list_events(), store.list_deadlines()), media_type="text/calendar")

    @server.custom_route("/", methods=["GET"])
    async def web_app(request: Request) -> Response:
        return _serve_web()

    @server.custom_route("/kiosk", methods=["GET"])
    async def kiosk_app(request: Request) -> Response:
        return _serve_web()

    @server.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "TimeOS", "events": len(store.list_events())})

    # Google Calendar OAuth + sync endpoints (only when the google extras are installed)
    for path, handler in google_sync.routes(store):
        server.custom_route(path, ["GET"])(handler)

    return server


def _serve_web() -> Response:
    index = WEB_DIR / "index.html"
    if not index.exists():
        return Response("web/index.html not found", status_code=404)
    return Response(index.read_text(encoding="utf-8"), media_type="text/html")