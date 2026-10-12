"""Router vs. taalmodel, tool calling en geheugen na herstart (met de nep-Ollama)."""

from jarvis.assistant import Assistant
from jarvis.config import load_config
from jarvis.events import EventBus
from jarvis.latency import Timings
from jarvis.llm import OllamaLLM
from jarvis.memory import Memory
from jarvis.timers import TimerManager
from jarvis.tools import load_tools


def make_assistant(config_path):
    cfg = load_config(config_path)
    bus = EventBus()
    events = []
    bus.subscribe(events.append)
    memory = Memory(cfg.path("paths.database"))
    a = Assistant(cfg, bus, memory, OllamaLLM(cfg), load_tools(), TimerManager())
    return a, events, memory


def ask(a, text, lang):
    t = Timings("test")
    t.mark("transcribed")
    return a.handle(text, lang, t), t


def test_time_goes_through_router_not_llm(fake_ollama, make_config):
    a, events, _ = make_assistant(make_config(fake_ollama.url))
    reply, t = ask(a, "Hoe laat is het?", "nl")
    assert reply.route == "router" and reply.text.startswith("Het is")
    reply, _ = ask(a, "What time is it?", "en")
    assert reply.route == "router" and reply.text.startswith("It's")
    assert fake_ollama.chat_requests() == []              # het taalmodel is NIET aangesproken
    assert t.steps()["decide"] < 0.05


def test_open_question_goes_to_llm(fake_ollama, make_config):
    a, events, _ = make_assistant(make_config(fake_ollama.url))
    reply, t = ask(a, "Wat is de zin van het leven?", "nl")
    assert reply.route == "llm"
    assert "**" not in reply.text and "testantwoord" in reply.text
    req = fake_ollama.chat_requests()[-1]
    assert req["model"] == "qwen3.5:9b" and req["think"] is False and req["stream"] is True
    assert {t["function"]["name"] for t in req["tools"]} >= {"remember", "recall", "set_timer", "get_time"}
    assert "Answer in Dutch" in req["messages"][0]["content"]
    states = [e["state"] for e in events if e["type"] == "status"]
    assert states[0] == "thinking"
    assert "llm_first_token" in t.steps()


def test_english_question_gets_english_prompt(fake_ollama, make_config):
    a, _, _ = make_assistant(make_config(fake_ollama.url))
    ask(a, "Tell me a joke", "en")
    assert "Answer in English." in fake_ollama.chat_requests()[-1]["messages"][0]["content"]


def test_remember_survives_restart(fake_ollama, make_config):
    config = make_config(fake_ollama.url)
    a, events, memory = make_assistant(config)
    reply, _ = ask(a, "Onthoud dat mijn auto een Suzuki Vitara is", "nl")
    assert reply.route == "llm" and "onthoud" in reply.text.lower()
    tool_events = [e for e in events if e["type"] == "tool"]
    assert tool_events[0]["name"] == "remember"
    # Het tool-resultaat ging terug naar het model:
    assert fake_ollama.chat_requests()[-1]["messages"][-1]["role"] == "tool"
    memory.close()

    b, _, _ = make_assistant(config)                       # nieuwe instantie = herstart
    reply, _ = ask(b, "Welke auto heb ik?", "nl")
    assert "Suzuki Vitara" in reply.text
    assert "Suzuki Vitara" in fake_ollama.chat_requests()[-1]["messages"][0]["content"]


def test_llm_down_gives_spoken_error(make_config):
    a, _, _ = make_assistant(make_config("http://127.0.0.1:9"))
    reply, _ = ask(a, "Wat is de zin van het leven?", "nl")
    assert reply.text == "Mijn taalmodel is even niet bereikbaar."
