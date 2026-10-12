"""Wake word, VAD en de volledige spraakpipeline met een nep-microfoon die gesynthetiseerde spraak 'hoort'.

Gebruikt de echte openWakeWord-/Silero-modellen en echte Piper-stemmen. Stemmen: die uit config.yaml (als
ze gedownload zijn), of een map via JARVIS_TEST_VOICES met daarin <iets>en<iets>.onnx en <iets>nl<iets>.onnx.
Whisper wordt hier vervangen door een stub (mlx draait enkel op Apple Silicon).
"""

import os
import threading
import time
from pathlib import Path

import numpy as np
import pytest
import yaml

from conftest import ROOT

MODELS = ROOT / "models" / "openwakeword"
pytestmark = pytest.mark.skipif(not (MODELS / "hey_jarvis_v0.1.onnx").exists(),
                                reason="openWakeWord-modellen niet gedownload (scripts/download_models.py)")


def _voices() -> dict:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    voices = {k: ROOT / v for k, v in cfg["tts"]["voices"].items()}
    if all(p.exists() for p in voices.values()):
        return voices
    d = os.environ.get("JARVIS_TEST_VOICES")
    if d:
        found = {lang: next(iter(sorted(Path(d).rglob(f"*{lang}*.onnx"))), None) for lang in ("en", "nl")}
        if all(found.values()):
            return found
    pytest.skip("Geen Piper-stemmen beschikbaar")


@pytest.fixture(scope="module")
def voices():
    from piper import PiperVoice
    return {lang: PiperVoice.load(str(p)) for lang, p in _voices().items()}


def speech(voices, lang, text) -> np.ndarray:
    """Synthetiseer en resample naar 16 kHz int16 (zoals de microfoon het zou aanleveren)."""
    from scipy.signal import resample_poly
    chunks = list(voices[lang].synthesize(text))
    audio = np.concatenate([c.audio_int16_array for c in chunks]).astype(np.float32)
    sr = chunks[0].sample_rate
    if sr != 16000:
        audio = resample_poly(audio, 16000, sr)
    return (audio * 0.7).astype(np.int16)


def silence(seconds) -> np.ndarray:
    rng = np.random.default_rng(0)
    return (rng.normal(0, 30, int(16000 * seconds))).astype(np.int16)   # licht ruisje, geen digitale stilte


def frames(audio):
    for i in range(0, len(audio) - 1279, 1280):
        yield audio[i:i + 1280]


@pytest.fixture
def cfg(make_config, tmp_path):
    from jarvis.config import load_config
    path = make_config()
    data = yaml.safe_load(path.read_text())
    data["tts"]["voices"] = {k: str(v) for k, v in _voices().items()}
    path.write_text(yaml.safe_dump(data))
    return load_config(path)


def test_wakeword_only_on_hey_jarvis(cfg, voices):
    """Piper klinkt elke keer iets anders, dus elke zin wordt meerdere keren gesynthetiseerd."""
    from jarvis.wakeword import WakeWord
    ww = WakeWord(cfg)

    def detected(lang, text):
        ww.reset()
        audio = np.concatenate([silence(1), speech(voices, lang, text), silence(1)])
        return any(ww.detect(f)[0] for f in frames(audio))

    cases = [("en", "Hey Jarvis", True), ("en", "Hey Jarvis, what time is it?", True),
             ("en", "Hey Siri, what time is it?", False), ("en", "Hey Travis", False),
             ("en", "Harvest is coming", False), ("en", "Hey Marvin", False),
             ("nl", "Hoe laat is het?", False), ("nl", "Wat weet je over mijn auto?", False)]
    hits = {text: sum(detected(lang, text) for _ in range(6)) for lang, text, _ in cases}
    print(hits)
    for lang, text, expected in cases:
        assert hits[text] == (6 if expected else 0), (text, hits[text])


def test_vad_recorder_detects_end_of_speech(cfg, voices):
    from jarvis.listen import UtteranceRecorder
    rec = UtteranceRecorder(cfg)
    utterance = speech(voices, "nl", "Wat is de hoofdstad van Frankrijk?")
    audio = np.concatenate([silence(0.5), utterance, silence(3)])
    rec.start()
    result, n = None, 0
    for f in frames(audio):
        n += 1
        result = rec.feed(f)
        if result:
            break
    assert result == "done"
    ended_at = n * 0.08
    speech_end = 0.5 + len(utterance) / 16000
    assert speech_end < ended_at < speech_end + 1.5          # ~silence_ms na het einde van de zin
    recorded = len(rec.audio()) / 16000
    assert len(utterance) / 16000 - 0.3 < recorded < len(utterance) / 16000 + 1.0

    rec.start()                                             # alleen stilte -> no_speech
    outcome = [rec.feed(f) for f in frames(silence(7))]
    assert "no_speech" in outcome and "done" not in outcome


class StubSTT:
    def __init__(self, text, lang):
        self.result, self.calls = (text, lang), []

    def transcribe(self, audio):
        self.calls.append(len(audio) / 16000)
        time.sleep(0.05)
        return self.result


def run_pipeline(cfg, mic_audio, stt, monkeypatch, max_wait=30):
    """Draait de echte VoicePipeline; de microfoon speelt mic_audio af en daarna stilte tot alles klaar is."""
    import jarvis.pipeline as pl
    from jarvis.assistant import Assistant
    from jarvis.events import EventBus
    from jarvis.latency import LatencyLog
    from jarvis.llm import OllamaLLM
    from jarvis.memory import Memory
    from jarvis.timers import TimerManager
    from jarvis.tools import load_tools
    from jarvis.tts import Speaker

    bus, events = EventBus(), []
    bus.subscribe(events.append)
    finished = threading.Event()
    bus.subscribe(lambda e: e["type"] in ("latency",) and finished.set())

    played = []

    def fake_play(self, audio, sr, gen, on_start):            # geen geluidskaart in de testomgeving
        if on_start:
            on_start()
        played.append(len(audio) / sr)
        time.sleep(len(audio) / sr / 10)

    monkeypatch.setattr(Speaker, "_play", fake_play)

    class FakeMic:
        def __init__(self, device=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def frames(self):
            for f in frames(mic_audio):
                time.sleep(0.004)
                yield f
            deadline = time.time() + max_wait
            while not finished.is_set() and time.time() < deadline:
                time.sleep(0.02)
                yield silence(0.08)
            time.sleep(0.3)

    monkeypatch.setattr(pl, "Microphone", FakeMic)
    speaker = Speaker(cfg)
    speaker.load()
    memory = Memory(cfg.path("paths.database"))
    assistant = Assistant(cfg, bus, memory, OllamaLLM(cfg), load_tools(), TimerManager(), speaker)
    pipeline = pl.VoicePipeline(cfg, bus, assistant, speaker, stt, LatencyLog(cfg.path("paths.log_dir")))
    pipeline.run()
    return events, played


def test_full_voice_pipeline_router(cfg, voices, monkeypatch):
    question = speech(voices, "en", "What time is it?")
    mic = np.concatenate([silence(1), speech(voices, "en", "Hey Jarvis"), silence(0.4), question, silence(2)])
    stt = StubSTT("What time is it?", "en")
    events, played = run_pipeline(cfg, mic, stt, monkeypatch)

    kinds = [e["type"] if e["type"] != "status" else e["state"] for e in events]
    print(kinds)
    assert kinds.index("wake") < kinds.index("listening") < kinds.index("thinking") \
        < kinds.index("transcript") < kinds.index("speaking")
    assert kinds[-2:] == ["latency", "idle"] or kinds[-1] == "idle"
    response = next(e for e in events if e["type"] == "response")
    assert response["route"] == "router" and response["lang"] == "en" and response["text"].startswith("It's")
    assert len(stt.calls) == 1 and abs(stt.calls[0] - len(question) / 16000) < 1.2   # de opgenomen vraag
    latency = next(e for e in events if e["type"] == "latency")
    assert {"stt", "decide", "speech_end_to_audio", "wake_to_audio"} <= set(latency) and latency["route"] == "router"
    assert len(played) == 2                                   # bevestigingstoon + antwoord


def test_no_wake_word_no_reaction(cfg, voices, monkeypatch):
    mic = np.concatenate([silence(1), speech(voices, "en", "Hey Siri, what time is it?"), silence(1),
                          speech(voices, "nl", "Hoe laat is het?"), silence(1)])
    stt = StubSTT("What time is it?", "en")
    events, played = run_pipeline(cfg, mic, stt, monkeypatch, max_wait=0.5)
    assert not [e for e in events if e["type"] in ("wake", "transcript", "response")]
    assert stt.calls == [] and played == []
