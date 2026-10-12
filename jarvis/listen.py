"""Opname na het wake word, met Silero VAD: weet zelf wanneer je uitgesproken bent."""

from __future__ import annotations

from collections import deque

import numpy as np

from .audio import FRAME, SAMPLE_RATE

FRAME_MS = FRAME * 1000 // SAMPLE_RATE   # 80
PRE_ROLL_FRAMES = 4                      # 320 ms vóór de eerste spraak bewaren (anders mis je de eerste klank)


class UtteranceRecorder:
    def __init__(self, cfg):
        from openwakeword.vad import VAD

        path = cfg.path("vad.model")
        if not path.exists():
            raise FileNotFoundError(f"VAD-model ontbreekt: {path}. Draai: python scripts/download_models.py")
        self.vad = VAD(model_path=str(path))
        self.threshold = cfg.get("vad.threshold", 0.5)
        self.silence_ms = cfg.get("vad.silence_ms", 800)
        self.max_wait_ms = cfg.get("vad.max_wait_s", 6) * 1000
        self.max_utt_ms = cfg.get("vad.max_utterance_s", 15) * 1000
        self.min_speech_ms = cfg.get("vad.min_speech_ms", 240)
        self.ignore_ms = cfg.get("vad.ignore_after_wake_ms", 250)
        self.start()

    def start(self) -> None:
        self.vad.reset_states()
        self._pre: deque = deque(maxlen=PRE_ROLL_FRAMES)
        self._frames: list[np.ndarray] = []
        self._elapsed = self._speech = self._silence = 0
        self._started = False

    def speech_prob(self, frame: np.ndarray) -> float:
        return float(self.vad.predict(frame, frame_size=FRAME // 2))

    def feed(self, frame: np.ndarray) -> str | None:
        """Geeft 'done' (zin compleet), 'no_speech' (niets gezegd) of None (verder luisteren)."""
        self._elapsed += FRAME_MS
        if self._elapsed <= self.ignore_ms:          # de bevestigingstoon niet als spraak zien
            self._pre.append(frame)
            return None
        is_speech = self.speech_prob(frame) >= self.threshold

        if not self._started:
            self._pre.append(frame)
            if is_speech:
                self._started = True
                self._frames = list(self._pre)
                self._speech, self._silence = FRAME_MS, 0
            elif self._elapsed >= self.max_wait_ms:
                return "no_speech"
            return None

        self._frames.append(frame)
        if is_speech:
            self._speech += FRAME_MS
            self._silence = 0
        else:
            self._silence += FRAME_MS
        if self._silence >= self.silence_ms:
            if self._speech >= self.min_speech_ms:
                return "done"
            self._started = False                   # kuchje of klik: opnieuw wachten
            self._pre.clear()
            return "no_speech" if self._elapsed >= self.max_wait_ms else None
        if self._elapsed >= self.max_utt_ms:
            return "done"
        return None

    def audio(self) -> np.ndarray:
        """Opgenomen zin als float32 [-1, 1], zonder de lange stilte op het einde."""
        keep = len(self._frames) - max(0, self._silence // FRAME_MS - 3)
        frames = self._frames[:max(1, keep)]
        return np.concatenate(frames).astype(np.float32) / 32768.0
