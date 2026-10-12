"""Minimale WebSocket-server: zendt elk event van de bus uit als JSON (status, transcript, antwoord...).

  http://HOST:PORT/     -> kale testpagina (web/test.html)
  ws://HOST:PORT/ws     -> eventstream; de HUD van later koppelt hier op aan
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from pathlib import Path

from websockets.asyncio.server import broadcast, serve

log = logging.getLogger(__name__)


class StatusServer:
    def __init__(self, bus, host: str, port: int, page: Path):
        self.bus, self.host, self.port, self.page = bus, host, port, page
        self._clients: set = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()
        bus.subscribe(self._on_event)

    def start(self) -> None:
        threading.Thread(target=self._run, name="ws-server", daemon=True).start()
        if not self._ready.wait(5):
            raise RuntimeError("WebSocket-server startte niet")

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._loop.run_until_complete(self._serve())

    async def _serve(self) -> None:
        async with serve(self._handler, self.host, self.port, process_request=self._http):
            log.info("Statuspagina: http://%s:%s/", self.host, self.port)
            self._ready.set()
            await asyncio.Future()

    def _http(self, connection, request):
        if request.path == "/ws":
            return None                                  # gewone WebSocket-handshake
        if request.path in ("/", "/test", "/test.html"):
            resp = connection.respond(200, self.page.read_text(encoding="utf-8"))
            del resp.headers["Content-Type"]
            resp.headers["Content-Type"] = "text/html; charset=utf-8"
            return resp
        return connection.respond(404, "Not found\n")

    async def _handler(self, ws) -> None:
        self._clients.add(ws)
        try:
            await ws.send(json.dumps({"type": "status", "state": self.bus.state, "hello": True}))
            async for _ in ws:                           # berichten van de client negeren we in fase 1
                pass
        finally:
            self._clients.discard(ws)

    def _on_event(self, event: dict) -> None:
        if self._loop is not None and self._clients:
            msg = json.dumps(event, ensure_ascii=False, default=str)
            self._loop.call_soon_threadsafe(lambda: broadcast(set(self._clients), msg))
