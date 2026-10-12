"""Ollama-client met streaming en tool calling (lokale REST API, geen account nodig)."""

from __future__ import annotations

import json
import logging
import threading
from typing import Callable, Iterator

import httpx

log = logging.getLogger(__name__)


class OllamaError(RuntimeError):
    pass


class OllamaLLM:
    def __init__(self, cfg):
        self.host = cfg.get("llm.host").rstrip("/")
        self.model = cfg.get("llm.model")
        self.think = cfg.get("llm.think", False)
        self.keep_alive = cfg.get("llm.keep_alive", "30m")
        self.options = {"temperature": cfg.get("llm.temperature", 0.7), "num_ctx": cfg.get("llm.num_ctx", 8192)}
        self.max_tool_rounds = cfg.get("llm.max_tool_rounds", 3)
        self._http = httpx.Client(timeout=httpx.Timeout(cfg.get("llm.timeout_s", 120), connect=5))

    def check(self) -> None:
        """Controleert of Ollama draait en het model aanwezig is, met een duidelijke foutmelding."""
        try:
            r = self._http.get(f"{self.host}/api/tags")
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise OllamaError(f"Ollama is niet bereikbaar op {self.host} ({e}). Start de Ollama-app of 'ollama serve'.")
        names = {m.get("name") for m in r.json().get("models", [])}
        if self.model not in names and f"{self.model}:latest" not in names:
            raise OllamaError(f"Model '{self.model}' ontbreekt. Haal het op met: ollama pull {self.model}")

    def warmup(self, messages: list[dict], tools: list[dict]) -> None:
        """Laadt het model met DEZELFDE opties als echte vragen (anders herlaadt Ollama het bij de eerste
        vraag) en verwerkt de vaste systeemtekst + tools alvast, zodat Ollama die kan hergebruiken."""
        payload = {"model": self.model, "messages": messages, "stream": False, "keep_alive": self.keep_alive,
                   "options": {**self.options, "num_predict": 1}}
        if tools:
            payload["tools"] = tools
        if self.think is not None:
            payload["think"] = self.think
        r = self._http.post(f"{self.host}/api/chat", json=payload)
        r.raise_for_status()

    def stream(self, messages: list[dict], tools: list[dict], run_tool: Callable[[str, dict], str],
               cancel: threading.Event | None = None) -> Iterator[str]:
        """Geeft tekst-stukjes terug zodra ze binnenkomen; tool calls worden tussendoor uitgevoerd."""
        msgs = list(messages)
        for round_ in range(self.max_tool_rounds + 1):
            payload = {
                "model": self.model, "messages": msgs, "stream": True,
                "keep_alive": self.keep_alive, "options": self.options,
            }
            if round_ < self.max_tool_rounds and tools:
                payload["tools"] = tools
            if self.think is not None:
                payload["think"] = self.think

            content, calls = "", []
            with self._http.stream("POST", f"{self.host}/api/chat", json=payload) as r:
                if r.status_code != 200:
                    r.read()
                    raise OllamaError(f"Ollama gaf {r.status_code}: {r.text[:300]}")
                for line in r.iter_lines():
                    if cancel is not None and cancel.is_set():
                        return
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    if "error" in chunk:
                        raise OllamaError(chunk["error"])
                    msg = chunk.get("message") or {}
                    if msg.get("content"):
                        content += msg["content"]
                        yield msg["content"]
                    calls.extend(msg.get("tool_calls") or [])
                    if chunk.get("done"):
                        break
            if not calls:
                return

            msgs.append({"role": "assistant", "content": content, "tool_calls": calls})
            for call in calls:
                fn = call.get("function") or {}
                name, args = fn.get("name", ""), fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                result = run_tool(name, args)
                log.info("Tool %s(%s) -> %s", name, json.dumps(args, ensure_ascii=False), result.replace("\n", " | "))
                msgs.append({"role": "tool", "tool_name": name, "content": result})
