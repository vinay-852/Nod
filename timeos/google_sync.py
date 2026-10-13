"""Optional Google Calendar sync (per-user OAuth).

Every user connects *their own* Google account once via the standard consent
screen (see the "Connect Google Calendar" button in the web app). The app needs
no credentials of its own beyond the OAuth client file (credentials.json).

- Push: TimeOS changes are written to Google immediately.
- Pull: Google changes come back via incremental sync (syncToken), throttled.

This module is fully optional: without the `google` extras or credentials.json,
the server runs standalone (ICS import/subscription still works).

Setup (one-time, ~5 min):
  1. console.cloud.google.com -> create project -> enable Google Calendar API
  2. Credentials -> Create credentials -> OAuth client ID -> "Desktop app"
  3. Download credentials.json into this project root (or set TIMEOS_GOOGLE_CREDS)
  4. pip install "timeos[google]"  (google-api-python-client, google-auth-oauthlib)
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

_PULL_INTERVAL_SECONDS = 60
_SCOPES = ["https://www.googleapis.com/auth/calendar"]

_HOME = Path(__file__).resolve().parent.parent


def available() -> bool:
    try:
        import googleapiclient  # noqa: F401
        import google_auth_oauthlib  # noqa: F401
        return True
    except ImportError:
        return False


def _creds_path() -> Path | None:
    env = Path(os.environ.get("TIMEOS_GOOGLE_CREDS", ""))
    candidates = [env] if str(env) else []
    candidates += [_HOME / "credentials.json"]
    for p in candidates:
        if p.is_file():
            return p
    return None


def is_configured() -> bool:
    if not available() or not _creds_path():
        return False
    return (_HOME / "data" / "google_token.json").is_file()


def _build_service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError  # noqa: F401  (re-exported for maybe_pull)

    token = json.loads((_HOME / "data" / "google_token.json").read_text())
    creds = Credentials.from_authorized_user_info(token, _SCOPES)
    return build("calendar", "v3", credentials=creds)


# ------------------------------------------------------------------ connect flow

def connect() -> dict:
    """Run the OAuth consent flow in the browser and store the user's token."""
    if not available():
        return {"ok": False, "error": "google extras not installed: uv pip install 'timeos[google]'"}
    creds_file = _creds_path()
    if not creds_file:
        return {"ok": False, "error": "credentials.json not found — see README (Google setup, ~5 min)"}

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), _SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)
    (_HOME / "data").mkdir(exist_ok=True)
    (_HOME / "data" / "google_token.json").write_text(
        json.dumps({"token": creds.token, "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri, "client_id": creds.client_id,
                    "client_secret": creds.client_secret, "scopes": _SCOPES})
    )
    return {"ok": True, "message": "Google Calendar connected for this household."}


def status() -> dict:
    if not available():
        return {"ok": False, "connected": False, "error": "google extras not installed"}
    if not _creds_path():
        return {"ok": False, "connected": False, "error": "credentials.json missing"}
    if not (_HOME / "data" / "google_token.json").is_file():
        return {"ok": False, "connected": False, "error": "not connected yet — click Connect"}
    return {"ok": True, "connected": True}


# ------------------------------------------------------------------ push

def _body(event: dict) -> dict:
    def aware(ts: str) -> str:
        return datetime.fromisoformat(ts).astimezone().isoformat()

    body = {
        "summary": event["title"],
        "start": {"dateTime": aware(event["start_ts"]), "timeZone": "UTC"},
        "end": {"dateTime": aware(event["end_ts"]), "timeZone": "UTC"},
    }
    if event.get("notes"):
        body["description"] = event["notes"]
    return body


def maybe_push(store, event: dict, action: str) -> None:
    """Write a single event change to Google. Never raises."""
    try:
        if not is_configured():
            return
        service = _build_service()
        if action == "deleted":
            if event.get("google_id"):
                service.events().delete(calendarId="primary", eventId=event["google_id"]).execute()
            return
        if event.get("google_id"):
            service.events().update(calendarId="primary", eventId=event["google_id"], body=_body(event)).execute()
        else:
            created = service.events().insert(calendarId="primary", body=_body(event)).execute()
            store.update_event(event["id"], google_id=created["id"])
    except Exception:  # sync is best-effort; never break the MCP server
        pass


# ------------------------------------------------------------------ pull

def maybe_pull(store) -> None:
    """Incremental sync from Google, throttled. Paginates, and recovers from an expired sync token (410). Never raises."""
    try:
        if not is_configured():
            return
        last = store.get_meta("google_last_pull", "0")
        if time.time() - float(last) < _PULL_INTERVAL_SECONDS:
            return
        service = _build_service()
        sync_token = store.get_meta("google_sync_token")
        kwargs = {"calendarId": "primary", "singleEvents": True}
        if sync_token:
            kwargs["syncToken"] = sync_token
        else:
            kwargs["timeMin"] = datetime.now().astimezone().isoformat()
        try:
            request = service.events().list(**kwargs)
            while request is not None:
                page = request.execute()
                _apply_page(store, page)
                if page.get("nextSyncToken"):  # token is only on the last page
                    store.set_meta("google_sync_token", page["nextSyncToken"])
                    break
                request = service.events().list_next(request, page)
        except HttpError as exc:
            if exc.resp.status == 410:  # token expired: clear and do a full sync
                store.set_meta("google_sync_token", "")
                return maybe_pull(store)
            raise
        store.set_meta("google_last_pull", str(time.time()))
    except Exception:
        pass


def _apply_page(store, page: dict) -> None:
    for item in page.get("items", []):
        existing = _find_by_google_id(store, item["id"])
        start = item.get("start", {}).get("dateTime")
        end = item.get("end", {}).get("dateTime")
        if item.get("status") == "cancelled":
            if existing:
                store.delete_event(existing["id"])
            continue
        if not start or not end:
            continue
        local_start = datetime.fromisoformat(start).astimezone().replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M")
        local_end = datetime.fromisoformat(end).astimezone().replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M")
        if existing:
            store.update_event(existing["id"], title=item.get("summary", existing["title"]),
                               start_ts=local_start, end_ts=local_end)
        else:
            store.add_event(item.get("summary", "(imported)"), local_start, local_end,
                            kind="event", google_id=item["id"])


def _find_by_google_id(store, google_id: str) -> dict | None:
    return next((e for e in store.list_events() if e.get("google_id") == google_id), None)


# ------------------------------------------------------------------ routes

def routes(store):
    """Return [(path, async_handler)] for the MCP server's custom routes."""
    import anyio
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    async def connect_handler(request: Request) -> JSONResponse:
        result = await anyio.to_thread.run_sync(connect)
        return JSONResponse(result)

    async def status_handler(request: Request) -> JSONResponse:
        return JSONResponse(status())

    return [("/google/connect", connect_handler), ("/google/status", status_handler)]