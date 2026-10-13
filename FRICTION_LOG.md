# Friction Log — TimeOS

> Per the hackathon rules: submissions with friction logs can earn up to a **10%
> judging bonus**. Each entry: task attempted, steps taken, expected vs actual,
> severity, workaround, actionable suggestion. Logged live during development.

---

## 1. mcp 2.x SDK renamed FastMCP → MCPServer

- **Task:** Scaffold the MCP server with the official Python SDK.
- **Steps:** `uv pip install mcp[cli]` → got mcp 2.3.0 → `from mcp.server.fastmcp import FastMCP` → ModuleNotFoundError.
- **Expected vs actual:** Expected the familiar FastMCP API; the SDK v2 renamed it to `MCPServer` (from `mcp.server.mcpserver`) and changed several APIs. No API left in `mcp.server.fastmcp` — it raises with a migration-guide pointer.
- **Severity:** High (blocked the scaffold until resolved).
- **Workaround:** Read the installed SDK source (`server.py`, `tools/base.py`) to learn `MCPServer`, `@server.tool()`, `custom_route`, and `run_streamable_http_async`. Kept mcp 2.x (not pinned to v1) because the hackathon requires spec 2025-11-25+, which v1 does not speak.
- **Suggestion:** The migration guide exists but is discoverable only via the error message; a `mcp.server.fastmcp` shim with a deprecated alias for one release would have saved hours.

## 2. SQLite created in one thread, used in another

- **Task:** Call a tool over HTTP.
- **Steps:** `get_daily_brief` → `ProgrammingError: SQLite objects created in a thread can only be used in that same thread`.
- **Expected vs actual:** Expected a normal response; the MCP server executes tool calls from a thread pool, and the connection was created in the main thread.
- **Severity:** High (every tool failed).
- **Workaround:** `sqlite3.connect(..., check_same_thread=False)` + a per-store lock.
- **Suggestion:** The SDK should document that tool callbacks run on worker threads; a mention in the migration guide would have prevented this.

## 3. threading.Lock deadlock (nested store calls)

- **Task:** Re-run the server after adding the lock.
- **Steps:** Started server → hung silently at seed; no logs, no banner.
- **Expected vs actual:** Expected it to start; `add_event` holds the lock then calls `get_event` → `threading.Lock` is non-reentrant → deadlock.
- **Severity:** High (hang, only found by foregrounding the process).
- **Workaround:** `threading.RLock()`.
- **Suggestion:** n/a — classic. Note: silent hangs are the worst failure mode; a startup timeout check would help the SDK.

## 4. Intent-parser overstepping (removed)

- **Task:** Make the web demo conversational without an API key by adding a `chat` tool with a rule-based parser.
- **Steps:** Built regex intent parser; "Add a meet at 5am tomorrow" booked **today 9:00** and left "5am" in the title (regex captured the `at ` prefix via `group(0)`, and "5am tomorrow" lost the day context).
- **Expected vs actual:** Expected reasonable NLU; got wrong-day bookings — and more importantly, **natural-language understanding is the agent's job, not the MCP server's** (Amazon: "Alexa+ handles natural language understanding…").
- **Severity:** High (wrong architecture, plus a wrong-time bug).
- **Workaround:** Deleted the `chat` tool entirely; the web app is now a pure MCP client (forms → tools), and conversation is shown through a real agent client (e.g. MCP Inspector / Claude Desktop) in the demo.
- **Suggestion:** Don't reimplement the host. MCP servers should stay thin tools with clean schemas.

## 5. Structured output not emitted for `dict` returns

- **Task:** Return rich JSON from tools.
- **Steps:** Tools return dicts; response `content[0].text` holds JSON but `structuredContent` is absent.
- **Expected vs actual:** Expected structuredContent; the SDK only builds it when the return annotation maps to a pydantic output model.
- **Severity:** Low (text JSON parses fine in every client; our web app does `JSON.parse`).
- **Workaround:** Parse `content[0].text`; documented in the web client.
- **Suggestion:** SDK auto-detect could treat `dict` annotations as structured; as-is it's easy to think structured output is on when it isn't.

## 6. Amazon Devices Builder Tools MCP on Node 26

- **Task:** Install the hackathon's official Amazon Devices MCP (`@amazon-devices/amazon-devices-buildertools-mcp`) for the dev environment.
- **Steps:** `npx -y @amazon-devices/amazon-devices-buildertools-mcp@latest --help` → worked; docs warn of an SQLite3 bindings failure on Node v26.
- **Expected vs actual:** Expected possible failure on Node 26.8.2; the package ran (help/exec worked) — but the warning is real for some platforms.
- **Severity:** Low/Medium.
- **Workaround:** If bindings fail, use Node v24 (per Amazon's troubleshooting doc).
- **Suggestion:** Amazon: pin or prebuild SQLite3 for modern Node LTS.

## 7. $150 AWS credit program already closed

- **Task:** Plan AWS usage (Bedrock for flashcard generation, hosting).
- **Steps:** Read the hackathon Resources page → "October 7th Update: we are out of credit codes".
- **Expected vs actual:** Expected $150/person credits; none available this close to the deadline.
- **Severity:** Low (we designed the demo to run with zero AWS anyway; Bedrock remains a documented optional extra).
- **Workaround:** Rule-based flashcards by default; optional Bedrock path stays as a hook for the AWS Builder mini-challenge.
- **Suggestion:** Publish credit availability clearly from day one; closing mid-hackathon changes cost planning.

## 8. iCalendar timezone ambiguity

- **Task:** Export events so phone calendars show correct local times.
- **Steps:** Chose floating local times (no Z/TZID).
- **Expected vs actual:** Every major client treats floating times as the user's local time — correct for a single-household local server; risky for multi-timezone hosting.
- **Severity:** Low.
- **Workaround:** Documented; Google sync path converts via `astimezone()` with explicit offsets.
- **Suggestion:** For a hosted multi-user version, emit TZID + VTIMEZONE.

---

### Product feedback (for the Devpost form)

- **MCP Python SDK (mcp 2.x):** onboarding was rough (rename without a shim, undocumented worker-thread behavior), but the Streamable HTTP transport, session management, and custom routes are clean once discovered. I'd build with it again.
- **Alexa+ path:** the "build a self-hosted MCP server" route is refreshingly open — no gated tools required, standard MCP works. The FAQ is honest about partner-only tooling.
- **Google Calendar API:** incremental sync with syncToken is well-documented; watch out for 410 token expiry and pageToken pagination on the last page.