"""Tekstmodus end-to-end (echte subprocess) + WebSocket-statusserver."""

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

import websockets

from conftest import ROOT, free_port
from jarvis.events import EventBus
from jarvis.ws_server import StatusServer


def run_text_mode(config, lines):
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    p = subprocess.run([sys.executable, "-m", "jarvis", "--text", "--config", str(config)],
                       input="\n".join(lines) + "\n", capture_output=True, text=True, timeout=60, env=env, cwd=ROOT)
    assert p.returncode == 0, p.stderr
    run_text_mode.stdout = p.stdout
    return [l for l in p.stdout.splitlines() if l.startswith("jarvis [")], p.stderr


def test_text_mode_and_memory_across_restarts(fake_ollama, make_config):
    config = make_config(fake_ollama.url)
    out, err = run_text_mode(config, ["Hoe laat is het?", "What's the date?",
                                      "Onthoud dat mijn auto een Suzuki Vitara is", "exit"])
    assert out[0].startswith("jarvis [router/nl]> Het is")
    assert out[1].startswith("jarvis [router/en]> It's")
    assert out[2].startswith("jarvis [llm/nl]>")
    assert "Latency [text/router]" in err
    summary = run_text_mode.stdout                                 # overzicht bij afsluiten
    assert "**text / router** (2 interacties)" in summary and "**text / llm** (1 interacties)" in summary
    assert "| router-beslissing |" in summary and "Totaal JARVIS + Ollama" in summary
    assert list((config.parent / "logs").glob("sessie-*.md"))

    out, _ = run_text_mode(config, ["Welke auto heb ik?"])          # tweede proces = herstart
    assert out == ["jarvis [llm/nl]> Je rijdt met een Suzuki Vitara."]


def test_status_server_streams_events(tmp_path):
    bus = EventBus()
    port = free_port()
    StatusServer(bus, "127.0.0.1", port, ROOT / "web" / "test.html").start()

    html = urllib.request.urlopen(f"http://127.0.0.1:{port}/").read().decode()
    assert "<title>JARVIS testpagina</title>" in html

    received = []

    async def client():
        async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws:
            received.append(json.loads(await ws.recv()))           # begroeting met huidige status
            threading.Thread(target=lambda: [time.sleep(0.2), *[bus.set_state(s) for s in
                             ("listening", "thinking", "speaking", "idle")],
                             bus.emit("transcript", text="Hoe laat is het?", lang="nl")]).start()
            for _ in range(5):
                received.append(json.loads(await asyncio.wait_for(ws.recv(), 5)))

    asyncio.run(client())
    assert received[0] == {"type": "status", "state": "idle", "hello": True}
    assert [e["state"] for e in received[1:5]] == ["listening", "thinking", "speaking", "idle"]
    assert received[5]["type"] == "transcript" and received[5]["text"] == "Hoe laat is het?"
