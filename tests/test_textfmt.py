from datetime import datetime

from jarvis.textfmt import (SentenceSplitter, clean_for_speech, detect_language, parse_duration, spoken_date,
                            spoken_duration, spoken_time)


def test_spoken_time():
    assert spoken_time(datetime(2026, 10, 12, 14, 5), "nl") == "Het is 14 uur 5."
    assert spoken_time(datetime(2026, 10, 12, 9, 0), "nl") == "Het is precies 9 uur."
    assert spoken_time(datetime(2026, 10, 12, 14, 5), "en") == "It's 2 oh 5 PM."
    assert spoken_time(datetime(2026, 10, 12, 0, 30), "en") == "It's 12 30 AM."


def test_spoken_date():
    assert spoken_date(datetime(2026, 10, 12), "nl") == "Het is maandag 12 oktober 2026."
    assert spoken_date(datetime(2026, 10, 12), "en") == "It's Monday, October 12th, 2026."
    assert spoken_date(datetime(2026, 10, 1), "en").endswith("October 1st, 2026.")


def test_durations():
    assert spoken_duration(330, "nl") == "5 minuten en 30 seconden"
    assert spoken_duration(3660, "en") == "1 hour and 1 minute"
    assert parse_duration("anderhalf uur") == 5400
    assert parse_duration("1,5 minuut") == 90
    assert parse_duration("5min") == 300
    assert parse_duration("de keuken") is None


def test_clean_for_speech():
    assert clean_for_speech("**Zeker!** Hier is het:\n- punt één\n- punt twee 😀") == "Zeker! Hier is het: punt één punt twee"
    assert clean_for_speech("<think>hmm</think>Oké.") == "Oké."


def test_sentence_splitter_streams():
    s = SentenceSplitter()
    out = []
    for piece in ["Het is ", "14.05 uur. Daarna", " komt de bus! En", " verder niets"]:
        out += s.feed(piece)
    assert out == ["Het is 14.05 uur.", "Daarna komt de bus!"]
    assert s.flush() == "En verder niets"


def test_detect_language():
    assert detect_language("Wat weet je over mijn auto?") == "nl"
    assert detect_language("What do you know about my car?") == "en"
    assert detect_language("Suzuki", default="nl") == "nl"
