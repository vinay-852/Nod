# Devpost Submission — TimeOS

Everything to paste into the Build, Ship, Shape: Amazon Developer Hackathon
submission forms.

## General info

**Project name:** TimeOS — your schedule that thinks ahead

**Elevator pitch (149 chars):**
Alexa+ gets real calendar tools via a self-hosted MCP server: book events, resolve conflicts, plan study time, send flashcards. Your data stays home.

**Thumbnail:** 3:2 ratio (e.g. 1200×800), ≤5 MB — screenshot of the web app at http://127.0.0.1:8000/ mid-demo.

## Project details — description

```markdown
# TimeOS — your schedule that thinks ahead

TimeOS is a self-hosted MCP server (spec 2025-11-25, Streamable HTTP) that
coordinates a schedule and study time for any learner — meetings, classes,
homework, exams, courses, certifications. Built for the Alexa+ track: Alexa+
is the agent, TimeOS is the tools. Any MCP client (Alexa+, Claude, ChatGPT,
MCP Inspector) can drive it.

## The killer flow
1. `get_daily_brief` — the agent opens with today's plan and deadlines.
2. "I have a meet at 5am tomorrow" — `add_event` returns a structured clash
   payload: the draft, the household policy, every conflicting event with a
   `movable` flag and linked deadline, and verified-free slots. Nothing is
   created. The agent asks one clear question and executes the choice — accept
   the overlap, use a free slot, or move the movable study session and retry.
3. "Spanish test Friday" — `add_deadline` → `create_study_plan` →
   `schedule_study` books real sessions on the calendar, avoiding conflicts.
4. `create_flashcards` — flip-cards sent right in the conversation.
5. Export to Google/Apple/Outlook via ICS, or per-user OAuth for live
   two-way Google Calendar sync.

## How it works
- 16 MCP tools (calendar / study / sync) — pure tools with clean schemas and
  structured results. No fake NLU: understanding language is the host's job,
  the server stays thin (we removed an intent parser that tried to do it).
- SQLite storage; iCalendar import/export; Google Calendar sync via syncToken
  incremental sync with 410 recovery.
- MCP Apps extension: card tools declare `ui://timeos/view.html` so hosts
  render inline views; the included web app is a real MCP client
  (initialize → tools/list → tools/call), the judging stand-in for Alexa+
  since the Alexa+ MCP Toolkit is partner-only.
- An Agent Skill (`skills/timeos-coordinator`) encodes the overlap procedure.
- Runs with zero cloud dependencies; optional Bedrock flashcard generation is
  a documented hook.

## Built during the hackathon
[TBD — fill in: repo created Oct 11, 2026; the server, web app, kiosk,
Agent Skill, and 8-entry friction log were all built in the submission
window. Nothing existed before.]

## Product feedback & friction log
8 friction-log entries captured live during development (per the rules, this
qualifies for the up to 10% judging bonus): the MCP 2.x SDK rename
FastMCP → MCPServer with no shim; SQLite worker-thread gotcha; a silent
non-reentrant-lock deadlock; structuredContent only emitted for pydantic
models; Node 26 SQLite bindings in the Amazon buildertools MCP; the $150 AWS
credit program closing early; ICS floating-time tradeoffs. Full log:
FRICTION_LOG.md in the repo.

## Track
Alexa+ — self-hosted MCP server (spec 2025-11-25+, Streamable HTTP).
```

## Project details — the seven fields

### Inspiration

Every learner juggles the same mess: classes, homework, exam dates, and "wait, when am I actually free?" Calendar apps store events but never think about them — so study time gets double-booked or silently skipped, and scheduling assistants book over conflicts without a second thought. The hackathon's Alexa+ route made the fix obvious: Amazon says Alexa+ is the agent and MCP servers are the tools, so we built the tools — a local-first calendar brain that an agent can actually drive, with a hard rule that nothing ever gets booked over something else silently.

### What it does

TimeOS is a self-hosted MCP server (spec 2025-11-25, Streamable HTTP) that coordinates a schedule and study time for any learner. It exposes 16 tools across three areas — calendar (daily brief, add/update/delete events, slot suggestions, overlap policy), study (deadlines, study plans, scheduling, flashcards), and sync (ICS export/import).

The killer flow: an agent opens with today's brief, tries to add a conflicting event and gets back a structured clash payload (the draft, the policy, every conflicting event with a `movable` flag, verified-free slots) — nothing is created until the user chooses. From "Spanish test Friday," it builds a study plan, books real sessions on the calendar, and sends flashcards in the conversation. Events export to Google/Apple/Outlook via ICS, or sync live via per-user Google Calendar OAuth. Data stays at home.

### How we built it

Python on the MCP SDK 2.x with Streamable HTTP on a single `/mcp` endpoint (spec 2025-11-25, Origin validation). SQLite for storage, iCalendar for import/export, per-user Google OAuth with `syncToken` incremental sync and 410 recovery. The MCP Apps extension declares `ui://` card views so hosts render inline UI; the included web app is a real MCP client (initialize → tools/list → tools/call) serving as the judging stand-in for Alexa+, since the Alexa+ MCP Toolkit is partner-only. Rule-based flashcards by default keep it running with zero cloud dependencies; an optional Bedrock path is a documented hook. An Agent Skill (`skills/timeos-coordinator`) encodes the overlap procedure.

### Challenges we ran into

- The MCP 2.x SDK renamed `FastMCP` to `MCPServer` with no shim, and tool callbacks running on worker threads is undocumented — SQLite immediately blew up with a cross-thread error, then a naive `threading.Lock` deadlocked silently (RLock fixed it; silent hangs are the worst failure mode).
- We originally built a rule-based NLU `chat` tool and watched it book "5am tomorrow" as today at 9:00 — wrong day and wrong architecture. We deleted it: understanding language is the host's job, an MCP server should stay thin.
- `structuredContent` only emits for pydantic-typed returns, not plain dicts — clients must parse `content[0].text`.
- The $150 AWS credit program closed Oct 7, mid-hackathon; we designed the demo to need zero AWS anyway.

### Accomplishments that we're proud of

- The overlap protocol: the tool reports, the agent negotiates, and nothing is ever created without user consent — a real safety property most scheduling agents lack.
- A spec-faithful server that any MCP client (Claude Desktop, MCP Inspector, ChatGPT, Alexa+) can drive, plus MCP Apps inline views.
- A genuine end-to-end demo: web app as a real MCP client, a family kiosk screen, ICS subscriptions landing on a phone, and live Google Calendar sync — with zero cloud spend.
- Shipping an 8-entry friction log captured live during development, which per the rules earns up to a 10% judging bonus.

### What we learned

- Don't reimplement the host. Natural-language understanding belongs to the agent; MCP servers should be thin tools with clean schemas and structured results.
- SDKs move fast — reading the installed source beats guessing, and a one-release compatibility shim would have saved hours.
- The architecture lesson that stuck: local-first agent tooling is genuinely viable. A useful assistant doesn't need your calendar in someone else's cloud.

### What's next for TimeOS — your schedule that thinks ahead

- Connect to the real Alexa+ MCP Toolkit when partner access opens.
- Hosted multi-user version with TZID/VTIMEZONE ICS output (fixes the floating-time caveat from the friction log).
- Bedrock-powered flashcard generation as the AWS Builder mini-challenge integration.
- Shared household calendars, push notifications for deadlines, and course/certification workflow coverage beyond exams.
- Ship the kiosk mode as a real home display — the living room, front door, and cloud, all from one schedule.

## Product feedback field

```
- MCP Python SDK (mcp 2.x): onboarding was rough — FastMCP renamed to
  MCPServer with no shim, and tool callbacks running on worker threads is
  undocumented. But Streamable HTTP transport, session handling, and custom
  routes are clean once discovered. I'd build with it again.
- Alexa+ path: the "build a self-hosted MCP server" route is refreshingly
  open — no gated tools, standard MCP works, and the FAQ is honest about
  partner-only tooling.
- Google Calendar API: incremental sync with syncToken is well-documented;
  watch for 410 token expiry and pageToken pagination.
```

## Submission checklist

- [ ] Project name + elevator pitch + thumbnail (overview step)
- [ ] Description + seven fields (project details step)
- [ ] Product feedback + friction log submitted (up to 10% judging bonus)
- [ ] Demo video (<3 min, public, English) — not yet recorded
- [ ] GitHub repo — not yet initialized/created (must contain LICENSE + runnable README; public, or private + invite chris-trag, knmeiss, giolaq, anishamalde, mosesroth, emersonsklar at submission time)
- [ ] Track selection: Alexa+ (self-hosted MCP server)
