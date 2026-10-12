"""Intent-router: simpele commando's (NL + EN) zonder taalmodel.

Bewust strikt: een zin moet in zijn geheel op een patroon passen. Zo gaat "hoe laat gaat de bakker
open?" niet per ongeluk naar de klok, maar naar het taalmodel.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .textfmt import parse_duration


@dataclass
class Intent:
    name: str                 # time | date | timer | cancel_timer | stop
    tool: str | None          # tool die het uitvoert (None = pipeline regelt het zelf)
    args: dict = field(default_factory=dict)
    lang: str | None = None   # taal die uit het patroon volgt (None = onbepaald, bv. "stop")


def normalize(text: str) -> str:
    t = text.lower().replace("’", "'").replace("‘", "'")
    t = re.sub(r"[?!.,;:¿¡\"“”()]", " ", t)
    t = " ".join(t.split())
    t = re.sub(r"^(?:(?:hey|hé|hee|hej|hi|oké|okay|ok) )?jarvis ", "", t)
    t = re.sub(r" jarvis$", "", t)
    t = re.sub(r"^(?:zeg|ok|oké|okay|hey|hé|so|well|nou|allez) ", "", t)
    t = re.sub(r" (?:alsjeblieft|alstublieft|aub|asjeblieft|please|eens|nu|eigenlijk|precies|now|right now|again)$", "", t)
    return t.strip()


def _full(pattern: str) -> re.Pattern:
    return re.compile(rf"^(?:{pattern})$")


_NL_ASK = r"(?:(?:kan|kun|kunt|wil) (?:je|jij|u) (?:me |mij )?(?:eens )?(?:zeggen|vertellen) |(?:zeg|vertel) (?:me |mij )?(?:eens )?|weet (?:je|jij|u) |mag ik weten )?"
_EN_ASK = r"(?:(?:can|could|would) you (?:please )?tell me |(?:please )?tell me |do you know |may i know )?"

TIME_NL = _full(_NL_ASK + r"(?:hoe laat is het|hoe laat het is|hoeveel uur is het|hoeveel uur het is|wat is het uur|"
                          r"wat het uur is|wat is de tijd|hoe laat|hoe laat zijn we|de tijd)(?: nu| eigenlijk| precies| al)*")
TIME_EN = _full(_EN_ASK + r"(?:what time is it|what's the time|what is the time|what time it is|the time|"
                          r"the current time|what's the current time|what is the current time|time)(?: now| right now)*")

DATE_NL = _full(_NL_ASK + r"(?:welke datum is het|welke datum het is|wat is de datum|wat de datum is|welke dag is het|"
                          r"welke dag het is|welke dag zijn we|de hoeveelste (?:is het|zijn we)|de hoeveelste het is|"
                          r"welke datum (?:hebben|zijn) we|wat voor dag is het|de datum|welke datum)(?: vandaag| van vandaag)*")
DATE_EN = _full(_EN_ASK + r"(?:what's the date|what is the date|what date is it|what day is it|what's today's date|"
                          r"what is today's date|today's date|what day is today|what date it is|what day it is|the date)"
                          r"(?: today)*")

TIMER_NL = _full(r"(?:(?:zet|start|maak) (?:eens )?(?:een |de |m'n |mijn )?)?(?:timer|kookwekker|wekker)"
                 r"(?: (?:van|op|voor|in))? (?P<dur>.+)|(?P<dur2>.+) timer|(?:zet|start) (?:een )?timer (?P<dur3>.+)")
TIMER_EN = _full(r"(?:(?:set|start|create|make) (?:me )?(?:a |the )?)?timer(?: (?:for|of|in))? (?P<dur>.+)"
                 r"|(?:(?:set|start) (?:me )?(?:a |an )?)?(?P<dur2>.+?) timer")

CANCEL_NL = _full(r"(?:annuleer|stop|verwijder|schrap) (?:de |alle |mijn |m'n )?(?:timers?|kookwekker|wekker)")
CANCEL_EN = _full(r"(?:cancel|delete|remove|clear) (?:the |all |my |all my |all the )?timers?")

STOP_NL = _full(r"stop|stil|stilte|zwijg|hou op|houd op|genoeg|sst+|wees stil|stop met praten|kop dicht|"
                r"stop maar|het is goed|laat maar")
STOP_EN = _full(r"stop|shut up|be quiet|quiet|silence|enough|stop it|stop talking|never mind|nevermind|hush|shh+")
STOP_BOTH = _full(r"stop|ok stop|oké stop|okay stop")


def _duration(m: re.Match) -> int | None:
    for g in ("dur", "dur2", "dur3"):
        try:
            value = m.group(g)
        except IndexError:
            continue
        if value:
            return parse_duration(value)
    return None


class IntentRouter:
    def match(self, text: str) -> Intent | None:
        t = normalize(text)
        if not t:
            return None
        if STOP_BOTH.match(t):
            return Intent("stop", None)
        if STOP_NL.match(t):
            return Intent("stop", None, lang="nl")
        if STOP_EN.match(t):
            return Intent("stop", None, lang="en")
        if TIME_NL.match(t):
            return Intent("time", "get_time", lang="nl")
        if TIME_EN.match(t):
            return Intent("time", "get_time", lang="en")
        if DATE_NL.match(t):
            return Intent("date", "get_date", lang="nl")
        if DATE_EN.match(t):
            return Intent("date", "get_date", lang="en")
        if CANCEL_NL.match(t):
            return Intent("cancel_timer", "cancel_timers", lang="nl")
        if CANCEL_EN.match(t):
            return Intent("cancel_timer", "cancel_timers", lang="en")
        for pattern, lang in ((TIMER_NL, "nl"), (TIMER_EN, "en")):
            m = pattern.match(t)
            if m:
                seconds = _duration(m)
                if seconds:
                    return Intent("timer", "set_timer", {"seconds": seconds}, lang=_timer_lang(t, lang))
        return None


def _timer_lang(t: str, fallback: str) -> str:
    """'timer 5 minutes' past op het NL-patroon, maar de eenheid verraadt de taal."""
    if re.search(r"\b(?:seconds?|minutes?|hours?|half an hour|quarter)\b", t):
        return "en"
    if re.search(r"\b(?:seconden?|minuut|minuten|uur|uren|kwartier)\b", t):
        return "nl"
    return fallback
