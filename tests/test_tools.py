"""Runnable check (no framework): clash reporting + overlap policy + agent-chained resolution.

Run: uv run python tests/test_tools.py
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from timeos.store import Store  # noqa: E402
from timeos.timeutil import iso  # noqa: E402
from timeos.tools.calendar import make_calendar_tools  # noqa: E402
from timeos.tools.study import make_study_tools  # noqa: E402

DAY = "2099-10-12"  # far future so 'not_before' filtering never bites


def fresh() -> tuple[Store, dict]:
    store = Store(tempfile.mkdtemp() + "/t.db")
    tools = {fn.__name__: fn for fn in make_calendar_tools(store)}
    return store, tools


def test_clash_returns_data_and_creates_nothing() -> None:
    store, tools = fresh()
    store.add_event("Standup", f"{DAY}T09:00", f"{DAY}T10:00", kind="meeting")
    before = len(store.list_events())
    res = tools["add_event"](title="Dentist", start=f"{DAY}T09:30")
    assert res["kind"] == "clash", res
    assert res["operation"] == "add_event"
    assert res["policy"] in ("ask", "allow", "disallow")
    assert len(res["conflicts"]) == 1 and res["conflicts"][0]["title"] == "Standup"
    assert res["conflicts"][0]["movable"] is False, "meetings are not movable without consent"
    assert res["suggestions"], "tool reports free slots as data; the agent negotiates"
    assert len(store.list_events()) == before, "a clash must not create anything"


def test_clash_marks_study_movable_with_deadline() -> None:
    store, tools = fresh()
    dl = store.add_deadline("Spanish test", f"{DAY}T20:00", context="exam", effort_hours=2.0)
    store.add_event("Study: Spanish", f"{DAY}T17:00", f"{DAY}T17:45", kind="study", deadline_id=dl["id"])
    res = tools["add_event"](title="Dentist", start=f"{DAY}T17:00")
    conflict = res["conflicts"][0]
    assert conflict["movable"] is True
    assert conflict["deadline"] and conflict["deadline"]["due"] == f"{DAY}T20:00"


def test_accept_overlap_via_flag() -> None:
    store, tools = fresh()
    store.add_event("Standup", f"{DAY}T09:00", f"{DAY}T10:00", kind="meeting")
    res = tools["add_event"](title="Dentist", start=f"{DAY}T09:30", allow_overlap=True)
    assert res["kind"] == "event" and res["conflicts"], res
    assert len(store.list_events()) == 2


def test_policy_disallow_refuses() -> None:
    store, tools = fresh()
    store.add_event("Standup", f"{DAY}T09:00", f"{DAY}T10:00", kind="meeting")
    tools["set_overlap_policy"](policy="disallow")
    res = tools["add_event"](title="Dentist", start=f"{DAY}T09:30")
    assert res["kind"] == "clash", res
    assert len(store.list_events()) == 1


def test_agent_chains_move_then_add() -> None:
    """The agent resolves a clash with two plain calls: move the study session (update_event), then retry the add."""
    store, tools = fresh()
    study = store.add_event("Study: Spanish", f"{DAY}T17:00", f"{DAY}T17:45", kind="study")
    res = tools["add_event"](title="Dentist", start=f"{DAY}T17:00")
    assert res["kind"] == "clash"
    move = tools["update_event"](study["id"], start=f"{DAY}T19:00", end=f"{DAY}T19:45")
    assert move["kind"] == "event", move
    res = tools["add_event"](title="Dentist", start=f"{DAY}T17:00")
    assert res["kind"] == "event", res
    assert not tools["get_daily_brief"](day=DAY)["conflicts"]


def test_update_clash_reports_and_changes_nothing() -> None:
    store, tools = fresh()
    store.add_event("Busy", f"{DAY}T09:00", f"{DAY}T10:00")
    ev = store.add_event("Move me", f"{DAY}T11:00", f"{DAY}T12:00")
    res = tools["update_event"](ev["id"], start=f"{DAY}T09:00", end=f"{DAY}T10:00")
    assert res["kind"] == "clash" and res["draft"]["event_id"] == ev["id"], res
    assert store.get_event(ev["id"])["start_ts"] == f"{DAY}T11:00", "clash must not move anything"


def test_suggested_slots_do_not_overlap() -> None:
    store, tools = fresh()
    store.add_event("Standup", f"{DAY}T09:00", f"{DAY}T10:00", kind="meeting")
    res = tools["suggest_slots"](duration_minutes=60, day=DAY)
    for s in res["slots"]:
        s_start, s_end = datetime.fromisoformat(s["start"]), datetime.fromisoformat(s["end"])
        assert not (datetime(2099, 10, 12, 9, 0) < s_end and datetime(2099, 10, 12, 10, 0) > s_start), s


def test_log_study_session_credits_hours() -> None:
    store = Store(tempfile.mkdtemp() + "/t.db")
    tools = {fn.__name__: fn for fn in make_study_tools(store)}
    dl = tools["add_deadline"](title="Spanish test", due=f"{DAY}T20:00", effort_hours=4.0)["deadline"]
    res = tools["log_study_session"](minutes=30, deadline_id=dl["id"])
    assert res["kind"] == "logged", res
    assert res["deadline"]["hours_logged"] == 0.5, res
    assert tools["list_deadlines"]()["items"][0]["hours_logged"] == 0.5, "hours persist in store"


if __name__ == "__main__":
    test_clash_returns_data_and_creates_nothing()
    test_clash_marks_study_movable_with_deadline()
    test_accept_overlap_via_flag()
    test_policy_disallow_refuses()
    test_agent_chains_move_then_add()
    test_update_clash_reports_and_changes_nothing()
    test_suggested_slots_do_not_overlap()
    test_log_study_session_credits_hours()
    print("clash + overlap-policy checks passed")