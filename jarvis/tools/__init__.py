"""Plugin-systeem voor tools.

Elk bestand in deze map is een plugin en wordt automatisch geladen. Een tool registreer je zo:

    from jarvis.tools import tool

    @tool(
        name="get_weather",
        description="...",                       # het taalmodel leest dit om te kiezen
        parameters={"type": "object", "properties": {...}, "required": [...]},
    )
    def get_weather(ctx, city: str) -> str:      # ctx = ToolContext
        return "..."                             # korte tekst in ctx.lang

De teruggegeven tekst gaat terug naar het taalmodel, of wordt door de router direct uitgesproken.
Later komen hier agenda, Home Assistant, bedrijfsdata... gewoon als extra bestanden bij.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

log = logging.getLogger(__name__)


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    func: Callable[..., str]

    def schema(self) -> dict:
        """Formaat dat Ollama verwacht in `tools`."""
        return {"type": "function", "function": {
            "name": self.name, "description": self.description, "parameters": self.parameters}}

    def run(self, ctx: "ToolContext", args: dict | None) -> str:
        return str(self.func(ctx, **(args or {})))


@dataclass
class ToolContext:
    lang: str                       # taal waarin geantwoord moet worden
    memory: Any                     # jarvis.memory.Memory
    timers: Any                     # jarvis.timers.TimerManager
    config: Any                     # jarvis.config.Config
    now: Callable[[], datetime]     # tijd in de tijdzone van de gebruiker

    def say(self, nl: str, en: str) -> str:
        return nl if self.lang == "nl" else en


_REGISTRY: dict[str, Tool] = {}


def tool(name: str, description: str, parameters: dict | None = None):
    def decorator(func):
        _REGISTRY[name] = Tool(name, description, parameters or {"type": "object", "properties": {}}, func)
        return func
    return decorator


def load_tools(disabled: list[str] | tuple = ()) -> dict[str, Tool]:
    """Importeert elk plugin-bestand in deze map en geeft alle actieve tools terug."""
    for mod in pkgutil.iter_modules(__path__):
        if not mod.name.startswith("_"):
            importlib.import_module(f"{__name__}.{mod.name}")
    tools = {n: t for n, t in _REGISTRY.items() if n not in set(disabled)}
    log.debug("Tools geladen: %s", ", ".join(sorted(tools)))
    return tools
