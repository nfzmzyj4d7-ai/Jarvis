"""Afteltimers. Bij afloop roept de manager `on_fire(timer)` aan (de pipeline spreekt dan een melding uit)."""

from __future__ import annotations

import itertools
import threading
import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Timer:
    id: int
    seconds: int
    lang: str
    ends_at: float
    _thread: threading.Timer | None = field(default=None, repr=False)


class TimerManager:
    def __init__(self, on_fire: Callable[[Timer], None] | None = None):
        self.on_fire = on_fire
        self._timers: dict[int, Timer] = {}
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def start(self, seconds: int, lang: str) -> Timer:
        t = Timer(next(self._ids), int(seconds), lang, time.time() + seconds)
        t._thread = threading.Timer(seconds, self._fire, args=(t.id,))
        t._thread.daemon = True
        with self._lock:
            self._timers[t.id] = t
        t._thread.start()
        return t

    def _fire(self, timer_id: int) -> None:
        with self._lock:
            t = self._timers.pop(timer_id, None)
        if t and self.on_fire:
            self.on_fire(t)

    def cancel_all(self) -> int:
        with self._lock:
            timers, self._timers = list(self._timers.values()), {}
        for t in timers:
            t._thread.cancel()
        return len(timers)

    def active(self) -> list[Timer]:
        with self._lock:
            return sorted(self._timers.values(), key=lambda t: t.ends_at)
