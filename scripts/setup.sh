#!/usr/bin/env bash
# Installeert JARVIS in deze projectmap: virtualenv + Python-pakketten + modellen.
# Raakt niets buiten de projectmap aan (behalve de HuggingFace-cache voor Whisper in ~/.cache).
set -euo pipefail
cd "$(dirname "$0")/.."

if command -v uv >/dev/null 2>&1; then
  echo "== virtualenv via uv (Python 3.12)"
  [ -d .venv ] || uv venv --python 3.12 .venv
  uv pip install --python .venv/bin/python -r requirements-dev.txt
else
  PY="${PYTHON:-python3.12}"
  command -v "$PY" >/dev/null 2>&1 || { echo "Python 3.12 niet gevonden. Zie README (Homebrew of uv)."; exit 1; }
  echo "== virtualenv via $PY"
  [ -d .venv ] || "$PY" -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements-dev.txt
fi

echo "== modellen"
.venv/bin/python scripts/download_models.py

MODEL="$(.venv/bin/python -c 'from jarvis.config import load_config; print(load_config().get("llm.model"))')"
if command -v ollama >/dev/null 2>&1; then
  echo "== Ollama gevonden. Taalmodel ophalen (eenmalig): ollama pull $MODEL"
else
  echo "== Ollama niet gevonden: installeer Ollama (zie README) en daarna: ollama pull $MODEL"
fi
echo "Klaar. Start met: .venv/bin/python -m jarvis   (of --text voor tekstmodus)"
