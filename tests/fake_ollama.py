"""Nep-Ollama voor tests: zelfde REST-formaat (/api/tags, /api/chat met NDJSON-streaming en tool_calls),
maar met vaste, gescripte antwoorden. Test de plumbing, niet de intelligentie van het echte model."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _reply(messages: list[dict]) -> tuple[str, list]:
    system = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
    last = messages[-1]
    if last["role"] == "tool":
        return "Genoteerd, ik onthoud het.", []
    text = last["content"].lower()
    if "onthoud" in text or "remember" in text:
        return "", [{"function": {"name": "remember", "arguments": {"fact": "De auto van Jules is een Suzuki Vitara"}}}]
    if "welke auto" in text or "which car" in text:
        if "Suzuki Vitara" in system:
            return "Je rijdt met een Suzuki Vitara.", []
        return "Dat weet ik niet.", []
    return "Dit is een **testantwoord** van de nep-Ollama. Tweede zin, zonder markdown!", []


class FakeOllama:
    def __init__(self, model: str = "qwen3:8b", port: int = 0):
        self.model = model
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, obj):
                body = json.dumps(obj).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/api/tags":
                    self._json({"models": [{"name": outer.model}]})
                else:
                    self.send_error(404)

            def do_POST(self):
                req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append(req)
                if not req.get("messages"):
                    return self._json({"model": outer.model, "done": True})
                content, calls = _reply(req["messages"])
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                chunks = [{"message": {"role": "assistant", "content": "", "tool_calls": calls}, "done": False}] if calls \
                    else [{"message": {"role": "assistant", "content": w + " "}, "done": False} for w in content.split(" ")]
                for c in chunks + [{"message": {"role": "assistant", "content": ""}, "done": True}]:
                    self.wfile.write((json.dumps(c) + "\n").encode())
                    self.wfile.flush()
                    time.sleep(0.005)

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def __enter__(self):
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()

    def chat_requests(self) -> list[dict]:
        return [r for r in self.requests if r.get("messages")]


if __name__ == "__main__":  # handmatig: python tests/fake_ollama.py [poort]
    import sys
    with FakeOllama(port=int(sys.argv[1]) if len(sys.argv) > 1 else 11434) as f:
        print("Nep-Ollama op", f.url)
        threading.Event().wait()
