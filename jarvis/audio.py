"""Microfoon-invoer, apparaatlijst en eenvoudige tonen (bevestiging/alarm)."""

from __future__ import annotations

import logging
import queue

import numpy as np

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
FRAME = 1280            # 80 ms @ 16 kHz: wat openWakeWord verwacht


class Microphone:
    """Opent de standaard (of gekozen) microfoon. macOS vraagt hier de eerste keer om toestemming."""

    def __init__(self, device=None):
        self.device = device
        self._q: queue.Queue = queue.Queue(maxsize=500)
        self._stream = None

    def __enter__(self):
        import sounddevice as sd
        self._stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=FRAME,
                                      device=self.device, callback=self._callback)
        self._stream.start()
        return self

    def __exit__(self, *exc):
        self._stream.stop()
        self._stream.close()

    def _callback(self, indata, frames, time_info, status):
        if status:
            log.debug("Mic-status: %s", status)
        try:
            self._q.put_nowait(indata[:, 0].copy())
        except queue.Full:
            pass

    def frames(self):
        while True:
            yield self._q.get()


def list_devices() -> str:
    import sounddevice as sd
    return str(sd.query_devices())


def tone(freqs: list[float], seconds: float, sr: int, volume: float = 0.25) -> np.ndarray:
    """Zachte toonreeks (int16) met korte fade in/uit tegen klikjes."""
    n = int(sr * seconds / len(freqs))
    t = np.arange(n) / sr
    fade = np.minimum(1, np.minimum(t, t[::-1]) / 0.01)
    wave = np.concatenate([np.sin(2 * np.pi * f * t) * fade for f in freqs])
    return (wave * volume * 32767).astype(np.int16)
