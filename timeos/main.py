"""TimeOS entry point — one command to run everything.

Run (after install):
  timeos

Or from a checkout:
  uv run python -m timeos.main

Open:
  - Web app:      http://127.0.0.1:8000/
  - TV kiosk:     http://127.0.0.1:8000/kiosk
  - MCP endpoint: http://127.0.0.1:8000/mcp   (Streamable HTTP, spec 2025-11-25)
  - Live ICS:     http://127.0.0.1:8000/calendar.ics
"""

from __future__ import annotations

import argparse
import webbrowser

from .seed import seed_demo
from .server import create_server
from .store import Store


def main() -> None:
    ap = argparse.ArgumentParser(description="TimeOS — schedule & study assistant (MCP server, spec 2025-11-25)")
    ap.add_argument("--host", default="127.0.0.1", help="Bind address (keep 127.0.0.1 unless you know why not)")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--db", default="data/timeos.db", help="SQLite database path (created on first run)")
    ap.add_argument("--seed", action="store_true", help="Force-load the demo schedule (default: seed only if the calendar is empty)")
    ap.add_argument("--no-open", action="store_true", help="Do not open the web app in a browser")
    args = ap.parse_args()

    store = Store(args.db)
    if args.seed or not store.list_events():
        seed_demo(store)

    server = create_server(store)
    print("TimeOS ready")
    print(f"  Web app:               http://{args.host}:{args.port}/")
    print(f"  TV kiosk:              http://{args.host}:{args.port}/kiosk")
    print(f"  MCP (Streamable HTTP): http://{args.host}:{args.port}/mcp")
    print(f"  Live calendar (.ics):  http://{args.host}:{args.port}/calendar.ics")
    if not args.no_open:
        webbrowser.open(f"http://{args.host}:{args.port}/")
    server.run(
        transport="streamable-http",
        host=args.host,
        port=args.port,
        streamable_http_path="/mcp",
        json_response=True,
    )


if __name__ == "__main__":
    main()