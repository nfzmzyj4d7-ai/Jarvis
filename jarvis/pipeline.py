"""Spraakmodus: wake word -> opname met VAD -> Whisper -> router/LLM -> Piper -> speaker."""

from __future__ import annotations

import logging
import threading
import time

from .audio import Microphone
from .latency import Timings
from .listen import UtteranceRecorder
from .wakeword import WakeWord

log = logging.getLogger(__name__)


class VoicePipeline:
    def __init__(self, cfg, bus, assistant, speaker, stt, latency_log):
        self.cfg, self.bus, self.assistant = cfg, bus, assistant
        self.speaker, self.stt, self.latency = speaker, stt, latency_log
        self.wake = WakeWord(cfg)
        self.recorder = UtteranceRecorder(cfg)
        self.cooldown = cfg.get("wakeword.cooldown_s", 1.5)
        self.earcon = cfg.get("audio.earcon", True)
        self.barge_in = cfg.get("audio.barge_in", True)

        self.mode = "idle"          # idle | listening | busy
        self._lock = threading.Lock()
        self._turn = 0
        self._cancel = threading.Event()
        self._timings: Timings | None = None
        self._last_wake = 0.0

    def run(self) -> None:
        with Microphone(self.cfg.get("audio.input_device", None)) as mic:
            self.bus.set_state("idle")
            log.info("Klaar. Zeg 'Hey Jarvis'.")
            for frame in mic.frames():
                if self.mode == "listening":
                    self._listen(frame)
                    continue
                detected, score = self.wake.detect(frame)
                if detected and time.monotonic() - self._last_wake > self.cooldown:
                    if self.mode == "busy" and not self.barge_in:
                        continue
                    self._on_wake(score)

    def _on_wake(self, score: float) -> None:
        self._last_wake = time.monotonic()
        with self._lock:
            self._cancel.set()                    # onderbreek een lopend antwoord (barge-in)
            self._cancel = threading.Event()
            self._turn += 1
            self.mode = "listening"
        self.speaker.stop()
        self._timings = Timings("voice")
        self._timings.mark("wake")
        log.info("Wake word (score %.2f)", score)
        self.bus.emit("wake", score=round(score, 3))
        if self.earcon:
            self.speaker.earcon()
        self.recorder.start()
        self.wake.reset()
        self.bus.set_state("listening")

    def _listen(self, frame) -> None:
        result = self.recorder.feed(frame)
        if result == "done":
            self._timings.mark("speech_end")
            with self._lock:
                self.mode = "busy"
                turn, cancel = self._turn, self._cancel
            threading.Thread(target=self._work, args=(self.recorder.audio(), self._timings, cancel, turn),
                             name=f"turn-{turn}", daemon=True).start()
            self.wake.reset()
        elif result == "no_speech":
            log.info("Niets gehoord, terug naar wachten.")
            self.bus.emit("no_speech")
            self.wake.reset()
            with self._lock:
                self.mode = "idle"
            self.bus.set_state("idle")

    def _work(self, audio, timings: Timings, cancel: threading.Event, turn: int) -> None:
        try:
            self.bus.set_state("thinking")
            text, lang = self.stt.transcribe(audio)
            timings.mark("transcribed")
            log.info("Transcript [%s]: %s", lang, text)
            if cancel.is_set():
                return
            if not text:
                self.bus.emit("no_speech")
            else:
                timings.text = text
                self.assistant.handle(text, lang, timings, cancel)
                self.speaker.wait()
                if not cancel.is_set():
                    row = self.latency.write(timings)
                    self.bus.emit("latency", **{k: v for k, v in row.items() if k not in ("ts", "text")})
        except Exception:
            log.exception("Fout tijdens verwerken van je vraag")
        finally:
            with self._lock:
                if turn == self._turn and self.mode == "busy":
                    self.mode = "idle"
                    self.bus.set_state("idle")
