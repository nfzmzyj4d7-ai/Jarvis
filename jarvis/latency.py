"""Latency per stap. Elke interactie wordt een regel in data/logs/latency.jsonl.

Tijdstippen (marks):
  wake         wake word gehoord
  speech_end   VAD: je bent uitgesproken
  transcribed  Whisper klaar
  routed       router/LLM-beslissing genomen
  first_token  eerste token van het taalmodel (alleen LLM-route)
  first_text   eerste zin klaar voor TTS
  first_audio  eerste geluid uit de speaker
  done         antwoord volledig klaar
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

log = logging.getLogger(__name__)

STEPS = [
    # naam,                 van,           tot
    ("stt",                 "speech_end",  "transcribed"),
    ("decide",              "transcribed", "routed"),
    ("llm_first_token",     "routed",      "first_token"),
    ("text_to_first_audio", "first_text",  "first_audio"),
    ("speech_end_to_audio", "speech_end",  "first_audio"),
    ("wake_to_audio",       "wake",        "first_audio"),
    ("input_to_audio",      "transcribed", "first_audio"),
    ("total_response",      "transcribed", "done"),
]


class Timings:
    def __init__(self, mode: str):
        self.mode = mode
        self.route: str | None = None
        self.text = ""
        self.marks: dict[str, float] = {}
        self._lock = threading.Lock()

    def mark(self, name: str, t: float | None = None, overwrite: bool = False) -> None:
        with self._lock:
            if overwrite or name not in self.marks:
                self.marks[name] = t if t is not None else time.perf_counter()

    def steps(self) -> dict[str, float]:
        out = {}
        for name, a, b in STEPS:
            if a in self.marks and b in self.marks:
                out[name] = round(self.marks[b] - self.marks[a], 3)
        return out


class LatencyLog:
    def __init__(self, log_dir: Path):
        log_dir.mkdir(parents=True, exist_ok=True)
        self.path = log_dir / "latency.jsonl"
        self._lock = threading.Lock()

    def write(self, t: Timings) -> dict:
        row = {"ts": round(time.time(), 3), "mode": t.mode, "route": t.route, "text": t.text, **t.steps()}
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        pretty = "  ".join(f"{k}={v:.3f}s" for k, v in t.steps().items())
        log.info("Latency [%s/%s] %s", t.mode, t.route, pretty)
        return row
