"""Geheugengebruik meten. Op macOS gebruiken we 'phys_footprint': hetzelfde getal als Activiteitenweergave."""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys
from pathlib import Path

import psutil


def footprint_mb(pid: int | None = None) -> float:
    pid = pid or os.getpid()
    if sys.platform == "darwin":
        try:
            libc = ctypes.CDLL(ctypes.util.find_library("c"))
            buf = (ctypes.c_uint8 * 512)()
            if libc.proc_pid_rusage(pid, 2, buf) == 0:      # RUSAGE_INFO_V2
                # rusage_info_v2: 16 bytes uuid + 7 x uint64, daarna ri_phys_footprint
                return int.from_bytes(bytes(buf[72:80]), "little") / 1e6
        except Exception:
            pass
    return psutil.Process(pid).memory_info().rss / 1e6


def processes_mb(match) -> dict[int, float]:
    """Geheugen per proces waarvoor match(name, cmdline) waar is."""
    out = {}
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if match(p.info["name"] or "", p.info["cmdline"] or []):
                out[p.info["pid"]] = footprint_mb(p.info["pid"])
        except (psutil.Error, OSError):
            continue
    return out


def is_jarvis(name: str, cmdline: list[str]) -> bool:
    """python ... -m jarvis"""
    return bool(cmdline) and "python" in Path(cmdline[0]).name.lower() and any(
        a == "-m" and b == "jarvis" for a, b in zip(cmdline, cmdline[1:]))


def is_ollama(name: str, cmdline: list[str]) -> bool:
    return "ollama" in name.lower()
