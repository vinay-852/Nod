"""MCP Apps views — the "UI as backend resources" story.

A single self-contained HTML view (`ui://timeos/view.html`) that any MCP Apps
host (including Alexa+, per Amazon's docs) fetches and renders inline after a
tool call. The host passes the tool result to the view via postMessage; the
view renders it as a card. When opened directly (e.g. in MCP Inspector) it
shows a friendly placeholder instead of a blank page.

The view is tolerant of the payload shapes different hosts use (raw result
object, `structuredContent`, `result.structuredContent`, `params.data`).
"""

from __future__ import annotations

URI = "ui://timeos/view.html"
NAME = "TimeOS View"
MIME = "text/html;profile=mcp-app"

# Tool names that render a card in the view (all share the same view).
CARD_TOOLS = {
    "get_daily_brief", "add_event", "update_event", "get_calendar", "suggest_slots",
    "add_deadline", "list_deadlines", "update_deadline", "create_study_plan",
    "schedule_study", "create_flashcards", "log_study_session",
}

VIEW_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TimeOS view</title>
<style>
  :root { --bg:#0b1220; --panel:#111a2e; --line:#1f2c47; --text:#e8edf7; --muted:#8fa1c0;
          --accent:#ff9900; --cyan:#4dd8ff; --green:#3ddc84; --red:#ff6b6b; --amber:#ffc857; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; padding:14px; }
  h1 { font-size:15px; font-weight:700; display:flex; align-items:center; gap:8px; margin-bottom:12px; }
  h1 .dot { width:18px; height:18px; border-radius:50%; background:conic-gradient(from 210deg,var(--accent),var(--cyan),var(--accent)); }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:12px 14px; font-size:13px; line-height:1.45; }
  .card.warn { border-color:#5b2b2b; background:#1d1518; }
  .card.good { border-color:#1d4a33; background:#10201a; }
  .row { display:flex; align-items:baseline; gap:8px; padding:5px 0; border-bottom:1px dashed var(--line); }
  .row:last-child { border-bottom:none; }
  .chip { display:inline-block; background:#1d2c4d; border:1px solid #2a3d66; border-radius:8px; padding:2px 8px; font-size:11px; color:var(--cyan); white-space:nowrap; }
  .chip.red { color:var(--red); border-color:#5b2b2b; background:#2a1718; }
  .chip.green { color:var(--green); border-color:#1d4a33; background:#12241c; }
  .chip.amber { color:var(--amber); border-color:#5a4517; background:#241d0f; }
  .muted { color:var(--muted); font-size:11.5px; }
  .deck { display:grid; grid-template-columns:repeat(auto-fill,minmax(130px,1fr)); gap:8px; margin-top:8px; }
  .fc { perspective:800px; height:96px; cursor:pointer; }
  .fc-inner { position:relative; width:100%; height:100%; transform-style:preserve-3d; transition:transform .45s; }
  .fc.flip .fc-inner { transform:rotateY(180deg); }
  .fc-face { position:absolute; inset:0; backface-visibility:hidden; border-radius:10px; display:flex; align-items:center; justify-content:center; text-align:center; padding:8px; font-size:11.5px; border:1px solid var(--line); background:linear-gradient(160deg,#16233d,#101a2e); }
  .fc-face.a { transform:rotateY(180deg); background:linear-gradient(160deg,#1d3a2a,#12241c); border-color:#1d4a33; }
  .placeholder { text-align:center; color:var(--muted); padding:24px 10px; font-size:13px; }
</style>
</head>
<body>
  <h1><span class="dot"></span>TimeOS</h1>
  <div id="root"><div class="placeholder">Connected. Tool results will render here.</div></div>
<script>
"use strict";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
const fmt = (t) => { const d = new Date(t.replace("T","T") + ":00"); return isNaN(d) ? t : d.toLocaleTimeString([], { hour:"numeric", minute:"2-digit" }); };
const dayLabel = (t) => { const d = new Date(t + "T00:00"); return d.toLocaleDateString([], { weekday:"short", month:"short", day:"numeric" }); };
const root = document.getElementById("root");

function render(res) {
  if (!res || typeof res !== "object") { root.innerHTML = `<div class="muted">${esc(String(res ?? ""))}</div>`; return; }
  const k = res.kind || "";
  let html = "";
  if (k === "error") html = `<div class="card warn"><div class="muted">${esc(res.error)}</div></div>`;
  else if (k === "brief") {
    const evs = (res.events||[]).map(e => `<div class="row"><span class="chip ${e.kind==="study"?"amber":""}">${fmt(e.start)}–${fmt(e.end)}</span><b>${esc(e.title)}</b></div>`).join("") || `<div class="muted">Nothing scheduled.</div>`;
    const dls = (res.deadlines||[]).map(d => `<div class="row"><span class="chip amber">due ${dayLabel(d.due)}</span> ${esc(d.title)}</div>`).join("");
    const cfs = (res.conflicts||[]).map(c => `<div class="row"><span class="chip red">conflict</span> ${esc(c.event.title)} ↔ ${esc(c.with.title)}</div>`).join("");
    html = `<div class="card"><div class="muted" style="margin-bottom:6px">Today — ${dayLabel(res.day)}</div>${evs}${dls?`<div style="margin-top:8px"><b class="muted">Deadlines</b></div>${dls}`:""}${cfs?`<div style="margin-top:8px"><b class="muted">Conflicts</b></div>${cfs}`:""}</div>`;
  }
  else if (k === "event") {
    const e = res.event;
    html = `<div class="card good"><div class="row"><span class="chip green">${fmt(e.start)}–${fmt(e.end)}</span><b>${esc(e.title)}</b></div></div>`;
    if ((res.conflicts||[]).length) html += `<div class="card warn" style="margin-top:8px"><b class="muted">⚠ Overlap</b>${(res.conflicts||[]).map(c=>`<div class="row"><span class="chip red">${fmt(c.start)}</span> ${esc(c.title)}</div>`).join("")}</div>`;
  }
  else if (k === "clash") {
    html = `<div class="card warn"><b class="muted">Clash — nothing added yet</b>${(res.conflicts||[]).map(c=>`<div class="row"><span class="chip red">${fmt(c.start)}</span> ${esc(c.title)}${c.movable?' · can move':''}</div>`).join("")}${(res.suggestions||[]).length?`<div class="muted" style="margin-top:6px">Free: ${res.suggestions.slice(0,3).map(s=>fmt(s.start)).join(" · ")}</div>`:""}</div>`;
  }
  else if (k === "calendar" || k === "slots") {
    const items = k === "calendar" ? (res.events||[]).map(e => [fmt(e.start)+"–"+fmt(e.end), e.title]) : (res.slots||[]).map(s => [fmt(s.start)+"–"+fmt(s.end), "free"]);
    html = `<div class="card">${items.map(([t,l]) => `<div class="row"><span class="chip">${t}</span> ${esc(l)}</div>`).join("") || `<div class="muted">Nothing here.</div>`}</div>`;
  }
  else if (k === "deadline") {
    const d = res.deadline;
    html = `<div class="card"><div class="row"><span class="chip amber">due ${dayLabel(d.due)}</span><b>${esc(d.title)}</b><span class="muted">${d.effort_hours}h</span></div></div>`;
  }
  else if (k === "deadlines" || k === "plan" || k === "scheduled") {
    let rows = (res.items||res.booked||[]).map(x => {
      const t = x.title || (res.deadline && res.deadline.title);
      const due = x.due ? `due ${dayLabel(x.due)}` : (x.start ? fmt(x.start)+"–"+fmt(x.end) : "");
      return `<div class="row"><span class="chip ${x.status==="done"?"green":k==="scheduled"?"amber":"amber"}">${due}</span>${esc(t||"")}</div>`;
    }).join("");
    if (k === "plan") rows = (res.steps||[]).map(s => `<div class="row">${s.step}. <span class="muted">${esc(s.focus)}</span> <span class="chip">${s.minutes} min</span></div>`).join("");
    if (!rows) rows = `<div class="muted">${res.remaining ? res.remaining + " session(s) still to book" : "Nothing here."}</div>`;
    html = `<div class="card">${rows}</div>`;
  }
  else if (k === "flashcards") {
    html = `<div class="card"><div class="muted">Flashcards — ${esc(res.topic)}</div><div class="deck">${(res.cards||[]).map(c=>`<div class="fc"><div class="fc-inner"><div class="fc-face q">${esc(c.q)}</div><div class="fc-face a">${esc(c.a)}</div></div></div>`).join("")}</div></div>`;
    root.querySelectorAll(".fc").forEach(fc => fc.addEventListener("click", () => fc.classList.toggle("flip")));
  }
  else if (k === "logged") html = `<div class="card good"><div class="row"><span class="chip green">+${res.minutes} min</span> study time logged</div></div>`;
  else if (k === "deleted") html = `<div class="card"><div class="muted">Removed: ${esc(res.title)}</div></div>`;
  else html = `<div class="card"><div class="muted">${esc(JSON.stringify(res).slice(0,400))}</div></div>`;
  root.innerHTML = html;
  root.querySelectorAll(".fc").forEach(fc => fc.addEventListener("click", () => fc.classList.toggle("flip")));
}

// Tolerant listener: hosts pass the tool result with different shapes.
window.addEventListener("message", (e) => {
  let data = e && e.data;
  if (!data) return;
  if (data.jsonrpc === "2.0") {                    // JSON-RPC envelope
    const p = data.params || {};
    if (data.method === "notifications/message" && p.message && p.message.content) {
      const c = p.message.content[0];
      if (c && (c.structuredContent || c.text)) { data = c.structuredContent || (() => { try { return JSON.parse(c.text); } catch (_) { return null; } })(); }
    } else if (p.data !== undefined) data = p.data;
    else if (data.result && data.result.structuredContent) data = data.result.structuredContent;
    else if (data.result) data = data.result;
    else return;
  } else if (data.structuredContent) data = data.structuredContent;
  else if (data.result && data.result.structuredContent) data = data.result.structuredContent;
  render(data);
});
</script>
</body>
</html>
"""