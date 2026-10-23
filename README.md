# Nod — your schedule that thinks ahead

A self-hosted **MCP server** (spec 2025-11-25, Streamable HTTP) that coordinates
a schedule and study time for any learner — meetings, classes, homework, exams,
courses, certifications. Built for the **Alexa+ track** of the Build, Ship,
Shape: Amazon Developer Hackathon.

**One sentence:** an AI assistant (Alexa+, Claude, ChatGPT, or the included web
app) gets real tools to *maintain a calendar*, *detect conflicts and suggest
fixes*, *schedule study sessions*, and *send flashcards* — while the data stays
in your home.

## Why it exists / how it's real

- **Alexa+ is the agent, this is the tools.** Amazon's docs: "Alexa+ acts as the
  MCP client… Alexa+ handles natural language understanding, response generation,
  and UI rendering." So TimeOS is a pure tools server: clean inputs, structured
  results, no fake NLU. Any MCP client can drive it.
- **Spec-faithful:** MCP 2025-11-25 (negotiated), Streamable HTTP transport on a
  single `/mcp` endpoint, Origin validation, localhost by default.
- **Real calendars:** every event lives in SQLite and exports/imports iCalendar
  (`.ics`) — import or subscribe in Google/Apple/Outlook, or connect Google
  Calendar via per-user OAuth for live two-way sync.

## Quickstart

```bash
# 1. Install (Python 3.11+; uv recommended, plain venv works too)
uv venv --python 3.14 && uv pip install -e .          # or: pip install -e .

# 2. Run (--seed loads a realistic demo day)
uv run python -m timeos.main --seed
```

Open:

| Surface | URL |
|---|---|
| MCP endpoint (Streamable HTTP) | http://127.0.0.1:8000/mcp |
| Web app (real MCP client UI) | http://127.0.0.1:8000/ |
| TV kiosk (family screen) | http://127.0.0.1:8000/kiosk |
| Live calendar (.ics) | http://127.0.0.1:8000/calendar.ics |

Try it from any MCP client (Claude Desktop, MCP Inspector, etc.) by adding the
server URL `http://127.0.0.1:8000/mcp`.

## The killer flow (demo script)

1. `get_daily_brief` → the agent opens with today's plan and deadlines.
2. *"I have a meet at 5am tomorrow"* → `add_event` → **clash** → the tool
   returns *data* (the draft, policy, each conflicting event with a
   `movable` flag and linked deadline, verified-free slots) and creates
   nothing. The agent — following the overlap rules in its instructions —
   asks the user and then executes their choice with plain calls:
   `allow_overlap=true`, a chosen slot, or moving the study session
   (`update_event`) and retrying.
3. *"Spanish test Friday"* → `add_deadline` → `create_study_plan` →
   `schedule_study` books sessions on the **real calendar**, avoiding conflicts.
4. `create_flashcards` → flip-cards sent right in the conversation.
5. Open `/calendar.ics` on a phone → "Add to Calendar" → the events are on the
   device. Connect Google Calendar → they sync live.

## Tools (16)

| Area | Tools |
|---|---|
| Calendar | `get_daily_brief`, `add_event`, `update_event`, `delete_event`, `get_calendar`, `suggest_slots`, `set_overlap_policy` |
| Study | `add_deadline`, `list_deadlines`, `update_deadline`, `create_study_plan`, `schedule_study`, `create_flashcards`, `log_study_session` |
| Sync | `export_ics`, `import_ics` |

## Overlap handling: the tool reports, the agent negotiates

TimeOS never books over anything silently. The household policy (default
`ask`) decides whether a clash is allowed:

- **ask** — `add_event`/`update_event` return a **`clash`** payload: the draft,
  the policy, every conflicting event (with a `movable` flag — study sessions
  can move, anything else needs explicit consent — and the linked deadline),
  and verified-free suggested slots. **Nothing is created.** The agent follows
  the overlap procedure in its instructions: state the collision, ask one clear
  question, then execute the user's choice (accept with `allow_overlap=true`,
  use a suggested slot, or move the movable event then retry). No choice → no
  change.
- **allow** — overlapping events are added (still reported).
- **disallow** — clashes are refused.

Set it once with `set_overlap_policy`; per-call override with
`allow_overlap=true|false`.

## Google Calendar (optional, per-user)

Every user connects their **own** account via the standard consent screen — you
register the app once, users connect themselves.

1. Google Cloud Console → enable **Google Calendar API** → OAuth client ID
   (**Desktop app**) → download `credentials.json` into this folder (or set
   `TIMEOS_GOOGLE_CREDS=/path/to/credentials.json`).
2. `uv pip install "timeos[google]"` (adds `google-api-python-client`,
   `google-auth-oauthlib`).
3. Restart, open the web app, click **Connect Google Calendar** → authorize.

Behavior (best-effort, never crashes the server):
- **Push:** every change the agent makes is written to Google immediately.
- **Pull:** incremental sync via `syncToken` (pagination + 410 recovery),
   throttled to once per minute.
- **Without credentials** everything still works — ICS import/subscription is the
  zero-setup path.

## UI: the backend ships it, the host renders it (MCP Apps)

TimeOS implements the **MCP Apps extension**: card tools declare
`_meta.ui.resourceUri` → `ui://timeos/view.html` (an HTML view, MIME
`text/html;profile=mcp-app`). Any MCP Apps host — Claude, ChatGPT, MCP
Inspector, and **Alexa+** (which supports MCP Apps per Amazon's docs) —
fetches the view and renders it inline after a tool call; the server pushes
data via postMessage.

- Verify: `npx @modelcontextprotocol/inspector --cli http://127.0.0.1:8000/mcp --transport http --method tools/call --tool-name get_daily_brief --app-info` → `{"hasApp": true, ...}`
- The included **web app is the judging stand-in** for Alexa+ (the rules require
  demoing via your own front end, since the Alexa+ MCP Toolkit is partner-only).
  It is a real MCP client: initialize → tools/list → tools/call over Streamable
  HTTP, no fake NLU — the agent is supposed to be Alexa+.

## Architecture (single responsibility)

```
timeos/
  store.py        SQLite storage only (events, deadlines, meta)
  scheduling.py   shared domain logic: conflicts, free slots
  seed.py         demo data
  timeutil.py     datetime parsing/formatting
  ics.py          iCalendar export/import
  flashcards.py   rule-based flashcard generation
  google_sync.py  per-user OAuth + push/pull sync (optional dep)
  mcp_apps.py     MCP Apps view (ui:// resource) — UI as backend resources
  tools/
    calendar.py   calendar tools
    study.py      study tools
    sync.py       ics tools
    serialize.py  row → API dicts
  server.py       MCP wiring + HTTP routes
  main.py         entry point
  web/index.html  the web app + kiosk (single file, judging stand-in)
skills/timeos-coordinator/SKILL.md   Agent Skill
```

## Submission checklist (hackathon)

- [x] Self-hosted MCP server, spec 2025-11-25+, Streamable HTTP
- [x] Repo actually calls the required tech (MCP) in code — not README-only
- [x] Demo surface: web app acting as a real MCP client (+ kiosk)
- [x] Agent Skill included (`skills/timeos-coordinator`)
- [ ] Product feedback + friction log (see `FRICTION_LOG.md`) submitted on Devpost
- [ ] Demo video (<3 min, public, English)
- [ ] GitHub repo public with LICENSE, or private + invite reviewers at submission time

## License

MIT — see LICENSE.
