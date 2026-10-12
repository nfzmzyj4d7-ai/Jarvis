"""Latencytabel (uit data/logs/latency.jsonl) + totaal geheugengebruik van JARVIS en Ollama.

Draai dit terwijl JARVIS nog draait (anders kan het geheugen van JARVIS niet gemeten worden):
  python scripts/report.py              # alles
  python scripts/report.py --last 20    # laatste 20 interacties
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from jarvis.config import load_config  # noqa: E402
from jarvis.latency import STEPS  # noqa: E402
from jarvis.sysinfo import footprint_mb, is_jarvis, is_ollama, processes_mb  # noqa: E402

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
    for (mode, route) in sorted({(r["mode"], r["route"]) for r in rows}):
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
    lines = ["| onderdeel | geheugen |", "|---|---|"]
    total = 0.0
    me = os.getpid()
    jarvis = {pid: mb for pid, mb in processes_mb(is_jarvis).items() if pid != me}
    for pid, mb in jarvis.items():
        lines.append(f"| JARVIS (pid {pid}: Python, Whisper, Piper, wake word, VAD) | {mb:,.0f} MB |")
        total += mb
    if not jarvis:
        lines.append("| JARVIS | (draait niet; start het eerst) |")
    ollama = processes_mb(is_ollama)
    for pid, mb in ollama.items():
        lines.append(f"| Ollama-proces (pid {pid}) | {mb:,.0f} MB |")
        total += mb
    try:
        ps = httpx.get(cfg.get("llm.host").rstrip("/") + "/api/ps", timeout=3).json()
        for m in ps.get("models", []):
            lines.append(f"| ↳ geladen model {m['name']} volgens Ollama | {m.get('size', 0) / 1e6:,.0f} MB |")
    except Exception:
        lines.append("| Ollama | (niet bereikbaar) |")
    vm = psutil.virtual_memory()
    lines.append(f"| **Totaal JARVIS + Ollama** | **{total:,.0f} MB** |")
    lines.append(f"| Systeem: totaal / beschikbaar | {vm.total / 1e9:.1f} GB / {vm.available / 1e9:.1f} GB |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--last", type=int)
    args = ap.parse_args()
    cfg = load_config(args.config)
    path = cfg.path("paths.log_dir") / "latency.jsonl"
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []
    if args.last:
        rows = rows[-args.last:]
    print("## Latency\n" + (latency_table(rows) if rows else "\n(nog geen metingen)"))
    print("\n## Geheugen\n\n" + memory_table(cfg))
    print(f"\n(dit rapport zelf: {footprint_mb():.0f} MB, niet meegeteld)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
