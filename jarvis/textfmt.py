"""Taalhulpjes: uitspreekbare tijd/datum/duur (NL + EN), duur herkennen, tekst opschonen voor TTS,
zinnen splitsen tijdens het streamen en een eenvoudige taalgok voor getypte tekst."""

from __future__ import annotations

import re
from datetime import datetime

# --- tijd, datum, duur ------------------------------------------------------

_NL_DAYS = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
_NL_MONTHS = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
              "september", "oktober", "november", "december"]
_EN_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_EN_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
              "September", "October", "November", "December"]


def spoken_time(dt: datetime, lang: str) -> str:
    if lang == "nl":
        if dt.minute == 0:
            return f"Het is precies {dt.hour} uur."
        return f"Het is {dt.hour} uur {dt.minute}."
    hour12 = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    if dt.minute == 0:
        return f"It's {hour12} o'clock {ampm}."
    minute = f"oh {dt.minute}" if dt.minute < 10 else str(dt.minute)
    return f"It's {hour12} {minute} {ampm}."


def _ordinal(n: int) -> str:
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def spoken_date(dt: datetime, lang: str) -> str:
    if lang == "nl":
        return f"Het is {_NL_DAYS[dt.weekday()]} {dt.day} {_NL_MONTHS[dt.month - 1]} {dt.year}."
    return f"It's {_EN_DAYS[dt.weekday()]}, {_EN_MONTHS[dt.month - 1]} {_ordinal(dt.day)}, {dt.year}."


def spoken_duration(seconds: int, lang: str) -> str:
    h, rest = divmod(int(seconds), 3600)
    m, s = divmod(rest, 60)
    if lang == "nl":
        parts = [f"{h} uur"] if h else []
        parts += [f"{m} {'minuut' if m == 1 else 'minuten'}"] if m else []
        parts += [f"{s} {'seconde' if s == 1 else 'seconden'}"] if s else []
        joiner = " en "
    else:
        parts = [f"{h} {'hour' if h == 1 else 'hours'}"] if h else []
        parts += [f"{m} {'minute' if m == 1 else 'minutes'}"] if m else []
        parts += [f"{s} {'second' if s == 1 else 'seconds'}"] if s else []
        joiner = " and "
    if not parts:
        return "0 seconden" if lang == "nl" else "0 seconds"
    return ", ".join(parts[:-1]) + joiner + parts[-1] if len(parts) > 1 else parts[0]


_NUMS = {
    # nl
    "een": 1, "één": 1, "twee": 2, "drie": 3, "vier": 4, "vijf": 5, "zes": 6, "zeven": 7, "acht": 8,
    "negen": 9, "tien": 10, "elf": 11, "twaalf": 12, "dertien": 13, "veertien": 14, "vijftien": 15,
    "zestien": 16, "zeventien": 17, "achttien": 18, "negentien": 19, "twintig": 20, "dertig": 30,
    "veertig": 40, "vijftig": 50, "zestig": 60,
    # en
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
}
_NL_COMPOUND = re.compile(r"^(een|twee|drie|vier|vijf|zes|zeven|acht|negen)(?:en|ën)(twintig|dertig|veertig|vijftig)$")
_UNITS = {
    1: {"s", "sec", "secs", "second", "seconds", "seconde", "seconden"},
    60: {"m", "min", "mins", "minute", "minutes", "minuut", "minuten"},
    3600: {"u", "h", "hr", "hrs", "hour", "hours", "uur", "uren"},
}
_UNIT_OF = {word: mult for mult, words in _UNITS.items() for word in words}
_PHRASES = [
    (r"\banderhalf uur\b", "90 minuten"), (r"\banderhalve minuut\b", "90 seconden"),
    (r"\b(?:een )?half uur(?:tje)?\b", "30 minuten"), (r"\b(?:een )?halve minuut\b", "30 seconden"),
    (r"\b(?:een )?kwartier(?:tje)?\b", "15 minuten"),
    (r"\ban hour and a half\b", "90 minutes"), (r"\ba minute and a half\b", "90 seconds"),
    (r"\b(?:a )?half (?:an )?hour\b", "30 minutes"), (r"\b(?:a )?half (?:a )?minute\b", "30 seconds"),
    (r"\b(?:a )?quarter (?:of an )?hour\b", "15 minutes"),
]
_CONNECTORS = {"en", "and", "plus", ","}


def _number(tokens: list[str], i: int) -> tuple[float | None, int]:
    tok = tokens[i]
    if re.fullmatch(r"\d+(?:[.,]\d+)?", tok):
        return float(tok.replace(",", ".")), i + 1
    m = _NL_COMPOUND.match(tok)
    if m:
        return _NUMS[m.group(1)] + _NUMS[m.group(2)], i + 1
    if tok in _NUMS:
        value = _NUMS[tok]
        # "twenty five"
        if value >= 20 and i + 1 < len(tokens) and tokens[i + 1] in _NUMS and _NUMS[tokens[i + 1]] < 10 \
                and tokens[i + 1] not in ("a", "an", "een"):
            return value + _NUMS[tokens[i + 1]], i + 2
        return value, i + 1
    return None, i


def parse_duration(text: str) -> int | None:
    """'5 minuten', 'vijf minuten en 30 seconden', 'half an hour', '1,5 uur' -> seconden. None als het geen duur is."""
    s = text.lower().replace("-", " ")
    s = re.sub(r"(\d)([a-z])", r"\1 \2", s)
    for pattern, repl in _PHRASES:
        s = re.sub(pattern, repl, s)
    s = s.replace(",", " , ") if not re.search(r"\d,\d", s) else s
    tokens = s.split()
    total, i, found = 0.0, 0, False
    while i < len(tokens):
        if tokens[i] in _CONNECTORS:
            i += 1
            continue
        value, i = _number(tokens, i)
        if value is None or i >= len(tokens) or tokens[i] not in _UNIT_OF:
            return None
        total += value * _UNIT_OF[tokens[i]]
        found = True
        i += 1
    seconds = int(round(total))
    return seconds if found and seconds > 0 else None


# --- tekst voor spraak --------------------------------------------------------

_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")


def clean_for_speech(text: str) -> str:
    """Verwijdert markdown, emoji's en eventuele <think>-blokken: wat overblijft is uitspreekbaar."""
    text = re.sub(r"<think>.*?</think>", " ", text, flags=re.S)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", text, flags=re.M)   # lijstjes
    text = re.sub(r"^\s*#+\s*", "", text, flags=re.M)                  # koppen
    text = re.sub(r"[*_`~#>|]", "", text)
    text = _EMOJI.sub("", text)
    return " ".join(text.split())


class SentenceSplitter:
    """Knipt gestreamde tekst in zinnen zodat de TTS al kan beginnen voor het antwoord compleet is."""

    _END = re.compile(r"[.!?…]+[\"')\]]*\s+|\n+")

    def __init__(self):
        self._buf = ""

    def feed(self, delta: str) -> list[str]:
        self._buf += delta
        out = []
        while True:
            m = self._END.search(self._buf)
            if not m:
                break
            sentence = self._buf[: m.end()].strip()
            self._buf = self._buf[m.end():]
            if sentence:
                out.append(sentence)
        return out

    def flush(self) -> str:
        rest, self._buf = self._buf.strip(), ""
        return rest


# --- taal van getypte tekst -------------------------------------------------

_NL_HINTS = set(
    "de het een en ik je jij u mijn wat hoe laat welke wie waar waarom niet dat van voor op met zijn "
    "heb hebt heeft wil kan kun moet ben bent onthoud zet weet er nu ook maar dan als wanneer "
    "hoeveel uur vandaag morgen gisteren alsjeblieft dank bedankt goed goeiemorgen dag mij me "
    "datum timer minuten seconden".split()
)
_EN_HINTS = set(
    "the a an and i you my what how which who where why not that of for on with are have has "
    "want can could should am remember set know there now also but then if it's what's when "
    "today tomorrow yesterday please thanks thank good morning me date minutes seconds time".split()
)


def detect_language(text: str, default: str = "nl") -> str:
    words = re.findall(r"[\w']+", text.lower())
    nl = sum(w in _NL_HINTS for w in words)
    en = sum(w in _EN_HINTS for w in words)
    if nl == en:
        return default
    return "nl" if nl > en else "en"
