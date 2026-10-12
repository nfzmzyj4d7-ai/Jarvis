"""Start JARVIS.

  python -m jarvis                 spraakmodus ("Hey Jarvis")
  python -m jarvis --text          tekstmodus (typen in de terminal, geen microfoon nodig)
  python -m jarvis --text --speak  tekstmodus, maar antwoorden ook hardop
  python -m jarvis --list-devices  toon audio-apparaten
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from .config import PROJECT_ROOT, load_config
from .events import EventBus
from .latency import LatencyLog, Timings
from .llm import OllamaLLM
from .memory import Memory
from .sysinfo import footprint_mb
from .textfmt import detect_language
from .timers import TimerManager
from .tools import load_tools

log = logging.getLogger("jarvis")


def setup_logging(cfg) -> None:
    log_dir = cfg.path("paths.log_dir")
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S")
    root = logging.getLogger()
    root.setLevel(cfg.get("logging.level", "INFO"))
    for handler in (logging.StreamHandler(sys.stderr), logging.FileHandler(log_dir / "jarvis.log", encoding="utf-8")):
        handler.setFormatter(fmt)
        root.addHandler(handler)
    for noisy in ("httpx", "httpcore", "websockets"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def run_text(cfg, bus, assistant, speaker, latency) -> None:
    default_lang = cfg.get("languages.default", "nl")
    interactive = sys.stdin.isatty()
    print("JARVIS tekstmodus. Typ je vraag ('exit' of Ctrl-D om te stoppen).", flush=True)
    while True:
        try:
            text = input("jij> " if interactive else "").strip()
        except EOFError:
            break
        if not text:
            continue
        if text.lower() in ("exit", "quit"):
            break
        timings = Timings("text")
        timings.mark("transcribed")
        timings.text = text
        reply = assistant.handle(text, detect_language(text, default_lang), timings)
        if speaker:
            speaker.wait()
        row = latency.write(timings)
        bus.emit("latency", **{k: v for k, v in row.items() if k not in ("ts", "text")})
        bus.set_state("idle")
        print(f"jarvis [{reply.route}/{reply.lang}]> {reply.text or '(stil)'}", flush=True)


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except (FileNotFoundError, RuntimeError) as e:   # ontbrekend model, geen mlx, ...: geen traceback nodig
        log.error("%s", e)
        return 1


def _main(argv: list[str] | None) -> int:
    ap = argparse.ArgumentParser(prog="jarvis", description="JARVIS - lokale spraakassistent")
    ap.add_argument("--text", action="store_true", help="tekstmodus (geen microfoon)")
    ap.add_argument("--speak", action="store_true", help="in tekstmodus ook hardop antwoorden")
    ap.add_argument("--config", help="pad naar config.yaml (of zet JARVIS_CONFIG)")
    ap.add_argument("--list-devices", action="store_true", help="toon audio-apparaten en stop")
    ap.add_argument("--no-server", action="store_true", help="start de WebSocket-server niet")
    args = ap.parse_args(argv)

    if args.list_devices:
        from .audio import list_devices
        print(list_devices())
        return 0

    cfg = load_config(args.config)
    setup_logging(cfg)
    t_start = time.perf_counter()
    session_start = time.time()
    bus = EventBus()

    if cfg.get("server.enabled", True) and not args.no_server:
        from .ws_server import StatusServer
        StatusServer(bus, cfg.get("server.host"), cfg.get("server.port"), PROJECT_ROOT / "web" / "test.html").start()

    memory = Memory(cfg.path("paths.database"))
    tools = load_tools(cfg.get("tools.disabled", []) or [])
    log.info("Tools: %s", ", ".join(sorted(tools)))
    llm = OllamaLLM(cfg)
    timers = TimerManager()
    latency = LatencyLog(cfg.path("paths.log_dir"))

    speaker = None
    if not args.text or args.speak:
        from .tts import Speaker
        speaker = Speaker(cfg)
        speaker.load()

    from .assistant import Assistant
    assistant = Assistant(cfg, bus, memory, llm, tools, timers, speaker)
    timers.on_fire = assistant.timer_fired

    try:
        t0 = time.perf_counter()
        llm.check()
        llm.warmup()
        log.info("Taalmodel %s geladen in %.1fs", llm.model, time.perf_counter() - t0)
    except Exception as e:  # bv. Ollama niet gestart of model nog niet gedownload
        log.warning("Taalmodel niet beschikbaar (de router werkt wel): %s", e)

    try:
        if args.text:
            log.info("Opgestart in %.1fs, geheugen JARVIS-proces: %.0f MB",
                     time.perf_counter() - t_start, footprint_mb())
            run_text(cfg, bus, assistant, speaker, latency)
        else:
            from .pipeline import VoicePipeline
            from .stt import Transcriber
            stt = Transcriber(cfg)
            t0 = time.perf_counter()
            stt.warmup()
            log.info("Whisper %s geladen in %.1fs", stt.model, time.perf_counter() - t0)
            pipeline = VoicePipeline(cfg, bus, assistant, speaker, stt, latency)
            log.info("Opgestart in %.1fs, geheugen JARVIS-proces: %.0f MB",
                     time.perf_counter() - t_start, footprint_mb())
            log.info("macOS vraagt nu mogelijk om microfoontoegang voor je Terminal: klik 'Sta toe'.")
            pipeline.run()
    except KeyboardInterrupt:
        pass
    finally:
        timers.cancel_all()
        memory.close()
    from .report import session_summary
    print("\n" + session_summary(cfg, session_start), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
