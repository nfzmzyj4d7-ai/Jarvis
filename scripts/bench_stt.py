"""Meet Whisper-modellen op JOUW stem: snelheid vs. nauwkeurigheid (vooral Nederlands).

  1. Opnemen (eenmalig):  python scripts/bench_stt.py --record
     Je leest telkens een zin voor; opname stopt vanzelf als je zwijgt (VAD).
  2. Meten:               python scripts/bench_stt.py
     -> tabel met gemiddelde tijd, real-time-factor, WER per taal en taalherkenning per model.
     Zet daarna de winnaar in config.yaml onder stt.model.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from jarvis.config import load_config  # noqa: E402

BENCH_DIR = ROOT / "data" / "bench"
SENTENCES = [
    ("nl", "Hoe laat is het?"),
    ("nl", "Zet een timer van vijf minuten."),
    ("nl", "Onthoud dat mijn auto een Suzuki Vitara is."),
    ("nl", "Welke auto heb ik?"),
    ("nl", "Wat is het verschil tussen een appel en een peer?"),
    ("nl", "Morgen moet ik om half negen in Hasselt zijn voor een afspraak met de garage."),
    ("en", "What time is it?"),
    ("en", "Set a timer for ten minutes."),
    ("en", "What is the capital of Australia?"),
    ("en", "Tell me what you know about my car."),
]
MODELS = [
    "mlx-community/whisper-small-mlx",
    "mlx-community/whisper-medium-mlx",
    "mlx-community/whisper-large-v3-turbo",
    "mlx-community/whisper-large-v3-mlx",
]


def words(text: str) -> list[str]:
    return re.sub(r"[^\w\s']", " ", text.lower()).split()


def wer(ref: str, hyp: str) -> float:
    r, h = words(ref), words(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(h)] / max(1, len(r))


def record(cfg) -> None:
    from jarvis.audio import Microphone
    from jarvis.listen import UtteranceRecorder
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    rec = UtteranceRecorder(cfg)
    rec.ignore_ms = 0
    meta = []
    print("macOS vraagt mogelijk om microfoontoegang: klik 'Sta toe'.")
    with Microphone(cfg.get("audio.input_device", None)) as mic:
        for i, (lang, text) in enumerate(SENTENCES):
            input(f"\n[{i + 1}/{len(SENTENCES)}] Druk Enter en zeg: \"{text}\"")
            rec.start()
            for frame in mic.frames():
                result = rec.feed(frame)
                if result:
                    break
            if result != "done":
                print("  niets gehoord, overgeslagen")
                continue
            audio = (rec.audio() * 32767).astype(np.int16)
            path = BENCH_DIR / f"{i:02d}_{lang}.wav"
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000), w.writeframes(audio.tobytes())
            meta.append({"file": path.name, "lang": lang, "text": text})
            print(f"  opgeslagen ({len(audio) / 16000:.1f}s)")
    (BENCH_DIR / "sentences.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0


def bench(cfg, models: list[str]) -> None:
    from jarvis.stt import Transcriber
    meta = json.loads((BENCH_DIR / "sentences.json").read_text(encoding="utf-8"))
    clips = [(m, load_wav(BENCH_DIR / m["file"])) for m in meta]
    rows = []
    for model in models:
        cfg.data["stt"]["model"] = model
        stt = Transcriber(cfg)
        try:
            t0 = time.perf_counter()
            stt.warmup()
            load_s = time.perf_counter() - t0
        except Exception as e:
            print(f"{model}: overgeslagen ({e})")
            continue
        times, audio_s, errs, lang_ok = [], 0.0, {"nl": [], "en": []}, 0
        for m, audio in clips:
            t0 = time.perf_counter()
            text, lang = stt.transcribe(audio)
            times.append(time.perf_counter() - t0)
            audio_s += len(audio) / 16000
            errs[m["lang"]].append(wer(m["text"], text))
            lang_ok += lang == m["lang"]
            print(f"  {model.split('/')[-1]:28} {times[-1]:.2f}s [{lang}] {text}")
        rows.append((model, load_s, float(np.mean(times)), sum(times) / audio_s,
                     float(np.mean(errs["nl"] or [0])), float(np.mean(errs["en"] or [0])), lang_ok, len(clips)))

    lines = ["| model | laadtijd | gem. tijd/zin | RTF | WER nl | WER en | taal juist |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {m} | {l:.1f}s | {t:.2f}s | {r:.2f} | {wn:.0%} | {we:.0%} | {ok}/{n} |"
              for m, l, t, r, wn, we, ok, n in rows]
    table = "\n".join(lines)
    (BENCH_DIR / "stt_results.md").write_text(table + "\n", encoding="utf-8")
    print("\n" + table + f"\n\nOpgeslagen in {BENCH_DIR / 'stt_results.md'}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--config")
    ap.add_argument("--models", nargs="*", default=MODELS)
    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.record:
        record(cfg)
    else:
        bench(cfg, args.models)
    return 0


if __name__ == "__main__":
    sys.exit(main())
