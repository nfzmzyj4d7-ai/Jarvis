# JARVIS roadmap

Alles blijft lokaal, gratis en zonder accounts. Nieuwe functies komen als **tools** (één bestand in
`jarvis/tools/`) of als **module** die op de event-bus/WebSocket aanhaakt. De kern hoeft daarvoor niet om.

## Fase 1: spraakassistent (deze versie)
- [x] Wake word "Hey Jarvis", opname met VAD, Whisper (NL/EN), Piper-stemmen NL (Vlaams) + EN
- [x] Intent-router zonder taalmodel: tijd, datum, timer, timer annuleren, stop/stil
- [x] Ollama met tool calling + plugin-systeem (tijd, datum, timer, onthoud, wat weet je)
- [x] SQLite-geheugen, JARVIS-persona, tekstmodus, WebSocket-statusserver + testpagina, latency-logging

## Volgende stap (voorstel): een natuurlijkere stem
- Piper is snel en licht, maar klinkt vlak. Kandidaat: **Chatterbox Multilingual** (MIT-licentie, 23 talen
  waaronder Nederlands) via **mlx-audio** op Apple Silicon.
- Eerst meten op de M1: snelheid (eerste geluid moet kort blijven), extra geheugen (~2-3 GB bovenop ~10 GB),
  en Vlaamse uitspraak. Piper blijft de snelle terugvaloptie (instelbaar in `tts`).

## Fase 2: HUD-webinterface
- HUD (ontwerp in Claude Design) op de bestaande WebSocket-eventstream (`ws://…:8765/ws`)
- Commando's ook vanuit de HUD sturen (berichten van client naar server)

## Fase 3: agenda en herinneringen
- Lokale agenda (CalDAV/ICS, gratis) als tool
- Herinneringen op tijdstip, blijvend opgeslagen in SQLite (overleven een herstart)

## Fase 4: bedrijfsdata
- Tools die je eigen bedrijfsgegevens lokaal raadplegen (alleen-lezen eerst)

## Fase 5: verhuis naar de Mac mini (24/7)
- Autostart via launchd, logrotatie, health-check
- Ander config-bestand via `JARVIS_CONFIG`; USB-microfoon/speaker via `audio.*_device`

## Fase 6: bellen en sms via een 4G-module
- Module voor een USB/serieel 4G-modem (AT-commando's), tools "bel", "stuur sms", "lees sms"

## Fase 7: projector met handgebaren
- Lokale handtracking (bv. MediaPipe) als invoermodule die events op de bus zet

## Fase 8: Home Assistant
- Tool die de lokale Home Assistant REST/WebSocket API aanspreekt (lampen, scènes, sensoren)
