"""Wake word 'Hey Jarvis' met het voorgetrainde openWakeWord-model (ONNX, volledig lokaal)."""

from __future__ import annotations

import numpy as np


class WakeWord:
    def __init__(self, cfg):
        from openwakeword.model import Model

        paths = {k: cfg.path(f"wakeword.{k}") for k in ("model", "melspec_model", "embedding_model")}
        for p in paths.values():
            if not p.exists():
                raise FileNotFoundError(f"Wake-word-model ontbreekt: {p}. Draai: python scripts/download_models.py")
        self.model = Model(wakeword_models=[str(paths["model"])], inference_framework="onnx",
                           melspec_model_path=str(paths["melspec_model"]),
                           embedding_model_path=str(paths["embedding_model"]))
        self.name = next(iter(self.model.models))
        self.threshold = float(cfg.get("wakeword.threshold", 0.5))
        # Aantal frames (80 ms) na elkaar boven de drempel. Gemeten: 'Hey Jarvis' 6-9 frames,
        # gelijkende woorden zoals 'Hey Travis' hooguit 3.
        self.patience = int(cfg.get("wakeword.patience_frames", 4))
        self._run = 0

    def score(self, frame: np.ndarray) -> float:
        """Score 0..1 voor een frame van 80 ms (1280 samples int16 @ 16 kHz)."""
        return float(self.model.predict(frame)[self.name])

    def detect(self, frame: np.ndarray) -> tuple[bool, float]:
        score = self.score(frame)
        self._run = self._run + 1 if score >= self.threshold else 0
        return self._run >= self.patience, score

    def reset(self) -> None:
        self.model.reset()
        self._run = 0
