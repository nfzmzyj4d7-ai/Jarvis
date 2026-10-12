"""Spraak naar tekst met mlx-whisper (meertalig Whisper op de Apple-Silicon-GPU)."""

from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger(__name__)

# Klassieke Whisper-hallucinaties op stilte/ruis (vooral in het Nederlands).
_HALLUCINATIONS = (
    "ondertiteling", "ondertiteld door", "ondertitels ingediend", "bedankt voor het kijken",
    "bedankt voor het luisteren", "thanks for watching", "thank you for watching", "subtitles by",
    "amara.org", "tv gelderland", "abonneer", "like en abonneer",
)


class Transcriber:
    def __init__(self, cfg):
        self.model = cfg.get("stt.model")
        self.allowed = list(cfg.get("languages.supported", ["nl", "en"]))
        self.fallback = cfg.get("stt.fallback_language", "nl")

    def _run(self, audio: np.ndarray, language: str | None) -> dict:
        try:
            import mlx_whisper
        except ImportError:
            raise RuntimeError("mlx-whisper is niet geïnstalleerd (vereist een Mac met Apple Silicon). "
                               "Zonder microfoon testen kan met: python -m jarvis --text")
        return mlx_whisper.transcribe(audio, path_or_hf_repo=self.model, language=language,
                                      condition_on_previous_text=False, verbose=None)

    def warmup(self) -> None:
        """Laadt het model (eerste keer: download van ~1,6 GB naar de HuggingFace-cache)."""
        self._run(np.zeros(16000, np.float32), "nl")

    def transcribe(self, audio: np.ndarray) -> tuple[str, str]:
        """Geeft (tekst, taal) terug; taal is altijd een van languages.supported."""
        result = self._run(audio, None)
        lang = result.get("language")
        if lang not in self.allowed:
            # Vlaams wordt soms als Afrikaans/Duits herkend: kies dan tussen nl en en, en transcribeer opnieuw.
            guess = self._best_allowed_language(audio)
            log.info("Whisper hoorde '%s', opnieuw als '%s'", lang, guess)
            lang = guess
            result = self._run(audio, lang)
        text = (result.get("text") or "").strip()
        if any(h in text.lower() for h in _HALLUCINATIONS):
            log.info("Whisper-hallucinatie genegeerd: %r", text)
            text = ""
        return text, lang

    def _best_allowed_language(self, audio: np.ndarray) -> str:
        """Taaldetectie beperkt tot de toegelaten talen (zelfde stappen als mlx_whisper.transcribe)."""
        try:
            import mlx.core as mx
            from mlx_whisper.audio import N_FRAMES, N_SAMPLES, log_mel_spectrogram, pad_or_trim
            from mlx_whisper.transcribe import ModelHolder

            model = ModelHolder.get_model(self.model, mx.float16)
            mel = log_mel_spectrogram(audio, n_mels=model.dims.n_mels, padding=N_SAMPLES)
            segment = pad_or_trim(mel, N_FRAMES, axis=-2).astype(mx.float16)
            _, probs = model.detect_language(segment)
            return max(self.allowed, key=lambda code: probs.get(code, 0.0))
        except Exception:
            log.exception("Beperkte taaldetectie faalde, val terug op %s", self.fallback)
            return self.fallback
