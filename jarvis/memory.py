"""SQLite-geheugen: gespreksgeschiedenis + feiten die Jules vraagt te onthouden."""

from __future__ import annotations

import re
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      REAL NOT NULL,
    role    TEXT NOT NULL,          -- user | assistant
    content TEXT NOT NULL,
    lang    TEXT,
    route   TEXT                    -- router | llm
);
CREATE TABLE IF NOT EXISTS facts (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      REAL NOT NULL,
    text    TEXT NOT NULL UNIQUE
);
"""

# Woorden die niets zeggen over het onderwerp van een zoekvraag.
_STOPWORDS = set(
    "de het een en of van over wat weet je jij mij me mijn ik is zijn heb hebt heeft welke wie waar "
    "die dat er op in te om voor met jules the a an and or of about what do you know my i is are "
    "have has which who where that there on in to for with".split()
)


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[\w']+", text.lower()) if len(w) >= 3 and w not in _STOPWORDS]


class Memory:
    def __init__(self, db_path: str | Path):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(SCHEMA)
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # --- gesprekken -------------------------------------------------------
    def add_message(self, role: str, content: str, lang: str | None = None, route: str | None = None) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO messages (ts, role, content, lang, route) VALUES (?, ?, ?, ?, ?)",
                (time.time(), role, content, lang, route),
            )
            self._db.commit()

    def recent_messages(self, turns: int, window_minutes: float) -> list[dict]:
        """Laatste `turns` vraag/antwoord-paren binnen het tijdsvenster, oudste eerst."""
        since = time.time() - window_minutes * 60
        with self._lock:
            rows = self._db.execute(
                "SELECT role, content FROM messages WHERE ts >= ? ORDER BY id DESC LIMIT ?",
                (since, turns * 2),
            ).fetchall()
        msgs = [{"role": r, "content": c} for r, c in reversed(rows)]
        while msgs and msgs[0]["role"] != "user":  # nooit beginnen met een los antwoord
            msgs.pop(0)
        return msgs

    # --- feiten -----------------------------------------------------------
    def add_fact(self, text: str) -> bool:
        """Slaat een feit op. False als het er al letterlijk in stond."""
        text = " ".join(text.split()).strip()
        if not text:
            return False
        with self._lock:
            cur = self._db.execute("INSERT OR IGNORE INTO facts (ts, text) VALUES (?, ?)", (time.time(), text))
            self._db.commit()
            return cur.rowcount > 0

    def facts(self, limit: int = 50) -> list[str]:
        with self._lock:
            rows = self._db.execute("SELECT text FROM facts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [r[0] for r in reversed(rows)]

    def search_facts(self, query: str, limit: int = 10) -> list[str]:
        """Feiten die woorden uit de vraag bevatten, meest relevante eerst."""
        words = _words(query)
        if not words:
            return self.facts(limit)
        with self._lock:
            rows = self._db.execute("SELECT id, text FROM facts").fetchall()
        scored = []
        for fid, text in rows:
            low = text.lower()
            score = sum(1 for w in words if w in low or (len(w) > 4 and w[:-1] in low))
            if score:
                scored.append((score, fid, text))
        scored.sort(key=lambda s: (-s[0], -s[1]))
        return [t for _, _, t in scored[:limit]]
