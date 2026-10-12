"""Kern van JARVIS: tekst in -> router of taalmodel -> antwoord (en spraak). Gedeeld door spraak- en tekstmodus."""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from .llm import OllamaError
from .persona import system_prompt
from .router import IntentRouter
from .textfmt import SentenceSplitter, clean_for_speech, spoken_duration
from .tools import ToolContext

log = logging.getLogger(__name__)


@dataclass
class Reply:
    text: str
    lang: str
    route: str          # router | llm
    intent: str | None


class Assistant:
    def __init__(self, cfg, bus, memory, llm, tools, timers, speaker=None):
        self.cfg, self.bus, self.memory, self.llm = cfg, bus, memory, llm
        self.tools, self.timers, self.speaker = tools, timers, speaker
        self.router = IntentRouter()
        self.user = cfg.get("user.name")
        self.tz = ZoneInfo(cfg.get("user.timezone"))
        self._schemas = [t.schema() for t in tools.values()]

    def now(self) -> datetime:
        return datetime.now(self.tz)

    # --- tools ----------------------------------------------------------------
    def run_tool(self, name: str, args: dict, lang: str) -> str:
        tool = self.tools.get(name)
        if tool is None:
            return f"Unknown tool: {name}"
        try:
            result = tool.run(ToolContext(lang, self.memory, self.timers, self.cfg, self.now), args)
        except Exception as e:  # een kapotte plugin mag JARVIS niet laten crashen
            log.exception("Tool %s faalde", name)
            result = f"Tool error: {e}"
        self.bus.emit("tool", name=name, args=json.loads(json.dumps(args, default=str)), result=result)
        return result

    # --- hoofdroute -------------------------------------------------------------
    def handle(self, text: str, lang: str, timings, cancel: threading.Event | None = None) -> Reply:
        text = text.strip()
        self.bus.set_state("thinking")
        self.bus.emit("transcript", text=text, lang=lang)

        intent = self.router.match(text)
        timings.mark("routed")
        if intent:
            lang = intent.lang or lang
            timings.route = "router"
            if intent.name == "stop":
                if self.speaker:
                    self.speaker.stop()
                reply_text = ""
            else:
                reply_text = self.run_tool(intent.tool, intent.args, lang)
                self._speak(reply_text, lang, timings)
            timings.mark("done")
        else:
            timings.route = "llm"
            reply_text = self._ask_llm(text, lang, timings, cancel)

        self.memory.add_message("user", text, lang, timings.route)
        if reply_text:
            self.memory.add_message("assistant", reply_text, lang, timings.route)
        self.bus.emit("response", text=reply_text, lang=lang, route=timings.route,
                      intent=intent.name if intent else None)
        return Reply(reply_text, lang, timings.route, intent.name if intent else None)

    def _ask_llm(self, text: str, lang: str, timings, cancel) -> str:
        facts = self.memory.facts(self.cfg.get("memory.facts_in_prompt", 50))
        messages = [{"role": "system", "content": system_prompt(self.user, lang, self.now(), facts)}]
        messages += self.memory.recent_messages(self.cfg.get("llm.history_turns", 6),
                                                self.cfg.get("llm.history_window_minutes", 30))
        messages.append({"role": "user", "content": text})

        splitter, parts = SentenceSplitter(), []
        try:
            for delta in self.llm.stream(messages, self._schemas, lambda n, a: self.run_tool(n, a, lang), cancel):
                timings.mark("first_token")
                parts.append(delta)
                for sentence in splitter.feed(delta):
                    self._speak(sentence, lang, timings)
            if cancel is None or not cancel.is_set():
                self._speak(splitter.flush(), lang, timings)
        except (OllamaError, httpx.HTTPError) as e:
            log.error("Taalmodel faalde: %s", e)
            msg = ("Mijn taalmodel is even niet bereikbaar." if lang == "nl"
                   else "My language model isn't reachable right now.")
            self._speak(msg, lang, timings)
            parts = [msg]
        timings.mark("done")
        return clean_for_speech("".join(parts))

    def _speak(self, text: str, lang: str, timings) -> None:
        text = clean_for_speech(text)
        if not text:
            return
        timings.mark("first_text")
        if self.speaker:
            def on_start():
                timings.mark("first_audio")
                self.bus.set_state("speaking")
            self.speaker.say(text, lang, on_start=on_start)

    # --- timers -----------------------------------------------------------------
    def timer_fired(self, timer) -> None:
        dur = spoken_duration(timer.seconds, timer.lang)
        text = (f"{self.user}, je timer van {dur} is afgelopen." if timer.lang == "nl"
                else f"{self.user}, your {dur} timer is done.")
        log.info("Timer %s afgelopen", timer.id)
        self.bus.emit("timer_done", id=timer.id, seconds=timer.seconds, text=text)
        if self.speaker:
            def on_end():
                if self.bus.state == "speaking":
                    self.bus.set_state("idle")
            self.speaker.alarm()
            self.speaker.say(text, timer.lang, on_start=lambda: self.bus.set_state("speaking"), on_end=on_end)
        else:
            print(f"\n⏰ {text}", flush=True)
