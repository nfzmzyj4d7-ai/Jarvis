"""Sessie-overzicht bij het afsluiten: latencytabel per stap + geheugengebruik van JARVIS en Ollama.

Wordt automatisch getoond (en bewaard in data/logs/sessie-*.md) als je JARVIS stopt met Ctrl-C of 'exit'.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from .latency import STEPS
from .sysinfo import footprint_mb, is_ollama, processes_mb

LABELS = {
    "stt": "spraak → tekst (Whisper)",
    "decide": "router-beslissing",
    "llm_first_token": "taalmodel: eerste token",
    "text_to_first_audio": "TTS: tekst → eerste geluid",
    "speech_end_to_audio": "uitgesproken → eerste geluid",
    "wake_to_audio": "wake word → eerste geluid",
    "input_to_audio": "vraag (tekst) → eerste geluid",
    "total_response": "vraag → antwoord compleet",
}


def latency_table(rows: list[dict]) -> str:
    out = []
    for mode, route in sorted({(r["mode"], r["route"]) for r in rows}):
        sub = [r for r in rows if r["mode"] == mode and r["route"] == route]
        out += [f"\n**{mode} / {route}** ({len(sub)} interacties)\n",
                "| stap | mediaan | p90 | min | max |", "|---|---|---|---|---|"]
        for name, _, _ in STEPS:
            vals = [r[name] for r in sub if name in r]
            if vals:
                out.append(f"| {LABELS[name]} | {np.median(vals):.2f}s | {np.percentile(vals, 90):.2f}s "
                           f"| {min(vals):.2f}s | {max(vals):.2f}s |")
    return "\n".join(out)


def memory_table(cfg) -> str:
    import httpx
    import psutil
    me = footprint_mb()
    lines = ["| onderdeel | geheugen |", "|---|---|",
             f"| JARVIS (Python, Whisper, Piper, wake word, VAD) | {me:,.0f} MB |"]
    total = me
    for pid, mb in processes_mb(is_ollama).items():
        lines.append(f"| Ollama-proces (pid {pid}) | {mb:,.0f} MB |")
        total += mb
    try:
        ps = httpx.get(cfg.get("llm.host").rstrip("/") + "/api/ps", timeout=3).json()
        for m in ps.get("models", []):
            size, vram = m.get("size", 0), m.get("size_vram", 0)
            gpu = f", {vram / size:.0%} op de GPU" if size else ""
            lines.append(f"| ↳ waarvan geladen model {m['name']} (volgens Ollama{gpu}) | {size / 1e6:,.0f} MB |")
    except Exception:
        lines.append("| Ollama | (niet bereikbaar) |")
    vm = psutil.virtual_memory()
    lines.append(f"| **Totaal JARVIS + Ollama** | **{total:,.0f} MB** |")
    lines.append(f"| Mac: totaal / nog beschikbaar | {vm.total / 1e9:.1f} GB / {vm.available / 1e9:.1f} GB |")
    return "\n".join(lines)


def session_summary(cfg, since: float) -> str:
    """Bouwt het overzicht voor alle interacties sinds `since` en bewaart het in de logmap."""
    log_dir: Path = cfg.path("paths.log_dir")
    path = log_dir / "latency.jsonl"
    rows = []
    if path.exists():
        rows = [r for r in (json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip())
                if r.get("ts", 0) >= since]
    text = ("## Latency (deze sessie)\n" + (latency_table(rows) if rows else "\n(geen vragen gesteld)")
            + "\n\n## Geheugen (bij afsluiten)\n\n" + memory_table(cfg) + "\n")
    out = log_dir / time.strftime("sessie-%Y%m%d-%H%M.md")
    out.write_text(text, encoding="utf-8")
    return text + f"\n(bewaard in {out})\n"
