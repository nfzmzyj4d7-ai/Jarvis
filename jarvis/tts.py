"""Tekst naar spraak met Piper (lokaal, ONNX). Eén stem per taal; afspelen in een eigen thread."""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from typing import Callable

import numpy as np

from .audio import tone

log = logging.getLogger(__name__)
BLOCK = 1024


@dataclass
class _Item:
    gen: int
    text: str | None
    audio: np.ndarray | None
    lang: str | None
    on_start: Callable | None
    on_end: Callable | None


class Speaker:
    def __init__(self, cfg):
        from piper import SynthesisConfig

        self.voice_paths = {lang: cfg.resolve(p) for lang, p in cfg.get("tts.voices").items()}
        self.default_lang = cfg.get("languages.default", "nl")
        self.syn = SynthesisConfig(length_scale=cfg.get("tts.length_scale", 1.0), volume=cfg.get("tts.volume", 1.0))
        self.device = cfg.get("audio.output_device", None)
        self.sample_rate = 22050
        self._voices: dict = {}
        self._q: queue.Queue[_Item] = queue.Queue()
        self._gen = 0
        self._pending = 0
        self._lock = threading.Lock()
        self._idle = threading.Event()
        self._idle.set()
        threading.Thread(target=self._worker, name="speaker", daemon=True).start()

    # --- stemmen ----------------------------------------------------------------
    def load(self) -> None:
        """Laadt alle stemmen vooraf (en faalt meteen als een stembestand ontbreekt)."""
        for lang in self.voice_paths:
            self._voice(lang)

    def _voice(self, lang: str):
        lang = lang if lang in self.voice_paths else self.default_lang
        if lang not in self._voices:
            from piper import PiperVoice
            path = self.voice_paths[lang]
            if not path.exists():
                raise FileNotFoundError(f"Piper-stem ontbreekt: {path}. Draai: python scripts/download_models.py")
            self._voices[lang] = PiperVoice.load(str(path))
            self.sample_rate = self._voices[lang].config.sample_rate
        return self._voices[lang]

    def synthesize(self, text: str, lang: str) -> tuple[np.ndarray, int]:
        voice = self._voice(lang)
        chunks = list(voice.synthesize(text, syn_config=self.syn))
        if not chunks:
            return np.zeros(0, np.int16), voice.config.sample_rate
        return np.concatenate([c.audio_int16_array for c in chunks]), chunks[0].sample_rate

    # --- publieke API -------------------------------------------------------------
    def say(self, text: str, lang: str, on_start=None, on_end=None) -> None:
        self._enqueue(_Item(self._gen, text, None, lang, on_start, on_end))

    def earcon(self) -> None:
        """Korte stijgende toon: 'ik luister'."""
        self._enqueue(_Item(self._gen, None, tone([880, 1320], 0.14, self.sample_rate), None, None, None))

    def alarm(self) -> None:
        beeps = np.concatenate([tone([1000], 0.18, self.sample_rate, 0.35), np.zeros(int(0.12 * self.sample_rate), np.int16)] * 3)
        self._enqueue(_Item(self._gen, None, beeps, None, None, None))

    def stop(self) -> None:
        """Stopt meteen met praten en gooit wat nog in de wachtrij zit weg."""
        with self._lock:
            self._gen += 1
        while True:
            try:
                self._q.get_nowait()
            except queue.Empty:
                break
            self._done_one()

    def wait(self, timeout: float | None = None) -> bool:
        return self._idle.wait(timeout)

    @property
    def speaking(self) -> bool:
        return not self._idle.is_set()

    # --- intern -------------------------------------------------------------------
    def _enqueue(self, item: _Item) -> None:
        with self._lock:
            item.gen = self._gen
            self._pending += 1
            self._idle.clear()
        self._q.put(item)

    def _done_one(self) -> None:
        with self._lock:
            self._pending -= 1
            if self._pending <= 0:
                self._pending = 0
                self._idle.set()

    def _worker(self) -> None:
        while True:
            item = self._q.get()
            try:
                if item.gen == self._gen:
                    if item.text is not None:
                        audio, sr = self.synthesize(item.text, item.lang)
                    else:
                        audio, sr = item.audio, self.sample_rate
                    if item.gen == self._gen and len(audio):
                        self._play(audio, sr, item.gen, item.on_start)
                    if item.on_end and item.gen == self._gen:
                        item.on_end()
            except Exception:
                log.exception("Afspelen faalde")
            finally:
                self._done_one()

    def _play(self, audio: np.ndarray, sr: int, gen: int, on_start) -> None:
        import sounddevice as sd
        with sd.OutputStream(samplerate=sr, channels=1, dtype="int16", device=self.device) as stream:
            for i in range(0, len(audio), BLOCK):
                if gen != self._gen:
                    stream.abort()
                    return
                if i == 0 and on_start:
                    on_start()
                stream.write(audio[i:i + BLOCK])
