import threading
from datetime import datetime

from jarvis.memory import Memory
from jarvis.timers import TimerManager
from jarvis.tools import ToolContext, load_tools


def test_facts_survive_restart(tmp_path):
    db = tmp_path / "j.db"
    m = Memory(db)
    assert m.add_fact("De auto van Jules is een Suzuki Vitara")
    assert not m.add_fact("De auto van Jules is een  Suzuki Vitara")   # dubbel
    m.add_message("user", "hallo", "nl", "llm")
    m.close()

    m2 = Memory(db)                                                    # "herstart"
    assert m2.facts() == ["De auto van Jules is een Suzuki Vitara"]
    assert m2.search_facts("welke auto heb ik") == ["De auto van Jules is een Suzuki Vitara"]
    assert m2.search_facts("verjaardag") == []
    assert m2.recent_messages(6, 30) == [{"role": "user", "content": "hallo"}]


def test_plugins_autoregistered():
    tools = load_tools()
    assert {"get_time", "get_date", "set_timer", "cancel_timers", "remember", "recall"} <= set(tools)
    for t in tools.values():
        s = t.schema()
        assert s["type"] == "function" and s["function"]["name"] == t.name
        assert s["function"]["parameters"]["type"] == "object"
    assert "set_timer" not in load_tools(disabled=["set_timer"])


def test_tools_run(tmp_path):
    tools = load_tools()
    fired = threading.Event()
    timers = TimerManager(on_fire=lambda t: fired.set())
    mem = Memory(tmp_path / "j.db")
    ctx = ToolContext("nl", mem, timers, None, lambda: datetime(2026, 10, 12, 14, 5))

    assert tools["get_time"].run(ctx, {}) == "Het is 14 uur 5."
    assert tools["remember"].run(ctx, {"fact": "Jules houdt van koffie"}).startswith("Opgeslagen")
    assert "koffie" in tools["recall"].run(ctx, {"topic": "koffie"})
    assert tools["set_timer"].run(ctx, {"seconds": "90"}) == "Timer gezet voor 1 minuut en 30 seconden."
    assert tools["set_timer"].run(ctx, {"minutes": 1}) == "Timer gezet voor 1 minuut."
    assert tools["set_timer"].run(ctx, {}) == "Voor hoelang moet de timer lopen?"
    assert len(timers.active()) == 2
    assert tools["cancel_timers"].run(ctx, {}) == "2 timers geannuleerd."
    assert tools["cancel_timers"].run(ctx, {}) == "Er loopt geen timer."
    assert not fired.is_set()

    timers.start(0.05, "nl")                       # afgelopen timer -> callback
    assert fired.wait(2)
