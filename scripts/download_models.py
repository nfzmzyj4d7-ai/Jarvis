"""Download alle modellen die in config.yaml staan (alles gratis, geen account nodig).

  - openWakeWord: hey_jarvis + feature-modellen + Silero VAD   (~5 MB, GitHub)
  - Piper-stemmen (NL + EN)                                     (~60 MB per stem, HuggingFace)
  - Whisper-model voor mlx-whisper                              (~1,6 GB voor large-v3-turbo, HuggingFace)

Het taalmodel haal je apart op met:  ollama pull <model uit config.yaml>

Gebruik:  python scripts/download_models.py [--config pad] [--skip-whisper]
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jarvis.config import load_config  # noqa: E402

OWW_RELEASE = "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/"


def mb(path: Path) -> str:
    return f"{path.stat().st_size / 1e6:.1f} MB"


def download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.rename(target)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--skip-whisper", action="store_true")
    args = ap.parse_args()
    cfg = load_config(args.config)

    print("== openWakeWord + VAD")
    for key in ("wakeword.model", "wakeword.melspec_model", "wakeword.embedding_model", "vad.model"):
        path = cfg.path(key)
        if not path.exists():
            download(OWW_RELEASE + path.name, path)
        print(f"  ok  {path.name} ({mb(path)})")

    print("== Piper-stemmen")
    from piper.download_voices import download_voice
    failed = False
    for lang, rel in cfg.get("tts.voices").items():
        path = cfg.resolve(rel)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                download_voice(path.stem, path.parent)   # naam = bestandsnaam, bv. nl_BE-nathalie-medium
            except Exception as e:
                print(f"  FOUT [{lang}] {path.stem}: {e}")
                failed = True
                continue
        print(f"  ok  [{lang}] {path.name} ({mb(path)})")

    if not args.skip_whisper:
        print("== Whisper (mlx)")
        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            print("  overgeslagen: mlx-whisper is niet geïnstalleerd (enkel op Apple Silicon)")
        else:
            repo = cfg.get("stt.model")
            local = Path(snapshot_download(repo_id=repo))
            size = sum(p.stat().st_size for p in local.rglob("*") if p.is_file()) / 1e9
            print(f"  ok  {repo} ({size:.2f} GB, in de HuggingFace-cache)")

    if failed:
        print("\nNiet alles kon gedownload worden (zie FOUT hierboven).")
        return 1
    print(f"\nKlaar. Taalmodel: ollama pull {cfg.get('llm.model')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
