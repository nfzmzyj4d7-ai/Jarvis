"""Eenvoudige event-bus: status, transcript, antwoord... De WebSocket-server (en later de HUD) luistert mee."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

log = logging.getLogger(__name__)

STATES = ("idle", "listening", "thinking", "speaking")


class EventBus:
    def __init__(self):
        self._subs: list[Callable[[dict], None]] = []
        self._lock = threading.Lock()
        self.state = "idle"

    def subscribe(self, fn: Callable[[dict], None]) -> None:
        with self._lock:
            self._subs.append(fn)

    def emit(self, type_: str, **data) -> None:
        event = {"type": type_, "ts": round(time.time(), 3), **data}
        with self._lock:
            subs = list(self._subs)
        for fn in subs:
            try:
                fn(event)
            except Exception:
                log.exception("Event-subscriber faalde")

    def set_state(self, state: str) -> None:
        assert state in STATES, state
        if state != self.state:
            self.state = state
            self.emit("status", state=state)
