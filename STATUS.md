# Status: on hold (12 oktober 2026)

Het project staat bewust stil. Dit bestand onthoudt waar we waren, zodat we later meteen verder kunnen.

## Wat werkt (getest op de MacBook Air M1, 16 GB)
- "Hey Jarvis" via spraak, Nederlands en Engels
- Router (bv. het uur) zonder taalmodel; open vragen via Ollama met tools
- Geheugen na herstart ("welke auto heb ik?" → Suzuki Vitara), tekstmodus, testpagina

## Waarom het stilstaat
Gemeten met `qwen3.5:9b` + `whisper-large-v3-turbo`:
- Geheugen: JARVIS 2,8 GB + Ollama 10,5 GB = 13,3 GB totaal, nog maar 3,7 GB vrij → te zwaar voor de laptop
- Snelheid: ~12 s van "uitgesproken" tot het eerste geluid (Whisper 2,9 s, taalmodel 5-10 s tot het eerste woord)
- De stem (Piper) klinkt vlak

## Al aangepast, maar nog NIET gemeten
- Standaardmodel nu `qwen3:8b` (~5,2 GB)
- Opwarmen met dezelfde opties als echte vragen (vroeger herlaadde Ollama het model bij de eerste vraag)
- Vaste system prompt, zodat Ollama systeemtekst + tools kan hergebruiken
- Overzicht bij afsluiten (Ctrl-C) toont latency, geheugen en het GPU-aandeel van het model

## Opties om later verder te gaan
- **A (aanrader):** installeren op de Mac mini M1 (16 GB, enkel voor JARVIS), dan meten met `qwen3:8b`
- **B:** lichte versie op de laptop: `qwen3:4b` + `whisper-small`, ~5 GB werkgeheugen, wel minder slim
- Daarna: Whisper-grootte kiezen met `scripts/bench_stt.py`, en een natuurlijkere stem (zie ROADMAP)

## Opnieuw starten
Volg "Installatie" in de README (`./scripts/setup.sh` en `ollama pull qwen3:8b`), start een sessie, druk op
Ctrl-C en bekijk het overzicht. Fase 1 is pas af als de latency en het geheugen goed zijn.
