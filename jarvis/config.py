"""Laadt config.yaml. Relatieve paden worden opgelost t.o.v. de map van het config-bestand."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_MISSING = object()


class Config:
    def __init__(self, data: dict, base_dir: Path):
        self.data = data
        self.base_dir = base_dir

    def get(self, dotted: str, default: Any = _MISSING) -> Any:
        node: Any = self.data
        for key in dotted.split("."):
            if not isinstance(node, dict) or key not in node:
                if default is _MISSING:
                    raise KeyError(f"Ontbrekende config-sleutel: {dotted}")
                return default
            node = node[key]
        return node

    def path(self, dotted: str) -> Path:
        return self.resolve(self.get(dotted))

    def resolve(self, value: str | Path) -> Path:
        p = Path(value).expanduser()
        return p if p.is_absolute() else (self.base_dir / p).resolve()


def load_config(path: str | Path | None = None) -> Config:
    path = Path(path or os.environ.get("JARVIS_CONFIG") or PROJECT_ROOT / "config.yaml").expanduser().resolve()
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return Config(data, path.parent)
