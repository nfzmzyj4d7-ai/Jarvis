# JARVIS (fase 1)

Persoonlijke spraakassistent, **volledig lokaal en gratis**: geen cloud-AI, geen API-sleutels, geen accounts.
Verstaat Nederlands en Engels en antwoordt in de taal waarin je spreekt.

```
"Hey Jarvis" ─► opname met VAD ─► Whisper (nl/en) ─► router ──(simpel)──► tool ─────────┐
 openWakeWord     Silero            mlx-whisper        │                                  ├─► Piper ─► speaker
                                                       └─(rest)─► Ollama + tool calling ──┘  (nl_BE / en_GB)
                     alle events ─► WebSocket-server ─► testpagina (later: de HUD)
```

## Gekozen onderdelen en geheugen

| Onderdeel | Keuze | Geschat RAM |
|---|---|---|
| Taalmodel | Ollama + `qwen3:8b` (Q4_K_M, tools), thinking uit, context 8k | ~5,2 GB + context |
| Spraak → tekst | `mlx-whisper` + `whisper-large-v3-turbo` (meertalig) | ~1,6 GB |
| Tekst → spraak | Piper: `nl_BE-nathalie-medium` (Vlaams), `en_GB-alan-medium` | ~0,2 GB |
| Wake word | openWakeWord, voorgetraind `hey_jarvis` | <0,1 GB |
| Spraakdetectie | Silero VAD (ONNX) | <0,05 GB |
| Geheugen | SQLite (`data/jarvis.db`) | - |

Gemeten op de MacBook Air M1 met het eerder gekozen `qwen3.5:9b`: JARVIS 2,8 GB + Ollama 10,5 GB = 13,3 GB,
met nog maar 3,7 GB vrij en ~12 s tot het eerste woord. Te krap, daarom is `qwen3:8b` nu de standaard.
Echt gemeten waarden toont JARVIS zelf wanneer je hem afsluit (inclusief welk deel van het model op de GPU draait).

## Installatie (MacBook Air M1 / Mac mini M1)

Systeembrede stappen (1 en 2) vragen jouw akkoord; de rest blijft in deze projectmap.

1. **Python 3.12**, één van beide:
   - Homebrew: `brew install python@3.12`
   - of uv (installeert in je thuismap): `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. **Ollama**: `brew install ollama` en daarna `brew services start ollama` (of `ollama serve` in een apart
   venster). De app van ollama.com kan ook. **Log niet in**: zonder account draait alles lokaal, en de
   cloud-modellen gebruik je niet.
3. **JARVIS en modellen** (venv, pakketten, wake word, VAD, Piper-stemmen, Whisper ~1,6 GB):
   ```bash
   ./scripts/setup.sh
   ```
4. **Taalmodel** (eenmalig, ~5,2 GB). Een ander model kies je met `llm.model` in config.yaml.
   ```bash
   ollama pull qwen3:8b
   ```

> Kopieer enkel de regels in de grijze blokken. De standaardshell op de Mac (zsh) ziet `#` niet als
> commentaar, daarom staat er geen uitleg in de blokken zelf.

## Starten

Eerst `source .venv/bin/activate`, daarna één van:

| Commando | Wat |
|---|---|
| `python -m jarvis` | spraakmodus: zeg "Hey Jarvis" |
| `python -m jarvis --text` | tekstmodus: typen, geen microfoon nodig |
| `python -m jarvis --text --speak` | tekstmodus, maar met gesproken antwoorden |
| `python -m jarvis --list-devices` | audio-apparaten (voor `audio.input_device` / `output_device`) |

- **Microfoontoegang:** bij de eerste start in spraakmodus vraagt macOS of Terminal (of iTerm/VS Code)
  de microfoon mag gebruiken. Klik **Sta toe**. Heb je per ongeluk geweigerd, zet het dan terug aan via
  Systeeminstellingen → Privacy en beveiliging → Microfoon.
- **Testpagina:** open <http://127.0.0.1:8765/> in je browser. Je ziet live de status
  (idle / listening / thinking / speaking), het transcript, het antwoord, tool calls en de latency per vraag.
  De eventstream zelf staat op `ws://127.0.0.1:8765/ws`.
- Na "Hey Jarvis" hoor je een korte toon: dan luistert hij. Zeg "Hey Jarvis" terwijl hij praat om hem te
  onderbreken. "Stop" of "stil" maakt hem stil.

### Wat gaat via de router (zonder taalmodel, in milliseconden)
- Tijd: "Hoe laat is het?", "Hoeveel uur is het?", "What time is it?"
- Datum: "Welke datum is het?", "De hoeveelste zijn we?", "What's the date?"
- Timer: "Zet een timer van 5 minuten", "Timer van een kwartier", "Set a timer for 10 minutes"
- Timer annuleren: "Annuleer de timer", "Cancel the timer"
- Stil: "Stop", "Stil", "Hou op", "Be quiet"

Al de rest gaat naar het taalmodel, dat zelf tools kan aanroepen, bv. "Onthoud dat mijn auto een Suzuki
Vitara is" → tool `remember`. Onthouden feiten staan in SQLite en blijven na een herstart bewaard.

## Configuratie (`config.yaml`)

Alles wat aan het toestel gebonden is, staat in één bestand. Relatieve paden zijn relatief t.o.v. dat bestand.
Een ander bestand gebruiken: `JARVIS_CONFIG=/pad/config.yaml python -m jarvis` of `--config`.

| Sectie | Wat |
|---|---|
| `user` | naam en tijdzone |
| `languages` | ondersteunde talen en de standaardtaal |
| `paths` | database en logmap |
| `llm` | Ollama-adres, model, thinking, keep_alive, temperatuur, contextgrootte, geschiedenis |
| `stt` | Whisper-model (HuggingFace-repo van mlx-community) en terugvaltaal |
| `tts` | Piper-stem per taal, spreeksnelheid, volume |
| `wakeword` | modelbestanden, `threshold` en `patience_frames` (gevoeligheid), cooldown |
| `vad` | spraakdrempel, hoe lang stilte = "uitgesproken", maximale wachttijd en zinslengte |
| `audio` | in- en uitvoerapparaat, bevestigingstoon, onderbreken tijdens praten |
| `memory` | hoeveel feiten het taalmodel altijd meekrijgt |
| `tools.disabled` | tools uitschakelen zonder code te wijzigen |
| `server` | host/poort van de WebSocket-server (`0.0.0.0` = bereikbaar vanuit je netwerk) |

Reageert hij te snel op gelijkende woorden, verhoog dan `wakeword.threshold` of `patience_frames`.
Mist hij jouw "Hey Jarvis", verlaag ze dan. Gemeten met synthetische spraak (40 keer per zin): "Hey Jarvis"
wordt altijd herkend (8 à 9 frames boven de drempel). Het bijna-rijm "Hey Travis" geeft bij `patience_frames: 4`
ongeveer 1 op 10 keer een valse activatie, bij 6 ongeveer 1 op 40.

## Een tool toevoegen

Maak één bestand in `jarvis/tools/`. Het wordt automatisch geladen en aan het taalmodel aangeboden:

```python
# jarvis/tools/dobbelsteen.py
import random
from jarvis.tools import tool

@tool(name="roll_die", description="Gooi een dobbelsteen. / Roll a die.")
def roll_die(ctx, **_):
    n = random.randint(1, 6)
    return ctx.say(f"Je gooide {n}.", f"You rolled {n}.")
```

`ctx` geeft toegang tot de taal (`ctx.lang`), het geheugen, de timers, de config en de tijd.

## Testen

pytest zit al in `setup.sh`:

```bash
python -m pytest -q
```

De tests draaien zonder microfoon en zonder echt taalmodel: een nep-Ollama met hetzelfde API-formaat
controleert de router, tool calling, het geheugen na herstart, de tekstmodus, de WebSocket-server en de volledige
spraakpipeline. Die laatste gebruikt een nep-microfoon die met Piper gesynthetiseerde spraak afspeelt, en echte
openWakeWord- en Silero-modellen.

### Acceptatietest op de Mac (fase 1 is klaar als alles klopt)

| # | Test | Hoe |
|---|---|---|
| 1 | Wake word | `python -m jarvis`. Zeg "Hoe laat is het?" zonder wake word: geen reactie. Zeg daarna "Hey Jarvis": je hoort een toon en de status wordt `listening`. |
| 2 | Taal | "Hey Jarvis… wat is de hoofdstad van Frankrijk?" geeft een Nederlands antwoord; "Hey Jarvis… what is the capital of France?" een Engels. |
| 3 | Router | "Hey Jarvis… hoe laat is het?" toont in de log `Latency [voice/router]` en op de testpagina `route: router`. |
| 4 | Open vraag | "Hey Jarvis… vertel iets over de maan" toont `[voice/llm]`. |
| 5 | Geheugen | "Hey Jarvis… onthoud dat mijn auto een Suzuki Vitara is". Stop JARVIS (Ctrl-C), start opnieuw: "Hey Jarvis… welke auto heb ik?" |
| 6 | Tekstmodus | `python -m jarvis --text` en typ dezelfde vragen. |
| 7 | Testpagina | <http://127.0.0.1:8765/> toont de statussen live. |
| 8 | Latency en geheugen | Stop JARVIS met Ctrl-C (of typ `exit` in tekstmodus): hij toont de latencytabel van die sessie en het geheugengebruik, en bewaart ze in `data/logs/sessie-*.md`. |

### Whisper-grootte kiezen op jouw stem

Eenmalig 10 zinnen voorlezen (NL + EN):

```bash
python scripts/bench_stt.py --record
```

Daarna de tabel met snelheid, WER per taal en taalherkenning per model:

```bash
python scripts/bench_stt.py
```

Zet de winnaar in `stt.model`. Een MacBook Air heeft geen ventilator, dus meet een paar keer.

## Verhuizen naar de Mac mini

Kopieer de projectmap (zonder `.venv`), voer `./scripts/setup.sh` uit, `ollama pull` het model, en neem
`data/` mee als je gesprekken en feiten wil houden. Toestelverschillen (microfoon, speaker, host) regel
je in `config.yaml`.

## Problemen oplossen

- **"Taalmodel niet beschikbaar"**: draait Ollama (`ollama list`)? Is het model gedownload?
- **Hij hoort niets**: kijk of macOS microfoontoegang gaf, en controleer `audio.input_device`.
- **Hij hoort "Hey Jarvis" niet goed met je accent**: zet `wakeword.patience_frames: 2` of `threshold: 0.4`.
- **Te traag of te warm**: kies een kleiner Whisper-model (zie "Whisper-grootte kiezen"). Met `keep_alive: -1` blijft het model
  geladen, zodat er nooit een koude start is.
- **Logs**: `data/logs/jarvis.log`, latency per vraag in `data/logs/latency.jsonl`, sessie-overzichten in `data/logs/sessie-*.md`.

## Projectstructuur

```
config.yaml            alle instellingen
jarvis/
  __main__.py          start, tekstmodus
  pipeline.py          spraakmodus: wake → opname → STT → assistent → TTS
  assistant.py         router of taalmodel, geheugen, tools
  router.py            intent-router (regex, NL + EN)
  llm.py               Ollama-client (streaming + tool calling)
  persona.py           JARVIS system prompt
  tools/               plugins, één bestand per tool
  memory.py            SQLite
  stt.py tts.py        Whisper / Piper
  wakeword.py listen.py audio.py   wake word / VAD-opname / microfoon
  events.py ws_server.py           event-bus / WebSocket + testpagina
  latency.py report.py sysinfo.py  metingen + overzicht bij afsluiten
web/test.html          kale testpagina
scripts/               setup, modellen downloaden, STT-benchmark
tests/                 pytest (+ nep-Ollama)
```
